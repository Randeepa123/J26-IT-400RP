export function value(n:number|null|undefined,digits=2){return n==null||!Number.isFinite(n)?'—':n.toLocaleString('en-GB',{minimumFractionDigits:digits,maximumFractionDigits:digits})}
export function friendly(text:string){return text.replaceAll('_',' ').replace(/\b\w/g,c=>c.toUpperCase())}
export function epoch(text:string){let iso=text.replace(' ','T');if(/^\d{4}-\d\d-\d\d$/.test(iso))iso+='T00:00:00';return Date.parse(/[zZ]$|[+-]\d\d:\d\d$/.test(iso)?iso:iso+'+05:30')}
export function date(text:string|null|undefined,withTime=false){if(!text||!Number.isFinite(epoch(text)))return 'Not available';return new Intl.DateTimeFormat('en-GB',{day:'2-digit',month:'short',year:'numeric',...(withTime?{hour:'2-digit',minute:'2-digit'}:{}),timeZone:'Asia/Colombo'}).format(epoch(text))}
export function axisDate(ms:number,hours=false){return new Intl.DateTimeFormat('en-GB',{...(hours?{hour:'2-digit',minute:'2-digit'}:{day:'2-digit',month:'short'}),timeZone:'Asia/Colombo'}).format(ms)}
