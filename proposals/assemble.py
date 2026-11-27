"""
Proposal assembler for the PnL app.

Merges three inputs into the JSON spec that skill/scripts/build_proposal.js expects:
  1. intake       (form fields from the app: brand, client, engagement, people ...)
  2. content      (model output, validated against content_schema.json)
  3. commercials  (built from the saved PnL version by pnl/engine.py, never by the model)

Boilerplate (confidentiality, value proposition, Cloud4C intro, guiding principles,
layer descriptions) comes from boilerplate.json word for word. The model never writes it.

CLI (used to build the samples):
    python -m proposals.assemble proposals/samples/automatonsx
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL_DIR = HERE / "skill"
ASSETS_DIR = SKILL_DIR / "assets"
BOILERPLATE = json.loads((HERE / "boilerplate.json").read_text(encoding="utf-8"))

BRAND_NAME = {"automatonsx": "AutomatonsX", "cloud4c": "Cloud4C"}


# --------------------------------------------------------------------------
# House style: no em or en dashes, no comma before or after "and".
# Applied to every string that goes into the document (model text included).
# --------------------------------------------------------------------------
_DASHES = "\u2014\u2013"

def house_style(text: str, strip_and_commas: bool = True) -> str:
    if not isinstance(text, str):
        return text
    t = text
    # "**Lead** – text" -> "**Lead**: text"
    t = re.sub(r"(\*\*[^*]+\*\*)\s*[" + _DASHES + r"]\s*", r"\1: ", t)
    # numeric ranges "F2–F2048", "1–2" -> "F2 to F2048"
    t = re.sub(r"(\w)\s*[" + _DASHES + r"]\s*(\w*\d)", r"\1 to \2", t)
    # parenthetical " — x — " / " – x "
    t = re.sub(r"\s+[" + _DASHES + r"]\s+", ", ", t)
    # anything left (e.g. "Principal Architect–Data") -> hyphen
    t = re.sub(r"[" + _DASHES + r"]", "-", t)
    if strip_and_commas:
        t = re.sub(r",\s+and\b", " and", t)
        t = re.sub(r"\band,\s+", "and ", t)
    return t


def _hs(obj):
    """Recursively apply house_style to all strings in a JSON-like object."""
    if isinstance(obj, str):
        return house_style(obj)
    if isinstance(obj, list):
        return [_hs(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _hs(v) for k, v in obj.items()}
    return obj


def _sub_client(text: str, intake: dict) -> str:
    return (text.replace("<ClientShort>", intake.get("client_short") or intake["client"])
                .replace("<Client>", intake["client"]))


def money(v, currency: str) -> str:
    if v is None:
        return "To follow"
    s = f"{abs(v):,.0f}"
    return f"({s})" if v < 0 else s


# --------------------------------------------------------------------------
# Block helpers
# --------------------------------------------------------------------------
def H(level, text): return {"type": "heading", "level": level, "text": text}
def P(text): return {"type": "para", "text": text}
def L(items, numbered=False): return {"type": "list", "items": items, **({"numbered": True} if numbered else {})}
def T(header, rows, widths=None):
    b = {"type": "table", "header": header, "rows": rows}
    if widths: b["widths"] = widths
    return b
def IMG(path, width=6.2, caption=None):
    b = {"type": "image", "path": str(path), "width": width}
    if caption: b["caption"] = caption
    return b
BR = {"type": "pagebreak"}


class Numberer:
    def __init__(self): self.n = 0; self.sub = 0
    def h1(self, title): self.n += 1; self.sub = 0; return H(1, f"{self.n}. {title}")
    def h2(self, title): self.sub += 1; return H(2, f"{self.n}.{self.sub} {title}")


# --------------------------------------------------------------------------
# Front matter per brand
# --------------------------------------------------------------------------
def _person_rows(p: dict) -> list:
    p = p or {}
    return [["Contact name", p.get("name", "")], ["Designation", p.get("designation", "")],
            ["Email", p.get("email", "")], ["Mobile number", p.get("mobile", "")]]


def _version_table(intake: dict) -> dict:
    pb = intake.get("people", {}).get("prepared_by", {})
    rv = intake.get("people", {}).get("reviewed_by", {})
    return T(["Version", "Date", "Prepared By", "Designation", "Reviewed By", "Designation", "Comments"],
             [[intake["version"], intake["date"], pb.get("name", ""), pb.get("designation", ""),
               rv.get("name", ""), rv.get("designation", ""), intake.get("version_comment", "First version")]])


def front_matter_ax(intake: dict, num: Numberer) -> list:
    bp = BOILERPLATE["automatonsx"]
    corp = intake.get("corporate", {})
    people = intake.get("people", {})
    blocks = [
        H(1, "Document Control"),
        H(2, "Corporate Information"),
        T(["Field", "Details"], [["Company name", corp.get("company_name", "AutomatonsX")],
                                  ["Type of Entity / Office", corp.get("entity_office", "")],
                                  ["Company website address", corp.get("website", "")]], [3000, 6360]),
        H(2, "Account Manager Details"),
        T(["Field", "Details"], _person_rows(people.get("account_manager")), [3000, 6360]),
        H(2, "Prepared By"),
        T(["Field", "Details"], _person_rows(people.get("prepared_by")), [3000, 6360]),
        H(2, "Document Version"),
        _version_table(intake),
        BR,
        num.h1("Confidentiality and Disclaimer Statement"),
        *[P(p) for p in bp["confidentiality"]],
        BR,
        num.h1("Value Proposition"),
        P(_sub_client(bp["value_lead"], intake)),
        P(bp["value_body"]),
        L([_sub_client(b, intake) for b in bp["value_bullets"]]),
        P(bp["value_close"]),
        BR,
    ]
    return blocks


def front_matter_c4c(intake: dict, num: Numberer) -> list:
    bp = BOILERPLATE["cloud4c"]
    corp = intake.get("corporate", {})
    people = intake.get("people", {})
    return [
        H(1, "Document Control"),
        H(2, "Document Version"),
        _version_table(intake),
        H(2, "Corporate Information"),
        T(["Field", "Details"], [["Company name", corp.get("company_name", "Cloud4C Services")],
                                  ["Office address", corp.get("entity_office", "")],
                                  ["Website", corp.get("website", "www.cloud4c.com")]], [3000, 6360]),
        H(2, "Account Manager Details"),
        T(["Field", "Details"], _person_rows(people.get("account_manager")), [3000, 6360]),
        H(2, "Customer Approval and Signature"),
        T(["Customer Name", "Position", "Signature"], [["", "", ""]]),
        BR,
        num.h1("Confidentiality"),
        *[P(p) for p in bp["confidentiality"]],
        num.h1("Copyright"),
        *[P(p) for p in bp["copyright"]],
        BR,
        num.h1("Introduction to Cloud4C"),
        H(2, "About Us"),
        *[P(p) for p in bp["about_us"]],
        H(2, "Cloud4C Value Levers"),
        L(bp["value_levers"]),
        H(2, "Analyst Recognition"),
        *[P(p) for p in bp["analyst_recognition"]],
        H(2, "Why Choose Cloud4C"),
        L(bp["why_choose"]),
        H(2, "Certifications and Compliances"),
        *[P(p) for p in bp["certifications"]],
        H(2, "Data Analytics Services Offering"),
        L(bp["offering_pillars"]),
        BR,
    ]


# --------------------------------------------------------------------------
# Client-specific sections (model content)
# --------------------------------------------------------------------------
def scope_section(c: dict, num: Numberer) -> list:
    b = [num.h1("Scope of Work"),
         num.h2("Executive Summary"), *[P(p) for p in c["executive_summary"]],
         num.h2("Objective"), L([f"**{o['lead']}**: {o['text']}" for o in c["objectives"]]),
         num.h2("Scope"), P(c["scope_intro"])]
    for s in c["scope_sections"]:
        b.append(H(3, s["title"]))
        if s.get("intro"):
            b.append(P(s["intro"]))
        b.append(L(s["items"]))
    if c.get("migration_mapping"):
        b += [H(3, "Service Mapping Matrix"),
              T(["Existing Service", "Target Service", "Approach", "Notes"],
                [[r["existing"], r["target"], r["approach"], r.get("notes", "")] for r in c["migration_mapping"]["rows"]],
                [2600, 2600, 1700, 2460])]
    if c.get("inventory"):
        b += [H(3, "Migration Inventory"),
              T(["Object Type", "Count", "Notes"],
                [[r["object_type"], r["count"], r.get("notes", "")] for r in c["inventory"]["rows"]],
                [3400, 1400, 4560])]
    b += [H(3, "Out of Scope"), L(c["out_of_scope"]),
          H(3, "Assumptions"), L(c["assumptions"]), BR]
    return b


def solution_section(intake: dict, c: dict, num: Numberer, diagram_png: Path | None) -> list:
    neutral = BOILERPLATE["neutral"]
    brand = BRAND_NAME[intake["brand"]]
    approach = neutral["solution_approach_c4c"].replace("Cloud4C", brand)
    principles = []
    for g in neutral["guiding_principles"]:
        m = re.match(r"\*\*(.+?)\*\*\s*[\u2014\u2013-]\s*(.+)", g)
        principles.append([m.group(1), m.group(2)] if m else [g, ""])
    b = [num.h1("Solution Overview"),
         P(_sub_client(approach, intake)),
         T(["Principle", "Description"], principles, [2400, 6960]),
         num.h2("Reference Architecture"),
         IMG(ASSETS_DIR / "reference_architecture.png", 6.2, "Reference Architecture"),
         *[P(p) for p in neutral["layer_descriptions"]],
         num.h2("Logical Architecture"),
         IMG(ASSETS_DIR / "logical_architecture.png", 6.2, "Logical Architecture"),
         *[P(p) for p in c["logical_architecture"]],
         BR,  # keeps the 7.3 heading on the same page as its diagram
         num.h2("Component Architecture and Data Flow")]
    if diagram_png and diagram_png.exists():
        b.append(IMG(diagram_png, 6.4, c["component_diagram"].get("title", "To-Be Component Architecture")))
    b += [L(c["data_flow"], numbered=True),
          T(["Architecture Layer", "Description", "Components"],
            [[l["layer"], l["description"], l["components"]] for l in c["architecture_layers"]],
            [2200, 4360, 2800]),
          BR]
    return b


def timeline_section(intake: dict, c: dict, num: Numberer) -> list:
    brand = BRAND_NAME[intake["brand"]]
    rows = [[str(i + 1), s["activity"], s["client_raci"], s["vendor_raci"], s["timeline"]]
            for i, s in enumerate(c["timeline"]["stages"])]
    return [num.h1("Timelines"), P(c["timeline"]["intro"]),
            T(["Stage", "Activity", intake.get("client_short") or "Client", brand, "High-Level Timeline"],
              rows, [900, 4060, 1300, 1300, 1800]),
            L(["**R** = Responsible (does the work)", "**A** = Accountable (owns the outcome and decision)",
               "**C** = Consulted (provides input)", "**I** = Informed (kept in the loop)"]),
            BR]


def commercials_section(intake: dict, com: dict, num: Numberer) -> list:
    cur = com.get("currency", "USD")
    b = [num.h1("Commercials")]
    if not intake.get("include_commercials", True):
        return b + [P("Commercials will be shared as a separate annexure."), BR]

    rows, i = [], 0
    total = 0.0
    for it in com["otc_items"]:
        i += 1; total += it["amount"]
        rows.append([str(i), it["component"], it.get("cost_type", "OTC"), money(it["amount"], cur)])
    for f in com.get("funding", []):
        i += 1; total -= f["amount"]
        rows.append([str(i), f["label"], "Funding", money(-f["amount"], cur)])
    rows.append(["", "**Net One Time Cost**", "", f"**{money(total, cur)}**"])
    b += [num.h2("One Time Cost"), T(["Sr. No.", "Component", "Cost Type", f"Cost ({cur})"], rows, [1100, 4900, 1600, 1760])]

    ms = com.get("managed_services")
    if ms:
        b += [num.h2("Optional Managed Services"),
              T(["Service", f"Monthly ({cur})", "Months", f"Total ({cur})"],
                [[ms.get("label", "Managed Data Services"), money(ms["monthly"], cur), str(ms["months"]),
                  money(ms["monthly"] * ms["months"], cur)]], [4160, 1800, 1400, 2000])]
    if com.get("consumption_note"):
        b += [num.h2("Cloud Consumption"), P(com["consumption_note"])]
    if com.get("payment_plan"):
        b += [num.h2("Payment Plan"),
              T(["Milestone", "Percentage"], [[m["milestone"], f"{m['percent']}%"] for m in com["payment_plan"]], [6360, 3000])]
    if com.get("payment_terms"):
        b += [H(3, "Payment Terms"), L(com["payment_terms"])]
    b += [P(com.get("tax_note", "All figures are exclusive of applicable local taxes.")), BR]
    return b


def optional_sections(c: dict, num: Numberer) -> list:
    b = []
    if c.get("governance_cadence"):
        b += [num.h1("Project Governance Structure"),
              T(["Meeting", "Frequency", "Stakeholders", "Agenda"],
                [[g["meeting"], g["frequency"], g["stakeholders"], g["agenda"]] for g in c["governance_cadence"]],
                [2000, 1600, 2600, 3160])]
    if c.get("risks"):
        b += [num.h1("Risk and Mitigation"),
              T(["Risk", "Impact", "Mitigation"], [[r["risk"], r["impact"], r["mitigation"]] for r in c["risks"]],
                [3000, 1400, 4960])]
    if b:
        b.append(BR)
    return b


def conclusion_section(intake: dict, c: dict, num: Numberer) -> list:
    b = [num.h1("Conclusion"), *[P(p) for p in c["conclusion"]]]
    year = intake["date"][-4:]
    if intake["brand"] == "cloud4c":
        b.append(P(f"**\u00a9 {year} Cloud4C. All Rights Reserved.**"))
    else:
        b.append(P(f"**\u00a9 {year} AutomatonsX. All Rights Reserved.**"))
    return b


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------
def build_spec(intake: dict, content: dict, commercials: dict, diagram_png: Path | None = None) -> dict:
    brand = intake["brand"]
    if brand not in BRAND_NAME:
        raise ValueError(f"unknown brand {brand}")
    num = Numberer()
    body = front_matter_ax(intake, num) if brand == "automatonsx" else front_matter_c4c(intake, num)
    body += scope_section(content, num)
    body += solution_section(intake, content, num, diagram_png)
    body += timeline_section(intake, content, num)
    body += commercials_section(intake, commercials, num)
    body += optional_sections(content, num)
    body += conclusion_section(intake, content, num)

    spec = {
        "brand": brand,
        "client": intake["client"],
        "clientShort": intake.get("client_short") or intake["client"],
        "docType": intake.get("doc_type", "Techno-Commercial Proposal"),
        "subtitle": content["subtitle"],
        "version": intake["version"],
        "date": intake["date"],
        "footerSection": intake.get("doc_type", "Techno-Commercial Proposal"),
        "assetsDir": str(ASSETS_DIR),
        "toc": True,
        "body": body,
    }
    if intake.get("client_logo_path"):
        spec["clientLogo"] = intake["client_logo_path"]
    # house style on every string except file paths
    paths = {"assetsDir", "clientLogo"}
    out = {k: (v if k in paths else _hs(v)) for k, v in spec.items()}
    for blk in out["body"]:
        if blk["type"] == "image":
            blk["path"] = str(blk["path"])
    return out


FONTS_DIR = HERE / "fonts"   # Liberation Sans: open licence, same widths as Arial


def _diagram_module():
    """The skill's own diagram layout (build_svg), loaded from skill/scripts unchanged."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("gen_component_diagram", SKILL_DIR / "scripts" / "gen_component_diagram.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def render_diagram(diagram: dict, out_png: Path) -> Path:
    """Draw the component diagram with the skill's layout and render it with resvg.
    resvg ships as a self-contained wheel and uses the bundled font, so the server needs
    no cairo or system fonts (the skill script's own PNG step needs both)."""
    import resvg_py
    out_png.parent.mkdir(parents=True, exist_ok=True)
    svg = _diagram_module().build_svg(_hs(diagram)).replace('font-family="Arial"', 'font-family="Liberation Sans"')
    out_png.with_suffix(".svg").write_text(svg, encoding="utf-8")
    png = resvg_py.svg_to_bytes(svg_string=svg, zoom=2, background="white", skip_system_fonts=True,
                                font_dirs=[str(FONTS_DIR)], font_family="Liberation Sans",
                                sans_serif_family="Liberation Sans")
    out_png.write_bytes(bytes(png))
    return out_png


