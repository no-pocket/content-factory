import {useEffect,useState} from 'react'
import type {ReactNode} from 'react'
export const Z='America/Sao_Paulo'
export const tc=(x:number)=>`${String(Math.floor(x/60)).padStart(2,'0')}:${(x%60).toFixed(1).padStart(4,'0')}`
export const useNow=(ms=1000)=>{const [n,set]=useState(Date.now());useEffect(()=>{const t=setInterval(()=>set(Date.now()),ms);return()=>clearInterval(t)},[ms]);return n}
export const fmt=(t:number,o:Intl.DateTimeFormatOptions={day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'})=>new Intl.DateTimeFormat('pt-BR',{timeZone:Z,...o}).format(t)
export const ymd=(t:number)=>new Intl.DateTimeFormat('en-CA',{timeZone:Z}).format(t)
export const hm=(t:number)=>fmt(t,{hour:'2-digit',minute:'2-digit',hourCycle:'h23'})
export const toTs=(d:string,t:string)=>Date.parse(`${d}T${t}:00-03:00`)
export const DEC:Record<string,[string,string]>={PENDING:['Pendente','n'],APPROVED:['Aprovado','ok'],APPROVED_WITH_ADJUSTMENTS:['Aprovado com ajustes','wr'],REJECTED:['Recusado','er'],UNCONFIRMED_LEGACY:['Legado não confirmado','wr']}
export const Tag=({k='n',children}:{k?:string;children:ReactNode})=><span className={'tag '+k}>{children}</span>
export function Seg<T extends string|number|null>({v,o,on}:{v:T;o:[T,string][];on:(x:T)=>void}){
 return <div className="seg" role="group">{o.map(([x,l])=><button type="button" key={String(x)} aria-pressed={x===v} onClick={()=>on(x)}>{l}</button>)}</div>}
export const Field=({l,children}:{l:string;children:ReactNode})=><label className="fl"><span>{l}</span>{children}</label>
export const Head=({t,s,children}:{t:string;s:string;children?:ReactNode})=><header className="hd"><div><h1>{t}</h1><p>{s}</p></div>{children}</header>
export const Meter=({l,v,max,note}:{l:string;v:number;max:number;note?:string})=>
 <div className="mt"><div><span>{l}</span><b>{note??`${v} de ${max}`}</b></div><div className="bar"><i style={{width:Math.min(100,v/max*100)+'%'}}/></div></div>
