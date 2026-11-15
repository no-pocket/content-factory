import {it,expect,vi,afterEach} from 'vitest'
import {newRequestId} from './request-id'
afterEach(()=>vi.unstubAllGlobals())
it('produces canonical v4 UUIDs on HTTP without crypto.randomUUID',()=>{
  vi.stubGlobal('crypto',{getRandomValues:(bytes:Uint8Array)=>{bytes.fill(0);return bytes}})
  expect(newRequestId()).toBe('00000000-0000-4000-8000-000000000000')
})
it('keeps CSPRNG uniqueness when only getRandomValues is available',()=>{
  const original=globalThis.crypto
  vi.stubGlobal('crypto',{getRandomValues:original.getRandomValues.bind(original)})
  const first=newRequestId(),second=newRequestId()
  expect(first).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/)
  expect(first).not.toBe(second)
})
