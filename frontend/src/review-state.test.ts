import {it,expect} from 'vitest'
import {canReviewJob,needsReview,publicationKey} from './review-state'
it('only idle jobs enter review even when an earlier candidate is already VALID',()=>{
  expect(canReviewJob('RENDERING')).toBe(false)
  expect(needsReview({st:'RENDERING',cands:[{dec:'PENDING'}]})).toBe(false)
  expect(needsReview({st:'NEEDS_REVIEW',cands:[{dec:'PENDING'}]})).toBe(true)
  expect(canReviewJob('FAILED')).toBe(true)
})
it('publication selection is invalidated when the approved artifact changes',()=>{
  expect(publicationKey('j','c','render-A')).not.toBe(publicationKey('j','c','render-B'))
})
