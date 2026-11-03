from app.director import direct_edit


def test_director_disabled(monkeypatch):
    monkeypatch.setenv("EDIT_DIRECTOR", "heuristic")
    assert direct_edit({"start": 0, "end": 30, "text": "GTA"}, {}) == ({}, "heuristic")


def test_invalid_host_falls_back(monkeypatch):
    monkeypatch.setenv("EDIT_DIRECTOR", "ollama")
    monkeypatch.setenv("OLLAMA_URL", "http://example.org:11434")
    assert direct_edit({"start": 0, "end": 30, "text": "GTA"}, {})[1] == "heuristic_fallback"
