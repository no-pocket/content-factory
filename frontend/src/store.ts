import {newRequestId} from './request-id'
import {useState,useSyncExternalStore} from 'react'
import {api,jobForm} from './client'
import type {S,Seen,Payload,Source,Draft,JobOptions,AssetOptions,ScheduleRow,Prov,Provider} from './types'
export {api,post,Conflict} from './client'
export type {Payload} from './types'
export const DEMO=import.meta.env.VITE_DEMO==='true'
export const STAGES=['QUEUED','DOWNLOADING','TRANSCRIBING','DIRECTING','RENDERING']
const providers=Object.fromEntries(['instagram','facebook','youtube','tiktok'].map(p=>[p,{state:'NOT_CONFIGURED',can_schedule:false,worker_online:false,title_limit:255,caption_limit:2200}])) as Record<Prov,Provider>
let st:S={jobs:[],agenda:[],drafts:[],sources:[],assets:[],providers,destinations:[],release:'—',toast:null,loading:true,error:null}
const subs=new Set<()=>void>()
const update=(data:Partial<S>)=>{st={...st,...data};subs.forEach(f=>f())}
export const useS=()=>useSyncExternalStore(f=>{subs.add(f);return()=>{subs.delete(f)}},()=>st)
let toastTimer:ReturnType<typeof setTimeout>
export const toast=(m:string,k:'ok'|'er'='ok')=>{clearTimeout(toastTimer);update({toast:{m,k}});toastTimer=setTimeout(()=>update({toast:null}),5500)}
let demo:typeof import('./demo')|undefined
async function demonstration(){if(!DEMO)throw new Error('Disponível somente em modo demonstração.');return demo??=await import('./demo')}
export async function refresh(){
  try{const data=DEMO?(await demonstration()).read():await api<Partial<S>>('/bootstrap');update({...data,loading:false,error:null})}
  catch(error){update({loading:false,error:message(error)})}
}
export const message=(error:unknown)=>error instanceof Error?error.message:'Não foi possível concluir.'
async function mutate(path:string,body:unknown,method='POST'){
  const result=await api(path,{method,body:JSON.stringify(body)});await refresh();return result
}
export async function review(jid:string,cid:string,seen:Seen,p:Payload,requestId:string=newRequestId()){
  if(DEMO){(await demonstration()).review(jid,cid,seen,p);await refresh();return}
  await mutate(`/jobs/${encodeURIComponent(jid)}/candidates/${encodeURIComponent(cid)}/review`,{seen,p,request_id:requestId})
}
export async function schedule(rows:ScheduleRow[],immediate:boolean){
  if(DEMO)(await demonstration()).schedule(rows,immediate);else await mutate('/publications/schedule',{rows,immediate})
  if(DEMO)await refresh()
}
export async function reschedule(id:string,at:number){
  if(DEMO)(await demonstration()).reschedule(id,at);else await mutate(`/publications/${id}/reschedule`,{at})
  if(DEMO)await refresh()
}
export async function cancel(id:string){
  if(DEMO)(await demonstration()).cancel(id);else await mutate(`/publications/${id}/cancel`,{})
  if(DEMO)await refresh()
}
export async function saveDraft(d:Omit<Draft,'id'|'at'>){
  if(DEMO)(await demonstration()).saveDraft(d);else await mutate('/publications/drafts',d)
  if(DEMO)await refresh()
}
export async function saveSource(r:Source,expectedRev:number){
  if(DEMO)(await demonstration()).saveSource(r,expectedRev);else await mutate('/sources/'+r.id,{r,expectedRev},'PUT')
  if(DEMO)await refresh()
}
export async function addJob(name:string,who:string,lic:string,options?:JobOptions){
  if(DEMO){(await demonstration()).addJob(name,who,lic);await refresh();return}
  const body=jobForm(name,who,lic,options)
  const job=await api<{id:string;duplicate?:boolean}>('/jobs',{method:'POST',body});await refresh();return job
}
export async function addAsset(d:string,options?:AssetOptions){
  if(DEMO){(await demonstration()).addAsset(d);await refresh();return}
  if(!options?.file||!options.rights_confirmed||!options.license_note.trim())throw new Error('Arquivo, licença e direitos obrigatórios.')
  const {file,...metadata}=options,form=new FormData();form.set('metadata',JSON.stringify({...metadata,description:d}));form.set('file',file)
  await api('/assets',{method:'POST',body:form});await refresh()
}
export async function simulateExternal(){(await demonstration()).simulateExternal();await refresh()}
export async function action(path:string,body:unknown={}){if(DEMO)throw new Error('Ação real indisponível na demonstração.');return mutate(path,body)}
export function media(jid:string,cid:string,kind:string,artifact:string|null,download=false){return `/api/jobs/${jid}/candidates/${cid}/media/${kind}?artifact=${encodeURIComponent(artifact??'')}${download?'&download=true':''}`}
// Session-only drafts survive navigation/reloads; bound to the opened artifact.
export function useDraft<T>(key:string,initial:()=>T):[T,(value:T)=>void,()=>void]{
  const read=()=>{try{const raw=sessionStorage.getItem('cf:'+key);return raw?JSON.parse(raw) as T:initial()}catch{return initial()}}
  const [value,set]=useState<T>(read)
  const save=(v:T)=>{set(v);try{sessionStorage.setItem('cf:'+key,JSON.stringify(v))}catch{/* In-memory draft remains usable. */}}
  const clear=()=>{try{sessionStorage.removeItem('cf:'+key)}catch{/* Optional browser persistence. */}}
  return [value,save,clear]
}
