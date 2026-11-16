export const canReviewJob=(state:string)=>['NEEDS_REVIEW','PARTIAL_FAILED','FAILED','APPROVED','REJECTED','EDITORIAL_NO_CANDIDATES'].includes(state)
export const needsReview=(job:{st:string;cands:{dec:string}[]})=>job.st==='EDITORIAL_NO_CANDIDATES'||(canReviewJob(job.st)&&job.cands.some(c=>c.dec==='PENDING'))
export const publicationKey=(job:string,candidate:string,artifact:string|null)=>[job,candidate,artifact].join(':')

export function syncReviewDraft<T extends {seen:unknown;requestId:string}>(draft:T,seen:T['seen'],requestId:string):T{return {...draft,seen,requestId}}
export function visibleReviewJobs<T extends {id:string}>(all:T[],filtered:T[],selected:string):T[]{const open=all.find(j=>j.id===selected);return open&&!filtered.some(j=>j.id===selected)?[open,...filtered]:filtered}
export function wasPublished(rows:{job_id:string;candidate_id:string;st:string}[],job:string,candidate:string){return rows.some(r=>r.job_id===job&&r.candidate_id===candidate&&r.st==='PUBLISHED')}
