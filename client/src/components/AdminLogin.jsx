import { useState, useEffect, useRef } from 'react'
import { requestJson } from '../api'
import styles from './AdminLogin.module.css'

export default function AdminLogin({ isAdmin, onLogin, onLogout }) {
  const [open, setOpen] = useState(false)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  const modalRef = useRef(null)
  const triggerRef = useRef(null)

  function closeModal() {
    setOpen(false)
    requestAnimationFrame(() => triggerRef.current?.focus())
  }

  useEffect(() => {
    if (!open) return
    function handleMouseDown(e) {
      if (modalRef.current && !modalRef.current.contains(e.target)) closeModal()
    }
    function handleKeyDown(e) {
      if (e.key === 'Escape') {
        closeModal()
        return
      }
      if (e.key !== 'Tab' || !modalRef.current) return
      const focusable = [...modalRef.current.querySelectorAll('button, input')]
        .filter(element => !element.disabled)
      if (focusable.length === 0) return
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault()
        last.focus()
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault()
        first.focus()
      }
    }
    document.addEventListener('mousedown', handleMouseDown)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('mousedown', handleMouseDown)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [open])

  async function handleLogin(e) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await requestJson('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ username, password }),
      })
      closeModal()
      setUsername('')
      setPassword('')
      onLogin()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleLogout() {
    setLoading(true)
    setError(null)
    try {
      await requestJson('/api/auth/logout', { method: 'POST', credentials: 'include' })
      onLogout()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  if (isAdmin) {
    return (
      <>
        <button className={styles.adminBtn} onClick={handleLogout} disabled={loading} title={error ?? undefined}>
          Admin ·&nbsp;<span className={styles.logout}>{error ? 'Logout failed' : loading ? 'Logging out…' : 'Log out'}</span>
        </button>
      </>
    )
  }

  return (
    <>
      <button ref={triggerRef} className={styles.adminBtn} onClick={() => { setError(null); setOpen(true) }}>
        Admin
      </button>

      {open && (
        <div className={styles.overlay}>
          <div className={styles.modal} ref={modalRef} role="dialog" aria-modal="true" aria-labelledby="admin-login-title">
            <button className={styles.closeBtn} type="button" onClick={closeModal} aria-label="Close admin login">×</button>
            <h2 className={styles.title} id="admin-login-title">Admin Login</h2>
            <form onSubmit={handleLogin} className={styles.form}>
              <label className={styles.srOnly} htmlFor="admin-username">Username</label>
              <input
                id="admin-username"
                className={styles.input}
                type="text"
                placeholder="Username"
                value={username}
                onChange={e => setUsername(e.target.value)}
                autoFocus
                required
              />
              <label className={styles.srOnly} htmlFor="admin-password">Password</label>
              <input
                id="admin-password"
                className={styles.input}
                type="password"
                placeholder="Password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                required
              />
              {error && <p className={styles.error} role="alert">{error}</p>}
              <button className={styles.submit} type="submit" disabled={loading}>
                {loading ? 'Logging in…' : 'Log in'}
              </button>
            </form>
          </div>
        </div>
      )}
    </>
  )
}
