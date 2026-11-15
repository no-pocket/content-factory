export class Conflict extends Error{}
export async function api<T>(path:string,options:RequestInit={}):Promise<T>{
  const response=await fetch('/api'+path,{...options,headers:{...(options.body instanceof FormData?{}:{'Content-Type':'application/json'}),...options.headers}})
  if(!response.ok){let message='Serviço indisponível. Tente novamente.'
    try{const data=await response.json();if(typeof data.error==='string')message=data.error}catch{/* Keep a safe message for proxy errors. */}
    throw response.status===409?new Conflict(message):new Error(message)
  }
  return response.json() as Promise<T>
}
export const post=<T>(path:string,body:unknown)=>api<T>(path,{method:'POST',body:JSON.stringify(body)})
export function jobForm(name:string,who:string,lic:string,options?:import('./types').JobOptions){
  if(!options||(!options.file&&!options.source_url)||!options.rights_confirmed||!who.trim()||!lic.trim())throw new Error('Informe vídeo, criador, autorização e confirmação de direitos.')
  if(options.source_url&&!options.platform_permission)throw new Error('Confirme a autorização da plataforma.')
  const {file,...metadata}=options
  const body={...metadata,creator:who,license_note:lic}
  if(!file)return JSON.stringify(body)
  const form=new FormData();form.set('metadata',JSON.stringify(body));form.set('file',file,name);return form
}
