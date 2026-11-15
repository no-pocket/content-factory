import {it,expect} from 'vitest'
import {syncReviewDraft,visibleReviewJobs,wasPublished} from './review-state'
it('keeps the review payload while synchronizing the current version',()=>{
 const draft={seen:{artifact:'old',n:1,revision:1},p:{comment:'manter'},requestId:'old'}
 expect(syncReviewDraft(draft,{artifact:'new',n:2,revision:3},'new')).toEqual({seen:{artifact:'new',n:2,revision:3},p:{comment:'manter'},requestId:'new'})
})
it('keeps the open job in view when it leaves the pending filter',()=>{
 expect(visibleReviewJobs([{id:'a'},{id:'b'}],[{id:'b'}],'a').map(j=>j.id)).toEqual(['a','b'])
})
it('recognizes only confirmed publications of the same candidate',()=>{
 const rows=[{job_id:'j',candidate_id:'c',st:'SCHEDULED'},{job_id:'j',candidate_id:'other',st:'PUBLISHED'}]
 expect(wasPublished(rows,'j','c')).toBe(false)
 expect(wasPublished([...rows,{job_id:'j',candidate_id:'c',st:'PUBLISHED'}],'j','c')).toBe(true)
})
