import {expect,it} from 'vitest'
import {newSourceDefaults} from './source-defaults'
it('starts new channels active with local and Hermes scopes, without inventing confirmations',()=>{
  const source=newSourceDefaults()
  expect(source.status).toBe('active')
  expect(source.scopes).toEqual(['local','external'])
  expect(source.kinds).toEqual(['video','short','live_archive'])
  expect(source.rights).toBe(false)
  expect(source.platform).toBe(false)
})
