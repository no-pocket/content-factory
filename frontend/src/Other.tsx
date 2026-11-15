import {useEffect,useState} from 'react'
import {useS,api,addJob,toast,message,STAGES,DEMO} from './store'
import {Field,Head,Tag,Meter} from './ui'
import {DIMS} from './types'
import type {Schema,Settings,Dim} from './types'
import {SettingsFields,preferences} from './Settings'
import {needsReview} from './review-state'
export interface Health{worker:{online:boolean;age_seconds?:number};ollama:{reachable:boolean;loaded?:boolean;installed?:boolean};kepler?:{reachable:boolean;loaded?:boolean;context_window?:number};queue:number|null;processing:number|null;agenda_online:boolean;release:string}
export function Painel({health}:{health:Health|null}){
  const s=useS(),pending=s.jobs.filter(needsReview),active=s.jobs.filter(j=>STAGES.includes(j.st))
  return <><Head t="Painel" s="Produção local, revisão humana e publicação escolhida."/><div className="stats"><div><b>{pending.length}</b><span>Jobs para revisar</span></div><div><b>{active.length}</b><span>Em processamento</span></div><div><b>{s.agenda.filter(a=>a.st==='SCHEDULED').length}</b><span>Agendados</span></div></div>
    <h2>Doctor</h2><div className="cand"><div className="two">
      <p><i className={'led '+(health?.worker.online?'ok':'er')}/>Worker {DEMO?'simulado':health?.worker.online?'online':'sem sinal'}{health?.worker.age_seconds!=null&&` · há ${health.worker.age_seconds} s`}</p>
      <p>Fila: {health?.queue??'—'} · Processando: {health?.processing??'—'}</p>
      <p><i className={'led '+(health?.kepler?.reachable?'ok':'er')}/>GPU K4200 {health?.kepler?.reachable?'online':'indisponível / não configurada'}{health?.kepler?.context_window&&` · contexto ${health.kepler.context_window}`}</p>
      <p>Ollama: {health?.ollama.reachable?(health.ollama.loaded?'modelo carregado':health.ollama.installed?'modelo instalado':'modelo ausente'):'indisponível'} · fallback por job</p>
      <p>Agenda: {health?.agenda_online?'executor ativo':'executor sem sinal'}</p><p>Release {s.release}</p></div><p className="hint">Doctor não executa inferência. Fallbacks e seus motivos ficam registrados no job.</p></div>
    <h2>Em andamento</h2>{active.length?active.map(j=><a key={j.id} className="rw job-link" href={'#revisao?job='+j.id}><span>{j.name}</span><Tag>{j.st}</Tag></a>):<p className="mu">Nenhum job em processamento.</p>}
    <h2>Para revisar</h2>{pending.length?pending.slice(0,12).map(j=><a className="rw job-link" key={j.id} href={'#revisao?job='+j.id}><span>{j.name}<small className="mu"> · {j.eng}</small></span><Tag k="ac">{j.cands.filter(c=>c.dec==='PENDING').length} pendentes</Tag></a>):<p className="mu">Nenhum candidato disponível está pendente.</p>}
  </>
}
export function Novo({schema}:{schema:Schema}){
  const [kind,setKind]=useState('upload'),[file,setFile]=useState<File>(),[url,setUrl]=useState(''),[who,setWho]=useState(''),[lic,setLic]=useState(''),[rights,setRights]=useState(false),[platform,setPlatform]=useState(false)
  const [title,setTitle]=useState(''),[metadataBusy,setMetadataBusy]=useState(false),[metadataError,setMetadataError]=useState(''),[videoId,setVideoId]=useState(''),[lookup,setLookup]=useState(0)
  useEffect(()=>{
    setMetadataBusy(false);setMetadataError('');setVideoId('')
    if(kind!=='youtube'||!url.trim())return
    if(DEMO){setTitle('Vídeo de demonstração');setWho('Canal de demonstração');return}
    const controller=new AbortController()
    const timer=setTimeout(async()=>{setMetadataBusy(true);try{
      const info=await api<{title:string;creator:string;video_id:string}>('/youtube/metadata',{method:'POST',body:JSON.stringify({source_url:url}),signal:controller.signal})
      if(!controller.signal.aborted){setTitle(info.title);setWho(info.creator);setVideoId(info.video_id)}
    }catch(e){if(!controller.signal.aborted)setMetadataError(message(e))}finally{if(!controller.signal.aborted)setMetadataBusy(false)}},650)
    return()=>{clearTimeout(timer);controller.abort()}
  },[kind,url,lookup])
  const [settings,setSettings]=useState<Settings>(()=>preferences(schema)),[qc,setQc]=useState({...schema.qc_defaults}),[assembly,setAssembly]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('')
  async function submit(e:React.FormEvent){e.preventDefault();setBusy(true);setError('');try{
    const job=await addJob(file?.name??'YouTube',who,lic,{...(kind==='upload'?{file}:{source_url:url}),video_title:title,rights_confirmed:rights,platform_permission:platform,settings,qc_settings:qc,...(assembly.trim()?{assembly_plan:JSON.parse(assembly)}:{})})
    toast(job?.duplicate?'Vídeo já cadastrado: job existente e ajustes preservados.':'Job criado e enfileirado. Acompanhe a produção no Painel.');location.hash=job?.duplicate?'revisao?job='+job.id:'painel'
  }catch(error){setError(message(error))}finally{setBusy(false)}}
  return <><Head t="Novo vídeo" s="Use somente fontes autorizadas. Cada job preserva sua configuração."/>
    <form className="cand" onSubmit={submit}><Field l="Origem"><select value={kind} onChange={e=>setKind(e.target.value)}><option value="upload">Upload local</option><option value="youtube" disabled={!schema.youtube_enabled&&!DEMO}>URL do YouTube</option></select></Field>
      {kind==='upload'?<Field l="Vídeo autorizado (MP4, MOV ou MKV)"><input required={!DEMO} type="file" accept=".mp4,.mov,.mkv" onChange={e=>{const f=e.target.files?.[0];setFile(f);setTitle(f?.name.replace(/\.[^.]+$/,'')??'');setRights(false)}}/></Field>:<><Field l="URL individual do YouTube"><input type="url" required value={url} onChange={e=>{setUrl(e.target.value);setTitle('');setWho('');setRights(false);setPlatform(false)}}/></Field>{metadataBusy&&<p role="status">Consultando título e criador no YouTube…</p>}{metadataError&&<p className="warn" role="alert">{metadataError} <button className="b" type="button" onClick={()=>setLookup(lookup+1)}>Consultar novamente</button></p>}{videoId&&<p className="hint">Vídeo {videoId} · o mesmo ID não cria um job duplicado.</p>}<label className="ck"><input type="checkbox" required checked={platform} onChange={e=>setPlatform(e.target.checked)}/>Confirmo autorização da plataforma para este método de download.</label></>}
      <div className="two"><Field l="Título do vídeo"><input required maxLength={4000} readOnly={metadataBusy} value={title} onChange={e=>setTitle(e.target.value)}/></Field><Field l="Criador / canal"><input required maxLength={4000} readOnly={metadataBusy} value={who} onChange={e=>setWho(e.target.value)}/></Field></div><Field l="Referência e escopo da autorização"><textarea required maxLength={4000} value={lic} onChange={e=>setLic(e.target.value)} placeholder="Licença ou autorização do titular; este campo não é o título."/></Field>
      <details><summary>Ajustes de processamento deste job</summary><SettingsFields schema={schema} value={settings} onChange={setSettings}/><Field l="Plano de montagem v3 opcional (JSON)"><textarea maxLength={16000} value={assembly} onChange={e=>setAssembly(e.target.value)}/></Field><p className="hint">Requer montagem multitrecho e protocolo 2. Não edita jobs anteriores.</p></details>
      <details><summary>Limites de QC por job</summary><div className="two">{Object.entries(qc).map(([k,v])=><Field key={k} l={k}><input type="number" step={['max_attempts','timeout_seconds'].includes(k)?1:'any'} required value={v} onChange={e=>setQc({...qc,[k]:e.target.valueAsNumber})}/></Field>)}</div></details>
      <label className="ck"><input type="checkbox" required checked={rights} onChange={e=>setRights(e.target.checked)}/>Confirmo permissão para editar, cortar e realizar os usos pretendidos deste vídeo.</label>
      {error&&<p role="alert" className="warn">{error}</p>}<button className="b p" disabled={busy}>{busy?'Enviando…':'Criar job de cortes'}</button>
    </form></>
}
interface Metrics{models:Record<string,{reviewed:number;approved:number;adjusted:number;rejected:number;pending:number}>;dimensions:Record<Dim,{mean:number|null;n:number}>;grades:Record<string,number>;readiness:Record<string,number|string[]>;gates:Record<string,number>;automatic_training:false;configuration_comparison:unknown;source_comparison:unknown}
export function Metricas(){
  const [data,set]=useState<Metrics>(),[error,setError]=useState(''),[busy,setBusy]=useState(false)
  async function load(){setBusy(true);setError('');try{if(DEMO)throw new Error('Métricas reais indisponíveis no modo demonstração.');set(await api<Metrics>('/metrics'))}catch(e){setError(message(e))}finally{setBusy(false)}}
  useEffect(()=>{void load()},[])
  return <><Head t="Métricas" s="Avaliações humanas e prontidão do dataset. Sem treino ou promoção automática."><button className="b" onClick={load} disabled={busy}>Atualizar métricas</button></Head>{busy&&<p role="status">Calculando…</p>}{error&&<p role="alert">{error}</p>}{data&&<>
    <h2>Aprovação por modelo</h2><div className="table-scroll"><table><thead><tr><th>Modelo</th><th>Aprovados</th><th>Com ajustes</th><th>Recusados</th><th>Pendentes</th><th>Taxa limpa</th></tr></thead><tbody>{Object.entries(data.models).map(([name,m])=><tr key={name}><td>{name}</td><td>{m.approved}</td><td>{m.adjusted}</td><td>{m.rejected}</td><td>{m.pending}</td><td>{m.reviewed?`${Math.round(100*m.approved/m.reviewed)}%`:'—'}</td></tr>)}</tbody></table></div>
    <div className="cols"><section><h2>Notas médias por dimensão</h2>{Object.entries(data.dimensions).map(([k,v])=><div key={k} className="rw"><span>{DIMS[k as Dim]}</span><span>{v.mean??'Não avaliado'} <small className="mu">(n={v.n})</small></span></div>)}</section><section><h2>Grau de conteúdo</h2>{Object.entries(data.grades).map(([k,v])=><div className="rw" key={k}><span>{k==='unknown'?'Não avaliado':`Grau ${k}`}</span><b>{v}</b></div>)}</section></div>
    <h2>Prontidão do dataset</h2><div className="cand">{Object.entries(data.gates).map(([k,max])=><Meter key={k} l={k} max={max} v={Number(data.readiness[k]??0)}/>)}<p className="hint">Critérios experimentais existentes; alcançar contagens não autoriza treino ou promoção. Legados e dados sem confirmação permanecem separados.</p></div><details><summary>Comparação por configuração, fonte e idioma</summary><pre>{JSON.stringify({configuration:data.configuration_comparison,source:data.source_comparison},null,2)}</pre></details></>}
  </>
}
