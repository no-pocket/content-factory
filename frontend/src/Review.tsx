import {newRequestId} from './request-id'
import {useEffect,useState} from 'react'
import {useS,useDraft,review,action,media,api,toast,message,DEMO,simulateExternal,Conflict} from './store'
import {Head,Field,Tag,Seg,DEC,fmt,tc} from './ui'
import {DIMS,REASONS} from './types'
import type {Job,Cand,Payload,Seen,Dim,Dec} from './types'
import {canReviewJob,needsReview,syncReviewDraft,visibleReviewJobs,canScheduleCandidate,publicationKey} from './review-state'
import {Publish} from './Publish'
import {Editor} from './Editor'
const seen=(c:Cand):Seen=>({artifact:c.artifact,n:c.hist.length,revision:c.revision})
const fresh=(c:Cand):Payload=>({dec:'PENDING',comment:'',adjust:'',reasons:[],rating:{...c.rating},grade:c.grade})
export function Candidate({job,c,index}:{job:Job;c:Cand;index:number}){
  const [draft,setDraft,clear]=useDraft('review:'+job.id+':'+c.id,()=>({seen:seen(c),p:fresh(c),requestId:newRequestId()}))
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[format,setFormat]=useState('webm'),[player]=useState(0),[editor,setEditor]=useState(false),[publishing,setPublishing]=useState(false)
  const stale=draft.seen.artifact!==c.artifact||draft.seen.n!==c.hist.length||draft.seen.revision!==c.revision
  useEffect(()=>{if(stale&&!busy){setDraft(syncReviewDraft(draft,seen(c),newRequestId()));setError('');if(draft.seen.artifact!==c.artifact)toast('Vídeo atualizado. Confira a nova versão antes de avaliar.')}},[stale,busy,c.artifact,c.hist.length,c.revision])
  const set=(p:Partial<Payload>)=>setDraft({...draft,p:{...draft.p,...p},requestId:newRequestId()})
  const p=draft.p,idle=canReviewJob(job.st),valid=idle&&['VALID','WARNING'].includes(c.qc)&&(job.protocol!==2||c.intact)
  const wordTiming=c.word_timing as {reason?:string;partial_segments_omitted?:number;zero_duration_words_grouped?:number}|undefined
  const titleDiagnostic=(c as Cand & {title_diagnostic?:{reason?:string}}).title_diagnostic
  const captionWarnings=(c.diagnostic as {caption_readability?:{warnings?:{code:string;start:number;end:number;characters_per_second?:number}[]}}|null)?.caption_readability?.warnings??[]
  async function submit(dec:Dec){setBusy(true);setError('');try{
    await review(job.id,c.id,draft.seen,{...p,dec},draft.requestId);clear();setDraft({seen:{...draft.seen,n:draft.seen.n+1,revision:draft.seen.revision+1},p:{...p,dec},requestId:newRequestId()});toast('Avaliação salva.')
  }catch(e){setError((e instanceof Conflict?'Conflito de revisão. ':'')+message(e))}finally{setBusy(false)}}
  async function run(name:string){setBusy(true);setError('');try{await action(`/jobs/${job.id}/candidates/${c.id}/${name}`,{artifact:c.artifact});toast(name==='retry'?'Nova tentativa enfileirada.':'Sugestões geradas.')}catch(e){setError(message(e))}finally{setBusy(false)}}
  return <article className="cand" aria-label={'Candidato '+(index+1)}><div className="mh"><h2>Candidato {index+1}</h2><Tag k={DEC[c.dec]?.[1]}>{DEC[c.dec]?.[0]??c.dec}</Tag><Tag k={c.qc==='FAILED'?'er':c.qc==='WARNING'?'wr':'n'}>QC {c.qc}</Tag></div>
    <p className="mo">{tc(c.s)} → {tc(c.e)} · {(c.output_seconds??c.e-c.s).toFixed(1)} s de saída · {c.model}</p>
    {c.pace&&<p className="hint">Ritmo {c.pace.rate.toFixed(2)}× · {c.pace.words_per_minute==null?'ritmo original mantido':c.pace.words_per_minute+' palavras/min na fonte'} · áudio e legendas sincronizados</p>}
    {!!c.word_timing?.zero_duration_words_grouped&&<p className="warn">{c.word_timing.zero_duration_words_grouped} palavras foram agrupadas por falta de duração individual. Foram usados os tempos observados da fala adjacente; confira as legendas.</p>}
    {wordTiming?.reason==='word_alignment_not_verified'&&<p className="warn">As legendas usam tempos de segmentos, sem alinhamento confiável por palavra. Confira o texto com o áudio.</p>}
    {!!wordTiming?.partial_segments_omitted&&<p className="warn">{wordTiming.partial_segments_omitted} segmento(s) nas bordas ficaram sem legendas porque foram cortados. Confira e corrija as legendas antes de aprovar.</p>}
    {captionWarnings.length>0&&<details><summary>Legendas: {captionWarnings.length} alerta(s) de legibilidade</summary>{captionWarnings.map((w,i)=><p className="hint" key={i}>{tc(w.start)}–{tc(w.end)} · {w.code==='caption_fast'?'Texto rápido':w.code==='caption_long'?'Texto longo':'Duração inválida'}{w.characters_per_second!=null?` · ${w.characters_per_second} caracteres/s`:''}</p>)}</details>}
    {titleDiagnostic&&<p className="warn">O título proposto exige conferência editorial ({titleDiagnostic.reason}). Confira se corresponde ao áudio.</p>}
    {c.pace?.reason==='native_timing_unavailable'&&<p className="warn">Sem aceleração por tempos de palavras insuficientes. Confira as legendas.</p>}
    <p className="hint">Direção: {c.director} · Render: {c.renderer} · Palavras: {c.w??'não registrado'} · Tentativa {c.attempts}</p>
    {c.ai&&<p className="ai">{c.ai}</p>}{c.renderer.startsWith('ffmpeg')&&<p className="warn"><b>Renderização simplificada FFmpeg:</b> mantém legendas e enquadramentos programados, mas não compõe títulos animados, zooms ou B-roll. Confira o mestre e as legendas antes de aprovar.</p>}
    {!DEMO&&valid&&job.protocol===2&&<button type="button" className="b" disabled={busy||!idle||stale} onClick={()=>setEditor(!editor)}>{editor?'Fechar editor':'Editar vídeo'}</button>}
    <div className="rv"><div>{DEMO?<div className="pv"><em>Demonstração sem mídia real</em></div>:valid?<>
      <Seg v={format} on={setFormat} o={[["webm","Prévia WebM"],["mp4","MP4 mestre"]]}/>
      <video key={format+player} controls playsInline preload="metadata" src={media(job.id,c.id,format,draft.seen.artifact)} aria-label={'Vídeo do candidato '+(index+1)} onError={()=>setError('Não foi possível reproduzir esta versão. Recarregue e confira o QC.')}/>
      <div className="ac"><a className="b" href={media(job.id,c.id,'mp4',c.artifact,true)}>Baixar MP4</a><a className="b" href={media(job.id,c.id,'timeline',c.artifact,true)}>Timeline JSON</a></div>
    </>:<p className="warn">Arquivo não verificado, alterado ou com falha. Pode ser recusado com comentário.</p>}
      <details><summary>Transcrição e informações do corte</summary><p className="transcript">{c.tx||'Transcrição indisponível.'}</p>{c.assembly!=null&&<pre>{JSON.stringify(c.assembly,null,2)}</pre>}</details>
      <details><summary>Diagnóstico técnico e sinais editoriais</summary><pre>{JSON.stringify({qc:c.diagnostic,story:c.story},null,2)}</pre></details>
      {!DEMO&&c.qc==='FAILED'&&<button type="button" className="b" disabled={busy||c.attempts>=(job.qc_settings.max_attempts??2)} onClick={()=>run('retry')}>Tentar novamente este candidato</button>}
      {!DEMO&&valid&&<button className="b" type="button" disabled={busy} onClick={()=>run('captions')}>Gerar sugestões de legenda</button>}
      {c.captions&&<details><summary>Sugestões para redes sociais</summary>{Object.entries(c.captions).map(([provider,v])=><section key={provider}><h3>{provider}</h3><p>{v.text}</p><p className="hint">{v.origin}{v.reason&&` · ${v.reason}`}</p></section>)}</details>}
    </div><div><form onSubmit={e=>e.preventDefault()} aria-label={'Avaliação do candidato '+(index+1)}>
      {error&&<div className="warn" role="alert"><p>{error}</p></div>}
      {job.protocol!==2&&<p className="hint">Protocolo legado: sem grau de conteúdo nem aprovação com ajustes. Avaliações anteriores são preservadas sem migração automática.</p>}
      <Field l="Comentário / motivo"><textarea maxLength={4000} value={p.comment} onChange={e=>set({comment:e.target.value})} placeholder="Obrigatório para recusar; opcional para aprovação limpa."/></Field>
      <details><summary>Motivos, notas e ajustes</summary><div className="chips">{Object.entries(REASONS).map(([code,label])=><button type="button" key={code} aria-pressed={p.reasons.includes(code)} onClick={()=>set({reasons:p.reasons.includes(code)?p.reasons.filter(x=>x!==code):[...p.reasons,code]})}>{label}</button>)}</div>
        <div className="two">{Object.entries(DIMS).filter(([k])=>job.protocol===2||['hook','context','closure','captions'].includes(k)).map(([k,label])=><Field key={k} l={label}><select value={p.rating[k as Dim]??''} onChange={e=>set({rating:{...p.rating,[k]:e.target.value?Number(e.target.value):null}})}><option value="">Não avaliado</option>{[1,2,3,4,5].map(n=><option key={n}>{n}</option>)}</select></Field>)}</div>
        {job.protocol===2&&<Field l="Grau de conteúdo"><select value={p.grade??''} onChange={e=>set({grade:e.target.value===''?null:Number(e.target.value)})}><option value="">Não avaliado</option>{[0,1,2,3].map(n=><option key={n} value={n}>{n}</option>)}</select></Field>}
        <Field l="Pedidos de ajuste"><textarea maxLength={4000} value={p.adjust} onChange={e=>set({adjust:e.target.value})}/></Field>
      </details>
      <div className="ac">{canScheduleCandidate(job,c)&&<button type="button" className="b p" disabled={busy||stale} onClick={()=>setPublishing(true)}>Agendar publicação</button>}<button className="b ok" type="button" disabled={busy||stale||!valid} onClick={()=>submit('APPROVED')}>Aprovar</button>{job.protocol===2&&<button className="b" type="button" disabled={busy||stale||!valid} onClick={()=>submit('APPROVED_WITH_ADJUSTMENTS')}>Aprovar com ajustes</button>}<button className="b er" type="button" disabled={busy||stale||!idle||!p.comment.trim()} onClick={()=>submit('REJECTED')}>Recusar</button></div>
      {busy&&<p role="status">Salvando…</p>}<p className="hint">Avaliar não publica. Rascunho mantido nesta sessão do navegador.</p>
    </form><details><summary>Histórico ({c.hist.length}) e ajustes registrados</summary>{c.hist.map((e,i)=><div key={i} className="rw col"><span className="hint">{fmt(e.at)} · {e.by} · {DEC[e.dec]?.[0]??e.dec}</span><p>{e.comment||'Sem comentário.'}</p></div>)}{c.edits.length>0&&<pre>{JSON.stringify(c.edits,null,2)}</pre>}</details></div></div>
    {editor&&<Editor job={job} c={c} onClose={()=>setEditor(false)}/>}
    {publishing&&<div className="schedule-backdrop"><section role="dialog" aria-modal="true" aria-labelledby="review-publish-title" className="schedule-dialog review-publish-dialog" onKeyDown={e=>{if(e.key==='Escape'&&!e.defaultPrevented)setPublishing(false)}}><div className="mh"><h2 id="review-publish-title">Agendar publicação</h2><button type="button" className="b" onClick={()=>setPublishing(false)}>Fechar</button></div><Publish embedded candidateKey={publicationKey(job.id,c.id,c.artifact)}/></section></div>}
  </article>
}
interface GroupSummary{group_id:string;jobs:{id:string;original_name:string;model:{label:string}}[];candidate_count:number}
interface Group extends GroupSummary{revision:string;candidates:{job_id:string;candidate_id:string;candidate_version:number;render_revision:number;artifact_id:string;selectable:boolean;selected_current:boolean;release_ready:boolean;overlaps:unknown[]}[];selection_history:unknown[];reconciliation_required:boolean}
function Compare({requested}:{requested?:string}){
  const s=useS(),[groups,setGroups]=useState<GroupSummary[]>([]),[selected,setSelected]=useState(''),[group,setGroup]=useState<Group>(),[checked,setChecked]=useState<string[]>([]),[error,setError]=useState(''),[busy,setBusy]=useState(false)
  useEffect(()=>{if(!DEMO)api<GroupSummary[]>('/groups').then(setGroups).catch(e=>setError(message(e)))},[])
  async function load(id:string){setSelected(id);setBusy(true);try{const g=await api<Group>('/groups/'+encodeURIComponent(id));setGroup(g);setChecked(g.candidates.filter(c=>c.selected_current).map(c=>c.job_id+':'+c.candidate_id));setError('')}catch(e){setError(message(e))}finally{setBusy(false)}}
  useEffect(()=>{if(requested)void load(requested)},[requested])
  async function save(){if(!group)return;setBusy(true);try{const selected=group.candidates.filter(c=>checked.includes(c.job_id+':'+c.candidate_id)).map(({job_id,candidate_id,candidate_version,render_revision,artifact_id})=>({job_id,candidate_id,candidate_version,render_revision,artifact_id}));await action('/groups/'+encodeURIComponent(group.group_id)+'/finals',{request_id:newRequestId(),expected_revision:group.revision,selected});await load(group.group_id);toast('Finais selecionados. A aprovação editorial permanece separada.')}catch(e){setError(message(e))}finally{setBusy(false)}}
  return <><Field l="Fonte para comparar"><select value={selected} onChange={e=>e.target.value&&load(e.target.value)}><option value="">Selecione uma fonte</option>{groups.map(g=><option key={g.group_id} value={g.group_id}>{g.jobs[0]?.original_name} · {g.jobs.length} jobs · {g.candidate_count} candidatos</option>)}</select></Field>{error&&<p className="warn" role="alert">{error}<button className="b" onClick={()=>load(selected)}>Recarregar comparação</button></p>}{busy&&<p role="status">Carregando…</p>}{group&&<>
    {group.reconciliation_required&&<p className="warn">Fontes foram agrupadas. Reconfirme a seleção de finais.</p>}
    {group.candidates.map(row=>{const j=s.jobs.find(j=>j.id===row.job_id),c=j?.cands.find(c=>c.id===row.candidate_id);if(!j||!c)return null;const key=row.job_id+':'+row.candidate_id
      return <section key={key}><label className="ck"><input type="checkbox" disabled={!row.selectable||busy} checked={checked.includes(key)} onChange={e=>setChecked(e.target.checked?[...checked,key]:checked.filter(k=>k!==key))}/>Selecionar final · {c.model} · {tc(c.s)}–{tc(c.e)} · {row.release_ready?'Pronto para preflight':'Exige revisão'} · {row.overlaps.length} sobreposição(ões)</label><Candidate job={j} c={c} index={j.cands.indexOf(c)}/></section>})}
    <button className="b p" disabled={busy} onClick={save}>Salvar seleção de finais</button><details><summary>Histórico de seleção</summary><pre>{JSON.stringify(group.selection_history,null,2)}</pre></details></>}{DEMO&&<p>Comparação real indisponível no modo demonstração.</p>}</>
}
export function Review({requested,requestedGroup}:{requested?:string;requestedGroup?:string}){
  const s=useS(),[mode,setMode]=useState('job'),[filter,setFilter]=useState(requested?'all':'pending'),[decision,setDecision]=useState('all'),[selected,setSelected]=useState(requested??''),[busy,setBusy]=useState(false)
  useEffect(()=>{if(requested){setMode('job');setSelected(requested);setFilter('all')}},[requested])
  useEffect(()=>{if(requestedGroup)setMode('compare')},[requestedGroup])
  const filteredJobs=s.jobs.filter(j=>filter==='all'||(filter==='pending'?needsReview(j):filter==='done'?j.review_status==='COMPLETED':!canReviewJob(j.st)))
  const jobs=visibleReviewJobs(s.jobs,filteredJobs,selected)
  const job=jobs.find(j=>j.id===selected)??jobs[0]
  useEffect(()=>{if(!selected&&job)setSelected(job.id)},[selected,job?.id])
  async function run(name:string,body={}){if(!job)return;setBusy(true);try{await action(`/jobs/${job.id}/${name}`,body);toast('Operação concluída.')}catch(e){toast(message(e),'er')}finally{setBusy(false)}}
  return <><Head t="Revisão" s="Confira a fala, imagem, áudio e legendas antes de avaliar.">{DEMO&&<button className="b" onClick={()=>simulateExternal().then(()=>toast('Alteração externa simulada.'))}>Simular alteração externa</button>}</Head><Seg v={mode} on={setMode} o={[["job","Job individual"],["compare","Comparar fontes"]]}/>
    {mode==='compare'?<Compare requested={requestedGroup}/>:<><div className="two"><Field l="Exibir jobs"><select value={filter} onChange={e=>{setSelected('');setFilter(e.target.value)}}><option value="pending">Para revisar</option><option value="all">Todos</option><option value="done">Revisados</option><option value="running">Em processamento</option></select></Field><Field l="Filtrar candidatos"><select value={decision} onChange={e=>setDecision(e.target.value)}><option value="all">Todos</option>{Object.entries(DEC).map(([k,[l]])=><option key={k} value={k}>{l}</option>)}</select></Field></div>
      {jobs.length?<Field l="Selecione um job"><select value={job?.id??''} onChange={e=>setSelected(e.target.value)}>{[...jobs].sort((a,b)=>b.created-a.created).map(j=><option key={j.id} value={j.id}>{j.name} · {j.eng} · {j.st} · {j.id.slice(0,8)}</option>)}</select></Field>:<p className="cand">Nenhum job corresponde aos filtros.</p>}
      {job&&<><p>{job.who} · {job.lang||'Idioma não registrado'} · {job.lic}</p><details><summary>Ajustes salvos e histórico de fallbacks</summary><pre>{JSON.stringify({settings:job.settings,editorial:job.editorial_result,events:job.events,activity:job.activity},null,2)}</pre></details>{job.error&&<p className="warn">{job.error}</p>}
        {job.st==='WAITING_EDITORIAL_PLAN'&&<p role="status">Aguardando análise editorial do Hermes.{job.editorial_result?.deadline_ms?` Prazo: ${new Date(job.editorial_result.deadline_ms).toLocaleString('pt-BR')}.`:''}</p>}
        {job.st==='EDITORIAL_NO_CANDIDATES'&&<div className="cand"><p>O Hermes não encontrou cortes adequados nesta análise.</p><p>{job.editorial_result?.reason}</p>{!DEMO&&job.editorial_result?.run_id&&<button className="b" disabled={busy} onClick={()=>run('retry-editorial',{request_id:crypto.randomUUID(),expected_run_id:job.editorial_result?.run_id})}>Solicitar nova análise</button>}</div>}
        {job.auto_rework_enabled&&<p className="hint">Ao concluir todas as avaliações, se houver aprovação com ajustes, será enfileirada uma nova proposta usando o conjunto das avaliações. Os originais são preservados; o novo vídeo exige revisão e não é publicado automaticamente.</p>}
        {job.parent_id&&<p className="cand">Reedição orientada pelas avaliações humanas. <a href={'#revisao?job='+job.parent_id}>Ver job original</a>. O resultado exige nova revisão.</p>}
        {(job.reworks??[]).map(r=><p className="cand" role="status" key={r.child_id}>Reedição com o conjunto das avaliações · {r.state==='PENDING'?'Aguardando fila':r.state==='BLOCKED'?'Bloqueada: confira fonte, permissões e configuração':'Job criado'} {r.state==='CREATED'&&<a href={'#revisao?job='+r.child_id}>Acompanhar novo candidato</a>}</p>)}
        <div className="ac">{job.cands.length>0&&!DEMO&&<button className="b" disabled={busy} onClick={()=>run('verify')}>{busy?'Verificando arquivos completos…':'Verificar arquivos existentes (sem renderizar)'}</button>}{job.st==='QUEUE_FAILED'&&<button className="b" disabled={busy} onClick={()=>run('retry-enqueue')}>Tentar enfileirar novamente</button>}</div>
        {job.cands.filter(c=>decision==='all'||c.dec===decision).map(c=><Candidate key={job.id+c.id} job={job} c={c} index={job.cands.indexOf(c)}/>)}
        {job.protocol!==2&&job.cands.length>0&&<details><summary>Recusar o job inteiro (legado)</summary><RejectAll onReject={reason=>run('reject',{reason})} busy={busy}/></details>}
        {job.review_status==='COMPLETED'&&<p role="status">Revisão concluída. Use Para revisar para seguir ao próximo job.</p>}</>}
    </>}
  </>
}
function RejectAll({onReject,busy}:{onReject:(s:string)=>void;busy:boolean}){const [reason,set]=useState('');return <><Field l="Motivo da recusa total"><textarea value={reason} onChange={e=>set(e.target.value)} maxLength={4000}/></Field><button className="b er" disabled={busy||!reason.trim()} onClick={()=>onReject(reason)}>Recusar todos os candidatos</button></>}
