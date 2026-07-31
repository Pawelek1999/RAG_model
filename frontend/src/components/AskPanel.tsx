import type { ChatMessage } from '../types'

/**
 * Props for the AskPanel component.
 */
type AskPanelProps = {
  /** Disables inputs and submit actions while a response is in progress. */
  isAsking: boolean
  /** Full conversation history rendered in the chat area. */
  messages: ChatMessage[]
  /** Current textarea value controlled by the parent container. */
  question: string
  /** Number of retrieved chunks requested from the backend. */
  topK: number
  /** Submits the current question to the backend. */
  onAsk: () => void
  /** Updates the controlled question input in the parent state. */
  onQuestionChange: (question: string) => void
  /** Updates retrieval depth in the parent state. */
  onTopKChange: (topK: number) => void
}

/**
 * Renders the RAG chat area with message history and question composer.
 */
export function AskPanel({
  isAsking,
  messages,
  question,
  topK,
  onAsk,
  onQuestionChange,
  onTopKChange,
}: AskPanelProps) {
  return (
    <section className="flex min-h-[32rem] flex-col rounded-lg border border-slate-200 bg-white">
      <div className="border-b border-slate-200 px-4 py-3">
        <h2 className="text-sm font-bold">Chat RAG</h2>
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto bg-slate-50 p-4">
        {messages.length ? (
          messages.map((message) => (
            <ChatBubble key={message.id} message={message} />
          ))
        ) : (
          <p className="rounded-lg border border-slate-200 bg-white p-3 text-sm text-slate-500">
            Zadaj pierwsze pytanie do zaindeksowanych dokumentow.
          </p>
        )}
        {isAsking ? (
          <div className="max-w-[80%] rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-500">
            Odpowiadam...
          </div>
        ) : null}
      </div>

      <div className="border-t border-slate-200 p-4">
        <div className="grid gap-3">
          <textarea
            className="min-h-24 resize-none rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-teal-600"
            placeholder="Wpisz pytanie..."
            value={question}
            disabled={isAsking}
            onChange={(event) => onQuestionChange(event.target.value)}
            onKeyDown={(event) => {
              if (
                event.key === 'Enter' &&
                !event.shiftKey &&
                !event.ctrlKey &&
                !event.metaKey
              ) {
                event.preventDefault()
                onAsk()
              }
            }}
          />
          <div className="flex flex-wrap items-center gap-3">
            <label className="text-sm">
              k:{' '}
              <input
                className="w-16 rounded-md border border-slate-300 px-2 py-1"
                type="number"
                min="1"
                value={topK}
                disabled={isAsking}
                onChange={(event) => onTopKChange(Number(event.target.value))}
              />
            </label>
            <button
              className="rounded-md bg-slate-950 px-4 py-2 text-sm font-bold text-white disabled:bg-slate-300"
              type="button"
              disabled={!question.trim() || isAsking}
              onClick={onAsk}
            >
              {isAsking ? 'Pytam...' : 'Zapytaj'}
            </button>
          </div>
        </div>
      </div>
    </section>
  )
}

/**
 * Props for a single chat bubble row.
 */
type ChatBubbleProps = {
  /** Chat item to render, including optional source references. */
  message: ChatMessage
}

function ChatBubble({ message }: ChatBubbleProps) {
  const isUser = message.role === 'user'

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[80%] rounded-lg px-3 py-2 text-sm leading-6 ${
          isUser
            ? 'bg-slate-950 text-white'
            : 'border border-slate-200 bg-white text-slate-800'
        }`}
      >
        <p className="whitespace-pre-wrap">{message.content}</p>
        {!isUser && message.sources?.length ? (
          <div className="mt-3 border-t border-slate-200 pt-2">
            <p className="text-xs font-bold text-slate-500">Zrodla</p>
            <ul className="mt-1 grid gap-1 text-xs text-slate-500">
              {message.sources.map((source) => (
                <li key={source}>{source}</li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </div>
  )
}
