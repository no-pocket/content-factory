import {afterEach,expect,it,vi} from 'vitest'
import {preferences} from './Settings'
import type {Schema} from './types'

afterEach(()=>vi.unstubAllGlobals())
it('preserves legacy protocol 1 preferences without implicitly selecting Hermes',()=>{
  vi.stubGlobal('localStorage',{getItem:()=>JSON.stringify({editorial_protocol:1})})
  const schema={defaults:{editorial_protocol:2,editorial_planner:'hermes_first'}} as unknown as Schema
  expect(preferences(schema).editorial_planner).toBe('local')
})
it('preserves an explicit planner choice',()=>{
  vi.stubGlobal('localStorage',{getItem:()=>JSON.stringify({editorial_protocol:2,editorial_planner:'local'})})
  const schema={defaults:{editorial_protocol:2,editorial_planner:'hermes_first'}} as unknown as Schema
  expect(preferences(schema).editorial_planner).toBe('local')
})
