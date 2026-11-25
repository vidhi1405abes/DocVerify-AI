import { useEffect, useState } from 'react'
import { Trash2 } from 'lucide-react'
import Spinner from '@/components/ui/Spinner'
import Message from '@/components/ui/Message'
import { formatDateTime } from '@/components/documents/verdict'
import { createRecord, deleteRecord, getDocumentTypes, getRecords, importRecords } from '@/services/api/documentApi'

const inputClass =
  'mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500'

const EMPTY = { documentType: 'marksheet10', identifier: '', name: '', dateOfBirth: '', subjects: '', extra: '', source: '' }
const SAMPLE_CSV =
  'documentType,identifier,name,source,dateOfBirth,result,subject:MATHEMATICS,subject:SCIENCE\n' +
  'marksheet10,25147975,Vaibhav Kumar,CBSE results portal,2004-05-08,PASS,100,95\n'

// "MATHEMATICS=100, SCIENCE=95" -> { MATHEMATICS: 100, SCIENCE: 95 }
const parsePairs = (text, numeric) =>
  Object.fromEntries(
    text
      .split(/[,\n]/)
      .map((pair) => pair.split('='))
      .filter(([key, value]) => key?.trim() && value?.trim())
      .map(([key, value]) => [numeric ? key.trim().toUpperCase() : key.trim(), numeric ? Number(value) : value.trim()])
  )

