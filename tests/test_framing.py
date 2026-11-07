import pytest


def test_web_roi_survives_vertical_output():
    from app.framing import validate_framing
    result = validate_framing({'preset': 'web', 'roi': {'x': 0, 'y': 0, 'width': 1, 'height': 1}}, (1280,720), (720,1280))
    assert result['mode'] == 'contain'
    assert result['roi_visible'] is True
    assert result['caption_safe_area']['y'] >= .7


@pytest.mark.parametrize('roi', [{'x': -.1, 'y': 0, 'width': .5, 'height': .5},
                                {'x': .8, 'y': .1, 'width': .5, 'height': .5},
                                {'x': 0, 'y': 0, 'width': 0, 'height': 1},
                                {'x': 0, 'y': float('nan'), 'width': 1, 'height': 1}])
def test_invalid_roi_is_rejected(roi):
    from app.framing import validate_framing
    with pytest.raises(ValueError):
        validate_framing({'preset': 'web', 'roi': roi}, (1280,720), (720,1280))


def test_captions_avoid_important_region():
    from app.framing import validate_framing
    result = validate_framing({'preset': 'tweet', 'roi': {'x': 0, 'y': 0, 'width': 1, 'height': 1}}, (1280,720), (720,1280))
    region, captions = result['projected_roi'], result['caption_safe_area']
    assert region['y']+region['height'] <= captions['y'] or captions['y']+captions['height'] <= region['y']


def test_legacy_framing_is_unchanged():
    from app.framing import validate_framing
    assert validate_framing({}, (1280,720), (720,1280)) == {}


def test_manual_framing_settings_are_snapshotted_and_validated():
    from app.job_settings import normalize_job_settings
    result = normalize_job_settings({'framing_preset': 'document', 'framing_roi': '{"x":0,"y":0,"width":1,"height":1}'})
    assert result['framing_roi']['width'] == 1
    with pytest.raises(ValueError):
        normalize_job_settings({'framing_preset': 'document', 'framing_roi': '{"x":-1}'})
