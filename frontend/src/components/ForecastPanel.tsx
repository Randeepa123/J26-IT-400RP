import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ArrowUpRight, Clock3, Info, Leaf } from 'lucide-react'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { request, download } from '@/lib/api'
import type { Forecast } from '@/lib/types'
import { date, value } from '@/lib/format'
import { Chart, forecastOption } from './Chart'
import { ChartSkeleton, ErrorNotice, Legend, Panel } from './ResearchUI'

export default function ForecastPanel(){
  const [hours,setHours]=useState<24|168>(24)
  const [model,setModel]=useState<'both'|'static'|'adapted'>('both')
  const [origin,setOrigin]=useState('now')
  const query=useQuery({queryKey:['forecast',hours,origin],queryFn:({signal})=>request<Forecast>('/forecast',new URLSearchParams({horizon_hours:String(hours),origin}),signal)})
  const result=query.data
  const average=result?result.data.reduce((sum,r)=>sum+r.adapted_generation_mw,0)/result.count:null
  const peak=result?Math.max(...result.data.map(r=>r.adapted_generation_mw)):null
  function exportForecast(){if(!result)return;download(result.data.map(row=>({timestamp:row.timestamp,static_generation_mw:row.static_generation_mw,adapted_generation_mw:row.adapted_generation_mw,...Object.fromEntries(Object.entries(row.assumed_features).map(([k,v])=>['assumed_'+k,v])),forecast_origin:result.forecast_origin,data_as_of:result.data_as_of,feature_method:result.feature_method})),'pucsl-forecast-'+hours+'h.csv')}
  return <Panel title="Generation forecast" eyebrow="LOOKING AHEAD" className="forecast-panel" actions={<div className="segmented" role="group" aria-label="Forecast horizon"><button aria-pressed={hours===24} onClick={()=>setHours(24)}>Next 24 hours</button><button aria-pressed={hours===168} onClick={()=>setHours(168)}>Next 7 days</button></div>}>
    <div className="forecast-topline"><div className="forecast-number">{query.isPending?<span className="loading-text">Loading forecast…</span>:<><span>{value(average,0)}</span><small>MW</small><Badge variant="secondary"><Leaf size={12}/>Adapted mean</Badge></>}</div><div className="forecast-context"><Clock3 size={14}/>{result?`${date(result.start,true)} – ${date(result.end,true)}`:'Asia/Colombo · 15-minute intervals'}</div></div>
    <div className="chart-controls"><Legend model={model}/><div className="chart-selects"><select aria-label="Forecast origin" value={origin} onChange={e=>setOrigin(e.target.value)}><option value="now">From now</option><option value="dataset_end">From data end</option></select><select aria-label="Forecast models" value={model} onChange={e=>setModel(e.target.value as typeof model)}><option value="both">Compare models</option><option value="adapted">Adapted model</option><option value="static">Static baseline</option></select></div></div>
    {query.error?<ErrorNotice error={query.error} retry={()=>void query.refetch()}/>:result?<Chart option={forecastOption(result,model)} label={`${hours}-hour electricity generation forecast in MW. ${result.count} intervals. Adapted mean ${value(average)} MW.`} height={340}/>:<ChartSkeleton height={340}/>}
    {result&&<><div className="forecast-footer"><div><span className="mini-label">PEAK ADAPTED</span><strong>{value(peak,0)} <small>MW</small></strong></div><div><span className="mini-label">RESOLUTION</span><strong>15 <small>minutes</small></strong></div><div><span className="mini-label">MODEL STRATEGY</span><strong className="strategy-text">{result.adapted_strategy}</strong></div><Button variant="ghost" size="sm" onClick={exportForecast}>Export forecast<ArrowUpRight size={14}/></Button></div>
    {result.warnings.map((warning,i)=><div key={i} className="subtle-warning"><Info size={14}/><span>{warning}</span></div>)}
    <div className="forecast-disclosure"><span>Conditional forecast · recent-history weather & solar estimates</span><Dialog><DialogTrigger asChild><button className="inline-link">View assumptions<Info size={13}/></button></DialogTrigger><DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-2xl"><DialogHeader><DialogTitle>What this forecast assumes</DialogTitle><DialogDescription>Real model inference, with explicit estimates for unavailable future inputs.</DialogDescription></DialogHeader><div className="assumptions-list">{result.assumptions.map(a=><p key={a}>{a}</p>)}<p><strong>Last observed data:</strong> {date(result.data_as_of,true)}</p><p><strong>Input method:</strong> {result.feature_method}</p></div><div className="table-scroll"><table><thead><tr><th>Time</th>{Object.keys(result.data[0]?.assumed_features||{}).map(k=><th key={k}>{k}</th>)}</tr></thead><tbody>{result.data.slice(0,12).map(row=><tr key={row.timestamp}><td>{date(row.timestamp,true)}</td>{Object.values(row.assumed_features).map((v,i)=><td key={i}>{value(v)}</td>)}</tr>)}</tbody></table></div><p className="footnote">First 12 intervals shown. Export includes every interval and its assumed inputs. Forecast-horizon accuracy and uncertainty have not been validated.</p></DialogContent></Dialog></div></>}
  </Panel>
}
