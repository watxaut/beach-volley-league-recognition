import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The commit a deploy was built from (Cloudflare sets it), sent with a feedback report.
const build = (process.env.WORKERS_CI_COMMIT_SHA ?? process.env.CF_PAGES_COMMIT_SHA ?? 'dev').slice(0, 7)

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  define: { __BUILD__: JSON.stringify(build) },
  server: { port: 5173, host: '127.0.0.1' },
})
