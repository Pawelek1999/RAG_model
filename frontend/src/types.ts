export type ApiStatus = 'checking' | 'online' | 'offline'

export type ChatMessage = {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: string[]
}
