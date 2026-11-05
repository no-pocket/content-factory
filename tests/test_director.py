from app.director import direct_edit


def test_gpu_backend_routes_director_to_kepler(monkeypatch):
    import json
    seen = []
    class Reply:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self): return json.dumps({'response': '{"hook":"GTA","effects":[],"broll":[]}'}).encode()
    def open_request(request, timeout):
        seen.append(request.full_url)
        return Reply()
    monkeypatch.setattr('app.director.urllib.request.urlopen', open_request)
    hints, engine = direct_edit({'start': 0, 'end': 30, 'text': 'GTA'}, {}, mode='ollama', llm_backend='kepler_gpu')
    assert (hints['hook'], engine) == ('GTA', 'kepler_gpu')
    assert seen == ['http://kepler-bridge:11434/api/generate']


def test_director_disabled(monkeypatch):
    monkeypatch.setenv("EDIT_DIRECTOR", "heuristic")
    assert direct_edit({"start": 0, "end": 30, "text": "GTA"}, {}) == ({}, "heuristic")


def test_director_rejects_output_stopped_by_limit(monkeypatch):
    import json
    class Reply:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self):
            return json.dumps({'response': '{"hook":"GTA","effects":[],"broll":[]}',
                               'done_reason': 'length'}).encode()
    monkeypatch.setattr('app.director.urllib.request.urlopen', lambda *a, **k: Reply())
    assert direct_edit({'start': 0, 'end': 30, 'text': 'GTA'}, {}, mode='ollama') == ({}, 'heuristic_fallback')


def test_job_director_mode_overrides_worker_default(monkeypatch):
    monkeypatch.setenv('EDIT_DIRECTOR', 'ollama')
    assert direct_edit({'start': 0, 'end': 30, 'text': 'GTA'}, {}, mode='heuristic') == ({}, 'heuristic')


def test_invalid_host_falls_back(monkeypatch):
    monkeypatch.setenv("EDIT_DIRECTOR", "ollama")
    monkeypatch.setenv("OLLAMA_URL", "http://example.org:11434")
    assert direct_edit({"start": 0, "end": 30, "text": "GTA"}, {})[1] == "heuristic_fallback"
