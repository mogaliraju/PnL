"""Simple schema validators — no external deps needed."""
from typing import Any

class ValidationError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def require(d: dict, *keys: str):
    for k in keys:
        if not d.get(k):
            raise ValidationError(f"'{k}' is required and cannot be empty")


def validate_project(p: Any):
    if not isinstance(p, dict):
        raise ValidationError("'project' must be an object")
    # customer is the only truly required field
    if not p.get('customer', '').strip():
        raise ValidationError("Customer name is required")


def validate_resource(r: Any, idx: int):
    if not isinstance(r, dict):
        raise ValidationError(f"Resource #{idx+1} is malformed")
    if not r.get('role', '').strip():
        raise ValidationError(f"Resource #{idx+1}: role is required")
    if not r.get('level', '').strip():
        raise ValidationError(f"Resource #{idx+1}: level is required")
    hours = r.get('hours', 0)
    if not isinstance(hours, (int, float)) or hours < 0:
        raise ValidationError(f"Resource #{idx+1}: hours must be a non-negative number")


def validate_rate_card(rc: Any):
    if not isinstance(rc, list) or len(rc) == 0:
        raise ValidationError("Rate card must have at least one level")
    for i, entry in enumerate(rc):
        if not entry.get('level', '').strip():
            raise ValidationError(f"Rate card row #{i+1}: level name is required")
        rate = entry.get('rate', -1)
        if not isinstance(rate, (int, float)) or rate < 0:
            raise ValidationError(f"Rate card row #{i+1}: rate must be >= 0")


def validate_payload(data: Any) -> None:
    """Full payload validation before save/export."""
    if not isinstance(data, dict):
        raise ValidationError("Request body must be a JSON object")

    validate_project(data.get('project', {}))

    for i, r in enumerate(data.get('resources', [])):
        validate_resource(r, i)

    if data.get('rate_card') is not None:
        validate_rate_card(data['rate_card'])
