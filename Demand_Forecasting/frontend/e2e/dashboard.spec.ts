import { test, expect } from '@playwright/test'

test.beforeEach(async({page})=>{page.on('pageerror',error=>console.error('Browser error:',error.message))})

test('real API overview, both horizons and full forecast export',async({page})=>{
 const errors:string[]=[];page.on('pageerror',error=>errors.push(error.message))
 await page.goto('/')
 await expect(page.getByRole('heading',{name:'Your grid, in perspective.'})).toBeVisible()
 await expect(page.getByRole('img',{name:/24-hour electricity generation forecast/})).toBeVisible({timeout:60000})
 await expect(page.locator('.kpi-value').first()).not.toHaveText('—')
 await page.screenshot({path:'test-results/dashboard-desktop.png',fullPage:true})
 const forecast=page.waitForResponse(r=>r.url().includes('/api/forecast?')&&r.url().includes('168'))
 await page.getByRole('button',{name:'Next 7 days',exact:true}).click()
 expect((await (await forecast).json()).count).toBe(672)
 await expect(page.getByRole('img',{name:/168-hour electricity generation forecast/})).toBeVisible()
 const download=page.waitForEvent('download');await page.getByRole('button',{name:'Export forecast',exact:true}).click()
 expect((await download).suggestedFilename()).toContain('168h.csv')
 expect(errors).toEqual([])
})

test('navigation connects to real drift, comparison, recovery and simulation APIs',async({page})=>{
 await page.goto('/drifts')
 await expect(page.getByRole('heading',{name:'Detected drift events',exact:true})).toBeVisible()
 await expect(page.locator('tbody tr').first()).toBeVisible({timeout:60000})
 await page.getByRole('button',{name:'Structural',exact:true}).click()
 await expect(page.getByRole('heading',{name:'No drift events match this selection'})).toBeVisible()
 await page.getByRole('button',{name:'All classifications',exact:true}).click()
 await page.getByRole('link',{name:'Model performance',exact:true}).click()
 await expect(page.getByRole('heading',{name:'Regime evaluation results'})).toBeVisible()
 await expect(page.locator('tbody tr')).toHaveCount(4)
 await page.getByRole('link',{name:'Adaptation recovery',exact:true}).click()
 await expect(page.getByRole('heading',{name:'Recovery evidence'})).toBeVisible()
 await expect(page.locator('tbody tr')).toHaveCount(7)
 await page.getByRole('link',{name:'Prediction simulation',exact:true}).click()
 await expect(page.getByRole('button',{name:/Run prediction simulation/})).toBeEnabled()
 await page.getByRole('button',{name:/Run prediction simulation/}).click()
 await expect(page.locator('.result-adapted strong')).toBeVisible({timeout:60000})
 await expect(page.locator('.error-notice')).toHaveCount(0)
})

test('filters, empty state, accessible assumptions and reduced motion',async({page})=>{
 await page.emulateMedia({reducedMotion:'reduce'})
 await page.goto('/')
 await expect(page.getByRole('button',{name:'View assumptions'})).toBeVisible({timeout:60000})
 await page.getByRole('button',{name:'View assumptions'}).click()
 await expect(page.getByRole('dialog')).toBeVisible()
 await expect(page.getByRole('heading',{name:'What this forecast assumes'})).toBeVisible()
 await page.keyboard.press('Escape')
 await page.getByRole('button',{name:/Filters/}).click()
 for(const checkbox of await page.locator('.regime-checkboxes input').all())await checkbox.uncheck()
 await expect(page.getByText(/Select at least one regime in Filters/)).toBeVisible()
 await expect(page.getByRole('img',{name:/24-hour electricity generation forecast/})).toBeVisible()
 await page.getByRole('button',{name:'Reset filters',exact:true}).click()
 await expect(page.locator('.regime-checkboxes input:checked')).toHaveCount(4)
})

test('tablet and mobile layouts avoid horizontal overflow and expose navigation',async({page})=>{
 for(const width of [1024,768,390]){
  await page.setViewportSize({width,height:950});await page.goto('/')
  await expect(page.getByRole('img',{name:/24-hour electricity generation forecast/})).toBeVisible({timeout:60000})
  await expect(page.locator('.kpi-value').first()).toBeVisible()
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth+1)).toBe(true)
  if(width===390){
   await page.screenshot({path:'test-results/dashboard-mobile.png',fullPage:true})
   await page.getByRole('button',{name:'Open navigation'}).click()
   await page.getByRole('link',{name:'Generation forecast',exact:true}).click()
   await expect(page.getByRole('heading',{name:'See what comes next.'})).toBeVisible()
   expect(await page.evaluate(()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth+1)).toBe(true)
  }
 }
})
