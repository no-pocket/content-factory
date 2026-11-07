from app.signals import boundary_experiment, parse_signals


def test_signal_parser_keeps_evidence_separate_and_handles_nonfinite_energy():
    result = parse_signals('pts_time:1.5\nlavfi.astats.Overall.RMS_level=-inf\nsilence_start: 2\nsilence_end: 4 | silence_duration: 2\npts_time:7.5\nlavfi.scene_score=0.45\n')
    assert result['energy'][0] == {'time': 1.5, 'rms_db': None}
    assert result['silence'] == [{'start': 2, 'end': 4}]
    assert result['scenes'] == [{'time': 7.5, 'score': 0.45}]


def test_experiment_preserves_input_and_bounds():
    clips = [{'start': 1, 'end': 20}]
    evidence = {'silence': [{'start': 0.5, 'end': 1.2}, {'start': 19.7, 'end': 20.3}],
                'scenes': [], 'energy': []}
    adjusted = boundary_experiment(clips, evidence, 30, min_seconds=8, max_seconds=60)
    assert clips == [{'start': 1, 'end': 20}]
    assert adjusted[0]['start'] == 1.2
    assert adjusted[0]['end'] == 19.7
    assert adjusted[0]['experimental'] is True
