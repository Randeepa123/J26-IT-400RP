import { test, expect } from '@playwright/test'

const screens=[{width:1366,height:768},{width:1280,height:720},{width:1093,height:614},{width:1024,height:576},{width:911,height:512},{width:320,height:568}]
for(const viewport of screens)test(`all views fit ${viewport.width}x${viewport.height}`,async({page})=>{
 await page.emulateMedia({reducedMotion:'reduce'})
 const routes=['/','/forecasts','/drifts','/models','/recovery','/simulation','/methodology']
  await page.setViewportSize(viewport)
  await page.goto('/',{waitUntil:'networkidle'})
  for(const route of routes){
   if(route!=='/'){
    const menu=page.getByRole('button',{name:'Open navigation'})
    if(await menu.isVisible())await menu.click()
    await page.locator(`.sidebar .nav-item[href="${route}"]`).click()
    await expect(page).toHaveURL(route)
   }
   await expect(page.locator('main h1')).toBeInViewport()
   await expect(page.locator('.chart-skeleton')).toHaveCount(0)
   const issues=await page.evaluate(()=>{
    const result:string[]=[]
    if(document.documentElement.scrollWidth>innerWidth+1)result.push('horizontal page overflow')
    for(const panel of document.querySelectorAll('.panel'))if(panel.scrollHeight>panel.clientHeight+2)result.push('card clips vertical content')
    for(const parent of document.querySelectorAll('.panel-heading,.research-toolbar,.chart-controls,.page-heading,.topbar,.forecast-footer,.form-field,.classification-card')){
     const bounds=parent.getBoundingClientRect()
     for(const child of parent.children){const rect=child.getBoundingClientRect();if(rect.width&&rect.right>bounds.right+2)result.push(parent.className.split(' ')[0]+' clips controls')}
    }
    return result
   })
   expect(issues,`${viewport.width}×${viewport.height} ${route}`).toEqual([])
   const menu=page.getByRole('button',{name:'Open navigation'})
   if(await menu.isVisible())await menu.click()
   const status=page.locator('.sidebar-status')
   await status.scrollIntoViewIfNeeded()
   const bounds=await status.boundingBox()
   expect(bounds!.y+bounds!.height,`Sidebar status reachable at ${viewport.width}×${viewport.height}`).toBeLessThanOrEqual(viewport.height+1)
   if(await menu.isVisible())await page.locator('.close-sidebar').click()
   if(viewport.width===1280&&route==='/')await page.screenshot({path:'test-results/laptop-1280.png',fullPage:true})
   // Navigation should reset a previous view's scroll position.
   await page.evaluate(()=>window.scrollTo(0,document.body.scrollHeight))
  }
})
