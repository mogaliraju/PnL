"""Offline tests for the proposal module. No Bedrock calls."""
import json
from pathlib import Path

import pytest

from proposals import assemble, generator

SAMPLES = Path(__file__).resolve().parents[1] / "proposals" / "samples"


@pytest.mark.parametrize("brand", ["automatonsx", "cloud4c"])
def test_sample_content_matches_schema(brand):
    content = json.loads((SAMPLES / brand / "content.json").read_text())
    assert generator._validate(content) == []


@pytest.mark.parametrize("brand", ["automatonsx", "cloud4c"])
def test_sample_builds_docx(brand, tmp_path):
    folder = tmp_path / brand
    folder.mkdir()
    for f in ("intake.json", "content.json", "commercials.json"):
        (folder / f).write_text((SAMPLES / brand / f).read_text())
    out = assemble.build_from_folder(folder)
    assert out.exists() and out.stat().st_size > 50_000


def test_house_style():
    hs = assemble.house_style
    assert hs("**Lead** \u2013 text") == "**Lead**: text"
    assert hs("Weeks 1\u20132") == "Weeks 1 to 2"
    assert hs("fast \u2014 and safe") == "fast, and safe".replace(", and", " and")
    assert hs("A, B, and C") == "A, B and C"


def test_commercials_never_come_from_model():
    schema = json.loads((Path(assemble.HERE) / "content_schema.json").read_text())
    text = json.dumps(schema).lower()
    for word in ("otc_items", "price", "amount"):
        assert word not in schema["properties"], word
