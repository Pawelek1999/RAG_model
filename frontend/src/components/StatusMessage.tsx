/**
 * Props for a transient status banner.
 */
type StatusMessageProps = {
  /** Message content displayed to the user when not empty. */
  message: string
}

/**
 * Renders a compact status banner for API and workflow feedback.
 */
export function StatusMessage({ message }: StatusMessageProps) {
  if (!message) {
    return null
  }

  return (
    <p className="rounded-lg border border-slate-200 bg-white p-3 text-sm text-slate-700">
      {message}
    </p>
  )
}
