# Beach League web app

Static React SPA (Vite + TypeScript + supabase-js). Everything sensitive is
enforced in the database (row-level security + security-definer functions in
`../supabase/migrations`); the browser only holds the publishable key.

```bash
npm install
npm run dev                 # http://127.0.0.1:5173 -- demo data unless .env.local is set
VITE_DEMO=1 npm run dev     # force the synthetic demo league
npm test                    # vitest
npx tsc -b && npx oxlint    # typecheck + lint
npm run build               # -> dist/ (what Cloudflare Workers serves)
```

To develop against your Supabase project, copy `.env.example` to `.env.local`
and fill in `VITE_SUPABASE_URL` and `VITE_SUPABASE_PUBLISHABLE_KEY`.

Layout: `src/lib/api.ts` is the only module that talks to Supabase (the `Api`
interface; `src/lib/demo.ts` implements it with fixtures), `src/pages/` one
file per route, `src/pages/admin/` the admin screens, `src/styles.css` the
design tokens (light/dark). Deployment: `../docs/deploy_web_platform.md`.
