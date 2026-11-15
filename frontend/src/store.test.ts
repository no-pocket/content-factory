import {it,expect,vi,afterEach} from 'vitest'
import {review,addJob,simulateExternal,DEMO} from './store'
afterEach(()=>vi.unstubAllGlobals())
it('review preserves the opened identity and request id on the HTTP boundary',async()=>{
  const calls:{url:string;body:unknown}[]=[]
  vi.stubGlobal('fetch',vi.fn(async(url:string,init:RequestInit)=>{
    calls.push({url,body:init?.body?JSON.parse(init.body as string):null})
    return new Response(JSON.stringify(url.endsWith('bootstrap')?{jobs:[],agenda:[],drafts:[],sources:[],assets:[],providers:{},release:'test'}:{}))
  }))
  const seen={artifact:'sha256:a',n:2,revision:4}
  const p={dec:'REJECTED' as const,comment:'Falha',reasons:[],adjust:'',rating:{},grade:0}
  await review('job','candidate',seen,p,'request-id')
  expect(calls[0]).toEqual({url:'/api/jobs/job/candidates/candidate/review',body:{seen,p,request_id:'request-id'}})
})
it('production refuses incomplete legacy calls and demo simulation',async()=>{
  expect(DEMO).toBe(false)
  await expect(addJob('a','b','c')).rejects.toThrow()
  await expect(simulateExternal()).rejects.toThrow('demonstração')
})
