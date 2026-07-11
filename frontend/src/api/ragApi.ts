const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000'

export type ApiSource = {
  file_name: string | null
  file_type: string | null
  source: string | null
  page: number | null
  sheet_name: string | null
  chunk_index: number | null
}

export type AskApiResponse = {
  answer: string
  sources: ApiSource[]
}

export type DocumentApiInfo = {
  file_name: string | null
  file_type: string | null
  source: string | null
  chunks_count: number
}

export type DocumentsApiResponse = {
  documents: DocumentApiInfo[]
  total_chunks_count: number
}

export type IngestApiResponse = {
  file_name: string
  documents_count: number
  chunks_count: number
  added_chunks_count: number
  total_chunks_count: number
}

export type DeleteDocumentApiResponse = {
  source: string
  deleted_chunks_count: number
  total_chunks_count: number
}

export async function getDocuments() {
  return requestJson<DocumentsApiResponse>('/documents')
}

export async function askQuestion(question: string, k: number) {
  return requestJson<AskApiResponse>('/ask', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ question, k }),
  })
}

export async function ingestDocument(file: File) {
  const formData = new FormData()
  formData.append('file', file)

  return requestJson<IngestApiResponse>('/ingest', {
    method: 'POST',
    body: formData,
  })
}

export async function deleteDocument(source: string) {
  return requestJson<DeleteDocumentApiResponse>('/documents/delete', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ source }),
  })
}

async function requestJson<TResponse>(
  path: string,
  init?: RequestInit,
): Promise<TResponse> {
  const response = await fetch(`${API_BASE_URL}${path}`, init)

  if (!response.ok) {
    const message = await readErrorMessage(response)
    throw new Error(message)
  }

  return response.json() as Promise<TResponse>
}

async function readErrorMessage(response: Response) {
  try {
    const data = (await response.json()) as { detail?: string }
    return data.detail ?? `API zwrocilo blad ${response.status}`
  } catch {
    return `API zwrocilo blad ${response.status}`
  }
}
