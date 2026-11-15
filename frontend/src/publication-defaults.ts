import type {Job,Cand,Prov} from './types'
export function publicationDefaults(job:Pick<Job,'name'|'who'>,c:Pick<Cand,'title'|'tx'|'captions'>,provider:Prov,titleLimit:number,captionLimit:number){
  const title=c.title?.trim()||job.name
  let quote=c.tx.trim().split(/(?<=[.!?])\s+/)[0]||job.name
  if(quote.length>350)quote=quote.slice(0,347).replace(/\s+\S*$/,'')+'…'
  const caption=c.captions?.[provider]?.text?.trim()||quote+(job.who?'\n\nFonte: '+job.who:'')
  return {title:Array.from(title).slice(0,titleLimit).join(''),caption:Array.from(caption).slice(0,captionLimit).join('')}
}
