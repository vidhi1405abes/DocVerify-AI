import { useCallback, useEffect, useMemo, useState } from 'react'
import * as authApi from '@/services/api/authApi'
import { getToken, setToken, SESSION_EXPIRED_EVENT } from '@/services/api/client'
import { AuthContext } from './useAuth'

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null)
  const [checking, setChecking] = useState(() => Boolean(getToken()))

  useEffect(() => {
    if (!getToken()) return undefined
    let current = true
    authApi
      .getCurrentUser()
      .then((data) => current && setUser(data.user))
      .catch(() => current && setToken(null))
      .finally(() => current && setChecking(false))
    return () => {
      current = false
    }
  }, [])

  useEffect(() => {
    const onExpired = () => setUser(null)
    window.addEventListener(SESSION_EXPIRED_EVENT, onExpired)
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, onExpired)
  }, [])

  const startSession = useCallback((data) => {
    setToken(data.token)
    setUser(data.user)
    return data.user
  }, [])

  const login = useCallback(
    async (email, password) => startSession(await authApi.login(email, password)),
    [startSession]
  )

  const register = useCallback(
    async (name, email, password) => startSession(await authApi.register(name, email, password)),
    [startSession]
  )

  const logout = useCallback(() => {
    setToken(null)
    setUser(null)
  }, [])

  const value = useMemo(
    () => ({
      user,
      checking,
      isAuthenticated: Boolean(user),
      isAdmin: user?.role === 'admin',
      login,
      register,
      logout,
    }),
    [user, checking, login, register, logout]
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
