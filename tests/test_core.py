from pathlib import Path
from app.core import propose_clips, write_srt, srt_time


def test_timestamp():
    assert srt_time(61.123) == "00:01:01,123"
    assert srt_time(-10) == "00:00:00,000"


def test_selection_no_large_overlap():
    s = [{"start": i * 5.0, "end": i * 5.0 + 4.5, "text": "GTA VI Rockstar crazy new secret moment " * 3} for i in range(30)]
    clips = propose_clips(s, 150.0, count=3)
    assert len(clips) == 3
    for c in clips:
        assert 15 <= c["end"] - c["start"] <= 60
    for i, a in enumerate(clips):
        for b in clips[i+1:]:
            overlap = max(0, min(a["end"], b["end"]) - max(a["start"], b["start"]))
            assert overlap < 0.2 * min(a["end"] - a["start"], b["end"] - b["start"])


def test_srt_relative_time(tmp_path):
    p = tmp_path / "caption.srt"
    write_srt([{"start": 10, "end": 13, "text": "Hello\nworld"}], 11, 14, p)
    output = p.read_text()
    assert "00:00:00,000 --> 00:00:02,000" in output
    assert "Hello world" in output


def test_empty():
    assert propose_clips([], 100) == []
