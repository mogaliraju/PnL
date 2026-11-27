"""
Calls Claude Opus on Amazon Bedrock to write the client-specific proposal content.

The model must answer through the `submit_proposal_content` tool, whose input schema is
content_schema.json. The result is validated with jsonschema and retried once with the
validation errors if it fails.

Env vars (Render > Environment, never in code):
    AWS_BEARER_TOKEN_BEDROCK     existing Bedrock API key
    AWS_REGION                   ap-south-1
    BEDROCK_PROPOSAL_MODEL_ID    default global.anthropic.claude-opus-4-6-v1
    BEDROCK_PROPOSAL_FALLBACK_MODEL_ID   default global.anthropic.claude-sonnet-4-5-20250929-v1:0;
                                 used when the main model call fails ('none' turns it off)
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import boto3
import jsonschema
from botocore.config import Config

HERE = Path(__file__).resolve().parent
REFS = HERE / "skill" / "references"
SCHEMA = json.loads((HERE / "content_schema.json").read_text(encoding="utf-8"))
SYSTEM_TEMPLATE = (HERE / "prompts" / "system_prompt.md").read_text(encoding="utf-8")

MODEL_ID_DEFAULT = "global.anthropic.claude-opus-4-6-v1"
FALLBACK_MODEL_ID_DEFAULT = "global.anthropic.claude-sonnet-4-5-20250929-v1:0"
TOOL_NAME = "submit_proposal_content"
MAX_DOC_CHARS = 60_000   # cap for extracted BRD / SOW text
MAX_TOKENS = 16_000

_client = None


def set_client(client) -> None:
    """Tests and local demos pass a fake Bedrock client here."""
    global _client
    _client = client


def model_ids() -> list[str]:
    main = os.environ.get("BEDROCK_PROPOSAL_MODEL_ID") or MODEL_ID_DEFAULT
    fb = os.environ.get("BEDROCK_PROPOSAL_FALLBACK_MODEL_ID", FALLBACK_MODEL_ID_DEFAULT).strip()
    return [main] + ([fb] if fb and fb.lower() not in ("none", "off") and fb != main else [])


def bedrock():
    global _client
    if _client is None:
        _client = boto3.client(
            "bedrock-runtime",
            region_name=os.environ.get("AWS_REGION", "ap-south-1"),
            # Opus can take a few minutes for a full proposal. The default 60s read timeout is too short.
            config=Config(read_timeout=600, connect_timeout=10, retries={"max_attempts": 2, "mode": "standard"}),
        )
    return _client


def build_system_prompt(intake: dict) -> str:
    brand = {"automatonsx": "AutomatonsX", "cloud4c": "Cloud4C"}[intake["brand"]]
    parts = [SYSTEM_TEMPLATE.replace("{BRAND_NAME}", brand),
             "\n\n---\n\n# Reference: proposal structure\n\n", (REFS / "proposal_structure.md").read_text(encoding="utf-8")]
    if intake.get("engagement_type") == "migration":
        parts += ["\n\n---\n\n# Reference: migrations\n\n", (REFS / "migration.md").read_text(encoding="utf-8")]
    gov = intake.get("governance") or {}
    if intake.get("engagement_type") == "governance" or (gov.get("included") and gov.get("purview_allowed")):
        parts += ["\n\n---\n\n# Reference: Purview\n\n", (REFS / "purview.md").read_text(encoding="utf-8")]
    return "".join(parts)


def build_user_message(intake: dict, pnl_context: dict) -> str:
    intake = dict(intake)
    doc = intake.get("document_text") or ""
    if len(doc) > MAX_DOC_CHARS:
        intake["document_text"] = doc[:MAX_DOC_CHARS] + "\n[truncated]"
    # Only what the model needs. People, corporate info and file paths stay out.
    for k in ("people", "corporate", "client_logo_path"):
        intake.pop(k, None)
    return json.dumps({"intake": intake, "pnl_context": pnl_context}, ensure_ascii=False, indent=2)


def _tool_config():
    return {
        "tools": [{"toolSpec": {
            "name": TOOL_NAME,
            "description": "Submit the client-specific proposal content. Call exactly once.",
            "inputSchema": {"json": {k: v for k, v in SCHEMA.items() if k not in ("$schema", "title")}},
        }}],
        "toolChoice": {"tool": {"name": TOOL_NAME}},
    }


def _extract_tool_use(response: dict) -> dict | None:
    for block in response["output"]["message"]["content"]:
        if "toolUse" in block and block["toolUse"]["name"] == TOOL_NAME:
            return block["toolUse"]
    return None


def _validate(content: dict) -> list[str]:
    v = jsonschema.Draft202012Validator(SCHEMA)
    errors = [f"{'/'.join(map(str, e.path)) or '(root)'}: {e.message}" for e in v.iter_errors(content)]
    return errors[:20]


def generate_content(intake: dict, pnl_context: dict, model_id: str | None = None) -> tuple[dict, dict]:
    """Returns (content, usage). Raises RuntimeError if the content stays invalid after one retry."""
    models = [model_id] if model_id else model_ids()
    system = [{"text": build_system_prompt(intake)}]
    messages = [{"role": "user", "content": [{"text": build_user_message(intake, pnl_context)}]}]
    usage = {"inputTokens": 0, "outputTokens": 0, "model_id": None}

    for attempt in range(2):
        resp = None
        for i, m in enumerate(models):      # next model only when the call itself fails (access, throttling, outage)
            try:
                resp = bedrock().converse(
                    modelId=m,
                    system=system,
                    messages=messages,
                    toolConfig=_tool_config(),
                    inferenceConfig={"maxTokens": MAX_TOKENS},
                )
                models = models[i:]
                usage["model_id"] = m
                break
            except Exception:
                if i == len(models) - 1:
                    raise
        for k in ("inputTokens", "outputTokens"):
            usage[k] += resp.get("usage", {}).get(k, 0)

        tool_use = _extract_tool_use(resp)
        if tool_use is None:
            raise RuntimeError(f"model did not call {TOOL_NAME} (stopReason={resp.get('stopReason')})")
        content = tool_use["input"]
        errors = _validate(content)
        if not errors:
            return content, usage
        if attempt == 1:
            raise RuntimeError("content failed validation: " + "; ".join(errors))

        # One retry: hand the errors back as a failed tool result.
        messages += [
            resp["output"]["message"],
            {"role": "user", "content": [{"toolResult": {
                "toolUseId": tool_use["toolUseId"],
                "status": "error",
                "content": [{"text": "Validation failed. Fix these and call the tool again with the full content:\n"
                                     + "\n".join(errors)}],
            }}]},
        ]
    raise RuntimeError("unreachable")
