import {useEffect,useMemo,useState} from 'react'
import {api,action,message,toast} from './store'
import {Field} from './ui'
import {newRequestId} from './request-id'
import type {Cand,Job} from './types'

type Word={start:number;end:number;text:string;source_start?:number;source_end?:number}
type Scene='CREATOR_FACE'|'GAMEPLAY'|'SCREEN_CONTENT'|'DOCUMENT'|'OTHER'|'UNCERTAIN'
type Roi={x:number;y:number;width:number;height:number}
interface Timeline{
  schema_version:string;duration:number;source_range?:{start:number;end:number}
  segments?:{source_in:number;source_out:number;output_start:number;duration:number}[]
  layers:{captions:Word[];text:{text:string;origin?:string}[];effects:unknown[];broll:unknown[]}
  framing_schedule?:unknown[]
}
interface Frame{frame_id:number;time:number;image:string;ocr:{status:string;text:string;reason?:string};vision:null|{scene:Scene;confidence:number;roi:Roi|null}}
interface FrameResult{frames:Frame[];vision:{status:string;model?:string;reason?:string}}
interface BoundarySuggestion{suggested_seconds:number;original_seconds:number;method:string|null;reason:string}
interface BoundaryResult{start:BoundarySuggestion;end:BoundarySuggestion}
const sceneNames:Record<Scene,string>={CREATOR_FACE:'Rosto do criador',GAMEPLAY:'Gameplay',SCREEN_CONTENT:'Tela / página',DOCUMENT:'Documento / slide',OTHER:'Outro',UNCERTAIN:'Incerto'}
const fullRoi={x:0,y:0,width:1,height:1}

function sourceBounds(timeline:Timeline,word:Word):[number,number]{
  return timeline.schema_version==='3.0'?[word.source_start??0,word.source_end??0]:
    [(timeline.source_range?.start??0)+word.start,(timeline.source_range?.start??0)+word.end]
}
function captionKey(start:number,end:number){return `${start.toFixed(3)}:${end.toFixed(3)}`}
function framingFor(scene:Scene,roi:Roi|null){
  const region=roi??fullRoi
  if(scene==='CREATOR_FACE')return {preset:'face',roi:region}
  if(scene==='GAMEPLAY')return {preset:'gameplay',roi:fullRoi}
  if(scene==='SCREEN_CONTENT'||scene==='DOCUMENT')return {preset:scene==='DOCUMENT'?'document':'web',roi:region,layout_version:'proof_compact_v2'}
  return null
}

