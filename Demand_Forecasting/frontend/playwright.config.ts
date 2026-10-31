import { defineConfig } from '@playwright/test'
export default defineConfig({
  testDir:'./e2e',fullyParallel:false,workers:1,timeout:90000,
  use:{baseURL:'http://127.0.0.1:5173',headless:true,viewport:{width:1440,height:1080},
    channel:process.env.PLAYWRIGHT_BROWSER_CHANNEL||(process.platform==='win32'?'chrome':undefined),
    screenshot:'only-on-failure',trace:'retain-on-failure'},
})
