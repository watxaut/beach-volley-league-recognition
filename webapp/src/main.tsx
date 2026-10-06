import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { App } from './App'
import { AppProvider } from './app/context'
import { supabaseApi } from './lib/api'
import { demoApi } from './lib/demo'
import './styles.css'

// VITE_SUPABASE_URL + VITE_SUPABASE_PUBLISHABLE_KEY (the publishable/anon key:
// public by design, every table is protected by RLS). VITE_DEMO=1 -- or a
// local `npm run dev` without them -- runs on synthetic in-memory data. A
// PRODUCTION build without them refuses to start rather than show a fake
// league on the real URL.
const url = import.meta.env.VITE_SUPABASE_URL as string | undefined
const key = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY as string | undefined
const configured = Boolean(url && key)
const demo = import.meta.env.VITE_DEMO === '1' || (!configured && import.meta.env.DEV)
const root = createRoot(document.getElementById('root')!)

if (!demo && !configured) {
  root.render(
    <main className="login">
      <h1>Site not configured</h1>
      <p className="muted">
        VITE_SUPABASE_URL and VITE_SUPABASE_PUBLISHABLE_KEY are missing from this build. Set them in
        the hosting settings and redeploy (docs/deploy_web_platform.md, step 4).
      </p>
    </main>,
  )
} else {
  root.render(
    <StrictMode>
      <AppProvider api={demo ? demoApi() : supabaseApi(url!, key!)} demo={demo}>
        <App />
      </AppProvider>
    </StrictMode>,
  )
}
