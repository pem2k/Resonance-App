import { useEffect, useState } from 'react'
import SeasonAdmin from './SeasonAdmin'
import PlayerAdmin from './PlayerAdmin'
import SyncAdmin from './SyncAdmin'
import TournamentAdmin from './TournamentAdmin'
import ImportAdmin from './ImportAdmin'
import styles from './AdminPanel.module.css'

const SECTIONS = [
  { id: 'seasons',     label: 'Seasons' },
  { id: 'players',     label: 'Teams & Players' },
  { id: 'sync',        label: 'Sync' },
  { id: 'tournaments', label: 'Tournaments' },
  { id: 'import',      label: 'Import' },
]

export default function AdminPanel({ seasons, onSeasonsChange }) {
  const [section, setSection] = useState('seasons')
  const [activeSeason, setActiveSeason] = useState(seasons[0] ?? null)
  const [syncCount, setSyncCount] = useState(0)

  useEffect(() => {
    setActiveSeason(current => {
      if (!current) return seasons[0] ?? null
      return seasons.find(season => season.id === current.id) ?? seasons[0] ?? null
    })
  }, [seasons])

  function onSyncStart() { setSyncCount(n => n + 1) }
  function onSyncEnd()   { setSyncCount(n => Math.max(0, n - 1)) }
  const isSyncing = syncCount > 0

  return (
    <div className={styles.root}>
      <div className={styles.header}>
        <h1 className={styles.title}>
          Admin Panel
          {isSyncing && (
            <span className={styles.syncIndicator} title="Sync in progress…">
              <span className={styles.arrowCW}>↻</span>
              <span className={styles.arrowCCW}>↺</span>
            </span>
          )}
        </h1>
        {activeSeason && (
          <div className={styles.seasonPicker}>
            <label>Season</label>
            <select
              value={activeSeason.id}
              onChange={e => setActiveSeason(seasons.find(s => s.id === +e.target.value))}
            >
              {seasons.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </div>
        )}
      </div>

      <nav className={styles.tabs}>
        {SECTIONS.map(s => (
          <button
            key={s.id}
            className={`${styles.tab} ${section === s.id ? styles.active : ''}`}
            onClick={() => setSection(s.id)}
          >
            {s.label}
          </button>
        ))}
      </nav>

      <div className={styles.body}>
        {section === 'seasons'     && <SeasonAdmin seasons={seasons} activeSeason={activeSeason} setActiveSeason={setActiveSeason} onSeasonsChange={onSeasonsChange} onSyncStart={onSyncStart} onSyncEnd={onSyncEnd} />}
        {section === 'players'     && <PlayerAdmin activeSeason={activeSeason} />}
        {section === 'sync'        && <SyncAdmin activeSeason={activeSeason} onSyncStart={onSyncStart} onSyncEnd={onSyncEnd} />}
        {section === 'tournaments' && activeSeason && <TournamentAdmin seasonId={activeSeason.id} />}
        {section === 'tournaments' && !activeSeason && <p className={styles.empty}>No season selected.</p>}
        {section === 'import'      && <ImportAdmin activeSeason={activeSeason} />}
      </div>
    </div>
  )
}
