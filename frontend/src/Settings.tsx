import {useState} from 'react'
import type {Schema,Settings as Values} from './types'
import {Field,Head} from './ui'
import {toast,useS} from './store'
const key='cf:processing-defaults:v1'
export function preferences(schema:Schema):Values{try{return {...schema.defaults,...JSON.parse(localStorage.getItem(key)??'{}')}}catch{return {...schema.defaults}}}
const labels:Record<string,string>={auto_pace:'Ajustar fala lenta (até 1,15×, preservando o tom)',editorial_protocol:'Protocolo editorial',clip_count:'Quantidade de candidatos',duration_mode:'Duração da história',target_seconds:'Duração de referência (s)',min_seconds:'Duração mínima (s)',max_seconds:'Duração máxima (s)',proposal_max_chunks:'Máximo de blocos Qwen',shortlist:'Candidatos para classificação',ollama_timeout:'Prazo por consulta Qwen (s)',whisper_model:'Modelo Whisper',whisper_beam_size:'Beam size Whisper',ranker_mode:'Seleção dos destaques',llm_backend:'Backend Qwen',llm_model:'Modelo Qwen',director_mode:'Direção da edição',render_engine:'Motor de render',render_quality:'Qualidade de render',render_fallback_ffmpeg:'Permitir fallback FFmpeg (apenas standard)',timeline_v3:'Montagem multitrecho v3 (requer protocolo 2)',framing_preset:'Conteúdo visual',framing_roi:'ROI manual (JSON ou vazio)',framing_windows:'Intervalos de página/tweet (ex.: 12.5-18;40-47)',retrieval_mode:'Exemplos editoriais',retrieval_dataset_id:'ID do dataset de exemplos',outro_asset_id:'Encerramento licenciado opcional'}
const choices:Record<string,[string|number,string][]>= {
  editorial_planner:[['local','Modelo local'],['hermes_first','Hermes quando autorizado']],
  editorial_protocol:[[2,'2 — revisão versionada'],[1,'1 — legado']],duration_mode:[['classic','Clássica (até 60 s)'],['flexible','Flexível (até 180 s)']],
  ranker_mode:[['ollama','Qwen'],['heuristic','Heurística']],director_mode:[['ollama','Qwen'],['heuristic','Heurística']],
  llm_backend:[['kepler_gpu','GPU K4200 (experimental)'],['ollama','CPU / Ollama']],llm_model:[['qwen2.5:3b','Qwen 2.5 3B'],['qwen2.5:1.5b','Qwen 2.5 1.5B']],
  render_engine:[['remotion','Remotion'],['ffmpeg','FFmpeg (simplificado)']],render_quality:[['high','Alta fidelidade — exige Remotion'],['standard','Standard']],
  framing_preset:[['legacy','Vertical aprovado'],['face','Rosto'],['gameplay','Gameplay'],['web','Página web'],['tweet','Tweet'],['document','Documento']],retrieval_mode:[['off','Desativados'],['lexical','Busca lexical local']]}
export function SettingsFields({schema,value,onChange}:{schema:Schema;value:Values;onChange:(s:Values)=>void}){
  labels.editorial_planner='Planejamento editorial'
  labels.editorial_fallback_local='Permitir fallback editorial local'
  const {assets}=useS()
  function set(k:string,v:Values[string]){let next={...value,[k]:v};if(k==='duration_mode')next={...next,min_seconds:v==='flexible'?8:15,max_seconds:v==='flexible'?180:60};onChange(next)}
  return <div className="two settings-fields">{Object.keys({...schema.defaults,render_fallback_ffmpeg:true}).map(k=>{
    const v=value[k],opts=k==='whisper_model'?schema.whisper_models.map(x=>[x,x] as [string,string]):k==='outro_asset_id'?[['','Desativado'],...assets.filter(a=>a.duration<=120).map(a=>[a.id,a.d])]:choices[k]
    if(typeof v==='boolean')return <label key={k} className="ck"><input type="checkbox" checked={k==='render_fallback_ffmpeg'&&value.render_quality==='high'?false:v} disabled={k==='render_fallback_ffmpeg'&&value.render_quality==='high'} onChange={e=>set(k,e.target.checked)}/>{labels[k]??k}</label>
    if(opts)return <Field key={k} l={labels[k]??k}><select value={String(v??'')} onChange={e=>set(k,k==='editorial_protocol'?Number(e.target.value):e.target.value||null)}>{opts.map(([v,l])=><option key={v} value={v}>{l}</option>)}</select></Field>
    const range=schema.ranges[k],flex=value.duration_mode==='flexible'&&['min_seconds','max_seconds','target_seconds'].includes(k)
    if(range)return <Field key={k} l={labels[k]??k}><input type="number" min={flex?8:range[0]} max={flex?180:range[1]} required value={Number(v)} onChange={e=>set(k,e.target.valueAsNumber)}/></Field>
    const text=typeof v==='string'?v:v==null?'':JSON.stringify(v)
    return <Field key={k} l={labels[k]??k}><input value={text} maxLength={k==='framing_windows'?2000:1000} onChange={e=>set(k,e.target.value||null)}/></Field>
  })}</div>
}
export function Settings({schema}:{schema:Schema}){
  const [value,set]=useState(()=>preferences(schema))
  return <><Head t="Configurações" s="Preferências para novos jobs. Ajustes já salvos em jobs são preservados."/>
    <form className="cand" onSubmit={e=>{e.preventDefault();localStorage.setItem(key,JSON.stringify(value));toast('Preferências salvas neste navegador.')}}>
      <SettingsFields schema={schema} value={value} onChange={set}/><p className="hint">High exige Remotion. CPU/Ollama e standard continuam disponíveis. Nenhuma alteração reinicia serviços.</p>
      <div className="ac"><button className="b p">Salvar preferências</button><button type="button" className="b" onClick={()=>{localStorage.removeItem(key);set({...schema.defaults});toast('Defaults restaurados.')}}>Restaurar defaults</button></div>
    </form><p className="hint">YouTube: {schema.youtube_enabled?'habilitado':'desabilitado'} na instalação. Direitos e permissão da plataforma continuam obrigatórios. Variáveis de instalação e credenciais são administradas no servidor.</p></>
}
