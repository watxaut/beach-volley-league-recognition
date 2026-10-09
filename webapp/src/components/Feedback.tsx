import { useEffect, useRef, useState, type ClipboardEvent, type FormEvent } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useApp } from '../app/state'
import { explainError } from '../lib/api'
import { blobDataUrl, KIND_LABEL, MAX_MESSAGE, MAX_SHOTS, pageContext, shrinkImage } from '../lib/feedback'
import type { FeedbackKind } from '../lib/types'
import { ErrorBox, Segmented } from './ui'

interface Shot {
  blob: Blob
  preview: string
}

const PROMPT: Record<FeedbackKind, string> = {
  bug: 'What happened, and what did you expect?',
  suggestion: 'What would make this better?',
}

/** The top-bar button and its form: a bug or a suggestion, with screenshots. */
export function FeedbackButton() {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button type="button" className="feedback-open" onClick={() => setOpen(true)}>Feedback</button>
      {open && <FeedbackDialog onClose={() => setOpen(false)} />}
    </>
  )
}

function FeedbackDialog({ onClose }: { onClose: () => void }) {
  const { api, session, demo } = useApp()
  const location = useLocation()
  const page = location.pathname + location.search
  const dialog = useRef<HTMLDialogElement>(null)
  const picker = useRef<HTMLInputElement>(null)
  const [kind, setKind] = useState<FeedbackKind>('bug')
  const [message, setMessage] = useState('')
  const [shots, setShots] = useState<Shot[]>([])
  const [busy, setBusy] = useState(false)
  const [sent, setSent] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const d = dialog.current
    if (d && !d.open) d.showModal()
  }, [])

  async function addImages(files: File[]) {
    const images = files.filter((f) => f.type.startsWith('image/'))
    if (!images.length) return
    setError(null)
    const room = MAX_SHOTS - shots.length
    if (images.length > room) setError(`Up to ${MAX_SHOTS} screenshots per report.`)
    try {
      const added: Shot[] = []
      for (const file of images.slice(0, Math.max(0, room))) {
        const blob = await shrinkImage(file)
        added.push({ blob, preview: await blobDataUrl(blob) })
      }
      setShots((s) => [...s, ...added].slice(0, MAX_SHOTS))
    } catch (err) {
      setError(explainError(err))
    }
  }

  function onPaste(e: ClipboardEvent) {
    const files = [...e.clipboardData.files]
    if (!files.some((f) => f.type.startsWith('image/'))) return
    e.preventDefault()
    void addImages(files)
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!session || !message.trim()) return
    setBusy(true)
    setError(null)
    try {
      await api.sendFeedback(session.userId, {
        kind, message: message.trim(), page, context: pageContext(), images: shots.map((s) => s.blob) })
      setSent(true)
    } catch (err) {
      setError(explainError(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <dialog ref={dialog} className="feedback" aria-labelledby="feedback-title" onClose={onClose} onPaste={onPaste}>
      {sent ? (
        <>
          <h2 id="feedback-title">Sent, thank you</h2>
          <p>
            {demo ? 'Demo mode: the report stays in this tab only. ' : ''}
            You can follow it under <Link to="/settings" onClick={onClose}>Settings</Link>.
          </p>
          <div className="feedback-actions">
            <button type="button" className="primary" onClick={onClose}>Close</button>
          </div>
        </>
      ) : (
        <form onSubmit={submit}>
          <h2 id="feedback-title">Send feedback</h2>
          <Segmented label="Kind of report" value={kind} onChange={setKind}
                     options={[{ key: 'bug', label: KIND_LABEL.bug }, { key: 'suggestion', label: KIND_LABEL.suggestion }]} />
          <label className="feedback-field">
            <span>{PROMPT[kind]}</span>
            <textarea value={message} onChange={(e) => setMessage(e.target.value)} rows={5} required
                      maxLength={MAX_MESSAGE} autoFocus />
          </label>
          {shots.length > 0 && (
            <ul className="shots">
              {shots.map((s, i) => (
                <li key={s.preview.slice(-32) + i}>
                  <img src={s.preview} alt={`Screenshot ${i + 1}`} />
                  <button type="button" className="link" disabled={busy}
                          onClick={() => setShots((all) => all.filter((_, j) => j !== i))}>Remove</button>
                </li>
              ))}
            </ul>
          )}
          <input ref={picker} type="file" accept="image/*" multiple hidden
                 onChange={(e) => {
                   void addImages([...(e.target.files ?? [])])
                   e.target.value = ''
                 }} />
          {shots.length < MAX_SHOTS && (
            <button type="button" className="feedback-add" disabled={busy} onClick={() => picker.current?.click()}>
              Add a screenshot
            </button>
          )}
          <p className="muted small">
            Up to {MAX_SHOTS} screenshots; on a computer you can also paste one. Sent with it: the page you
            are on (<code>{page}</code>), your screen size and browser.
          </p>
          <ErrorBox error={error} />
          <div className="feedback-actions">
            <button type="button" onClick={onClose} disabled={busy}>Cancel</button>
            <button type="submit" className="primary" disabled={busy || !message.trim()}>
              {busy ? 'Sending…' : 'Send'}
            </button>
          </div>
        </form>
      )}
    </dialog>
  )
}
