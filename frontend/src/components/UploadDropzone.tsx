import { type DragEvent, useState } from 'react'

type UploadDropzoneProps = {
  isIngesting: boolean
  uploadProgress: number | null
  onFilesSelected: (files: FileList) => void
}

export function UploadDropzone({
  isIngesting,
  uploadProgress,
  onFilesSelected,
}: UploadDropzoneProps) {
  const [isDragging, setIsDragging] = useState(false)

  const handleDrop = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault()
    setIsDragging(false)

    if (event.dataTransfer.files.length > 0) {
      onFilesSelected(event.dataTransfer.files)
    }
  }

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4">
      <h2 className="text-sm font-bold">Dodaj dokument</h2>
      <label
        className={`mt-3 flex min-h-36 cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed p-6 text-center transition ${
          isDragging
            ? 'border-teal-600 bg-teal-50'
            : 'border-slate-300 bg-slate-50'
        }`}
        onDragOver={(event) => {
          event.preventDefault()
          setIsDragging(true)
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
      >
        <span className="text-sm font-semibold">
          {isIngesting
            ? `Wgrywanie: ${uploadProgress ?? 0}%`
            : 'Przeciagnij plik tutaj'}
        </span>
        <span className="mt-1 text-xs text-slate-500">
          albo kliknij i wybierz plik
        </span>
        <input
          className="sr-only"
          type="file"
          multiple
          accept=".docx,.pdf,.txt,.md,.xlsx"
          disabled={isIngesting}
          onChange={(event) => {
            if (event.target.files) {
              onFilesSelected(event.target.files)
              event.target.value = ''
            }
          }}
        />
      </label>
    </section>
  )
}
