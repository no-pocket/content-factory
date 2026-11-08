import pytest
from app import store, source_registry as registry

CHANNEL = 'UC' + 'a' * 22

@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(store, 'ROOT', tmp_path)

def source(**changes):
    return {'channel_id':CHANNEL, 'name':'Canal', **changes}

def test_defaults_deny_and_canonical_identity():
    record = registry.upsert_source(source())
    assert record['status'] == 'pending'
    assert record['allowed_model_scopes'] == ['local']
    assert registry.get_source(CHANNEL) == record
    with pytest.raises(ValueError):
        registry.upsert_source(source(channel_id='UC' + 'a' * 25))

def test_active_requires_explicit_authority_and_revision():
    with pytest.raises(ValueError):
        registry.upsert_source(source(status='active'))
    first = registry.upsert_source(source())
    record = registry.upsert_source(source(status='active', authorization_reference='Owner consent 2026',
        rights_confirmed=True, platform_permission=True), expected_revision=first['revision'])
    assert record['revision'] == 2
    with pytest.raises(ValueError, match='revision'):
        registry.upsert_source(source(), expected_revision=1)
