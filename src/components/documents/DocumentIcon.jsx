import { FileCheck, FileText, GraduationCap, IdCard, ScrollText } from 'lucide-react'

const ICONS = {
  marksheet10: [GraduationCap, 'text-blue-500'],
  marksheet12: [GraduationCap, 'text-green-500'],
  jeeResult: [ScrollText, 'text-purple-500'],
  tc: [FileText, 'text-orange-500'],
  domicile: [FileCheck, 'text-red-500'],
  aadhaar: [IdCard, 'text-teal-600'],
}

const DocumentIcon = ({ type }) => {
  const [Icon, color] = ICONS[type] ?? [FileText, 'text-gray-500']
  return <Icon className={`h-6 w-6 ${color}`} />
}

export default DocumentIcon
