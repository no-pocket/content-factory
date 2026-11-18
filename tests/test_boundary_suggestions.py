import pytest
from app.boundary_suggestions import suggest_word_boundary

def test_uses_nearby_gap_and_reports_provenance():
    words=[{'start':1.0,'end':1.4},{'start':1.6,'end':2.0}]
    result=suggest_word_boundary(1.45,words,source_duration=5,max_shift=.5)
    assert result['suggested_seconds']==pytest.approx(1.5)
    assert result['method']=='word_gap' and result['original_seconds']==1.45
    assert result['confidence']=='advisory'

def test_unusable_timing_keeps_original():
    result=suggest_word_boundary(1.4,[{'start':1,'end':1},{'start':1,'end':2}],source_duration=5,max_shift=.5)
    assert result['suggested_seconds']==1.4
    assert result['method'] is None and result['reason']=='unreliable_word_timing'

def test_will_not_jump_far_or_use_overlapping_timing():
    result=suggest_word_boundary(1,[{'start':0,'end':.4},{'start':.3,'end':.9}],source_duration=5,max_shift=.1)
    assert result['suggested_seconds']==1 and result['method'] is None

def test_audio_valley_is_advisory_and_silence_alone_is_not_confidence():
    from app.boundary_suggestions import suggest_audio_boundary
    samples=[.2]*20+[.001]*5+[.2]*25
    result=suggest_audio_boundary(1.25,samples,window_start=1.0,source_duration=3,sample_rate=100)
    assert result['method']=='audio_valley' and result['confidence']=='advisory'
    assert 1.2<=result['suggested_seconds']<=1.25
    silent=suggest_audio_boundary(1.2,[0.0]*50,window_start=1.0,source_duration=3,sample_rate=100)
    assert silent['method'] is None