const Records = () => {
  const [types, setTypes] = useState([])
  const [records, setRecords] = useState([])
  const [form, setForm] = useState(EMPTY)
  const [csvFile, setCsvFile] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  useEffect(() => {
    let current = true
    Promise.all([getDocumentTypes(), getRecords()])
      .then(([typeList, recordList]) => {
        if (!current) return
        setTypes(typeList)
        setRecords(recordList)
      })
      .catch((loadError) => current && setError(loadError.message))
      .finally(() => current && setLoading(false))
    return () => {
      current = false
    }
  }, [])

  const typeName = (id) => types.find((type) => type.id === id)?.name ?? id
  const update = (field) => (event) => setForm((current) => ({ ...current, [field]: event.target.value }))

  const handleSubmit = async (event) => {
    event.preventDefault()
    setError('')
    setNotice('')
    const subjects = parsePairs(form.subjects, true)
    if (Object.values(subjects).some(Number.isNaN)) {
      setError('Subject totals must be numbers, e.g. MATHEMATICS=100.')
      return
    }
    const fields = { ...parsePairs(form.extra, false) }
    if (form.dateOfBirth) fields.dateOfBirth = form.dateOfBirth
    if (Object.keys(subjects).length) fields.subjects = subjects
    setSaving(true)
    try {
      const record = await createRecord({
        documentType: form.documentType,
        identifier: form.identifier.trim(),
        name: form.name.trim(),
        source: form.source.trim(),
        fields,
      })
      setRecords((current) => [record, ...current])
      setForm({ ...EMPTY, documentType: form.documentType })
      setNotice(`Record ${record.identifier} added.`)
    } catch (saveError) {
      setError(saveError.message)
    } finally {
      setSaving(false)
    }
  }

  const handleImport = async () => {
    setError('')
    setNotice('')
    const formData = new FormData()
    formData.append('file', csvFile)
    setSaving(true)
    try {
      const response = await importRecords(formData)
      setRecords(await getRecords())
      setNotice(`Imported ${response.imported} record(s).${response.errors.length ? ` Skipped: ${response.errors.join(' ')}` : ''}`)
      setCsvFile(null)
    } catch (importError) {
      setError(importError.message)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (record) => {
    if (!window.confirm(`Delete the record for ${record.identifier}?`)) return
    try {
      await deleteRecord(record.id)
      setRecords((current) => current.filter((entry) => entry.id !== record.id))
    } catch (deleteError) {
      setError(deleteError.message)
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center py-24">
        <Spinner label="Loading authorized records..." />
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-5xl py-8">
      <h1 className="text-3xl font-bold text-gray-900">Authorized records</h1>
      <p className="mt-2 text-gray-600">
        Records from an authorized source, such as the issuing board&apos;s result data. A verified document is looked
        up by its roll number, application or certificate number, and every value in the record is compared with it.
      </p>

      <Message className="mt-6">{error}</Message>
      <Message type="success" className="mt-6">{notice}</Message>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <form onSubmit={handleSubmit} className="space-y-4 rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
          <h2 className="text-lg font-semibold text-gray-900">Add a record</h2>
          <label className="block text-sm font-medium text-gray-700">
            Document type
            <select className={inputClass} value={form.documentType} onChange={update('documentType')}>
              {types.map((type) => (
                <option key={type.id} value={type.id}>{type.name}</option>
              ))}
            </select>
          </label>
          <label className="block text-sm font-medium text-gray-700">
            Roll / application / certificate number
            <input className={inputClass} value={form.identifier} onChange={update('identifier')} required />
          </label>
          <label className="block text-sm font-medium text-gray-700">
            Name
            <input className={inputClass} value={form.name} onChange={update('name')} />
          </label>
          <label className="block text-sm font-medium text-gray-700">
            Date of birth
            <input className={inputClass} type="date" value={form.dateOfBirth} onChange={update('dateOfBirth')} />
          </label>
          <label className="block text-sm font-medium text-gray-700">
            Subject totals
            <textarea className={inputClass} rows={2} placeholder="MATHEMATICS=100, SCIENCE=95" value={form.subjects} onChange={update('subjects')} />
          </label>
          <label className="block text-sm font-medium text-gray-700">
            Other fields
            <textarea className={inputClass} rows={2} placeholder="result=PASS, totalPercentile=98.5" value={form.extra} onChange={update('extra')} />
          </label>
          <label className="block text-sm font-medium text-gray-700">
            Source
            <input className={inputClass} placeholder="e.g. CBSE results portal" value={form.source} onChange={update('source')} />
          </label>
          <button type="submit" disabled={saving} className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50">
            {saving ? 'Saving...' : 'Add record'}
          </button>
        </form>

        <div className="space-y-4 rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
          <h2 className="text-lg font-semibold text-gray-900">Import from CSV</h2>
          <p className="text-sm text-gray-600">
            Columns: <code>documentType</code>, <code>identifier</code>, <code>name</code>, <code>source</code>, any field
            such as <code>dateOfBirth</code>, and one <code>subject:NAME</code> column per subject total.
          </p>
          <pre className="overflow-x-auto rounded bg-gray-50 p-3 text-xs text-gray-700">{SAMPLE_CSV}</pre>
          <input type="file" accept=".csv,text/csv" onChange={(event) => setCsvFile(event.target.files[0] ?? null)} className="block w-full text-sm text-gray-600" />
          <button type="button" disabled={!csvFile || saving} onClick={handleImport} className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50">
            Import records
          </button>
        </div>
      </div>

      <h2 className="mt-10 text-xl font-semibold text-gray-900">{records.length} record{records.length === 1 ? '' : 's'}</h2>
      {records.length === 0 ? (
        <div className="mt-4 rounded-lg border border-dashed border-gray-300 bg-white p-10 text-center text-gray-500">
          No authorized records yet.
        </div>
      ) : (
        <div className="mt-4 overflow-x-auto rounded-lg border border-gray-200 bg-white shadow-sm">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-gray-200 bg-gray-50 text-xs uppercase text-gray-500">
              <tr>
                <th className="px-4 py-3">Identifier</th>
                <th className="px-4 py-3">Type</th>
                <th className="px-4 py-3">Name</th>
                <th className="px-4 py-3">Fields</th>
                <th className="px-4 py-3">Added</th>
                <th className="px-4 py-3"><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody>
              {records.map((record) => (
                <tr key={record.id} className="border-b border-gray-100 last:border-0 align-top">
                  <td className="px-4 py-3 font-medium text-gray-900">{record.identifier}</td>
                  <td className="px-4 py-3 text-gray-600">{typeName(record.documentType)}</td>
                  <td className="px-4 py-3">{record.name || '—'}</td>
                  <td className="px-4 py-3 text-xs text-gray-600">
                    {Object.entries(record.fields).map(([key, value]) => (
                      <div key={key}>
                        {key}: {typeof value === 'object' ? Object.entries(value).map(([k, v]) => `${k} ${v}`).join(', ') : value}
                      </div>
                    ))}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-gray-500">{formatDateTime(record.createdAt)}</td>
                  <td className="px-4 py-3 text-right">
                    <button type="button" onClick={() => handleDelete(record)} className="text-gray-400 hover:text-red-600" aria-label={`Delete record ${record.identifier}`}>
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

export default Records
