/**
 * Frontend API service for the RAG backend.
 *
 * This module performs HTTP requests and progress tracking only.
 * It intentionally contains no UI-level business decisions.
 */
const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000'

/**
 * Progress snapshot for the full ingest pipeline.
 */
export type IngestPipelineProgress = {
  /** Completion percentage from 0 to 100. */
  percent: number
  /** Human-readable stage label shown in the UI. */
  message: string
}

type UploadProgressCallback = (progress: IngestPipelineProgress) => void

/**
 * Raw ingest progress payload returned by the backend polling endpoint.
 */
type IngestProgressApiResponse = {
  upload_id: string
  progress_percent: number
  stage: string
  status: string
  message: string
}

/**
 * Source metadata attached to answer chunks.
 */
export type ApiSource = {
  file_name: string | null
  file_type: string | null
  source: string | null
  page: number | null
  sheet_name: string | null
  chunk_index: number | null
}

/**
 * Response returned by the ask endpoint.
 */
export type AskApiResponse = {
  answer: string
  sources: ApiSource[]
}

/**
 * Single document summary shown in the documents table.
 */
export type DocumentApiInfo = {
  file_name: string | null
  file_type: string | null
  source: string | null
  chunks_count: number
}

/**
 * Documents listing payload returned by the backend.
 */
export type DocumentsApiResponse = {
  documents: DocumentApiInfo[]
  total_chunks_count: number
}

/**
 * Ingest endpoint payload after processing a single file.
 */
export type IngestApiResponse = {
  file_name: string
  documents_count: number
  chunks_count: number
  added_chunks_count: number
  total_chunks_count: number
}

/**
 * Delete endpoint payload containing deleted chunks count.
 */
export type DeleteDocumentApiResponse = {
  source: string
  deleted_chunks_count: number
  total_chunks_count: number
}

/**
 * Fetches the current list of indexed documents.
 */
export async function getDocuments() {
  return requestJson<DocumentsApiResponse>('/documents')
}

/**
 * Sends a user question with the retrieval depth parameter.
 */
export async function askQuestion(question: string, k: number) {
  return requestJson<AskApiResponse>('/ask', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ question, k }),
  })
}

/**
 * Uploads one file and reports combined upload and indexing progress.
 */
export async function ingestDocument(
  file: File,
  onProgress?: UploadProgressCallback,
) {
  const formData = new FormData()
  formData.append('file', file)
  const uploadId = crypto.randomUUID()

  return uploadFormDataWithProgress<IngestApiResponse>(
    '/ingest',
    formData,
    uploadId,
    onProgress,
  )
}

/**
 * Deletes all indexed chunks linked to a given source path.
 */
export async function deleteDocument(source: string) {
  return requestJson<DeleteDocumentApiResponse>('/documents/delete', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ source }),
  })
}

/**
 * Executes a JSON request and converts non-success responses into errors.
 */
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

/**
 * Extracts a readable API error from JSON response bodies.
 */
async function readErrorMessage(response: Response) {
  try {
    const data = (await response.json()) as { detail?: string }
    return data.detail ?? `API zwrocilo blad ${response.status}`
  } catch {
    return `API zwrocilo blad ${response.status}`
  }
}

/**
 * Uses XMLHttpRequest to emit upload progress events and poll pipeline status.
 */
function uploadFormDataWithProgress<TResponse>(
  path: string,
  formData: FormData,
  uploadId: string,
  onProgress?: UploadProgressCallback,
): Promise<TResponse> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', `${API_BASE_URL}${path}`)
    xhr.setRequestHeader('X-Upload-Id', uploadId)

    const stopPolling = startIngestProgressPolling(uploadId, onProgress)

    xhr.upload.onprogress = (event) => {
      if (!onProgress || !event.lengthComputable) {
        return
      }

      // Reserve the first quarter for raw file upload, then poll backend indexing.
      const uploadPercent = Math.round((event.loaded / event.total) * 100)
      const pipelinePercent = Math.round(uploadPercent * 0.25)
      onProgress({
        percent: Math.min(25, Math.max(0, pipelinePercent)),
        message: 'Wgrywanie pliku do API',
      })
    }

    xhr.onerror = () => {
      stopPolling()
      reject(new Error('Nie udalo sie polaczyc z API.'))
    }

    xhr.onload = () => {
      stopPolling()
      const status = xhr.status
      const rawResponse = xhr.responseText

      if (status >= 200 && status < 300) {
        try {
          onProgress?.({
            percent: 100,
            message: 'Dokument gotowy do pracy',
          })
          resolve(JSON.parse(rawResponse) as TResponse)
        } catch {
          reject(new Error('API zwrocilo nieprawidlowy JSON.'))
        }
        return
      }

      reject(new Error(readErrorMessageFromText(rawResponse, status)))
    }

    xhr.send(formData)
  })
}

/**
 * Polls ingest progress until processing is completed or failed.
 */
function startIngestProgressPolling(
  uploadId: string,
  onProgress?: UploadProgressCallback,
) {
  if (!onProgress) {
    return () => undefined
  }

  let isActive = true
  let timeoutId: ReturnType<typeof setTimeout> | null = null

  const scheduleNext = () => {
    if (!isActive) {
      return
    }
    timeoutId = setTimeout(() => {
      void pollProgress()
    }, 350)
  }

  const pollProgress = async () => {
    if (!isActive) {
      return
    }

    try {
      const response = await fetch(`${API_BASE_URL}/ingest/progress/${uploadId}`)

      if (response.status === 404) {
        scheduleNext()
        return
      }

      if (!response.ok) {
        scheduleNext()
        return
      }

      const progress = (await response.json()) as IngestProgressApiResponse
      const mappedPercent = Math.round(25 + progress.progress_percent * 0.75)

      onProgress({
        percent: Math.min(99, Math.max(25, mappedPercent)),
        message: progress.message,
      })

      if (progress.status !== 'completed' && progress.status !== 'failed') {
        scheduleNext()
      }
    } catch {
      scheduleNext()
    }
  }

  scheduleNext()

  return () => {
    isActive = false
    if (timeoutId) {
      clearTimeout(timeoutId)
    }
  }
}

/**
 * Reads error details from plain response text when upload fails.
 */
function readErrorMessageFromText(responseText: string, status: number) {
  try {
    const data = JSON.parse(responseText) as { detail?: string }
    return data.detail ?? `API zwrocilo blad ${status}`
  } catch {
    return `API zwrocilo blad ${status}`
  }
}
