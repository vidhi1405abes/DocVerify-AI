import { Link } from 'react-router-dom'
import { Calculator, FileSearch, Fingerprint, QrCode, ScanText, ShieldCheck } from 'lucide-react'
import { useAuth } from '@/context/useAuth'

const LAYERS = [
  { icon: ScanText, title: 'OCR & information extraction', text: 'Cleans up the image, reads the text and pulls out names, roll numbers, dates and marks.' },
  { icon: FileSearch, title: 'Classification & structure', text: 'Recognises the document type and checks that every required field is present.' },
  { icon: Calculator, title: 'Data consistency', text: 'Marks must add up, totals must match the total in words, and dates must be in order.' },
  { icon: Fingerprint, title: 'Tampering detection', text: 'Flags values printed in a different size, ink or background, and files saved by editing tools.' },
  { icon: QrCode, title: 'QR & record verification', text: 'Decodes QR codes and compares the document with authorized records and genuine references.' },
  { icon: ShieldCheck, title: 'Explainable risk score', text: 'Combines every check into a 0–100 risk score with the reasons behind the result.' },
]

const PIPELINE = ['Upload', 'Preprocess', 'Classify', 'OCR', 'Extract', 'Structure', 'Consistency', 'Tampering', 'QR / ID', 'Records', 'Risk score', 'Result']

const OUTCOMES = [
  { label: 'Verified', className: 'border-green-200 bg-green-50 text-green-900', text: 'Most checks passed and nothing suspicious was found.' },
  { label: 'Requires Review', className: 'border-amber-200 bg-amber-50 text-amber-900', text: 'The system cannot decide confidently, so a person should inspect it.' },
  { label: 'Suspicious', className: 'border-red-200 bg-red-50 text-red-900', text: 'Checks point to manipulation, inconsistent data or a record mismatch.' },
]

export default function Home() {
  const { isAuthenticated } = useAuth()
  const start = isAuthenticated ? '/verify' : '/register'

  return (
    <div>
      <section className="py-16 text-center sm:py-20">
        <p className="text-sm font-semibold uppercase tracking-wide text-blue-600">Intelligent document verification</p>
        <h1 className="mx-auto mt-3 max-w-4xl text-4xl font-bold text-gray-900 sm:text-5xl">
          Catch manipulated documents that still look genuine
        </h1>
        <p className="mx-auto mt-6 max-w-3xl text-lg text-gray-600">
          DocVerify AI reads a document, understands its information, checks that it is consistent, looks for signs of
          editing and compares it with authorized records, then explains its verdict.
        </p>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <Link to={start} className="rounded-lg bg-blue-600 px-8 py-3 text-lg font-medium text-white hover:bg-blue-700">
            {isAuthenticated ? 'Verify a document' : 'Get started'}
          </Link>
          {!isAuthenticated && (
            <Link to="/login" className="rounded-lg border border-gray-300 bg-white px-8 py-3 text-lg font-medium text-gray-700 hover:bg-gray-50">
              Sign in
            </Link>
          )}
        </div>
      </section>

      <section className="py-12">
        <h2 className="text-center text-3xl font-bold text-gray-900">Multi-layer verification</h2>
        <div className="mt-10 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {LAYERS.map((layer) => (
            <div key={layer.title} className="rounded-xl bg-white p-6 shadow-sm">
              <layer.icon className="h-10 w-10 text-blue-600" />
              <h3 className="mt-4 text-lg font-semibold text-gray-900">{layer.title}</h3>
              <p className="mt-2 text-gray-600">{layer.text}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="py-12">
        <h2 className="text-center text-3xl font-bold text-gray-900">How a document is checked</h2>
        <ol className="mt-8 flex flex-wrap justify-center gap-2">
          {PIPELINE.map((step, index) => (
            <li key={step} className="flex items-center gap-2 rounded-full border border-blue-100 bg-white px-4 py-2 text-sm text-gray-700">
              <span className="flex h-6 w-6 items-center justify-center rounded-full bg-blue-600 text-xs font-bold text-white">{index + 1}</span>
              {step}
            </li>
          ))}
        </ol>
      </section>

      <section className="py-12">
        <h2 className="text-center text-3xl font-bold text-gray-900">Three clear outcomes</h2>
        <div className="mt-8 grid gap-4 md:grid-cols-3">
          {OUTCOMES.map((outcome) => (
            <div key={outcome.label} className={`rounded-lg border p-6 ${outcome.className}`}>
              <h3 className="text-xl font-bold">{outcome.label}</h3>
              <p className="mt-2">{outcome.text}</p>
            </div>
          ))}
        </div>
        <p className="mx-auto mt-6 max-w-3xl text-center text-sm text-gray-500">
          Supports 10th and 12th marksheets, JEE results, transfer certificates, domicile certificates and Aadhaar cards.
          Results support a human verifier and are not proof of official authenticity.
        </p>
      </section>
    </div>
  )
}
