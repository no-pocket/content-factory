import {it,expect} from 'vitest'
import {canScheduleCandidate} from './review-state'
it('only offers scheduling for a current approved v2 artifact with valid QC',()=>{
  const job={protocol:2}, candidate={dec:'APPROVED',intact:true,qc:'VALID',artifact:'sha256:abc'}
  expect(canScheduleCandidate(job,candidate)).toBe(true)
  expect(canScheduleCandidate(job,{...candidate,qc:'WARNING'})).toBe(true)
  for (const change of [{dec:'PENDING'},{dec:'APPROVED_WITH_ADJUSTMENTS'},{intact:false},{qc:'FAILED'},{artifact:null}])
    expect(canScheduleCandidate(job,{...candidate,...change})).toBe(false)
  expect(canScheduleCandidate({protocol:1},candidate)).toBe(false)
})