def render_docx(spec: dict, out_docx: Path) -> Path:
    out_docx.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False)
        spec_path = f.name
    try:
        r = subprocess.run(["node", str(SKILL_DIR / "scripts" / "build_proposal.js"), spec_path, str(out_docx)],
                           capture_output=True, text=True, timeout=180)
        if r.returncode != 0:
            raise RuntimeError(f"build_proposal.js failed: {r.stderr[-2000:]}")
    finally:
        os.unlink(spec_path)
    return out_docx


def build_from_folder(folder: Path) -> Path:
    """Build a proposal from a folder holding intake.json, content.json, commercials.json."""
    intake = json.loads((folder / "intake.json").read_text(encoding="utf-8"))
    content = json.loads((folder / "content.json").read_text(encoding="utf-8"))
    commercials = json.loads((folder / "commercials.json").read_text(encoding="utf-8"))
    png = render_diagram(content["component_diagram"], folder / "component_arch.png")
    spec = build_spec(intake, content, commercials, png)
    (folder / "spec.json").write_text(json.dumps(spec, indent=2, ensure_ascii=False), encoding="utf-8")
    name = f"{intake['client'].replace(' ', '_')}_Proposal_{intake['version']}.docx"
    return render_docx(spec, folder / name)


if __name__ == "__main__":
    print(build_from_folder(Path(sys.argv[1]).resolve()))
