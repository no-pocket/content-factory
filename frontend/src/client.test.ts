import {describe,it,expect,vi,afterEach} from 'vitest'
import {api,Conflict,jobForm} from './client'
afterEach(()=>vi.unstubAllGlobals())
describe('real store boundary',()=>{
  it('maps HTTP 409 to Conflict without discarding the caller payload',async()=>{
    vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({error:'Render mudou'}),{status:409})))
    await expect(api('/jobs/test')).rejects.toBeInstanceOf(Conflict)
  })
  it('never falls back to simulated state on network failure',async()=>{
    vi.stubGlobal('fetch',vi.fn(async()=>{throw new Error('offline')}))
    await expect(api('/bootstrap')).rejects.toThrow('offline')
  })
  it('requires explicit rights and a source for production jobs',()=>{
    expect(()=>jobForm('a.mp4','test','grant')).toThrow()
    expect(()=>jobForm('a.mp4','test','grant',{rights_confirmed:false,platform_permission:true,source_url:'url',settings:{}})).toThrow()
  })
  it('sends independent settings snapshot and platform attestation',()=>{
    const settings={whisper_model:'tiny'}
    const data=jobForm('a','test','grant',{rights_confirmed:true,platform_permission:true,source_url:'url',settings})
    settings.whisper_model='base'
    expect(JSON.parse(data as string).settings.whisper_model).toBe('tiny')
    expect(JSON.parse(data as string).platform_permission).toBe(true)
  })
})
