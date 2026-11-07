"""One explicit human-guided revision; no new inference or approval of the result."""
import copy
import hashlib
import json
import time
from pathlib import Path

from app.store import JOBS, load, new_job, save
from app.edit_render import read_assets
from app.timeline import build_timeline
from app.worker import process


def main():
    parent = load('77b79d5e-c999-45bf-86ee-a4ddfacaaf6e')
    before = hashlib.sha256((JOBS/(parent['id']+'.json')).read_bytes()).hexdigest()
    transcript = json.loads((JOBS/(parent['id']+'.transcript.json')).read_text(encoding='utf-8'))
    old = parent['candidates'][0]
    title = 'ÍCONE DOURADO NO GTA 6!! CROCODILO LENDÁRIO?!'
    clip = {key: copy.deepcopy(old[key]) for key in ('start', 'end', 'text', 'score', 'reason')}
    hints = {key: copy.deepcopy(old['timeline']['layers'][key]) for key in ('effects', 'broll')}
    clip['timeline'] = build_timeline(clip, transcript['segments'], edit=hints, assets=read_assets(), editorial_title=title)
    assert clip['timeline']['layers']['captions'] == old['timeline']['layers']['captions']
    clip['director_used'] = 'human_revision_of_kepler_gpu'
    job = new_job(Path(parent['source']), 'Revisão editorial - título humano e final suave.mp4',
                  parent['creator'], parent['license_note'], settings=parent['settings'])
    job.update(candidates=[clip], source_fingerprint=parent.get('source_fingerprint'),
               source_parent_job=parent['id'], source_parent_candidate=0,
               pipeline_version='editorial-title-ending-v1', ranker_used='reused_parent_kepler_gpu',
               evaluation={'cohort':'approved-style-gpu-v1','variant':'human-title-soft-ending-v1'},
               qc_settings=parent['qc_settings'], editorial_feedback=[{
                   'at':time.time(), 'origin':'explicit_user_message', 'decision':None,
                   'reason':'Ambos os modelos produziram o mesmo candidato. Imagem, legendas e efeitos ótimos; '
                            'fechamento bom, mas corte final seco. Título repetia a legenda.',
                   'requested_title':title, 'compared_jobs':[parent['id'],'90dda26b-ae0d-4ee1-8b3f-643c554eb078']}])
    save(job)
    (JOBS/(job['id']+'.transcript.json')).write_text(json.dumps(transcript, ensure_ascii=False),encoding='utf-8')
    print('REVISION_JOB '+job['id'], flush=True)
    process(job['id'])
    result = load(job['id'])
    report = {'job_id':result['id'], 'status':result['status'], 'source_parent_job':parent['id'],
              'source_window':[old['start'],old['end']], 'title':title,
              'parent_record_unchanged':before == hashlib.sha256((JOBS/(parent['id']+'.json')).read_bytes()).hexdigest(),
              'candidate':{k:result['candidates'][0].get(k) for k in ('state','renderer_used','director_used','file','qc')},
              'editorial_approval':None}
    Path('/data/title-ending-revision.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False),flush=True)


if __name__ == '__main__':
    main()
