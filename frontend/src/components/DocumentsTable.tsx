import type { DocumentApiInfo, DocumentsApiResponse } from '../api/ragApi'

type DocumentsTableProps = {
  documentsResponse: DocumentsApiResponse | null
  isDeleting: boolean
  onDelete: (source: string) => void
  onRefresh: () => void
}

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

type DocumentRowProps = {
  document: DocumentApiInfo
  isDeleting: boolean
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
