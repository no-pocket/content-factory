import copy
import json
import pytest

from app.core import propose_clips
from app.job_settings import normalize_job_settings
from app.timeline import build_timeline, validate_timeline, candidate_duration


def story(end=90):
    return [
        {'start': 0, 'end': 10, 'text': 'GTA revela um segredo importante no novo mapa.'},
        {'start': 10, 'end': end-10, 'text': 'O teste compara as rotas e demonstra o caminho usado pelo jogador.'},
        {'start': end-10, 'end': end, 'text': 'Portanto esta rota revela a saída e conclui o teste.'},
    ]


def test_flexible_settings_opt_in_and_old_snapshot_unchanged():
    old = {'max_seconds': 50, 'target_seconds': 30, 'min_seconds': 15}
    before = copy.deepcopy(old)
    assert normalize_job_settings(old)['duration_mode'] == 'classic'
    assert old == before
    flexible = normalize_job_settings({'duration_mode': 'flexible'})
    assert (flexible['min_seconds'], flexible['max_seconds']) == (8, 180)
    with pytest.raises(ValueError):
        normalize_job_settings({'duration_mode': 'flexible', 'max_seconds': 181})
    with pytest.raises(ValueError):
        normalize_job_settings({'max_seconds': 90})


@pytest.mark.parametrize('end', [24, 90, 175])
def test_flexible_heuristic_selects_shortest_complete_story(end):
    segments = story(end) + [{'start':end, 'end':end+5, 'text':'Inscreva no meu canal.'}]
    clips = propose_clips(segments, end+5, count=3, target=40, min_seconds=8,
                          max_seconds=180, duration_mode='flexible')
    assert any(c['start'] == 0 and c['end'] == end for c in clips)
    assert all('Inscreva' not in c['text'] for c in clips)


def test_flexible_does_not_accept_only_promotion_or_unfinished_development():
    assert propose_clips([{'start':0,'end':20,'text':'Inscreva no meu canal. Portanto deixe o like.'}],
                         20, duration_mode='flexible', min_seconds=8, max_seconds=180) == []
    assert propose_clips(story(190), 190, duration_mode='flexible', min_seconds=8, max_seconds=180) == []


def test_flexible_timeline_bounds_and_actual_outro_duration():
    clip = {'start':0, 'end':175, 'text':'GTA teste completo.', 'duration_mode':'flexible'}
    timeline = build_timeline(clip, [])
    assert timeline['duration_mode'] == 'flexible'
    timeline['outro'] = {'duration':12}
    assert candidate_duration({**clip, 'timeline':timeline}) == pytest.approx(187.35)
    validate_timeline(timeline)
    with pytest.raises(ValueError):
        build_timeline({**clip, 'end':181}, [])
    with pytest.raises(ValueError):
        build_timeline({'start':0, 'end':90, 'text':'legado'}, [])
    invalid = {**timeline, 'duration':181}
    with pytest.raises(ValueError):
        validate_timeline(invalid)

def test_flexible_model_requires_anchored_development_and_conclusion(monkeypatch):
    import io
    from app.ranker import propose_from_transcript
    segments = story(90)
    evidence = [{'segment_id':i, 'quote':s['text']} for i,s in enumerate(segments)]
    item = {'start_segment':0, 'end_segment':2, 'reason':'Complete story',
            'story': {'closure':'COMPLETE', 'evidence':evidence,
                      'parts': {'hook':0, 'setup':1, 'payoff':2}}}
    prompts=[]
    def response(request, **kwargs):
        prompts.append(json.loads(request.data)['prompt'])
        return io.BytesIO(json.dumps({'response': json.dumps({'clips':[item]})}).encode())
    monkeypatch.setattr('app.ranker.urllib.request.urlopen', response)
    kwargs = {'duration_mode':'flexible', 'min_seconds':8, 'max_seconds':180}
    result = propose_from_transcript(segments, 90, **kwargs)
    assert [(c['start'], c['end']) for c in result] == [(0,90)]
    assert result[0]['model_story']['closure'] == 'COMPLETE'
    assert 'menor' in prompts[0] and 'alvo' in prompts[0]
    item['story']['parts']['setup'] = 2
    assert propose_from_transcript(segments, 90, **kwargs) == []
    item['story']['parts']['setup'] = 1
    item['story']['evidence'][-1]['quote'] = 'Invented payoff'
    assert propose_from_transcript(segments, 90, **kwargs) == []


