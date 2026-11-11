import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // 固定监听 IPv4 回环地址与端口，与 dev_start.py 打印的地址一致。
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    // 同源代理：浏览器只访问 5173，/api 开头的请求去掉前缀后转发给后端。
    // 前端路由也有 /candidate、/employer 等路径，统一加 /api 前缀才不会和页面路由冲突。
    // 会话 Cookie 因此是同源 Cookie，后端无需 CORS 即可工作。
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
