import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { AlertTriangle, Camera, CheckCircle2, ChevronDown, Download, MinusCircle, Printer, XCircle } from 'lucide-react'
import Spinner from '@/components/ui/Spinner'
import Message from '@/components/ui/Message'
import VerdictBadge from '@/components/documents/VerdictBadge'
import { STATUS_STYLES, VERDICT_STYLES, formatDateTime } from '@/components/documents/verdict'
import { getVerificationResult } from '@/services/api/documentApi'

const STATUS_ICONS = {
  pass: <CheckCircle2 className="h-5 w-5 shrink-0 text-green-600" />,
  warn: <AlertTriangle className="h-5 w-5 shrink-0 text-amber-500" />,
  fail: <XCircle className="h-5 w-5 shrink-0 text-red-600" />,
  skipped: <MinusCircle className="h-5 w-5 shrink-0 text-gray-400" />,
}

const Card = ({ title, children, action }) => (
  <section className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm print:break-inside-avoid print:shadow-none">
    <div className="mb-4 flex items-center justify-between gap-2">
      <h2 className="text-lg font-semibold text-gray-900">{title}</h2>
      {action}
    </div>
    {children}
  </section>
)

const RiskMeter = ({ score, verdict }) => (
  <div>
    <div className="flex items-end justify-between">
      <span className="text-sm font-medium text-gray-600">Risk score</span>
      <span className="text-3xl font-bold text-gray-900">
        {score}
        <span className="text-base font-medium text-gray-500">/100</span>
      </span>
    </div>
    <div className="mt-2 h-3 w-full overflow-hidden rounded-full bg-gray-100" role="meter" aria-valuenow={score} aria-valuemin={0} aria-valuemax={100} aria-label="Risk score">
      <div className={`h-full rounded-full ${VERDICT_STYLES[verdict].bar}`} style={{ width: `${Math.max(score, 3)}%` }} />
    </div>
    <div className="mt-1 flex justify-between text-xs text-gray-500">
      <span>0 · Verified</span>
      <span>25 · Review</span>
      <span>55 · Suspicious</span>
      <span>90 · Rejected</span>
    </div>
  </div>
)

const LayerRow = ({ layer }) => {
  const [open, setOpen] = useState(layer.status === 'fail' || layer.status === 'warn')
  const style = STATUS_STYLES[layer.status]
  return (
    <li className="border-b border-gray-100 last:border-0">
      <button type="button" onClick={() => setOpen((value) => !value)} className="flex w-full items-center gap-3 py-3 text-left" aria-expanded={open}>
        {STATUS_ICONS[layer.status]}
        <span className="flex-1 font-medium text-gray-900">{layer.name}</span>
        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${style.className}`}>{style.label}</span>
        <ChevronDown className={`h-4 w-4 text-gray-400 transition-transform print:hidden ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <div className="pb-4 pl-8">
          <ul className="list-disc space-y-1 pl-5 text-sm text-gray-700">
            {layer.details.map((detail) => (
              <li key={detail}>{detail}</li>
            ))}
          </ul>
          {layer.ranking && (
            <p className="mt-2 text-xs text-gray-500">
              Classifier ranking: {layer.ranking.map((r) => `${r.name} ${Math.round(r.probability * 100)}%`).join(' · ')}
            </p>
          )}
          {layer.qrPreview && <p className="mt-2 break-all text-xs text-gray-500">QR content: {layer.qrPreview}</p>}
          {layer.heatmap && (
            <figure className="mt-3">
              <img src={layer.heatmap} alt="Document with suspicious values outlined in red" className="max-h-[32rem] rounded border border-gray-200" />
              <figcaption className="mt-1 text-xs text-gray-500">Values that look different from the rest of the table are outlined in red.</figcaption>
            </figure>
          )}
        </div>
      )}
    </li>
  )
}

const SubjectsTable = ({ subjects }) => (
  <div className="overflow-x-auto">
    <table className="min-w-full text-left text-sm">
      <thead className="border-b border-gray-200 text-xs uppercase text-gray-500">
        <tr>
          <th className="py-2 pr-3">Code</th>
          <th className="py-2 pr-3">Subject</th>
          <th className="py-2 pr-3 text-right">Theory</th>
          <th className="py-2 pr-3 text-right">Practical</th>
          <th className="py-2 pr-3 text-right">Total</th>
          <th className="py-2 pr-3">In words</th>
          <th className="py-2 pr-3">Grade</th>
          <th className="py-2">Check</th>
        </tr>
      </thead>
      <tbody>
        {subjects.map((row) => {
          const sumOk = row.theory == null || row.total === row.theory + (row.practical ?? 0)
          const wordsOk = row.totalFromWords == null || row.totalFromWords === row.total
          const ok = sumOk && wordsOk && (row.total ?? 0) <= 100
          return (
            <tr key={`${row.code}-${row.subject}`} className={`border-b border-gray-100 ${ok ? '' : 'bg-red-50'}`}>
              <td className="py-2 pr-3 text-gray-500">{row.code}</td>
              <td className="py-2 pr-3 font-medium text-gray-900">{row.subject}</td>
              <td className="py-2 pr-3 text-right">{row.theory ?? '—'}</td>
              <td className="py-2 pr-3 text-right">{row.practical ?? '—'}</td>
              <td className="py-2 pr-3 text-right font-semibold">{row.total ?? '—'}</td>
              <td className="py-2 pr-3 text-gray-600">{row.totalInWords ?? '—'}</td>
              <td className="py-2 pr-3">{row.grade ?? '—'}</td>
              <td className="py-2">{ok ? STATUS_ICONS.pass : STATUS_ICONS.fail}</td>
            </tr>
          )
        })}
      </tbody>
    </table>
  </div>
)

