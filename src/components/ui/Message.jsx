import { AlertCircle, CheckCircle2 } from 'lucide-react'
import { Alert, AlertDescription } from '@/components/ui/alert'

const STYLES = {
  error: { box: 'bg-red-50 border border-red-200', text: 'text-red-800', Icon: AlertCircle, icon: 'text-red-600' },
  success: { box: 'bg-green-50 border border-green-200', text: 'text-green-800', Icon: CheckCircle2, icon: 'text-green-600' },
}

const Message = ({ type = 'error', children, className = '' }) => {
  if (!children) return null
  const style = STYLES[type]
  return (
    <Alert className={`${style.box} ${className}`} role={type === 'error' ? 'alert' : 'status'}>
      <style.Icon className={`h-4 w-4 shrink-0 ${style.icon}`} />
      <AlertDescription className={`ml-2 ${style.text}`}>{children}</AlertDescription>
    </Alert>
  )
}

export default Message
