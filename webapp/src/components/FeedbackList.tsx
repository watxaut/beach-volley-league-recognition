import { Link } from 'react-router-dom'
import { KIND_LABEL, reportDate, STATUS_LABEL } from '../lib/feedback'
import type { Feedback } from '../lib/types'

export function FeedbackStatusBadge({ status }: { status: Feedback['status'] }) {
  return <span className={`badge badge-fb-${status}`}>{STATUS_LABEL[status]}</span>
}

/** Screenshots of a report as thumbnails that open full size in a new tab. */
export function Shots({ paths, urls }: { paths: string[]; urls: Record<string, string> }) {
  if (!paths.length) return null
  return (
    <ul className="shots">
      {paths.map((p, i) => (
        <li key={p}>
          {urls[p]
            ? <a href={urls[p]} target="_blank" rel="noreferrer"><img src={urls[p]} alt={`Screenshot ${i + 1}`} loading="lazy" /></a>
            : <span className="muted small">Screenshot {i + 1} unavailable</span>}
        </li>
      ))}
    </ul>
  )
}

/** The head line of a report: kind, status, date, the page it came from. */
export function ReportHead({ report, author }: { report: Feedback; author?: string }) {
  return (
    <div className="report-head">
      <strong>{KIND_LABEL[report.kind]}</strong>
      <FeedbackStatusBadge status={report.status} />
      <span className="muted small">
        {reportDate(report.created_at)}
        {author && <> · {author}</>}
        {report.page && <> · <Link to={report.page}>{report.page}</Link></>}
      </span>
    </div>
  )
}