def test_flexible_one_story_has_generation_capacity_and_classic_budget_stays(monkeypatch):
    import io
    from app.ranker import propose_from_transcript
    segments=story(90)
    evidence=[{'segment_id':i,'quote':s['text']} for i,s in enumerate(segments)]
    item={'start_segment':0,'end_segment':2,'story':{'closure':'COMPLETE','evidence':evidence,
          'parts':{'hook':0,'setup':1,'payoff':2}}}
    calls=[]; events=[]
    def response(request,**kwargs):
        request_body=json.loads(request.data); calls.append(request_body)
        if request_body['options']['num_predict'] < 700:
            return io.BytesIO(json.dumps({'response':'{"clips":[','done_reason':'length'}).encode())
        return io.BytesIO(json.dumps({'response':json.dumps({'clips':[item]}),'done_reason':'stop'}).encode())
    monkeypatch.setattr('app.ranker.urllib.request.urlopen',response)
    result=propose_from_transcript(segments,90,duration_mode='flexible',min_seconds=8,max_seconds=180,
        backend='kepler_gpu',on_event=lambda event,details:events.append((event,details)))
    assert len(result) == 1
    assert 'no máximo 1' in calls[0]['prompt']
    assert '8 palavras' in calls[0]['prompt']
    budget=next(details['context_budget'] for event,details in events if event=='analyzing')
    assert budget['generation_reserve'] == calls[0]['options']['num_predict'] == 700
    assert budget['prompt_upper_bound']+budget['generation_reserve'] <=4096
    calls.clear()
    propose_from_transcript(segments,90,duration_mode='classic',min_seconds=15,max_seconds=60)
    assert calls[0]['options']['num_predict'] == 350


def test_flexible_job_enforces_saved_max_before_renderer(monkeypatch, tmp_path):
    from app import candidates
    from tests.test_candidates import setup, job
    calls,_ = setup(monkeypatch,tmp_path)
    record = job()
    record['candidates'] = [{'start':0, 'end':100, 'duration_mode':'flexible'}]
    candidates.render_candidates(record, tmp_path/'source', [],
        {'duration_mode':'flexible','max_seconds':90}, False)
    assert calls == []
    assert record['candidates'][0]['state'] == 'FAILED'
    assert 'duration' in record['candidates'][0]['attempt_history'][0]['error'].lower()

@pytest.mark.parametrize('path, select', [
    ('contracts/youtube_ingest.schema.json', lambda schema:schema['properties']['settings']),
    ('contracts/api-v1.openapi.json', lambda schema:schema['components']['schemas']['Settings']),
])
def test_duration_settings_contracts_match_runtime(path, select):
    from pathlib import Path
    import jsonschema
    schema = select(json.loads(Path(path).read_text(encoding='utf-8')))
    jsonschema.validate({'duration_mode':'flexible','max_seconds':180}, schema)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({'max_seconds':90}, schema)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({'duration_mode':'flexible','max_seconds':181}, schema)


def test_flexible_timeline_json_contract():
    from pathlib import Path
    import jsonschema
    schema = json.loads(Path('contracts/timeline.schema.json').read_text(encoding='utf-8'))
    timeline = build_timeline({'start':0,'end':90,'text':'test','duration_mode':'flexible'},[])
    jsonschema.validate(timeline,schema)
    timeline.pop('duration_mode')
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(timeline,schema)


