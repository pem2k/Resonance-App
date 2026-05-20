import { useState, useEffect, useRef } from 'react'
import styles from './AdminLogin.module.css'

export default function AdminLogin({ isAdmin, onLogin, onLogout }) {
  const [open, setOpen] = useState(false)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  const modalRef = useRef(null)

  // Close on outside click
  useEffect(() => {
    if (!open) return
    function handle(e) {
      if (modalRef.current && !modalRef.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', handle)
    return () => document.removeEventListener('mousedown', handle)
  }, [open])

  async function handleLogin(e) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ username, password }),
      })
      if (res.ok) {
        setOpen(false)
        setUsername('')
        setPassword('')
        onLogin()
      } else {
        const data = await res.json()
        setError(data.error ?? 'Login failed')
      }
    } finally {
      setLoading(false)
    }
  }

  async function handleLogout() {
    await fetch('/api/auth/logout', { method: 'POST', credentials: 'include' })
    onLogout()
  }

  if (isAdmin) {
    return (
      <button className={styles.adminBtn} onClick={handleLogout}>
        Admin ·&nbsp;<span className={styles.logout}>Log out</span>
      </button>
    )
  }

  return (
    <>
      <button className={styles.adminBtn} onClick={() => setOpen(true)}>
        Admin
      </button>

      {open && (
        <div className={styles.overlay}>
          <div className={styles.modal} ref={modalRef}>
            <h2 className={styles.title}>Admin Login</h2>
            <form onSubmit={handleLogin} className={styles.form}>
              <input
                className={styles.input}
                type="text"
                placeholder="Username"
                value={username}
                onChange={e => setUsername(e.target.value)}
                autoFocus
                required
              />
              <input
                className={styles.input}
                type="password"
                placeholder="Password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                required
              />
              {error && <p className={styles.error}>{error}</p>}
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
