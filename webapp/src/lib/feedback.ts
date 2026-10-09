// What the "Feedback" form sends besides the text: screenshots small enough to
// upload from a phone, and where the report was written.
import type { FeedbackKind, FeedbackStatus } from './types'

declare const __BUILD__: string

export const MAX_SHOTS = 3
export const MAX_MESSAGE = 4000
/** Longest side of an uploaded screenshot, px (text stays readable). */
export const MAX_SIDE = 1600

export const KIND_LABEL: Record<FeedbackKind, string> = { bug: 'Bug', suggestion: 'Suggestion' }
export const STATUS_LABEL: Record<FeedbackStatus, string> = { open: 'Open', done: 'Done', dismissed: 'Not planned' }

/** The size an image is drawn at: never enlarged, longest side <= `max`. */
export function fitWithin(width: number, height: number, max = MAX_SIDE): { width: number; height: number } {
  const scale = Math.min(1, max / Math.max(width, height))
  return { width: Math.max(1, Math.round(width * scale)), height: Math.max(1, Math.round(height * scale)) }
}

/** A picked or pasted image as a JPEG of at most MAX_SIDE px. Decoded with
 * createImageBitmap, not an <img>: the site's CSP has no `blob:` image source. */
export async function shrinkImage(file: Blob): Promise<Blob> {
  let bitmap: ImageBitmap
  try {
    bitmap = await createImageBitmap(file)
  } catch {
    throw new Error('That image could not be read. Try a JPEG or PNG screenshot.')
  }
  const { width, height } = fitWithin(bitmap.width, bitmap.height)
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const ctx = canvas.getContext('2d')!
  // a transparent PNG would turn black as a JPEG
  ctx.fillStyle = '#fff'
  ctx.fillRect(0, 0, width, height)
  ctx.drawImage(bitmap, 0, 0, width, height)
  bitmap.close()
  return new Promise((resolve, reject) => canvas.toBlob(
    (blob) => (blob ? resolve(blob) : reject(new Error('That image could not be read.'))), 'image/jpeg', 0.82))
}

export function blobDataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result))
    reader.onerror = () => reject(new Error('That image could not be read.'))
    reader.readAsDataURL(blob)
  })
}

/** Screen, browser and build of the reporter: what makes "it looks wrong" reproducible. */
export function pageContext(): Record<string, string> {
  return {
    viewport: `${window.innerWidth}x${window.innerHeight}`,
    pixel_ratio: String(window.devicePixelRatio),
    theme: window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light',
    language: navigator.language,
    user_agent: navigator.userAgent.slice(0, 300),
    build: typeof __BUILD__ === 'string' ? __BUILD__ : 'dev',
  }
}

export function reportDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
}
