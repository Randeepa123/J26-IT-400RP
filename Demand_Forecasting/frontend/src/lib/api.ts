import type { Filters } from './types'
const BASE=(import.meta.env.VITE_API_URL || '/api').replace(/\/$/,'')
export class ApiError extends Error {constructor(message:string,public status:number){super(message)}}
export async function request<T>(path:string,params?:URLSearchParams,signal?:AbortSignal,body?:unknown):Promise<T>{
  const timeout=AbortSignal.timeout(60000)
  const response=await fetch(`${BASE}${path}${params?.size?'?'+params:''}`,{signal:signal?AbortSignal.any([signal,timeout]):timeout,method:body?'POST':'GET',headers:body?{'Content-Type':'application/json'}:undefined,body:body?JSON.stringify(body):undefined})
  let value
  try{value=await response.json()}catch{throw new ApiError(response.status===499?'Local web protection blocked this API request. Check your security software’s report.':'The API returned an unreadable response. Check that FastAPI is running and the /api proxy is configured.',response.status)}
  if(!response.ok) throw new ApiError(value.error?.message || value.warnings?.join(' ') || `Request failed (${response.status})`,response.status)
  return value as T
}
export function filterParams(f:Filters){const p=new URLSearchParams();if(f.start)p.set('start_date',f.start);if(f.end)p.set('end_date',f.end);for(const r of f.regimes)p.append('regimes',r);return p}
export function eventParams(f:Filters){const p=filterParams(f);if(f.classification!=='all')p.set('drift_type',f.classification);if(f.match!=='all')p.set('match_status',f.match);return p}
export function csvText(rows:Record<string,unknown>[]){
  if(!rows.length)return ''
  const columns=Array.from(new Set(rows.flatMap(row=>Object.keys(row))))
  const escape=(value:unknown)=>{let s=value===null||value===undefined?'':typeof value==='object'?JSON.stringify(value):String(value);if(/^[=+@\-]/.test(s)&&typeof value!=='number')s="'"+s;return '"'+s.replaceAll('"','""')+'"'}
  return [columns.map(escape).join(','),...rows.map(row=>columns.map(col=>escape(row[col])).join(','))].join('\r\n')
}
export function download(rows:unknown[],name:string){const blob=new Blob(['\uFEFF'+csvText(rows as Record<string,unknown>[])],{type:'text/csv;charset=utf-8;'});const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download=name;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
export async function exportPredictions(filters:Filters,signal?:AbortSignal){
  const rows:unknown[]=[];let offset=0
  while(true){const p=filterParams(filters);p.set('model_type',filters.model);p.set('limit','50000');p.set('offset',String(offset));const page=await request<{data:unknown[];count:number;total:number}>('/predict',p,signal);rows.push(...page.data);offset+=page.count;if(offset>=page.total||page.count===0)break}
  download(rows,`pucsl-${filters.model}-predictions.csv`)
}
