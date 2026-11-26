import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Trash2 } from 'lucide-react'
import { useAuth } from '@/context/useAuth'
import Spinner from '@/components/ui/Spinner'
import Message from '@/components/ui/Message'
import VerdictBadge from '@/components/documents/VerdictBadge'
import { VERDICT_LABELS, formatDateTime } from '@/components/documents/verdict'
import { deleteVerificationResult, getHistory } from '@/services/api/documentApi'

const History = () => {
  const { isAdmin } = useAuth()
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [scope, setScope] = useState('mine')
  const [verdict, setVerdict] = useState('all')
  const [search, setSearch] = useState('')

  useEffect(() => {
    let current = true
    setLoading(true)
    getHistory(scope)
      .then((data) => current && setItems(data))
      .catch((loadError) => current && setError(loadError.message))
      .finally(() => current && setLoading(false))
    return () => {
      current = false
    }
  }, [scope])

  const counts = useMemo(
    () => items.reduce((total, item) => ({ ...total, [item.verdict]: (total[item.verdict] ?? 0) + 1 }), {}),
    [items]
  )

  const visible = items.filter(
    (item) =>
      (verdict === 'all' || item.verdict === verdict) &&
      `${item.filename} ${item.documentTypeName}`.toLowerCase().includes(search.toLowerCase())
  )

  const handleDelete = async (item) => {
    if (!window.confirm(`Delete the result for ${item.filename}? This cannot be undone.`)) return
    try {
      await deleteVerificationResult(item.id)
      setItems((current) => current.filter((entry) => entry.id !== item.id))
    } catch (deleteError) {
      setError(deleteError.message)
    }
  }

  return (
    <div className="mx-auto max-w-5xl py-8">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Verification history</h1>
          <p className="mt-1 text-gray-600">Every document you have verified, newest first.</p>
        </div>
        <Link to="/verify" className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">
          Verify a document
        </Link>
      </div>

      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-5">
        {[['all', 'Total', items.length], ...Object.keys(VERDICT_LABELS).map((key) => [key, VERDICT_LABELS[key], counts[key] ?? 0])].map(
          ([key, label, count]) => (
            <button
              key={key}
              type="button"
              onClick={() => setVerdict(key)}
              className={`rounded-lg border bg-white p-4 text-left shadow-sm ${verdict === key ? 'border-blue-500 ring-1 ring-blue-500' : 'border-gray-200'}`}
            >
              <p className="text-sm text-gray-500">{label}</p>
              <p className="text-2xl font-bold text-gray-900">{count}</p>
            </button>
          )
        )}
      </div>

      <div className="mb-4 flex flex-wrap gap-3">
        <input
          type="search"
          placeholder="Search by file name or type"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          className="min-w-0 flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          aria-label="Search history"
        />
        {isAdmin && (
          <select
            value={scope}
            onChange={(event) => setScope(event.target.value)}
            className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm"
            aria-label="Whose verifications to show"
          >
            <option value="mine">My verifications</option>
            <option value="all">All users</option>
          </select>
        )}
      </div>

      <Message className="mb-4">{error}</Message>

      {loading ? (
        <div className="flex justify-center py-16">
          <Spinner label="Loading history..." />
        </div>
      ) : visible.length === 0 ? (
        <div className="rounded-lg border border-dashed border-gray-300 bg-white p-10 text-center text-gray-500">
          {items.length === 0 ? 'No documents verified yet.' : 'No results match your filters.'}
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white shadow-sm">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-gray-200 bg-gray-50 text-xs uppercase text-gray-500">
              <tr>
                <th className="px-4 py-3">Document</th>
                <th className="px-4 py-3">Type</th>
                <th className="px-4 py-3">Result</th>
                <th className="px-4 py-3 text-right">Risk</th>
                <th className="px-4 py-3">Date</th>
                <th className="px-4 py-3"><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody>
              {visible.map((item) => (
                <tr key={item.id} className="border-b border-gray-100 last:border-0 hover:bg-gray-50">
                  <td className="max-w-[16rem] truncate px-4 py-3">
                    <Link to={`/results/${item.id}`} className="font-medium text-blue-600 hover:text-blue-700">
                      {item.filename}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-gray-600">{item.documentTypeName}</td>
                  <td className="px-4 py-3"><VerdictBadge verdict={item.verdict} /></td>
                  <td className="px-4 py-3 text-right font-medium">{item.riskScore}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-gray-500">{formatDateTime(item.createdAt)}</td>
                  <td className="px-4 py-3 text-right">
                    <button type="button" onClick={() => handleDelete(item)} className="text-gray-400 hover:text-red-600" aria-label={`Delete result for ${item.filename}`}>
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

export default History
