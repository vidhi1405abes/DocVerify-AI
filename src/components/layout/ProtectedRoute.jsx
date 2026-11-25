import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '@/context/useAuth'
import Spinner from '@/components/ui/Spinner'

const ProtectedRoute = ({ children, adminOnly = false }) => {
  const { isAuthenticated, isAdmin, checking } = useAuth()
  const location = useLocation()

  if (checking) {
    return (
      <div className="flex justify-center py-24">
        <Spinner label="Checking your session..." />
      </div>
    )
  }
  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }
  if (adminOnly && !isAdmin) {
    return <Navigate to="/verify" replace />
  }
  return children
}

export default ProtectedRoute
