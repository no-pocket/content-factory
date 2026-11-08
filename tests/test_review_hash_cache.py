from test_editorial_service_v2 import v2job


def test_presentation_reuses_hashes_but_explicit_verification_is_fresh(v2job,monkeypatch):
    from app import service,artifacts
    calls=[];original=artifacts.hashlib.file_digest
    monkeypatch.setattr(artifacts.time,'monotonic',lambda:100.0)
    def counted(*args,**kwargs):
        calls.append(1);return original(*args,**kwargs)
    monkeypatch.setattr(artifacts.hashlib,'file_digest',counted)
    service.get_editorial_view(v2job);first=len(calls)
    service.get_editorial_view(v2job)
    assert first==3 and len(calls)==first
    artifacts.artifact_manifest(v2job,0)
    assert len(calls)==first+3


def test_presentation_cache_invalidates_after_same_size_media_change(v2job):
    from app import service
    from pathlib import Path
    assert service.get_editorial_view(v2job)['candidates'][0]['artifact_intact']
    path=Path(v2job['candidates'][0]['file']);path.write_bytes(b'x'*path.stat().st_size)
    import os
    stat=path.stat();os.utime(path,ns=(stat.st_atime_ns,stat.st_mtime_ns+1_000_000_000))
    assert not service.get_editorial_view(v2job)['candidates'][0]['artifact_intact']


def test_cached_presentation_never_authorizes_changed_media(v2job):
    from pathlib import Path
    import pytest
    from app import service
    from test_editorial_service_v2 import review_request
    request=review_request(v2job)
    service.get_editorial_view(v2job)
    path=Path(v2job['candidates'][0]['file']);path.write_bytes(b'z'*path.stat().st_size)
    with pytest.raises(service.Conflict):
        service.review_candidate_v2(v2job['id'],v2job['candidates'][0]['candidate_id'],request)
