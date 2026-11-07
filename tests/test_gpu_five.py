"""Batch completion must prove processing happened, not merely a zero exit code."""
import pytest
from research.run_gpu_five import completed_entry
from research import run_gpu_five as batch


def test_batch_rejects_unprocessed_worker_result():
    with pytest.raises(RuntimeError, match='did not process'):
        completed_entry({'id':'synthetic','status':'TRANSCRIBING','candidates':[]},'parent',1)


def test_empty_failed_result_is_not_gpu_completion():
    result=completed_entry({'id':'synthetic','status':'FAILED','original_name':'synthetic',
                            'ranker_used':'kepler_gpu','candidates':[]},'parent',1)
    assert result['gpu_and_remotion_complete'] is False


def test_restoration_attempts_worker_after_engine_failure(monkeypatch):
    calls=[]
    def run(*args):
        calls.append(args)
        if args[:2]==('docker','start') and args[-1].endswith('engine-1'):
            raise RuntimeError('Synthetic engine startup failure')
        return 'true'
    monkeypatch.setattr(batch,'run',run)
    result=batch.restore_production(['content-factory-worker-1','content-factory-kepler-engine-1'])
    assert ('docker','start','content-factory-worker-1') in calls
    assert result['restoration_errors'] and result['production_gpu_healthy'] is False


def test_restoration_does_not_claim_gpu_health_after_timeout(monkeypatch):
    monkeypatch.setattr(batch,'run',lambda *args:'true')
    monkeypatch.setattr(batch,'wait_for_production_gpu',lambda:False)
    result=batch.restore_production(['content-factory-worker-1','content-factory-kepler-engine-1'])
    assert result['production_services_running'] is True
    assert result['production_gpu_healthy'] is False
    assert result['restoration_errors']