export function Editor({job,c,onClose}:{job:Job;c:Cand;onClose:()=>void}){
  const [timeline,setTimeline]=useState<Timeline>(),[loading,setLoading]=useState(true),[error,setError]=useState('')
  const [start,setStart]=useState(c.s),[end,setEnd]=useState(c.e),[title,setTitle]=useState('')
  const [wordText,setWordText]=useState<Record<string,string>>({}),[framingSchedule,setFramingSchedule]=useState<unknown[]>([])
  const [frames,setFrames]=useState<FrameResult>(),[frameBusy,setFrameBusy]=useState(false),[selected,setSelected]=useState<Record<number,Scene>>({})
  const [boundaries,setBoundaries]=useState<BoundaryResult>(),[boundaryBusy,setBoundaryBusy]=useState(false)
  const [scheduleEdited,setScheduleEdited]=useState(false),[confirmed,setConfirmed]=useState(false),[busy,setBusy]=useState(false)
  const url=`/jobs/${encodeURIComponent(job.id)}/candidates/${encodeURIComponent(c.id)}/media/timeline?artifact=${encodeURIComponent(c.artifact??'')}`

  useEffect(()=>{
    let active=true
    api<Timeline>(url).then(value=>{if(!active)return;setTimeline(value);setStart(value.source_range?.start??c.s);setEnd(value.source_range?.end??c.e);setTitle(value.layers.text.find(x=>x.text)?.text??'');setFramingSchedule(value.framing_schedule??[])})
      .catch(e=>{if(active)setError(message(e))}).finally(()=>{if(active)setLoading(false)})
    return()=>{active=false}
  },[url,c.s,c.e])

  const originalTitle=timeline?.layers.text.find(x=>x.text)?.text??''
  const captionOverrides=useMemo(()=>timeline?timeline.layers.captions.flatMap(word=>{
    const [a,b]=sourceBounds(timeline,word),text=wordText[captionKey(a,b)]
    return text!==undefined&&text!==word.text?[{source_start:a,source_end:b,text}]:[]
  }):[],[timeline,wordText])
  const sourceMax=job.dur??Math.max(c.e,end)
  const rangeChanged=!!timeline&&timeline.schema_version==='2.0'&&(Math.abs(start-(timeline.source_range?.start??c.s))>.001||Math.abs(end-(timeline.source_range?.end??c.e))>.001)
  const titleChanged=!!timeline&&title!==originalTitle
  const hasChanges=rangeChanged||titleChanged||captionOverrides.length>0||scheduleEdited

  function update<T>(fn:()=>void){fn();setConfirmed(false)}
  async function analyze(){
    setFrameBusy(true);setError('')
    try{
      const result=await api<FrameResult>(`/jobs/${encodeURIComponent(job.id)}/candidates/${encodeURIComponent(c.id)}/frames`,{
        method:'POST',body:JSON.stringify({artifact:c.artifact,candidate_version:c.candidate_version,render_revision:c.render_revision}),
      })
      setFrames(result);setSelected(Object.fromEntries(result.frames.map(frame=>[frame.frame_id,frame.vision?.scene??'UNCERTAIN'])))
    }catch(e){setError(message(e))}finally{setFrameBusy(false)}
  }
  async function suggestBoundaries(){
    setBoundaryBusy(true);setError('')
    try{
      setBoundaries(await api<BoundaryResult>(`/jobs/${encodeURIComponent(job.id)}/candidates/${encodeURIComponent(c.id)}/boundaries`,{
        method:'POST',body:JSON.stringify({artifact:c.artifact,candidate_version:c.candidate_version,render_revision:c.render_revision}),
      }))
    }catch(e){setError(message(e))}finally{setBoundaryBusy(false)}
  }
  function applyFrames(){
    if(!timeline||!frames)return
    const duration=timeline.duration
    const interval=Math.min(1,Math.max(.25,duration/(frames.frames.length*2)*.4))
    const schedule=frames.frames.flatMap(frame=>{
      const scene=selected[frame.frame_id]??'UNCERTAIN',framing=framingFor(scene,frame.vision?.roi??null)
      if(!framing)return[]
      const from=Math.max(0,frame.time-interval),to=Math.min(duration,frame.time+interval)
      if(to<=from)return[]
      return[{start:from,end:to,framing}]
    })
    if(schedule.length>8){setError('Selecione no máximo oito janelas de enquadramento.');return}
    setFramingSchedule(schedule);setScheduleEdited(true);setConfirmed(false)
    toast(`${schedule.length} sugestão(ões) adicionada(s) ao rascunho. Confira antes de renderizar.`)
  }
  async function save(){
    if(!timeline||!hasChanges||!confirmed)return
    const changes:Record<string,unknown>={}
    if(rangeChanged){changes.source_start=start;changes.source_end=end}
    if(titleChanged)changes.title=title
    if(captionOverrides.length)changes.caption_overrides=captionOverrides
    if(scheduleEdited)changes.framing_schedule=framingSchedule
    setBusy(true);setError('')
    try{
      await action(`/jobs/${encodeURIComponent(job.id)}/candidates/${encodeURIComponent(c.id)}/edit`,{
        artifact:c.artifact,candidate_version:c.candidate_version,render_revision:c.render_revision,
        editorial_revision:c.revision,request_id:newRequestId(),changes,
      })
      toast('Edição confirmada e enviada para renderização. A nova versão exigirá outra revisão.')
      onClose()
    }catch(e){setError(message(e))}finally{setBusy(false)}
  }

  return <section className="editor-panel" aria-label="Editor visual do candidato">
    <div className="mh"><h3>Editar candidato</h3><button type="button" className="b" onClick={onClose}>Fechar editor</button></div>
    <p className="hint">As sugestões não alteram o vídeo por conta própria. Confira e confirme cada ajuste; uma nova versão será renderizada sem substituir a anterior.</p>
    {loading&&<p role="status">Carregando timeline…</p>}
    {error&&<p className="warn" role="alert">{error}</p>}
    {timeline&&<>
      {timeline.schema_version==='2.0'?<div className="two">
        <Field l="Início na fonte (s)"><input type="number" min="0" max={end-.1} step=".01" value={start} onChange={e=>{const n=e.target.valueAsNumber;if(Number.isFinite(n))update(()=>setStart(n))}}/></Field>
        <Field l="Fim na fonte (s)"><input type="number" min={start+.1} max={sourceMax} step=".01" value={end} onChange={e=>{const n=e.target.valueAsNumber;if(Number.isFinite(n))update(()=>setEnd(n))}}/></Field>
        <p className="hint editor-span">Cortes que atravessam uma palavra são recusados. O vídeo acima mostra a versão atual; a nova será pré-visualizada após renderização.</p>
      </div>:<p className="hint">Montagem multitrecho: a ordem e os cortes das cenas são mantidos. Legendas e enquadramento continuam editáveis.</p>}
      {timeline.schema_version==='2.0'&&<div className="ac"><span className="hint">Sugestões locais por pausas ou energia do áudio; confira o resultado antes de renderizar.</span><button type="button" className="b" disabled={busy||boundaryBusy} onClick={suggestBoundaries}>{boundaryBusy?'Buscando sugestões…':'Sugerir limites'}</button>{boundaries&&(['start','end'] as const).map(side=>{const b=boundaries[side];return b.method?<button type="button" className="b" key={side} onClick={()=>update(()=>side==='start'?setStart(b.suggested_seconds):setEnd(b.suggested_seconds))}>Usar sugestão de {side==='start'?'início':'fim'}: {b.suggested_seconds.toFixed(2)} s · {b.method==='word_gap'?'pausa entre palavras':'vale de áudio'}</button>:<span className="hint" key={side}>Sem sugestão confiável para {side==='start'?'o início':'o fim'}.</span>})}</div>}
      <Field l="Título sobreposto (vazio remove)"><input maxLength={80} value={title} onChange={e=>update(()=>setTitle(e.target.value))}/></Field>
      <details className="editor-captions"><summary>Corrigir palavras das legendas ({timeline.layers.captions.length})</summary>
        <div className="caption-list">{timeline.layers.captions.map((word,index)=>{
          const [a,b]=sourceBounds(timeline,word),key=captionKey(a,b)
          return <label className="caption-word" key={`${key}-${index}`}><span>{word.start.toFixed(2)}s</span>
            <input aria-label={`Palavra ${index+1} da legenda`} maxLength={64} value={wordText[key]??word.text}
              onChange={e=>update(()=>setWordText(current=>({...current,[key]:e.target.value})))}/></label>
        })}</div>
      </details>
      <section className="frame-analysis">
        <div className="bar2"><div><h4>Analisar alguns quadros</h4><p className="hint">OCR detecta texto; o modelo local sugere rosto, gameplay ou conteúdo de tela.</p></div>
          <button type="button" className="b" disabled={frameBusy||busy} onClick={analyze}>{frameBusy?'Analisando localmente…':'Analisar quadros'}</button>
        </div>
        {frames&&<><p className="hint">Visão: {frames.vision.status}{frames.vision.model?` · ${frames.vision.model}`:''}{frames.vision.reason?` · ${frames.vision.reason}`:''}. OCR e visão são sugestões, não decisões automáticas.</p>
          {frames.frames.length===0?<p className="hint">Nenhum quadro foi extraído.</p>:<div className="editor-frames">{frames.frames.map(frame=>{
            const scene=selected[frame.frame_id]??'UNCERTAIN'
            return <article className="frame-card" key={frame.frame_id}>
              <img src={frame.image} alt={`Quadro de origem aos ${frame.time.toFixed(1)} segundos`}/>
              <b>{frame.time.toFixed(1)} s</b>
              <label className="ck"><input type="checkbox" checked={scene!=='UNCERTAIN'&&scene!=='OTHER'}
                onChange={e=>setSelected(current=>({...current,[frame.frame_id]:e.target.checked?(frame.vision?.scene??'SCREEN_CONTENT'):'UNCERTAIN'}))}/>Usar enquadramento</label>
              <select aria-label={`Classificação de cena aos ${frame.time.toFixed(1)} segundos`} value={scene}
                onChange={e=>setSelected(current=>({...current,[frame.frame_id]:e.target.value as Scene}))}>
                {Object.entries(sceneNames).map(([key,label])=><option key={key} value={key}>{label}</option>)}
              </select>
              {frame.vision&&<small>Visão: {sceneNames[frame.vision.scene]} · {Math.round(frame.vision.confidence*100)}%</small>}
              <small>OCR: {frame.ocr.status}</small>
              <p>{frame.ocr.text||frame.ocr.reason||'Nenhum texto legível detectado.'}</p>
            </article>
          })}</div>}
          <div className="ac"><button type="button" className="b" disabled={busy||!frames.frames.length} onClick={applyFrames}>Adicionar enquadramentos selecionados ao rascunho</button>
            {scheduleEdited&&<button type="button" className="b" onClick={()=>{setFramingSchedule([]);setScheduleEdited(true);setConfirmed(false)}}>Limpar janelas do rascunho</button>}</div>
        </>}
      </section>
      {framingSchedule.length>0&&<p className="hint">Rascunho contém {framingSchedule.length} janela(s) de enquadramento; elas só serão usadas ao salvar a revisão.</p>}
      {c.renderer.startsWith('ffmpeg')&&<p className="warn"><b>Renderizador simplificado:</b> FFmpeg mantém legendas e enquadramentos programados, mas não compõe títulos animados, zooms ou B-roll.</p>}
      {hasChanges&&<label className="ck editor-confirm"><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>Revisei os ajustes e confirmo gerar uma nova versão deste candidato.</label>}
      <div className="ac"><button type="button" className="b p" disabled={busy||loading||!hasChanges||!confirmed} onClick={save}>{busy?'Enviando edição…':'Confirmar e renderizar revisão'}</button></div>
    </>}
  </section>
}
