const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000'

export type IngestPipelineProgress = {
  percent: number
  message: string
}

type UploadProgressCallback = (progress: IngestPipelineProgress) => void

type IngestProgressApiResponse = {
  upload_id: string
  progress_percent: number
  stage: string
  status: string
  message: string
}

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

function readErrorMessageFromText(responseText: string, status: number) {
  try {
    const data = JSON.parse(responseText) as { detail?: string }
    return data.detail ?? `API zwrocilo blad ${status}`
  } catch {
    return `API zwrocilo blad ${status}`
  }
}
