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


def test_proof_layout_keeps_caption_close_and_uses_full_vertical_backdrop():
    from app.framing import validate_framing
    result=validate_framing({'preset':'web','layout_version':'proof_compact_v2'},(1280,720),(720,1280))
    roi,captions=result['projected_roi'],result['caption_safe_area']
    assert 0 < captions['y']-(roi['y']+roi['height']) <= .04
    assert result['background']=='source_blur'


def test_timed_proof_windows_keep_vertical_outside_source_interval():
    from app.framing import build_framing_schedule
    result=build_framing_schedule({'start':10,'end':30},
        {'framing_preset':'web','framing_roi':None,'framing_windows':[{'start':15,'end':20}]})
    assert len(result)==1 and result[0]['start']==5 and result[0]['end']==10
    assert result[0]['framing']['layout_version']=='proof_compact_v2'


def test_source_windows_map_to_assembly_clock():
    from app.framing import build_framing_schedule
    from app.assembly import validate_assembly
    plan=validate_assembly({'schema_version':'3.0','source_duration':60,'segments':[
        {'segment_id':'a','source_in':0,'source_out':10,'purpose':'setup'},
        {'segment_id':'b','source_in':30,'source_out':40,'purpose':'proof'}]},60)
    result=build_framing_schedule({'assembly':plan},{'framing_preset':'tweet','framing_roi':None,
                                                     'framing_windows':[{'start':32,'end':36}]})
    assert result[0]['start']==12 and result[0]['end']==16


@pytest.mark.parametrize('windows', ['4-3', '1-4; 3-5', [{'start':0,'end':float('inf')}], [{'start':0,'end':11}]])
def test_source_windows_reject_invalid_bounds(windows):
    from app.framing import normalize_source_windows
    with pytest.raises(ValueError):
        normalize_source_windows(windows,10)


def test_new_protected_job_requires_explicit_source_intervals():
    from app.service import create_job
    with pytest.raises(ValueError,match='interval'):
        create_job({'source_url':'https://youtu.be/dQw4w9WgXcQ','creator':'owner','license_note':'grant',
                    'rights_confirmed':True,'platform_permission':True,'settings':{'framing_preset':'web'}})
