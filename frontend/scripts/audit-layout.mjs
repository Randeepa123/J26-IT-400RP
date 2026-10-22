import { chromium } from '@playwright/test'
const browser=await chromium.launch({headless:true,channel:process.env.PLAYWRIGHT_BROWSER_CHANNEL||(process.platform==='win32'?'chrome':undefined)})
const page=await browser.newPage({viewport:{width:1280,height:720},reducedMotion:'reduce'})
const findings=[]
for(const width of [320,600,1024,1280]){
 await page.setViewportSize({width,height:720})
 for(const route of ['/','/forecasts','/drifts','/models','/recovery','/simulation','/methodology']){
  await page.goto('http://127.0.0.1:5173'+route,{waitUntil:'networkidle'})
  const issues=await page.evaluate(()=>{
   const problems=[]
   if(document.documentElement.scrollWidth>innerWidth+1)problems.push('page overflow '+document.documentElement.scrollWidth+' > '+innerWidth)
   for(const parent of document.querySelectorAll('.panel-heading,.research-toolbar,.chart-controls,.page-heading,.topbar,.forecast-footer,.form-field,.classification-card')){
    const pr=parent.getBoundingClientRect()
    for(const child of parent.children){
     const r=child.getBoundingClientRect()
     if(r.width&&r.right>pr.right+2)problems.push(parent.className.split(' ')[0]+' child clipped right: '+(r.right-pr.right).toFixed(0)+'px')
    }
   }
   const sidebar=document.querySelector('.sidebar')
   if(sidebar&&sidebar.getBoundingClientRect().left>=0){const last=sidebar.querySelector('.sidebar-status');if(last&&last.getBoundingClientRect().bottom>innerHeight+2)problems.push('sidebar content below viewport')}
   return [...new Set(problems)]
  })
  if(issues.length){findings.push({width,route,issues});console.log(JSON.stringify({width,route,issues}));await page.screenshot({path:`test-results/layout-${width}-${route.slice(1)||'overview'}.png`,fullPage:true})}
 }
}
console.log('LAYOUT FINDINGS',JSON.stringify(findings))
await browser.close()