def test_flexible_ffmpeg_over_minute_with_actual_outro_qc(monkeypatch,tmp_path):
    import shutil
    import subprocess
    from app.core import render, get_duration
    from app.outro import append_outro
    from app.quality import inspect_media
    if not shutil.which('ffmpeg'):
        pytest.skip('ffmpeg required')
    source = tmp_path/'source.mp4'
    outro = tmp_path/'outro.mp4'
    for path, length in ((source,61),(outro,2)):
        subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=c=blue:s=64x96:r=5',
                        '-f','lavfi','-i','sine=frequency=300:sample_rate=48000','-t',str(length),
                        '-c:v','libx264','-c:a','aac','-pix_fmt','yuv420p',str(path)],check=True)
    target=tmp_path/'target.mp4'
    with pytest.raises(ValueError):
        render(source,0,61,[],target,width=64,height=96)
    render(source,0,61,[],target,width=64,height=96,duration_mode='flexible')
    monkeypatch.setattr('app.edit_render.ASSETS_ROOT', tmp_path)
    metadata=append_outro(target,'outro',{'outro':{'path':outro,'license_note':'Synthetic test'}})
    clip={'start':0,'end':61,'timeline':{'duration':61,'outro':metadata}}
    expected=candidate_duration(clip)
    assert expected == pytest.approx(63)
    assert get_duration(target) == pytest.approx(expected,abs=.15)
    qc=inspect_media(target,expected,(64,96),True,{})
    assert qc['state'] in ('VALID','WARNING'), qc
    assert qc['measurements']['decoded_complete']
    assert inspect_media(target,61,(64,96),True,{})['state'] == 'FAILED'
    preview=tmp_path/'preview.webm'
    subprocess.run(['ffmpeg','-v','error','-y','-i',str(target),'-c:v','libvpx',
                    '-deadline','realtime','-c:a','libopus',str(preview)],check=True)
    preview_qc=inspect_media(preview,expected,(64,96),True,{})
    assert preview_qc['state'] in ('VALID','WARNING'), preview_qc
    assert preview_qc['measurements']['decoded_complete']

@pytest.mark.parametrize('settings, clip', [
    ({}, {'start':0,'end':90,'timeline':{'duration':90,'duration_mode':'flexible'}}),
    ({'duration_mode':'flexible','max_seconds':90},
     {'start':0,'end':50,'duration_mode':'flexible','timeline':{'duration':175,'duration_mode':'flexible'}}),
])
def test_cached_timeline_cannot_bypass_saved_duration_limits(monkeypatch,tmp_path,settings,clip):
    from app import candidates
    from tests.test_candidates import setup,job
    calls,_=setup(monkeypatch,tmp_path)
    record=job();record['candidates']=[clip]
    candidates.render_candidates(record,tmp_path/'source',[],settings,False)
    assert calls == []
    assert clip['state'] == 'FAILED'


def test_flexible_time_window_sees_sixty_segments_and_accepts_complete_120s(monkeypatch):
    import io
    from app.ranker import propose_from_transcript
    segments=[{'start':i*2,'end':(i+1)*2,'text':f'Detalhe {i}.'} for i in range(60)]
    segments[0]['text']='GTA mudou.'
    segments[-1]['text']='Resultado final.'
    seen=[]
    def response(request, **kwargs):
        prompt=json.loads(request.data)['prompt']
        seen.append(prompt)
        table=json.loads(prompt.split('SEGMENTOS: ',1)[1].split('\n',1)[0])
        # The actual full source table must expose the conclusion in one window.
        assert len(table) == 60
        assert table[-1] == [59,118.0,120.0,'Resultado final.']
        evidence=[{'segment_id':i,'quote':segments[i]['text']} for i in (0,30,59)]
        item={'start_segment':0,'end_segment':59,'story':{'closure':'COMPLETE',
              'evidence':evidence,'parts':{'hook':0,'setup':30,'payoff':59}}}
        return io.BytesIO(json.dumps({'response':json.dumps({'clips':[item]})}).encode())
    monkeypatch.setattr('app.ranker.urllib.request.urlopen',response)
    events=[]
    result=propose_from_transcript(segments,120,duration_mode='flexible',min_seconds=8,
        max_seconds=180,max_chunks=1,backend='kepler_gpu',on_event=lambda event,details:events.append((event,details)))
    assert [(c['start'],c['end']) for c in result] == [(0,120)]
    assert len(seen) == 1
    budget=next(details['context_budget'] for event,details in events if event=='analyzing')
    assert budget['prompt_upper_bound']+budget['generation_reserve'] <= 4096


