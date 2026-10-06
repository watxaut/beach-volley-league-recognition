// The login form's "email me a code" endpoint (docs/web_platform_design.md §6,
// migration 20261007140000_login_broker.sql).
//
// It gives ONE answer for every address: 200 {"ok": true}, whether the address
// is an invited player, a stranger, or over its rate limit. So it cannot be
// used to test who is in the league. Whether a mail really goes out is decided
// by login_code_gate() in the database; the request to Supabase Auth carries
// the service key, which is what lets it through the CAPTCHA lock that closes
// Auth's own public endpoints (deploy guide, step 2.9).
//
// Public by design (config.toml: verify_jwt = false). No dependencies.

const SUPABASE_URL = Deno.env.get('SUPABASE_URL') ?? ''
// The platform injects SUPABASE_SERVICE_ROLE_KEY; LOGIN_BROKER_SERVICE_KEY
// (`supabase secrets set`) overrides it, e.g. with a dedicated secret key.
const SERVICE_KEY = Deno.env.get('LOGIN_BROKER_SERVICE_KEY') ?? Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? ''
// Tests only: point the code request at another Auth instance.
const AUTH_URL = Deno.env.get('LOGIN_BROKER_AUTH_URL') ?? `${SUPABASE_URL}/auth/v1`

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}
const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/

declare const EdgeRuntime: { waitUntil?: (p: Promise<unknown>) => void } | undefined

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { ...CORS, 'Content-Type': 'application/json' } })
}

function service(path: string, body: unknown, base = SUPABASE_URL): Promise<Response> {
  return fetch(base + path, {
    method: 'POST',
    headers: { apikey: SERVICE_KEY, Authorization: `Bearer ${SERVICE_KEY}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') return new Response('ok', { headers: CORS })
  if (req.method !== 'POST') return json({ error: 'method not allowed' }, 405)

  let email = ''
  try {
    email = String((await req.json())?.email ?? '').trim().toLowerCase()
  } catch {
    // not JSON: refused below like any other malformed address
  }
  // Format only: this says nothing about who is a member.
  if (email.length > 254 || !EMAIL.test(email)) return json({ error: 'not an email address' }, 400)

  const ip = (req.headers.get('x-forwarded-for') ?? '').split(',')[0].trim() || 'unknown'
  let forward = false
  try {
    if (!SUPABASE_URL || !SERVICE_KEY) throw new Error('SUPABASE_URL / service key missing from the function environment')
    const gate = await service('/rest/v1/rpc/login_code_gate', { p_email: email, p_ip: ip })
    if (!gate.ok) throw new Error(`login_code_gate -> HTTP ${gate.status}: ${(await gate.text()).slice(0, 200)}`)
    forward = (await gate.json()) === true
  } catch (err) {
    // The database is down or the migration is missing: the same for everyone.
    console.error(String(err))
    return json({ error: 'login is temporarily unavailable' }, 503)
  }

  if (forward) {
    // Answer first and send after: the response time must not tell whether a
    // mail goes out. Failures are only logged (never shown to the caller).
    const send = service('/otp', { email, create_user: false }, AUTH_URL)
      .then(async (r) => {
        if (!r.ok) console.error(`auth /otp -> HTTP ${r.status}: ${(await r.text()).slice(0, 200)}`)
      })
      .catch((err) => console.error(`auth /otp failed: ${err}`))
    // Keeps the worker alive until the mail request is done (where the
    // runtime offers it; elsewhere the promise simply runs on).
    if (typeof EdgeRuntime !== 'undefined' && typeof EdgeRuntime.waitUntil === 'function') EdgeRuntime.waitUntil(send)
  }
  return json({ ok: true })
})
