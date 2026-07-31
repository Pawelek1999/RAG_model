/**
 * API availability state displayed in the application header.
 */
export type ApiStatus = 'checking' | 'online' | 'offline'

/**
 * Single chat entry rendered in the RAG conversation panel.
 */
export type ChatMessage = {
  /** Stable key used to render message lists in React. */
  id: string
  /** Message author role used for alignment and styling. */
  role: 'user' | 'assistant'
  /** Main message body shown to the user. */
  content: string
  /** Optional list of source references attached to assistant responses. */
  sources?: string[]
}
