import { useState } from 'react'
import { Link, NavLink, useNavigate } from 'react-router-dom'
import { LogOut, Menu, ShieldCheck, X } from 'lucide-react'
import { useAuth } from '@/context/useAuth'

const linkClass = ({ isActive }) =>
  `block rounded-md px-3 py-2 text-sm font-medium ${
    isActive ? 'bg-blue-50 text-blue-700' : 'text-gray-600 hover:bg-gray-50 hover:text-blue-600'
  }`

const Header = () => {
  const { user, isAdmin, logout } = useAuth()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)

  const links = user
    ? [
        { to: '/verify', label: 'Verify' },
        { to: '/history', label: 'History' },
        ...(isAdmin
          ? [
              { to: '/admin/references', label: 'Reference documents' },
              { to: '/admin/records', label: 'Authorized records' },
            ]
          : []),
      ]
    : [{ to: '/', label: 'Home' }]

  const handleLogout = () => {
    logout()
    setOpen(false)
    navigate('/')
  }

  return (
    <header className="sticky top-0 z-40 border-b border-gray-200 bg-white/95 backdrop-blur">
      <nav className="container mx-auto flex items-center justify-between px-4 py-3">
        <Link to="/" className="flex items-center gap-2 text-xl font-bold text-blue-600">
          <ShieldCheck className="h-7 w-7" />
          DocVerify AI
        </Link>

        <div className="hidden items-center gap-1 lg:flex">
          {links.map((link) => (
            <NavLink key={link.to} to={link.to} className={linkClass}>
              {link.label}
            </NavLink>
          ))}
        </div>

        <div className="hidden items-center gap-3 lg:flex">
          {user ? (
            <>
              <span className="text-sm text-gray-600">
                {user.name}
                {isAdmin && <span className="ml-2 rounded bg-blue-100 px-1.5 py-0.5 text-xs text-blue-700">Admin</span>}
              </span>
              <button
                type="button"
                onClick={handleLogout}
                className="flex items-center gap-1 rounded-md px-3 py-2 text-sm font-medium text-gray-600 hover:bg-gray-50"
              >
                <LogOut className="h-4 w-4" /> Sign out
              </button>
            </>
          ) : (
            <>
              <Link to="/login" className="rounded-md px-3 py-2 text-sm font-medium text-gray-600 hover:text-blue-600">
                Sign in
              </Link>
              <Link to="/register" className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">
                Create account
              </Link>
            </>
          )}
        </div>

        <button
          type="button"
          className="rounded-md p-2 text-gray-600 lg:hidden"
          onClick={() => setOpen((value) => !value)}
          aria-label={open ? 'Close menu' : 'Open menu'}
          aria-expanded={open}
        >
          {open ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
        </button>
      </nav>

      {open && (
        <div className="border-t border-gray-100 px-4 pb-4 lg:hidden">
          {links.map((link) => (
            <NavLink key={link.to} to={link.to} className={linkClass} onClick={() => setOpen(false)}>
              {link.label}
            </NavLink>
          ))}
          {user ? (
            <button type="button" onClick={handleLogout} className="mt-2 block w-full rounded-md px-3 py-2 text-left text-sm font-medium text-gray-600 hover:bg-gray-50">
              Sign out ({user.name})
            </button>
          ) : (
            <>
              <NavLink to="/login" className={linkClass} onClick={() => setOpen(false)}>Sign in</NavLink>
              <NavLink to="/register" className={linkClass} onClick={() => setOpen(false)}>Create account</NavLink>
            </>
          )}
        </div>
      )}
    </header>
  )
}

export default Header
