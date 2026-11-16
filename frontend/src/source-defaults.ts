import type {Source} from './types'
export function newSourceDefaults():Source {
  return {id:'',name:'',status:'active',ref:'',rights:false,platform:false,langs:'pt',kinds:['video','short','live_archive'],scopes:['local','external'],rev:0}
}
