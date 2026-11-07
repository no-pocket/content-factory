import copy
import json

import pytest


def test_policy_requires_explicit_approval_and_conflict_guard(tmp_path, monkeypatch):
    from app import editorial_policy as policy
    monkeypatch.setattr(policy, 'ROOT', tmp_path)
    draft = policy.initial_brief()
    policy.save_policy_draft(draft)
    assert policy.resolve_policy(None)['status'] == 'NONE'
    with pytest.raises(ValueError):
        policy.resolve_policy(draft['id'])
    approved = policy.approve_policy(draft['id'], 0, 'synthetic-owner')
    assert approved['revision'] == 1
    snapshot = policy.resolve_policy(None)
    before = copy.deepcopy(snapshot)
    assert snapshot['brief']['status'] == 'APPROVED'
    with pytest.raises(policy.PolicyConflict):
        policy.approve_policy(draft['id'], 0, 'synthetic-owner')
    assert policy.resolve_policy(None) == before


def test_approved_brief_cannot_be_overwritten(tmp_path, monkeypatch):
    from app import editorial_policy as policy
    monkeypatch.setattr(policy, 'ROOT', tmp_path)
    draft = policy.initial_brief()
    policy.save_policy_draft(draft)
    policy.approve_policy(draft['id'], 0, 'synthetic-owner')
    with pytest.raises((ValueError, FileExistsError)):
        policy.save_policy_draft({**draft, 'priorities': ['changed silently']})
    assert 'changed silently' not in policy.resolve_policy(None)['brief']['priorities']


def test_job_policy_snapshot_survives_active_policy_change(tmp_path, monkeypatch):
    from app import editorial_policy as policy, store
    monkeypatch.setattr(policy, 'ROOT', tmp_path / 'editorial')
    monkeypatch.setattr(store, 'JOBS', tmp_path / 'work')
    store.JOBS.mkdir()
    first = policy.initial_brief()
    policy.save_policy_draft(first)
    policy.approve_policy(first['id'], 0, 'synthetic-owner')
    job = store.new_job(None, 'SYNTHETIC', 'test', 'grant')
    snapshot = copy.deepcopy(job['editorial_policy'])
    second = {**first, 'id': 'brief-v2', 'parent_id': first['id'], 'priorities': ['Another priority']}
    policy.save_policy_draft(second)
    policy.approve_policy(second['id'], 1, 'synthetic-owner')
    assert store.load(job['id'])['editorial_policy'] == snapshot
    assert store.new_job(None, 'SYNTHETIC', 'test', 'grant')['editorial_policy']['brief_id'] == 'brief-v2'
    policy.approve_policy(first['id'], 2, 'synthetic-owner')
    assert policy.resolve_policy(None)['brief_id'] == first['id']
    assert store.load(job['id'])['editorial_policy'] == snapshot
