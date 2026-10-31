import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig(({mode})=>{
  const localSettings=loadEnv(mode,process.cwd(),'')
  const apiTarget=process.env.API_PROXY_TARGET||localSettings.API_PROXY_TARGET||'http://127.0.0.1:8000'
  return {
  plugins: [react(), tailwindcss()],
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  build: {rollupOptions:{output:{manualChunks(id){if(id.includes('/node_modules/zrender/'))return 'chart-renderer';if(id.includes('/node_modules/echarts/'))return 'chart-engine';if(id.includes('/node_modules/')&&/react|radix|tanstack/.test(id))return 'interface'}}}},
  server: { port: 5173, strictPort:true, proxy: { '/api': { target:apiTarget, changeOrigin: true, rewrite: path => path.replace(/^\/api/, '') } } },
  preview: { port: 5173, strictPort:true, proxy: { '/api': { target:apiTarget, changeOrigin: true, rewrite: path => path.replace(/^\/api/, '') } } },
  }
})
