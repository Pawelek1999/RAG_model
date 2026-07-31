import type { ApiStatus } from '../types'

/**
 * Props for the top header section.
 */
type HeaderProps = {
  /** Current backend connectivity status shown to the user. */
  apiStatus: ApiStatus
}

/**
 * Displays application title and backend status indicator.
 */
export function Header({ apiStatus }: HeaderProps) {
  return (
    <header className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold">RAG API</h1>
          <p className="mt-1 text-sm text-slate-600">
            Made by: PAWELEK Jakub
          </p>
        </div>
        <span className={`text-sm font-bold ${statusColor(apiStatus)}`}>
          API: {apiStatus}
        </span>
      </div>
    </header>
  )
}

/**
 * Maps API status values to semantic text color classes.
 */
function statusColor(status: ApiStatus) {
  if (status === 'online') {
    return 'text-emerald-700'
  }

  if (status === 'offline') {
    return 'text-rose-700'
  }

  return 'text-amber-700'
}
