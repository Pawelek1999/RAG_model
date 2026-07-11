import { useEffect, useState } from 'react'
import {
  askQuestion,
  deleteDocument,
  getDocuments,
  ingestDocument,
  type DocumentsApiResponse,
} from './api/ragApi'
import { AskPanel } from './components/AskPanel'
import { DocumentsTable } from './components/DocumentsTable'
import { Header } from './components/Header'
import { StatusMessage } from './components/StatusMessage'
import { UploadDropzone } from './components/UploadDropzone'
import type { ApiStatus, ChatMessage } from './types'

function App() {
  const [documentsResponse, setDocumentsResponse] =
    useState<DocumentsApiResponse | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [question, setQuestion] = useState('')
  const [topK, setTopK] = useState(4)
  const [apiStatus, setApiStatus] = useState<ApiStatus>('checking')
  const [isIngesting, setIsIngesting] = useState(false)
  const [isAsking, setIsAsking] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const [message, setMessage] = useState('')

  useEffect(() => {
    void refreshDocuments()
  }, [])

  const refreshDocuments = async () => {
    try {
      const response = await getDocuments()
      setDocumentsResponse(response)
      setApiStatus('online')
    } catch (error) {
      setApiStatus('offline')
      setMessage(getErrorMessage(error))
    }
  }

  const ingestFiles = async (files: FileList) => {
    setIsIngesting(true)
    setMessage(`Indeksuje ${files.length} plikow...`)

    try {
      for (const file of Array.from(files)) {
        await ingestDocument(file)
      }

      await refreshDocuments()
      setMessage('Dokumenty zostaly zaindeksowane.')
    } catch (error) {
      setMessage(getErrorMessage(error))
    } finally {
      setIsIngesting(false)
    }
  }

  const handleAsk = async () => {
    const trimmedQuestion = question.trim()

    if (!trimmedQuestion) {
      return
    }

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: trimmedQuestion,
    }

    setMessages((currentMessages) => [...currentMessages, userMessage])
    setQuestion('')
    setIsAsking(true)
    setMessage('')

    try {
      const response = await askQuestion(trimmedQuestion, topK)
      const assistantMessage: ChatMessage = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: response.answer,
        sources: response.sources.map(formatSource),
      }

      setMessages((currentMessages) => [
        ...currentMessages,
        assistantMessage,
      ])
      setApiStatus('online')
    } catch (error) {
      const assistantMessage: ChatMessage = {
        id: `assistant-error-${Date.now()}`,
        role: 'assistant',
        content: getErrorMessage(error),
      }

      setMessages((currentMessages) => [
        ...currentMessages,
        assistantMessage,
      ])
      setMessage(getErrorMessage(error))
    } finally {
      setIsAsking(false)
    }
  }

  const handleDeleteDocument = async (source: string) => {
    setIsDeleting(true)
    setMessage('Usuwam dokument z ChromaDB...')

    try {
      const response = await deleteDocument(source)
      await refreshDocuments()
      setMessage(`Usunieto chunkow: ${response.deleted_chunks_count}.`)
    } catch (error) {
      setMessage(getErrorMessage(error))
    } finally {
      setIsDeleting(false)
    }
  }

  return (
    <main className="min-h-screen bg-slate-50 px-4 py-6 text-slate-950">
      <div className="mx-auto grid max-w-5xl gap-4">
        <Header apiStatus={apiStatus} />
        <UploadDropzone
          isIngesting={isIngesting}
          onFilesSelected={(files) => void ingestFiles(files)}
        />
        <DocumentsTable
          documentsResponse={documentsResponse}
          isDeleting={isDeleting}
          onDelete={(source) => void handleDeleteDocument(source)}
          onRefresh={() => void refreshDocuments()}
        />
        <AskPanel
          isAsking={isAsking}
          messages={messages}
          question={question}
          topK={topK}
          onAsk={() => void handleAsk()}
          onQuestionChange={setQuestion}
          onTopKChange={setTopK}
        />
        <StatusMessage message={message} />
      </div>
    </main>
  )
}

function formatSource(source: {
  file_name: string | null
  page: number | null
  sheet_name: string | null
  chunk_index: number | null
}) {
  const parts = [
    source.file_name,
    source.page ? `strona ${source.page}` : null,
    source.sheet_name ? `arkusz ${source.sheet_name}` : null,
    source.chunk_index !== null ? `chunk ${source.chunk_index}` : null,
  ].filter(Boolean)

  return parts.join(' - ') || 'Nieznane zrodlo'
}

function getErrorMessage(error: unknown) {
  if (error instanceof Error) {
    return error.message
  }

  return 'Wystapil nieznany blad podczas komunikacji z API.'
}

export default App
