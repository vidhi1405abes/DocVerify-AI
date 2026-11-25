import { Loader2 } from 'lucide-react'

const Spinner = ({ label }) => (
  <div className="flex items-center gap-3 text-gray-600" role="status">
    <Loader2 className="h-5 w-5 animate-spin text-blue-600" />
    {label && <span>{label}</span>}
  </div>
)

export default Spinner
