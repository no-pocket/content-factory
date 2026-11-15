export const DIMS={relevance:'Relevância',hook:'Gancho',context:'Contexto',narrative:'Desenvolvimento',proof:'Prova',closure:'Fechamento',framing:'Enquadramento',captions:'Legendas',editing:'Edição',technical_quality:'Qualidade técnica'} as const
export type Dim=keyof typeof DIMS
export type Dec='PENDING'|'APPROVED'|'APPROVED_WITH_ADJUSTMENTS'|'REJECTED'|'UNCONFIRMED_LEGACY'
export const REASONS:Record<string,string>={IRRELEVANT_CONTENT:'Conteúdo irrelevante',CREATOR_SELF_PROMOTION:'Autopromoção',WEAK_HOOK:'Gancho fraco',MISSING_CONTEXT:'Falta de contexto',INCOMPLETE_PAYOFF:'Sem conclusão',ABRUPT_ENDING:'Final abrupto',MISSING_DEMONSTRATION:'Falta de demonstração',BAD_FRAMING:'Enquadramento ruim',IMPORTANT_CONTENT_CROPPED:'Conteúdo importante cortado',CAPTION_ERROR:'Erro de legenda',GOOD_CONTENT_NEEDS_REWORK:'Requer retrabalho',TECHNICAL_FAILURE:'Falha técnica'}
export interface Ev{at:number;dec:string;comment:string;by:string}
export interface Cand{id:string;output_seconds?:number;pace?:{rate:number;words_per_minute:number|null;reason?:string};word_timing?:{zero_duration_words_grouped:number};title?:string;s:number;e:number;heu:number|null;w:number|null;qc:string;ai:string;tx:string;artifact:string|null;intact:boolean;revision:number;candidate_version:number|null;render_revision:number|null;model:string;dec:Dec;hist:Ev[];rating:Partial<Record<Dim,number|null>>;grade:number|null;edits:unknown[];director:string;renderer:string;attempts:number;diagnostic:unknown;story:unknown;assembly:unknown;captions:Record<string,{text:string;origin:string;reason?:string}>|null}
export type Stage='QUEUED'|'DOWNLOADING'|'TRANSCRIBING'|'DIRECTING'|'RENDERING'
export type Settings=Record<string,string|number|boolean|null|unknown[]|Record<string,number>>
export interface Job{id:string;auto_rework_enabled?:boolean;parent_id?:string|null;reworks?:{child_id:string;state:string;error:string|null;review_revision:number}[];name:string;who:string;st:Stage|'NEEDS_REVIEW'|'APPROVED'|'REJECTED'|'PARTIAL_FAILED'|'FAILED'|'QUEUE_FAILED';lang:string;eng:string;dur:number|null;lic:string;created:number;cands:Cand[];settings:Settings;qc_settings:Record<string,number>;protocol:number;review_status:string;error:string|null;events:unknown[];activity:unknown}
export type Prov='instagram'|'facebook'|'youtube'|'tiktok'
export interface Item{id:string;at:number;pv:Prov;st:string;t:string;job_id:string;candidate_id:string;artifact:string;caption?:string;timezone?:string;error?:string|null;remote_id?:string|null;permalink?:string|null}
export interface Draft{id:string;pv:Prov;cand:string;job_id:string;artifact:string;title:string;desc:string;at:number}
export interface Source{id:string;name:string;status:'pending'|'active'|'disabled';ref:string;rights:boolean;platform:boolean;langs:string;kinds:string[];scopes:string[];rev:number}
export interface Asset{id:string;d:string;t:string;duration:number;license:string}
export interface Provider{state:string;can_schedule:boolean;worker_online:boolean;title_limit:number;caption_limit:number}
export interface Destination{id:string;pv:Prov;page_id:string;instagram_id:string|null;label:string}
export interface S{jobs:Job[];agenda:Item[];drafts:Draft[];sources:Source[];assets:Asset[];providers:Record<Prov,Provider>;destinations:Destination[];release:string;toast:{m:string;k:'ok'|'er'}|null;loading:boolean;error:string|null}
export interface Schema{defaults:Settings;ranges:Record<string,[number,number]>;qc_defaults:Record<string,number>;whisper_models:string[];dimensions:string[];reasons:string[];youtube_enabled:boolean;max_upload_bytes:number;release:string}
export interface Seen{artifact:string|null;n:number;revision:number}
export interface Payload{dec:Dec;comment:string;reasons:string[];adjust:string;rating:Cand['rating'];grade:number|null}
export interface JobOptions{file?:File;source_url?:string;video_title?:string;rights_confirmed:boolean;platform_permission:boolean;settings:Settings;qc_settings?:Record<string,number>;assembly_plan?:unknown}
export interface AssetOptions{file:File;license_note:string;rights_confirmed:boolean}
export interface ScheduleRow{pv:Prov;t:string;at:number;job_id?:string;candidate_id?:string;artifact?:string;page_id?:string;instagram_id?:string;caption?:string}
