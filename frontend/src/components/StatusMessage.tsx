type StatusMessageProps = {
  message: string
}

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
