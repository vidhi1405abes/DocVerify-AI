import { useEffect, useState } from 'react'
import Spinner from '@/components/ui/Spinner'
import Message from '@/components/ui/Message'
import DocumentIcon from '@/components/documents/DocumentIcon'
import { acceptFor, formatsLabel, isAllowedFile } from '@/components/documents/documentTypes'
import {
  deleteReferenceDocument,
  getDocumentTypes,
  getReferenceDocuments,
  uploadReferenceDocument,
} from '@/services/api/documentApi'

const References = () => {
  const [types, setTypes] = useState([])
  const [references, setReferences] = useState({})
  const [selectedFiles, setSelectedFiles] = useState({})
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  useEffect(() => {
    let current = true
    Promise.all([getDocumentTypes(), getReferenceDocuments()])
      .then(([typeList, referenceList]) => {
        if (!current) return
        setTypes(typeList)
        setReferences(referenceList)
      })
      .catch((loadError) => current && setError(loadError.message))
      .finally(() => current && setLoading(false))
    return () => {
      current = false
    }
  }, [])

  const run = async (key, action, successMessage) => {
    setBusy(key)
    setError('')
    setNotice('')
    try {
      await action()
      setReferences(await getReferenceDocuments())
      setNotice(successMessage)
    } catch (actionError) {
      setError(actionError.message)
    } finally {
      setBusy(null)
    }
  }

  const handleUpload = (type) => {
    const file = selectedFiles[type.id]
    const formData = new FormData()
    formData.append('file', file)
    formData.append('documentType', type.id)
    return run(type.id, async () => {
      await uploadReferenceDocument(formData)
      setSelectedFiles((current) => ({ ...current, [type.id]: null }))
    }, `Reference saved for ${type.name}. It is being read in the background.`)
  }

  const chooseFile = (type, file) => {
    setError('')
    if (file && !isAllowedFile(type, file)) {
      setError(`${type.name} references must be ${formatsLabel(type)} files.`)
      return
    }
    setSelectedFiles((current) => ({ ...current, [type.id]: file }))
  }

  if (loading) {
    return (
      <div className="flex justify-center py-24">
        <Spinner label="Loading reference documents..." />
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-5xl py-8">
      <h1 className="text-3xl font-bold text-gray-900">Reference documents</h1>
      <p className="mt-2 text-gray-600">
        Genuine documents used for comparison. When a verified document has the same roll number or ID as a
        reference, every value is compared with it. References also teach the document classifier what each type
        looks like. Files are stored only on this computer.
      </p>

      <Message className="mt-6">{error}</Message>
      <Message type="success" className="mt-6">{notice}</Message>

      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
        {types.map((type) => {
          const list = references[type.id] || []
          const selected = selectedFiles[type.id]
          return (
            <div key={type.id} className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
              <div className="flex items-center gap-2">
                <DocumentIcon type={type.id} />
                <h2 className="font-semibold text-gray-900">{type.name}</h2>
              </div>
              <p className="mt-1 text-sm text-gray-500">
                {list.length} reference{list.length === 1 ? '' : 's'} configured
              </p>
              {list.length > 0 && (
                <ul className="mt-3 space-y-2">
                  {list.map((reference) => (
                    <li key={reference.filename} className="flex items-center justify-between gap-2 text-sm">
                      <span className="break-all text-gray-700">{reference.displayName}</span>
                      <button
                        type="button"
                        className="shrink-0 text-red-600 hover:text-red-700 disabled:opacity-50"
                        disabled={busy !== null}
                        onClick={() => {
                          if (window.confirm(`Remove ${reference.displayName}?`)) {
                            run(reference.filename, () => deleteReferenceDocument(type.id, reference.filename), 'Reference removed.')
                          }
                        }}
                        aria-label={`Remove ${reference.displayName} from ${type.name} references`}
                      >
                        Remove
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              <label className="mt-4 block text-sm font-medium text-gray-700">
                Add reference ({formatsLabel(type)})
                <input
                  className="mt-1 block w-full text-sm text-gray-600"
                  type="file"
                  accept={acceptFor(type)}
                  disabled={busy !== null}
                  onChange={(event) => chooseFile(type, event.target.files[0])}
                />
              </label>
              <button
                type="button"
                className="mt-3 rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
                disabled={!selected || busy !== null}
                onClick={() => handleUpload(type)}
              >
                {busy === type.id ? 'Saving...' : 'Upload reference'}
              </button>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default References
