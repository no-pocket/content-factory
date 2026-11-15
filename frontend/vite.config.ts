import {defineConfig} from 'vite'
import react from '@vitejs/plugin-react'
// Server-only: never use a VITE_ variable for credentials.
export default defineConfig({plugins:[react()],server:{
  host:'127.0.0.1',port:5173,strictPort:true,
  proxy:{'/api':{target:process.env.CONTENT_FACTORY_WEB_API ?? 'http://127.0.0.1:8000',
    headers:{'X-Content-Factory-Web-Token':process.env.CONTENT_FACTORY_WEB_TOKEN ?? ''}}}
}})