const downloadJson = (result) => {
  const { ocrText, ...report } = result
  const blob = new Blob([JSON.stringify({ ...report, ocrText }, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `docverify-${result.id}.json`
  link.click()
  URL.revokeObjectURL(url)
}

const Results = () => {
  const { id } = useParams()
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let current = true
    setLoading(true)
    setError('')
    getVerificationResult(id)
      .then((data) => current && setResult(data))
      .catch((loadError) => current && setError(loadError.message))
      .finally(() => current && setLoading(false))
    return () => {
      current = false
    }
  }, [id])

  if (loading) {
    return (
      <div className="flex justify-center py-24">
        <Spinner label="Loading verification result..." />
      </div>
    )
  }
  if (error) {
    return (
      <div className="mx-auto max-w-2xl py-12">
        <Message>{error}</Message>
        <Link to="/verify" className="mt-6 inline-block text-blue-600 hover:text-blue-700">Verify another document</Link>
      </div>
    )
  }

  const style = VERDICT_STYLES[result.verdict]
  const problems = result.reasons.filter((reason) => reason.status !== 'pass')
  const passes = result.reasons.filter((reason) => reason.status === 'pass')

  return (
    <div className="mx-auto max-w-5xl space-y-6 py-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm text-gray-500">{result.documentTypeName} · {result.filename}</p>
          <h1 className="text-3xl font-bold text-gray-900">Verification result</h1>
          {result.createdAt && <p className="mt-1 text-sm text-gray-500">{formatDateTime(result.createdAt)}</p>}
        </div>
        <div className="flex gap-2 print:hidden">
          <button type="button" onClick={() => window.print()} className="flex items-center gap-1 rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50">
            <Printer className="h-4 w-4" /> Print
          </button>
          <button type="button" onClick={() => downloadJson(result)} className="flex items-center gap-1 rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50">
            <Download className="h-4 w-4" /> Download report
          </button>
        </div>
      </div>

      <section className={`rounded-lg border p-6 ${style.panel}`}>
        <div className="grid gap-6 md:grid-cols-2">
          <div>
            <VerdictBadge verdict={result.verdict} />
            <h2 className="mt-3 text-2xl font-bold">Result: {result.verdictLabel}</h2>
            <p className="mt-2">{result.message}</p>
            {result.rejectionReasons?.length > 0 && (
              <ul className="mt-3 list-disc space-y-1 pl-5 font-medium">
                {result.rejectionReasons.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
            )}
            <p className="mt-2 text-sm opacity-80">
              {Math.round(result.coverage * 100)}% of the verification checks could be run on this document.
            </p>
          </div>
          <div className="rounded-lg bg-white/70 p-4">
            <RiskMeter score={result.riskScore} verdict={result.verdict} />
          </div>
        </div>
      </section>

      <Card title="Why this result">
        <ul className="space-y-2">
          {problems.map((reason) => (
            <li key={`${reason.layer}-${reason.text}`} className="flex gap-2 text-sm">
              {STATUS_ICONS[reason.status]}
              <span><span className="font-medium">{reason.layer}:</span> {reason.text}</span>
            </li>
          ))}
          {passes.map((reason) => (
            <li key={reason.text} className="flex gap-2 text-sm text-gray-700">
              {STATUS_ICONS.pass}
              <span>{reason.text}</span>
            </li>
          ))}
        </ul>
      </Card>

      {result.photoTips?.length > 0 && (
        <section className="rounded-lg border border-amber-200 bg-amber-50 p-5 text-amber-900 print:hidden">
          <h2 className="flex items-center gap-2 text-lg font-semibold">
            <Camera className="h-5 w-5" /> Get a clearer result
          </h2>
          <p className="mt-1 text-sm">
            The image was cleaned up automatically, but some text was still hard to read. To get a reliable result:
          </p>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
            {result.photoTips.map((tip) => (
              <li key={tip}>{tip}</li>
            ))}
          </ul>
        </section>
      )}

      <Card title="Verification layers">
        <ul>
          {result.layers.map((layer) => (
            <LayerRow key={layer.key} layer={layer} />
          ))}
        </ul>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Extracted information">
          {result.fields.length ? (
            <dl className="divide-y divide-gray-100 text-sm">
              {result.fields.map((field) => (
                <div key={field.key} className="grid grid-cols-5 gap-2 py-2">
                  <dt className="col-span-2 text-gray-500">{field.label}</dt>
                  <dd className="col-span-3 break-words font-medium text-gray-900">{String(field.value)}</dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className="text-sm text-gray-500">No fields could be extracted.</p>
          )}
        </Card>
        <Card title="Image preprocessing">
          <ul className="list-disc space-y-1 pl-5 text-sm text-gray-700">
            {result.preprocessing.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ul>
        </Card>
      </div>

      {result.subjects.length > 0 && (
        <Card title="Marks table">
          <SubjectsTable subjects={result.subjects} />
        </Card>
      )}

      <details className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm print:hidden">
        <summary className="cursor-pointer text-lg font-semibold text-gray-900">Text read by OCR</summary>
        <pre className="mt-4 max-h-96 overflow-auto whitespace-pre-wrap rounded bg-gray-50 p-3 text-xs text-gray-700">{result.ocrText}</pre>
      </details>

      <p className="text-sm text-gray-500">{result.disclaimer}</p>
      <div className="flex gap-4 print:hidden">
        <Link to="/verify" className="font-medium text-blue-600 hover:text-blue-700">Verify another document</Link>
        <Link to="/history" className="font-medium text-blue-600 hover:text-blue-700">View history</Link>
      </div>
    </div>
  )
}

export default Results
