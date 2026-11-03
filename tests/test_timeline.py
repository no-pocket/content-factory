import copy
import json
from pathlib import Path
import pytest
from app.timeline import build_timeline, normalized_words, validate_timeline, write_timeline

SEGMENTS = [{"start": 10, "end": 15, "text": "A Lucia aparece em Vice City e esse detalhe é importante",
             "words": [{"start": 10.2, "end": 10.4, "text": "A"},
                       {"start": 10.5, "end": 11.1, "text": "Lúcia"},
                       {"start": 11.3, "end": 11.7, "text": "aparece"},
                       {"start": 12, "end": 12.5, "text": "Vice"},
                       {"start": 12.6, "end": 13.0, "text": "City"}]}]
CLIP = {"start": 10, "end": 25, "text": SEGMENTS[0]["text"]}


def test_words_relative_and_safe_correction():
    words = normalized_words(SEGMENTS, 10, 25)
    assert words[1] == {"start": 0.5, "end": 1.1, "text": "Lucia"}


def test_timeline_valid_and_saved(tmp_path):
    tl = build_timeline(CLIP, SEGMENTS)
    assert tl["duration"] == 15
    assert len(tl["layers"]["captions"]) == 5
    dest = tmp_path / "t.json"
    write_timeline(dest, tl)
    assert json.loads(dest.read_text())["schema_version"] == "2.0"


def test_director_cannot_invent_broll_or_hook():
    tl = build_timeline(CLIP, SEGMENTS, edit={"hook": "Trailer oficial confirma lançamento amanhã", "broll": [{"asset_id": "unknown", "at": 2, "duration": 3, "source_start": 0}], "effects": [{"type": "shell", "at": 3}]})
    assert tl["layers"]["broll"] == []
    assert "amanhã" not in tl["layers"]["text"][0]["text"]
    assert tl["layers"]["effects"] == []


def test_broll_bounds_overlap_and_zoom_limits():
    assets = {"city": {"duration": 12}}
    hints = {"hook": "A Lucia aparece em Vice City", "broll": [
        {"asset_id": "city", "at": 3, "duration": 4, "source_start": 1},
        {"asset_id": "city", "at": 5, "duration": 4, "source_start": 2},
        {"asset_id": "city", "at": 10, "duration": 3, "source_start": 1},
    ], "effects": [{"type": "punch_zoom", "at": 4}, {"type": "punch_zoom", "at": 5}, {"type": "punch_zoom", "at": 10}]}
    tl = build_timeline(CLIP, SEGMENTS, edit=hints, assets=assets)
    assert len(tl["layers"]["broll"]) == 2
    assert len(tl["layers"]["effects"]) == 2
    invalid = copy.deepcopy(tl)
    invalid["layers"]["broll"][0]["asset_id"] = "../../file"
    with pytest.raises(ValueError):
        validate_timeline(invalid)


def test_refuse_overlong_clip():
    with pytest.raises(ValueError):
        build_timeline({"start": 0, "end": 80, "text": "foo"}, [])


def test_no_fabricated_word_times():
    assert build_timeline(CLIP, [{"start": 10, "end": 12, "text": "sem palavras"}])["layers"]["captions"] == []
