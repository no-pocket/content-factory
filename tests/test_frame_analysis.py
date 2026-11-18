import pytest

from app import frame_analysis


def test_sample_times_are_bounded_and_inside_the_clip():
    times = frame_analysis._sample_times(120)

    assert len(times) == frame_analysis.MAX_FRAMES
    assert all(0 < value < 120 for value in times)


def test_v3_frame_time_maps_through_the_selected_source_segment():
    timeline = {'schema_version': '3.0', 'segments': [
        {'source_in': 10, 'output_start': 0, 'duration': 2},
        {'source_in': 40, 'output_start': 2, 'duration': 2},
    ]}

    assert frame_analysis._source_at(timeline, 2.5) == 40.5


def test_vision_response_requires_unique_bounded_scene_and_roi():
    valid = {'frames': [{
        'frame_id': 0, 'scene': 'SCREEN_CONTENT', 'confidence': .91,
        'roi': {'x': .1, 'y': .2, 'width': .7, 'height': .6},
    }]}

    assert frame_analysis._validate_vision(valid, {0})[0]['scene'] == 'SCREEN_CONTENT'
    with pytest.raises(ValueError, match='outside the frame'):
        frame_analysis._validate_vision({'frames': [{
            **valid['frames'][0], 'roi': {'x': .8, 'y': 0, 'width': .4, 'height': .2},
        }]}, {0})


def test_ocr_boxes_are_normalized_to_actual_sampled_frame_dimensions(monkeypatch):
    tsv = (
        'level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n'
        '5\t1\t1\t1\t1\t1\t24\t135\t120\t18\t90.0\tVice\n'
    )

    def fake_run(*args, **kwargs):
        return type('Result', (), {'stdout': tsv.encode()})()

    monkeypatch.setattr(frame_analysis.subprocess, 'run', fake_run)
    result = frame_analysis._ocr(b'jpeg', 540)

    assert result['regions'][0]['box'] == {'x': .05, 'y': .25, 'width': .25, 'height': 18 / 540}

def test_samples_opening_ending_and_segment_transitions():
    from app.frame_analysis import _sample_times
    times=_sample_times(12, transitions=[4,8])
    assert 0 <= times[0] <= .001
    assert times[-1]<12 and times[-1]>11.9
    assert 4 in times and 8 in times
    assert times==sorted(set(times))
