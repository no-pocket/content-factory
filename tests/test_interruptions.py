"""Synthetic crash checkpoints with real persistence; no user media or decisions."""
from pathlib import Path

import pytest

from app import candidates, store
from app.queueing import recover_inflight


def test_interrupt_render_preserves_valid_sibling_and_decisions(monkeypatch, tmp_path):
    monkeypatch.setattr(store, 'JOBS', tmp_path)
    monkeypatch.setattr(candidates, 'OUTPUT', tmp_path / 'output')
    monkeypatch.setattr(candidates, 'save', store.save)
    monkeypatch.setattr(candidates, 'read_assets', lambda: {})
    monkeypatch.setattr(candidates, 'direct_edit', lambda *a, **k: ({}, 'heuristic'))
    monkeypatch.setattr(candidates, 'build_timeline', lambda *a, **k: {'layers': {'captions': []}})
    monkeypatch.setattr(candidates, 'inspect_candidate', lambda *a: {'state': 'VALID'})
    calls = []
    def render(*args, **kwargs):
        ordinal = args[2]
        calls.append(ordinal)
        Path(args[7]).write_bytes(b'valid-master' if ordinal == 1 else b'partial')
        if calls == [1, 2]:
            raise KeyboardInterrupt('Synthetic hard interruption')
        return 'synthetic'
    monkeypatch.setattr(candidates, 'render_edited', render)
    job = {'id': 'crash', 'candidates': [{'start': 0, 'end': 20}, {'start': 30, 'end': 50}],
           'status': 'RENDERING', 'decision_history': [{'at': 1, 'note': 'synthetic history sentinel'}]}
    with pytest.raises(KeyboardInterrupt):
        candidates.render_candidates(job, Path('source'), [], {}, True)
    persisted = store.load('crash')
    assert persisted['candidates'][0]['state'] == 'VALID'
    assert persisted['candidates'][1]['state'] == 'RENDERING'
    class Queue:
        def lrange(self, *a): return ['crash']
        def lpush(self, *a): pass
        def lrem(self, *a): pass
    recover_inflight(Queue(), store.load, store.save)
    resumed = store.load('crash')
    candidates.render_candidates(resumed, Path('source'), [], {}, True)
    assert resumed['status'] == 'NEEDS_REVIEW'
    assert calls == [1, 2, 2]
    assert (tmp_path / 'output/crash/candidate_1.mp4').read_bytes() == b'valid-master'
    assert resumed['candidates'][1]['attempts'] == 2
    assert resumed['candidates'][1]['attempt_history'][0]['error'] == 'Worker interrupted'
    assert resumed['decision_history'] == job['decision_history']
