import { useEffect, useRef } from 'react'
import * as echarts from 'echarts/core'
import { LineChart, BarChart, PieChart, ScatterChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, MarkLineComponent, AriaComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { EChartsOption } from 'echarts'
import type { Drift, Forecast, Metric, Recovery, SeriesRow } from '@/lib/types'
import { axisDate, date, epoch, friendly, value } from '@/lib/format'

echarts.use([LineChart,BarChart,PieChart,ScatterChart,GridComponent,TooltipComponent,LegendComponent,DataZoomComponent,MarkLineComponent,AriaComponent,CanvasRenderer])
export const palette={forest:'#2d654b',sage:'#a7ba8b',charcoal:'#343e35',amber:'#bc8c42',muted:'#a6ada0'}
const escape=(s:string)=>s.replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;')
interface TooltipRow {seriesName:string;color:string;value:[number,number|null];axisValue:number}
export function timeTooltip(params:unknown){const rows=(Array.isArray(params)?params:[params]) as TooltipRow[];return `<div class="chart-tooltip"><strong>${escape(date(new Date(rows[0].axisValue).toISOString(),true))}</strong>${rows.map(r=>`<div><span style="color:${escape(r.color)}">●</span> ${escape(r.seriesName)}<b>${value(r.value[1])}</b></div>`).join('')}<small>Asia/Colombo</small></div>`}
export function Chart({option,label,height=320}:{option:EChartsOption;label:string;height?:number}){
  const ref=useRef<HTMLDivElement>(null)
  const instance=useRef<echarts.ECharts|null>(null)
  useEffect(()=>{if(!ref.current)return;const chart=echarts.init(ref.current,undefined,{renderer:'canvas'});instance.current=chart;const resize=new ResizeObserver(()=>chart.resize());resize.observe(ref.current);return()=>{resize.disconnect();chart.dispose();instance.current=null}},[])
  useEffect(()=>{instance.current?.setOption({...option,animation:!window.matchMedia('(prefers-reduced-motion: reduce)').matches,animationDuration:450,animationDurationUpdate:250,aria:{enabled:true,label:{description:label}}},true)},[option,label])
  return <div ref={ref} role="img" aria-label={label} className="echart" style={{height,width:'100%',minWidth:0}}/>
}
const base:EChartsOption={textStyle:{fontFamily:'Inter, Segoe UI, sans-serif',fontSize:11,color:'#7c8577'},grid:{top:24,left:54,right:24,bottom:52},tooltip:{trigger:'axis',backgroundColor:'#fff',borderColor:'#e4e9df',padding:14,extraCssText:'border-radius:12px;box-shadow:0 8px 32px #1b3c2512;',formatter:timeTooltip,axisPointer:{type:'line',lineStyle:{color:'#b9c7ac',type:'dashed'}}},xAxis:{type:'time',axisLine:{show:false},axisTick:{show:false},axisLabel:{hideOverlap:true,color:'#92998c',margin:16,formatter:(n:number)=>axisDate(n)}},yAxis:{type:'value',name:'MW',nameTextStyle:{align:'right',padding:[0,12,0,0]},axisLabel:{color:'#92998c'},splitLine:{lineStyle:{color:'#edf0e9',type:'dashed'}}}}
const line=(name:string,color:string,data:[number,number|null][],area=false)=>({name,type:'line' as const,data,showSymbol:false,symbolSize:5,smooth:false,lineStyle:{width:2,color},itemStyle:{color},emphasis:{focus:'series' as const},areaStyle:area?{color:new echarts.graphic.LinearGradient(0,0,0,1,[{offset:0,color:'#dae6caba'},{offset:1,color:'#f8faf500'}])}:undefined})
export function forecastOption(forecast:Forecast,model:'both'|'static'|'adapted'):EChartsOption{
  const rows=forecast.data
  return {...base,xAxis:{...(base.xAxis as object),axisLabel:{hideOverlap:true,formatter:(n:number)=>axisDate(n,forecast.horizon_hours===24)}},legend:{show:false},series:[...(model!=='static'?[line('Adapted · MW',palette.forest,rows.map(r=>[epoch(r.timestamp),r.adapted_generation_mw]),true)]:[]),...(model!=='adapted'?[line('Static baseline · MW',palette.sage,rows.map(r=>[epoch(r.timestamp),r.static_generation_mw]))]:[])],dataZoom:[{type:'inside',filterMode:'none',zoomOnMouseWheel:'ctrl',moveOnMouseMove:true},{type:'slider',height:15,bottom:0,borderColor:'transparent',fillerColor:'#dce6ce77',handleStyle:{color:'#a5b795'},backgroundColor:'#f4f6ef',showDetail:false}]}
}
export function historyOption(rows:SeriesRow[],events:Drift[],rolling=false):EChartsOption{
  const markers=events.map(event=>({xAxis:epoch(event.drift_date),name:friendly(event.drift_type),label:{show:false}}))
  const multiYear=rows.length>1&&epoch(rows[rows.length-1].timestamp)-epoch(rows[0].timestamp)>365*86400000
  return {...base,xAxis:{...(base.xAxis as object),axisLabel:{hideOverlap:true,formatter:(ms:number)=>multiYear?new Intl.DateTimeFormat('en-GB',{month:'short',year:'numeric',timeZone:'Asia/Colombo'}).format(ms):axisDate(ms)}},yAxis:{...(base.yAxis as object),name:rolling?'%':'MW'},series:[
    ...(!rolling?[line('Observed · MW',palette.charcoal,rows.map(r=>[epoch(r.timestamp),r.actual_generation_mw]))]:[]),
    {...line(rolling?'Adapted MAPE · %':'Adapted · MW',palette.forest,rows.map(r=>[epoch(r.timestamp),rolling?r.adapted_rolling_mape:r.adapted]),!rolling),markLine:{symbol:'none',silent:true,lineStyle:{color:'#c5a269',width:1,type:'dashed'},data:markers}},
    line(rolling?'Static MAPE · %':'Static baseline · MW',palette.sage,rows.map(r=>[epoch(r.timestamp),rolling?r.static_rolling_mape:r.static])),
  ],dataZoom:[{type:'inside',filterMode:'none',zoomOnMouseWheel:'ctrl'}]}
}
export function regimeOption(rows:Metric[],metric:'mape'|'rmse'='mape'):EChartsOption{
  const key=metric==='mape'?'mape':'rmse_mw'
  return {textStyle:base.textStyle,grid:{top:22,right:16,bottom:42,left:48},tooltip:{trigger:'axis',axisPointer:{type:'shadow'},valueFormatter:(v)=>value(typeof v==='number'?v:null)+(metric==='mape'?'%':' MW')},legend:{show:false},xAxis:{type:'category',data:rows.map(r=>friendly(r.regime).replace('Adjustment','Adj.')),axisLine:{show:false},axisTick:{show:false},axisLabel:{fontSize:10,interval:0,width:75,overflow:'break'}},yAxis:{type:'value',name:metric==='mape'?'MAPE (%)':'RMSE (MW)',splitLine:{lineStyle:{color:'#edf0e9',type:'dashed'}}},series:[{name:'Static baseline',type:'bar',data:rows.map(r=>r[('static_'+key) as keyof Metric] as number|null),barWidth:19,itemStyle:{color:palette.sage,borderRadius:[4,4,0,0]}},{name:'Cause-matched adapted',type:'bar',data:rows.map(r=>r[('adapted_'+key) as keyof Metric] as number|null),barWidth:19,itemStyle:{color:palette.forest,borderRadius:[4,4,0,0]}}]}
}
export function classificationOption(events:Drift[]):EChartsOption{
  return {tooltip:{trigger:'item',formatter:'{b}: {c} detections'},series:[{type:'pie',radius:['70%','86%'],center:['50%','50%'],label:{show:false},emphasis:{scaleSize:3},padAngle:3,itemStyle:{borderRadius:3},data:['gradual','abrupt','structural','unclassified','incremental'].map((name,i)=>({name:friendly(name),value:events.filter(e=>e.drift_type===name).length,itemStyle:{color:[palette.forest,palette.sage,palette.amber,'#d4d7cb','#8fa597'][i]}}))}]}
}
export function recoveryOption(rows:Recovery[]):EChartsOption{
  return {textStyle:base.textStyle,grid:{top:20,right:24,bottom:40,left:50},tooltip:{trigger:'axis',valueFormatter:v=>value(typeof v==='number'?v:null)+' days'},xAxis:{type:'category',data:rows.map(r=>date(r.drift_date)),axisLabel:{fontSize:10,rotate:20},axisTick:{show:false},axisLine:{show:false}},yAxis:{type:'value',name:'Days',splitLine:{lineStyle:{color:'#edf0e9',type:'dashed'}}},series:[{name:'Sustained recovery lag',type:'bar',barMaxWidth:38,data:rows.map(r=>r.lag_days),itemStyle:{color:palette.forest,borderRadius:[5,5,0,0]}}]}
}
