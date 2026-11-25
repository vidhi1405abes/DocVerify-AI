export const VERDICT_STYLES = {
  verified: {
    badge: 'bg-green-100 text-green-800 ring-green-600/20',
    panel: 'bg-green-50 border-green-200 text-green-900',
    bar: 'bg-green-500',
  },
  review: {
    badge: 'bg-amber-100 text-amber-800 ring-amber-600/20',
    panel: 'bg-amber-50 border-amber-200 text-amber-900',
    bar: 'bg-amber-500',
  },
  suspicious: {
    badge: 'bg-red-100 text-red-800 ring-red-600/20',
    panel: 'bg-red-50 border-red-200 text-red-900',
    bar: 'bg-red-500',
  },
}

export const VERDICT_LABELS = {
  verified: 'Verified',
  review: 'Requires Review',
  suspicious: 'Suspicious',
}

export const STATUS_STYLES = {
  pass: { label: 'Passed', className: 'bg-green-100 text-green-800' },
  warn: { label: 'Warning', className: 'bg-amber-100 text-amber-800' },
  fail: { label: 'Failed', className: 'bg-red-100 text-red-800' },
  skipped: { label: 'Not run', className: 'bg-gray-100 text-gray-600' },
}

export const formatDateTime = (value) =>
  new Date(value).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
