import type { DocumentApiInfo, DocumentsApiResponse } from '../api/ragApi'

/**
 * Props for the documents listing table.
 */
type DocumentsTableProps = {
  /** Cached backend response with indexed document summaries. */
  documentsResponse: DocumentsApiResponse | null
  /** Disables delete actions while a delete request is running. */
  isDeleting: boolean
  /** Removes all chunks for the selected document source. */
  onDelete: (source: string) => void
  /** Refreshes the document list from the backend. */
  onRefresh: () => void
}

/**
 * Displays indexed documents and allows refresh and delete actions.
 */
export function DocumentsTable({
  documentsResponse,
  isDeleting,
  onDelete,
  onRefresh,
}: DocumentsTableProps) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-sm font-bold">Dokumenty z API</h2>
        <button
          className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-semibold hover:bg-slate-50"
          type="button"
          onClick={onRefresh}
        >
          Odswiez
        </button>
      </div>

      <div className="mt-3 overflow-hidden rounded-lg border border-slate-200">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-100 text-xs uppercase text-slate-600">
            <tr>
              <th className="px-3 py-2">Plik</th>
              <th className="px-3 py-2">Typ</th>
              <th className="px-3 py-2">Chunki</th>
              <th className="px-3 py-2">Akcja</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {documentsResponse?.documents.length ? (
              documentsResponse.documents.map((document) => (
                <DocumentRow
                  key={document.source ?? document.file_name}
                  document={document}
                  isDeleting={isDeleting}
                  onDelete={onDelete}
                />
              ))
            ) : (
              <tr>
                <td className="px-3 py-4 text-slate-500" colSpan={4}>
                  Brak dokumentow w ChromaDB.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-xs text-slate-500">
        Wszystkich chunkow: {documentsResponse?.total_chunks_count ?? 0}
      </p>
    </section>
  )
}

/**
 * Props for a single document table row.
 */
type DocumentRowProps = {
  /** Document entry rendered in the current row. */
  document: DocumentApiInfo
  /** Global delete state used to prevent concurrent deletes. */
  isDeleting: boolean
  /** Invoked when a row delete action is confirmed. */
  onDelete: (source: string) => void
}

function DocumentRow({ document, isDeleting, onDelete }: DocumentRowProps) {
  const canDelete = Boolean(document.source)

  return (
    <tr>
      <td className="px-3 py-2 font-medium">{document.file_name ?? '-'}</td>
      <td className="px-3 py-2 text-slate-600">{document.file_type ?? '-'}</td>
      <td className="px-3 py-2 text-slate-600">{document.chunks_count}</td>
      <td className="px-3 py-2">
        <button
          className="rounded-md border border-rose-200 px-2 py-1 text-xs font-semibold text-rose-700 hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-50"
          type="button"
          disabled={!canDelete || isDeleting}
          onClick={() => {
            if (document.source) {
              onDelete(document.source)
            }
          }}
        >
          Usun
        </button>
      </td>
    </tr>
  )
}
