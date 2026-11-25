import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { ShieldCheck } from 'lucide-react'
import { useAuth } from '@/context/useAuth'
import Message from '@/components/ui/Message'

const inputClass =
  'mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500'

const AuthForm = ({ mode }) => {
  const isRegister = mode === 'register'
  const { login, register } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [form, setForm] = useState({ name: '', email: '', password: '' })
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const update = (field) => (event) => setForm((current) => ({ ...current, [field]: event.target.value }))

  const handleSubmit = async (event) => {
    event.preventDefault()
    setError('')
    if (isRegister && form.password.length < 8) {
      setError('Password must be at least 8 characters.')
      return
    }
    setSubmitting(true)
    try {
      if (isRegister) await register(form.name.trim(), form.email.trim(), form.password)
      else await login(form.email.trim(), form.password)
      navigate(location.state?.from ?? '/verify', { replace: true })
    } catch (submitError) {
      setError(submitError.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="mx-auto max-w-md py-12">
      <div className="mb-8 text-center">
        <ShieldCheck className="mx-auto h-12 w-12 text-blue-600" />
        <h1 className="mt-4 text-3xl font-bold text-gray-900">
          {isRegister ? 'Create your account' : 'Sign in to DocVerify AI'}
        </h1>
        <p className="mt-2 text-sm text-gray-600">
          {isRegister
            ? 'The first account created becomes the administrator.'
            : 'Verify documents and see your verification history.'}
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5 rounded-lg border border-gray-200 bg-white p-6 shadow-sm" noValidate>
        <Message>{error}</Message>
        {isRegister && (
          <label className="block text-sm font-medium text-gray-700">
            Full name
            <input className={inputClass} value={form.name} onChange={update('name')} required autoComplete="name" />
          </label>
        )}
        <label className="block text-sm font-medium text-gray-700">
          Email
          <input className={inputClass} type="email" value={form.email} onChange={update('email')} required autoComplete="email" />
        </label>
        <label className="block text-sm font-medium text-gray-700">
          Password
          <input
            className={inputClass}
            type="password"
            value={form.password}
            onChange={update('password')}
            required
            autoComplete={isRegister ? 'new-password' : 'current-password'}
          />
          {isRegister && <span className="mt-1 block text-xs font-normal text-gray-500">At least 8 characters.</span>}
        </label>
        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-md bg-blue-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {submitting ? 'Please wait...' : isRegister ? 'Create account' : 'Sign in'}
        </button>
        <p className="text-center text-sm text-gray-600">
          {isRegister ? 'Already have an account? ' : 'New to DocVerify AI? '}
          <Link to={isRegister ? '/login' : '/register'} state={location.state} className="font-medium text-blue-600 hover:text-blue-700">
            {isRegister ? 'Sign in' : 'Create an account'}
          </Link>
        </p>
      </form>
    </div>
  )
}

export default AuthForm