def test_flexible_oversized_windows_split_without_truncating_source_or_call_budget(monkeypatch):
    import io
    from app.ranker import propose_from_transcript
    segments=[{'start':i*2,'end':(i+1)*2,'text':f'Detalhe {i} '+('x'*100)+'.'} for i in range(60)]
    calls=[];events=[]
    def response(request, **kwargs):
        prompt=json.loads(request.data)['prompt']
        table=json.loads(prompt.split('SEGMENTOS: ',1)[1].split('\n',1)[0])
        assert all(row[3] == segments[int(row[1]/2)]['text'] for row in table)
        calls.append(table)
        return io.BytesIO(b'{"response":"{\\"clips\\":[]}"}')
    monkeypatch.setattr('app.ranker.urllib.request.urlopen',response)
    propose_from_transcript(segments,120,duration_mode='flexible',min_seconds=8,
        max_seconds=180,max_chunks=2,backend='kepler_gpu',on_event=lambda event,details:events.append((event,details)))
    assert 0 < len(calls) <= 2
    assert calls[-1][-1][1] >= 90  # Fit/sampling must reach the later source, not just its prefix.
    assert any(event=='proposal_window_split' for event,_ in events)
    assert any(event=='proposal_windows_deferred' for event,_ in events)
    assert all(details['context_budget']['prompt_upper_bound']+details['context_budget']['generation_reserve']<=4096
               for event,details in events if event=='analyzing')


def test_duration_mode_reruns_outside_ingest_form_without_creating_job(monkeypatch):
    from pathlib import Path
    import app
    from app import store, dashboard_health, edit_render, service
    from streamlit.testing.v1 import AppTest
    monkeypatch.setattr(store,'all_jobs',lambda:[])
    monkeypatch.setattr(edit_render,'read_assets',lambda:{})
    monkeypatch.setattr(dashboard_health,'render_doctor',lambda:None)
    submitted=[]
    monkeypatch.setattr(service,'create_job',lambda payload,**kwargs: (submitted.append(payload) or {'id':'synthetic-only'}))
    page=AppTest.from_file(str(Path(app.__file__).parent/'ui.py')).run(timeout=20)
    assert not page.exception
    page.radio(key='source_type').set_value('URL do YouTube').run()
    mode=page.selectbox(key='production_v2_duration_mode')
    assert mode.proto.form_id == ''
    mode.set_value('flexible').run()
    assert not page.exception
    maximum=page.number_input(key='production_v2_max_seconds_flexible')
    minimum=page.number_input(key='production_v2_min_seconds_flexible')
    assert maximum.max == 180 and maximum.value == 180
    assert minimum.min == 8 and minimum.value == 8
    assert submitted == []
    maximum.set_value(120)
    next(widget for widget in page.text_input if widget.label.startswith('URL de um')).set_value('https://www.youtube.com/watch?v=synthetic')
    next(widget for widget in page.text_input if widget.label == 'Criador / canal').set_value('Synthetic')
    next(widget for widget in page.text_area if widget.label.startswith('Comprova')).set_value('Synthetic test only')
    for checkbox in page.checkbox:
        if checkbox.label.startswith('Confirmo'):
            checkbox.check()
    next(button for button in page.button if button.label == 'Criar job de cortes').click().run()
    assert not page.exception
    assert submitted[0]['settings']['duration_mode'] == 'flexible'
    assert submitted[0]['settings']['max_seconds'] == 120
    page.selectbox(key='production_v2_duration_mode').set_value('classic').run()
    assert not page.exception
    assert page.number_input(key='production_v2_max_seconds_classic').max == 60
