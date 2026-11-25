import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { CheckCircle2, FileText, Loader2, Upload } from 'lucide-react'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import Message from '@/components/ui/Message'
import Spinner from '@/components/ui/Spinner'
import { getDocumentTypes, verifyDocument } from '@/services/api/documentApi'
import DocumentIcon from '@/components/documents/DocumentIcon'
import { acceptFor, formatsLabel, isAllowedFile } from '@/components/documents/documentTypes'

const PIPELINE = [
  'Uploading document',
  'Preprocessing image',
  'Reading text (OCR)',
  'Classifying document',
  'Extracting information',
  'Checking structure & consistency',
  'Analysing for tampering',
  'Checking QR code, records & references',
  'Calculating risk score',
]
const STEP_MS = 3500

const Verify = () => {
  const navigate = useNavigate()
  const [types, setTypes] = useState([])
  const [loadingTypes, setLoadingTypes] = useState(true)
  const [documentType, setDocumentType] = useState('')
  const [file, setFile] = useState(null)
  const [dragging, setDragging] = useState(false)
  const [error, setError] = useState('')
  const [verifying, setVerifying] = useState(false)
  const [step, setStep] = useState(0)

  const selected = types.find((type) => type.id === documentType)

  useEffect(() => {
    let current = true
    getDocumentTypes()
      .then((data) => current && setTypes(data))
      .catch((loadError) => current && setError(loadError.message))
      .finally(() => current && setLoadingTypes(false))
    return () => {
      current = false
    }
  }, [])

  useEffect(() => {
    if (!verifying) return undefined
    const timer = setInterval(() => setStep((value) => Math.min(value + 1, PIPELINE.length - 1)), STEP_MS)
    return () => clearInterval(timer)
  }, [verifying])

  const chooseFile = (candidate) => {
    if (!candidate) return
    if (!selected) {
      setError('Select a document type first.')
      return
    }
    if (!isAllowedFile(selected, candidate)) {
      setFile(null)
      setError(`${selected.name} accepts ${formatsLabel(selected)} files only.`)
      return
    }
    if (candidate.size > 15 * 1024 * 1024) {
      setFile(null)
      setError('File exceeds the 15 MB upload limit.')
      return
    }
    setError('')
    setFile(candidate)
  }

  const handleVerify = async () => {
    if (!file || !selected || verifying) return
    setVerifying(true)
    setStep(0)
    setError('')
    const formData = new FormData()
    formData.append('file', file)
    formData.append('documentType', selected.id)
    try {
      const result = await verifyDocument(formData)
      navigate(`/results/${result.id}`)
    } catch (verifyError) {
      setError(verifyError.message)
      setVerifying(false)
    }
  }

  if (loadingTypes) {
    return (
      <div className="flex justify-center py-24">
        <Spinner label="Loading document types..." />
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-4xl py-8">
      <div className="mb-10 text-center">
        <h1 className="text-3xl font-bold text-gray-900 sm:text-4xl">Verify a document</h1>
        <p className="mt-3 text-lg text-gray-600">
          Upload a document to run OCR, consistency, tampering, QR and record checks.
        </p>
      </div>

      {verifying ? (
        <section className="rounded-lg border border-blue-100 bg-white p-6 shadow-sm" aria-live="polite">
          <h2 className="text-lg font-semibold text-gray-900">Verifying {file?.name}</h2>
          <p className="mt-1 text-sm text-gray-500">
            This usually takes 10–60 seconds. The first verification after starting the server is slower while the OCR model loads.
          </p>
          <ol className="mt-6 space-y-3">
            {PIPELINE.map((label, index) => (
              <li key={label} className="flex items-center gap-3 text-sm">
                {index < step ? (
                  <CheckCircle2 className="h-5 w-5 text-green-600" />
                ) : index === step ? (
                  <Loader2 className="h-5 w-5 animate-spin text-blue-600" />
                ) : (
                  <span className="h-5 w-5 rounded-full border-2 border-gray-200" />
                )}
                <span className={index <= step ? 'text-gray-900' : 'text-gray-400'}>{label}</span>
              </li>
            ))}
          </ol>
        </section>
      ) : (
        <>
          <div className="mb-6">
            <label className="mb-2 block text-sm font-medium text-gray-700" htmlFor="document-type">
              Document type
            </label>
            <Select
              onValueChange={(value) => {
                setDocumentType(value)
                setFile(null)
                setError('')
              }}
              value={documentType}
            >
              <SelectTrigger id="document-type" className="w-full">
                <SelectValue placeholder="Select document type" />
              </SelectTrigger>
              <SelectContent>
                {types.map((type) => (
                  <SelectItem key={type.id} value={type.id}>
                    <div className="flex items-center gap-2">
                      <DocumentIcon type={type.id} />
                      <span>{type.name}</span>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {selected && (
            <div className="mb-6 rounded-lg bg-blue-50 p-4">
              <div className="flex items-center gap-2">
                <DocumentIcon type={selected.id} />
                <h2 className="text-lg font-medium text-blue-900">{selected.name}</h2>
              </div>
              <p className="mt-2 text-sm text-blue-800">{selected.description}</p>
              <p className="mt-1 text-sm text-blue-700">Accepted formats: {formatsLabel(selected)} · up to 15 MB</p>
              <p className="mt-1 text-sm text-blue-700">Must contain: {selected.requiredFields.join(', ')}</p>
            </div>
          )}

          <div
            className={`rounded-lg border-2 border-dashed p-10 text-center transition-colors ${
              dragging ? 'border-blue-500 bg-blue-50' : 'border-gray-300 bg-white'
            }`}
            onDragOver={(event) => {
              event.preventDefault()
              setDragging(true)
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(event) => {
              event.preventDefault()
              setDragging(false)
              chooseFile(event.dataTransfer.files[0])
            }}
          >
            <Upload className={`mx-auto h-14 w-14 ${dragging ? 'text-blue-500' : 'text-gray-400'}`} />
            <div className="mt-4 text-lg">
              <label className={`cursor-pointer font-medium text-blue-600 hover:text-blue-500 ${!selected ? 'pointer-events-none opacity-50' : ''}`}>
                <span>Choose a file</span>
                <input
                  type="file"
                  className="sr-only"
                  accept={acceptFor(selected)}
                  onChange={(event) => {
                    chooseFile(event.target.files[0])
                    event.target.value = ''
                  }}
                  disabled={!selected}
                />
              </label>
              <span className="text-gray-500"> or drag and drop</span>
            </div>
            <p className="mt-2 text-sm text-gray-500">
              {selected ? `Upload your ${selected.name}` : 'Select a document type first'}
            </p>
          </div>

          {file && <Message type="success" className="mt-4">Selected: {file.name}</Message>}
          <Message className="mt-4">{error}</Message>

          <button
            type="button"
            onClick={handleVerify}
            disabled={!file || !selected}
            className="mt-6 flex w-full items-center justify-center rounded-md bg-blue-600 px-4 py-3 text-base font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <FileText className="mr-2 h-5 w-5" />
            {selected ? `Verify ${selected.name}` : 'Verify document'}
          </button>
        </>
      )}
      {verifying && <Message className="mt-4">{error}</Message>}
    </div>
  )
}

export default Verify
