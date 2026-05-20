import styles from './Header.module.css'
import AdminLogin from './AdminLogin'

const DISCORD_URL = 'https://discord.gg/Bd3TxddY8n'

const NAV_TABS = [
  { id: 'leaderboard', label: 'Leaderboard' },
  { id: 'about',       label: 'About' },
]

export default function Header({ tab, onTabChange, isAdmin, onLogin, onLogout }) {
  return (
    <header className={styles.header}>
      <div className={styles.left}>
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
          <a
            href={DISCORD_URL}
            target="_blank"
            rel="noreferrer"
            className={styles.tab}
          >
            Discord ↗
          </a>
          {isAdmin && (
            <button
              className={`${styles.tab} ${tab === 'admin' ? styles.active : ''}`}
              onClick={() => onTabChange('admin')}
            >
              Admin
            </button>
          )}
        </nav>
      </div>
      <div className={styles.right}>
        <AdminLogin isAdmin={isAdmin} onLogin={onLogin} onLogout={onLogout} />
      </div>
    </header>
  )
}
