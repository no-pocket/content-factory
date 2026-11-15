import {useEffect,useState} from 'react'
import {useS,refresh,api,DEMO} from './store'
import type {Schema} from './types'
import {Review} from './Review'
import {Publish} from './Publish'
import {Library} from './Library'
import {Painel,Novo,Metricas} from './Other'
import type {Health} from './Other'
import {Settings} from './Settings'
import {needsReview} from './review-state'
const NAV=[['painel','Painel','M3 12h4l3-8 4 16 3-8h4'],['novo','Novo vídeo','M12 5v14M5 12h14'],['revisao','Revisão','M5 12l4 4 10-10'],['publicacao','Publicação','M4 7h16v13H4zM4 11h16M8 3v4M16 3v4'],['biblioteca','Biblioteca','M5 4h4v16H5zM11 4h4v16h-4zM17 6l3 1-3 13-3-1z'],['metricas','Métricas','M5 20V10M12 20V4M19 20v-7'],['configuracoes','Configurações','M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8M12 3v3M12 18v3M3 12h3M18 12h3']]
const read=()=>{if(location.hash.slice(1))return location.hash.slice(1);const q=new URLSearchParams(location.search);return q.has('job')?'revisao?job='+encodeURIComponent(q.get('job')!):q.has('group')?'revisao?group='+encodeURIComponent(q.get('group')!):'painel'}
const demoSchema:Schema={defaults:{editorial_protocol:2,clip_count:2,duration_mode:'classic',min_seconds:15,target_seconds:40,max_seconds:60,whisper_model:'base',render_engine:'remotion',render_quality:'high',render_fallback_ffmpeg:false},ranges:{clip_count:[1,6],min_seconds:[8,60],target_seconds:[8,60],max_seconds:[15,60]},qc_defaults:{max_attempts:2},whisper_models:['tiny','base','small'],dimensions:[],reasons:[],youtube_enabled:true,max_upload_bytes:2**31,release:'DEMO'}
export default function App(){
  const [route,setRoute]=useState(read),[more,setMore]=useState(false),[schema,setSchema]=useState<Schema>(),[health,setHealth]=useState<Health|null>(null),s=useS()
  const [tab,query]=route.split('?'),current=NAV.some(n=>n[0]===tab)?tab:'painel'
  const [visited,setVisited]=useState([current])
  useEffect(()=>{const changed=()=>{setRoute(read());setMore(false);scrollTo(0,0);document.querySelectorAll('video').forEach(v=>v.pause())};addEventListener('hashchange',changed);return()=>removeEventListener('hashchange',changed)},[])
  useEffect(()=>{setVisited(names=>names.includes(current)?names:[...names,current])},[current])
  useEffect(()=>{
    let stopped=false,timeout:ReturnType<typeof setTimeout>
    const run=async()=>{await refresh();if(!DEMO)try{const h=await api<Health>('/doctor');if(!stopped)setHealth(h)}catch{if(!stopped)setHealth(null)};if(!stopped)timeout=setTimeout(run,12000)}
    void run();(DEMO?Promise.resolve(demoSchema):api<Schema>('/settings')).then(value=>{if(!stopped)setSchema(value)}).catch(()=>{})
    return()=>{stopped=true;clearTimeout(timeout)}
  },[])
  useEffect(()=>{const h=document.querySelector<HTMLElement>(`[data-module="${current}"] h1`);h?.setAttribute('tabindex','-1');if(!s.loading)h?.focus()},[current,visited,s.loading])
  const pending=s.jobs.filter(needsReview).length
  return <div className="sh"><a className="skip" href="#content" onClick={e=>{e.preventDefault();document.getElementById('content')?.focus()}}>Pular para o conteúdo</a><nav className="nv" aria-label="Módulos"><div className="br">Content Factory<small>Creator Clips · {s.release}</small></div>
    {NAV.map(([k,l,path],i)=><a key={k} className={i>3?'secondary':''} href={'#'+k} aria-current={current===k?'page':undefined}><svg viewBox="0 0 24 24" aria-hidden="true"><path d={path}/></svg><span>{l}</span>{k==='revisao'&&pending>0&&<em aria-label={pending+' jobs para revisar'}>{pending}</em>}</a>)}
    <button className="more-nav" aria-expanded={more} aria-controls="more-menu" onClick={()=>setMore(!more)}>•••<span>Mais</span></button><p className="nt">Uso privado: localhost, túnel SSH ou VPN.</p></nav>
    {more&&<div id="more-menu" className="more-menu">{NAV.slice(4).map(([k,l])=><a key={k} href={'#'+k} aria-current={current===k?'page':undefined}>{l}</a>)}<button className="b" onClick={()=>setMore(false)}>Fechar</button></div>}
    <div className="mn"><div className="top" role="status"><span><i className={'led '+(health?.worker.online?'ok':'er')}/>Worker {DEMO?'simulado':health?.worker.online?'online':'sem sinal'}</span><span>GPU {health?.kepler?.reachable?'online':'indisponível'}</span><span>Agenda {health?.agenda_online?'ativa':'sem sinal'}</span>{DEMO&&<strong className="demo-banner">MODO DEMONSTRAÇÃO — dados simulados, sem envio</strong>}</div>
      <main id="content" tabIndex={-1}>{s.error&&<div className="warn" role="alert">{s.error}<button className="b" onClick={()=>refresh()}>Tentar novamente</button></div>}{s.loading?<p role="status">Carregando Content Factory…</p>:visited.map(name=><div key={name} data-module={name} hidden={current!==name}>{name==='painel'?<Painel health={health}/>:name==='revisao'?<Review requested={current==='revisao'?new URLSearchParams(query).get('job')??undefined:undefined} requestedGroup={current==='revisao'?new URLSearchParams(query).get('group')??undefined:undefined}/>:name==='publicacao'?<Publish/>:name==='biblioteca'?<Library/>:name==='metricas'?<Metricas/>:schema?(name==='novo'?<Novo schema={schema}/>:<Settings schema={schema}/>):<p role="alert">Configurações indisponíveis. Atualize a página para tentar novamente.</p>}</div>)}</main>
    </div>{s.toast&&<div id="ts" className={s.toast.k} role="status">{s.toast.m}</div>}</div>
}
