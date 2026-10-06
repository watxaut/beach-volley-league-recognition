import { useState, type FormEvent } from 'react'
import { useApp } from '../app/state'
import { ErrorBox } from '../components/ui'
import { explainError } from '../lib/api'

// The code's length is a Supabase setting (6-10 digits; docs/deploy_web_platform.md
// step 2.4), so the form takes any of them instead of pinning one.
const CODE_MIN = 6
const CODE_MAX = 10

/** Invite-only, password-less: we email a login code (and a link that
 * logs in on the same device). Unknown emails are refused by Supabase
 * because sign-ups are off. */
export function Login() {
  const { api, demo } = useApp()
  const [email, setEmail] = useState(demo ? 'ari@example.com' : '')
  const [code, setCode] = useState('')
  const [sent, setSent] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function send(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await api.sendCode(email.trim().toLowerCase())
      setSent(true)
    } catch (err) {
      setError(explainError(err))
    } finally {
      setBusy(false)
    }
  }

  async function verify(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await api.verifyCode(email.trim().toLowerCase(), code.trim())
    } catch (err) {
      setError(explainError(err))
      setBusy(false)
    }
  }

  return (
    <div className="login">
      <div className="brand"><span className="brand-dot" aria-hidden />Beach League</div>
      <section className="card">
        {!sent ? (
          <form onSubmit={send}>
            <h1>Log in</h1>
            <p className="muted">Enter the email your invite was sent to. We'll email you a login code.</p>
            <label className="field">
              <span>Email</span>
              <input type="email" required autoComplete="email" value={email}
                     onChange={(e) => setEmail(e.target.value)} style={{ width: '100%' }} />
            </label>
            <ErrorBox error={error} />
            <button className="primary" disabled={busy || !email} style={{ width: '100%' }}>
              {busy ? 'Sending…' : 'Email me a code'}
            </button>
          </form>
        ) : (
          <form onSubmit={verify}>
            <h1>Check your email</h1>
            <p className="muted">
              If <strong>{email}</strong> has been invited, a login code is on its way. Type it below, or
              tap the link in the email on this device.
            </p>
            <label className="field">
              <span>Code</span>
              <input className="code-input" inputMode="numeric" autoComplete="one-time-code" maxLength={CODE_MAX}
                     value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))} autoFocus />
            </label>
            <ErrorBox error={error} />
            <div className="row">
              <button className="primary" disabled={busy || code.length < CODE_MIN}>{busy ? 'Checking…' : 'Log in'}</button>
              <button type="button" className="link" onClick={() => { setSent(false); setCode('') }}>
                Use another email
              </button>
            </div>
            <p className="muted small" style={{ marginBottom: 0 }}>
              Nothing after a minute? Check the address, or ask a league admin to invite you.
            </p>
          </form>
        )}
      </section>
      <p className="muted small">No account? The league is invite-only — ask an admin.</p>
    </div>
  )
}
