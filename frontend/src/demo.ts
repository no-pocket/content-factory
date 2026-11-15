import {newRequestId} from './request-id'
// Loaded only by explicit VITE_DEMO=true builds. No HTTP or production writes.
import type {S,Job,Cand,Seen,Payload,Source,Draft,ScheduleRow,Prov,Provider} from './types'
import {Conflict} from './client'
const candidate=(id:string):Cand=>({id,s:12,e:42,heu:12,w:90,qc:'VALID',ai:'Demonstração de uma história completa.',tx:'Transcrição simulada. Este modo não contém mídia real.',artifact:'demo-render-1',intact:true,revision:0,candidate_version:1,render_revision:1,model:'Qwen (demo)',dec:'PENDING',hist:[],rating:{},grade:null,edits:[],director:'demo',renderer:'demo',attempts:1,diagnostic:null,story:null,assembly:null,captions:null})
const job=(id:string,name:string,who:string,lic:string):Job=>({id,name,who,lic,st:'NEEDS_REVIEW',lang:'pt',eng:'Simulado',dur:180,created:Date.now(),cands:[candidate(id+'-c1'),candidate(id+'-c2')],settings:{},qc_settings:{max_attempts:2},protocol:2,review_status:'PENDING',error:null,events:[],activity:null})
const providers=Object.fromEntries(['instagram','facebook','youtube','tiktok'].map(p=>[p,{state:'DEMO',can_schedule:true,worker_online:false,title_limit:255,caption_limit:2200}])) as Record<Prov,Provider>
const state:S={jobs:[job('demo-job','Vídeo autorizado de demonstração','Canal de exemplo','Autorização fictícia — não usar em produção')],sources:[],assets:[],agenda:[],drafts:[],providers,destinations:[],release:'DEMO',toast:null,loading:false,error:null}
export const read=()=>structuredClone(state)
export function review(jid:string,cid:string,seen:Seen,p:Payload){
  const j=state.jobs.find(j=>j.id===jid)!,c=j.cands.find(c=>c.id===cid)!
  if(c.artifact!==seen.artifact||c.hist.length!==seen.n||c.revision!==seen.revision)throw new Conflict('O render ou histórico mudou. Confira a versão atual; rascunho preservado.')
  c.dec=p.dec;c.grade=p.grade;c.rating=p.rating;c.hist.push({at:Date.now(),dec:p.dec,comment:p.comment,by:'você (demo)'});c.revision++
  j.review_status=j.cands.every(c=>c.dec!=='PENDING')?'COMPLETED':'PARTIAL'
}
let flip=0
export function simulateExternal(){const c=state.jobs.flatMap(j=>j.cands).find(c=>c.dec==='PENDING');if(!c)return
  if(flip++%2===0)c.artifact='demo-render-'+newRequestId();else{c.hist.push({at:Date.now(),dec:'PENDING',comment:'Alteração externa simulada',by:'Telegram (demo)'});c.revision++}}
export function addJob(name:string,who:string,lic:string){state.jobs.unshift(job(newRequestId(),name,who,lic))}
export function addAsset(d:string){state.assets.push({id:newRequestId(),d,duration:48,t:'48 s',license:'Licença fictícia'})}
export function saveSource(r:Source,expected:number){const old=state.sources.find(s=>s.id===r.id);if((old?.rev??0)!==expected)throw new Conflict('Cadastro alterado');state.sources=state.sources.filter(s=>s.id!==r.id);state.sources.push({...r,rev:expected+1})}
export function saveDraft(d:Omit<Draft,'id'|'at'>){state.drafts.unshift({...d,id:newRequestId(),at:Date.now()})}
export function schedule(rows:ScheduleRow[],immediate:boolean){for(const r of rows)state.agenda.push({...r,id:newRequestId(),st:immediate?'PUBLISHING':'SCHEDULED',job_id:r.job_id??'demo-job',candidate_id:r.candidate_id??'demo',artifact:r.artifact??'demo'})}
export function reschedule(id:string,at:number){const it=state.agenda.find(i=>i.id===id);if(!it||it.st!=='SCHEDULED'||at<=Date.now())throw new Error('Envio iniciado ou horário inválido');it.at=at}
export function cancel(id:string){const it=state.agenda.find(i=>i.id===id);if(!it||it.st!=='SCHEDULED')throw new Error('O envio já começou');it.st='CANCELLED'}
