import {expect,it} from 'vitest'
import {agendaForMonth} from './agenda-order'
it('shows only the selected month, newest scheduled first, without changing the source',()=>{
  const items=[{at:2},{at:4},{at:1},{at:3}]
  const dates:Record<number,string>={1:'2026-11-01',2:'2026-11-02',3:'2026-10-03',4:'2026-11-04'}
  expect(agendaForMonth(items,'2026-11',at=>dates[at]).map(item=>item.at)).toEqual([4,2,1])
  expect(items.map(item=>item.at)).toEqual([2,4,1,3])
})
