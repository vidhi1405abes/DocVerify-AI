import { Navigate, Route, Routes } from 'react-router-dom'
import Header from './components/layout/Header/Header'
import Footer from './components/layout/Footer/Footer'
import ProtectedRoute from './components/layout/ProtectedRoute'
import Home from './pages/Home/Home'
import AuthForm from './pages/Auth/AuthForm'
import Verify from './pages/Verify/Verify'
import Results from './pages/Results/Results'
import History from './pages/History/History'
import References from './pages/Admin/References'
import Records from './pages/Admin/Records'

const App = () => {
  return (
    <div className="flex min-h-screen flex-col bg-gray-50">
      <Header />
      <main className="container mx-auto flex-1 px-4">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/login" element={<AuthForm mode="login" />} />
          <Route path="/register" element={<AuthForm mode="register" />} />
          <Route path="/verify" element={<ProtectedRoute><Verify /></ProtectedRoute>} />
          <Route path="/upload" element={<Navigate to="/verify" replace />} />
          <Route path="/results/:id" element={<ProtectedRoute><Results /></ProtectedRoute>} />
          <Route path="/history" element={<ProtectedRoute><History /></ProtectedRoute>} />
          <Route path="/admin/references" element={<ProtectedRoute adminOnly><References /></ProtectedRoute>} />
          <Route path="/admin/records" element={<ProtectedRoute adminOnly><Records /></ProtectedRoute>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
      <Footer />
    </div>
  )
}

export default App
