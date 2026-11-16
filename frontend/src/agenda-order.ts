export function agendaForMonth<T extends {at:number}>(items:T[], month:string, dateKey:(at:number)=>string):T[]{
  return items.filter(item=>dateKey(item.at).startsWith(month)).sort((a,b)=>b.at-a.at)
}
