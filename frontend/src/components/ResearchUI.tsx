import type { ReactNode } from 'react'
import { AlertTriangle, ArrowDownToLine, ArrowUpRight, Inbox, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { download } from '@/lib/api'
import { friendly } from '@/lib/format'

export function Panel({title,eyebrow,description,actions,children,className=''}:{title:string;eyebrow?:string;description?:string;actions?:ReactNode;children:ReactNode;className?:string}){
  return <Card className={'panel '+className}><CardHeader className="panel-heading"><div>{eyebrow&&<p className="eyebrow">{eyebrow}</p>}<CardTitle className="panel-title"><h2>{title}</h2></CardTitle>{description&&<p className="panel-description">{description}</p>}</div>{actions&&<div className="panel-actions">{actions}</div>}</CardHeader><CardContent className="panel-content">{children}</CardContent></Card>
}
export function Empty({title='No observations in this selection',description='Choose a different date range or include another regime.'}:{title?:string;description?:string}){return <div className="empty-state"><span><Inbox size={23}/></span><h3>{title}</h3><p>{description}</p></div>}
export function ErrorNotice({error,retry}:{error:unknown;retry?:()=>void}){return <div className="error-notice" role="alert"><AlertTriangle size={18}/><div><strong>Unable to load this view</strong><p>{error instanceof Error?error.message:'The backend could not complete the request.'}</p></div>{retry&&<Button variant="outline" size="sm" onClick={retry}><RefreshCw size={14}/> Retry</Button>}</div>}
export function ChartSkeleton({height=320}:{height?:number}){return <div className="chart-skeleton" style={{height}} role="status" aria-label="Loading research data"><Skeleton className="h-4 w-32"/><div className="skeleton-grid">{[0,1,2,3].map(n=><Skeleton key={n} className="h-px w-full"/>)}</div><Skeleton className="h-3 w-48"/></div>}
export function LoadingCards(){return <div className="kpi-grid">{[0,1,2,3].map(n=><Card key={n} className="kpi"><Skeleton className="h-4 w-24"/><Skeleton className="mt-6 h-9 w-28"/><Skeleton className="mt-3 h-3 w-36"/></Card>)}</div>}
export function StatusBadge({type}:{type:string}){return <Badge variant="outline" className={'status-badge status-'+type}>{['recovered','confirmed'].includes(type)&&<span className="status-dot"/>}{friendly(type)}</Badge>}
export function ExportButton({rows,name,label='Export CSV'}:{rows:unknown[];name:string;label?:string}){return <Button variant="outline" size="sm" disabled={!rows.length} onClick={()=>download(rows,name)}><ArrowDownToLine size={14}/>{label}</Button>}
export function Legend({actual=false,model='both'}:{actual?:boolean;model?:'both'|'static'|'adapted'}){return <div className="chart-legend">{actual&&<span><i style={{background:'#343e35'}}/>Observed</span>}{model!=='static'&&<span><i style={{background:'#2d654b'}}/>Adapted model</span>}{model!=='adapted'&&<span><i style={{background:'#a7ba8b'}}/>Static baseline</span>}</div>}
export function InlineLink({children,onClick}:{children:ReactNode;onClick:()=>void}){return <button className="inline-link" onClick={onClick}>{children}<ArrowUpRight size={14}/></button>}
