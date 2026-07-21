import styles from './Header.module.css'
import AdminLogin from './AdminLogin'
import HeaderExternalLinks from './HeaderExternalLinks.mjs'

const NAV_TABS = [
  { id: 'leaderboard', label: 'Leaderboard' },
  { id: 'about',       label: 'About' },
]

export default function Header({ tab, onTabChange, isAdmin, onLogin, onLogout }) {
  return (
    <header className={styles.header}>
      <span className={styles.logo}>RESONANCE</span>
      <nav className={styles.nav}>
        {NAV_TABS.map(t => (
          <button
            key={t.id}
            className={`${styles.tab} ${tab === t.id ? styles.active : ''}`}
            onClick={() => onTabChange(t.id)}
          >
            {t.label}
          </button>
        ))}
        <HeaderExternalLinks className={styles.tab} />
        {isAdmin && (
          <button
            className={`${styles.tab} ${tab === 'admin' ? styles.active : ''}`}
            onClick={() => onTabChange('admin')}
          >
            Admin
          </button>
        )}
      </nav>
      <div className={styles.right}>
        <AdminLogin isAdmin={isAdmin} onLogin={onLogin} onLogout={onLogout} />
      </div>
    </header>
  )
}
