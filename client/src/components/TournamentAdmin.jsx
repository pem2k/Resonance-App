import { useState, useEffect } from 'react'
import styles from './TournamentAdmin.module.css'

export default function TournamentAdmin({ seasonId }) {
  const [tournaments, setTournaments] = useState([])
  const [removed, setRemoved] = useState([])
  const [loading, setLoading] = useState(true)
  const [acting, setActing] = useState(null)

  async function load() {
    setLoading(true)
    const [active, gone] = await Promise.all([
      fetch(`/api/seasons/${seasonId}/tournaments`).then(r => r.json()),
      fetch(`/api/admin/seasons/${seasonId}/removed-tournaments`, { credentials: 'include' }).then(r => r.json()),
    ])
    setTournaments(active)
    setRemoved(gone)
    setLoading(false)
  }

  useEffect(() => { load() }, [seasonId])

  async function handleRemove(t) {
    if (!confirm(`Remove "${t.name}"? It will be excluded from standings and future syncs, but can be restored.`)) return
    setActing(t.id)
    await fetch(`/api/admin/tournaments/${t.id}`, {
      method: 'DELETE',
      credentials: 'include',
    })
    setActing(null)
    load()
  }

  async function handleRestore(t) {
    setActing(t.id)
    await fetch(`/api/admin/tournaments/${t.id}/restore`, {
      method: 'POST',
      credentials: 'include',
    })
    setActing(null)
    load()
  }

  return (
    <section className={styles.section}>
      <h2 className={styles.heading}>Tournament Management</h2>
      <p className={styles.hint}>
        Remove online events or tournaments that shouldn't count toward points.
        Removed tournaments are excluded from standings and future syncs but can be restored.
      </p>

      {loading ? (
        <p className={styles.muted}>Loading…</p>
      ) : (
        <>
          {tournaments.length === 0 ? (
            <p className={styles.muted}>No tournaments synced yet.</p>
          ) : (
            <div className={styles.tableWrap}>
              <div className={tournaments.length > 10 ? styles.scrollBody : undefined}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th>Tournament</th>
                    <th className={styles.center}>Date</th>
                    <th className={styles.center}>Entrants</th>
                    <th className={styles.center}>Entries</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {tournaments
                    .slice()
                    .sort((a, b) => (b.date ?? '').localeCompare(a.date ?? ''))
                    .map(t => (
                      <tr key={t.id}>
                        <td className={styles.name}>
                          {t.startgg_slug
                            ? <a href={`https://www.start.gg/${t.startgg_slug}`} target="_blank" rel="noreferrer">{t.name}</a>
                            : t.name
                          }
                        </td>
                        <td className={`${styles.secondary} ${styles.center}`}>{t.date ?? '—'}</td>
                        <td className={`${styles.secondary} ${styles.center}`}>{t.total_entrants ?? '—'}</td>
                        <td className={`${styles.secondary} ${styles.center}`}>{t.entry_count ?? '—'}</td>
                        <td className={styles.actions}>
                          <button
                            className={styles.deleteBtn}
                            onClick={() => handleRemove(t)}
                            disabled={acting === t.id}
                          >
                            {acting === t.id ? '…' : 'Remove'}
                          </button>
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
              </div>
            </div>
          )}

          {removed.length > 0 && (
            <>
              <h2 className={`${styles.heading} ${styles.removedHeading}`}>Removed Tournaments</h2>
              <div className={styles.tableWrap}>
                <div className={removed.length > 10 ? styles.scrollBody : undefined}>
                <table className={styles.table}>
                  <thead>
                    <tr>
                      <th>Tournament</th>
                      <th className={styles.center}>Date</th>
                      <th className={styles.center}>Entrants</th>
                      <th className={styles.center}>Entries</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {removed
                      .slice()
                      .sort((a, b) => (b.date ?? '').localeCompare(a.date ?? ''))
                      .map(t => (
                        <tr key={t.id}>
                          <td className={`${styles.name} ${styles.removedName}`}>
                            {t.startgg_slug
                              ? <a href={`https://www.start.gg/${t.startgg_slug}`} target="_blank" rel="noreferrer">{t.name}</a>
                              : t.name
                            }
                          </td>
                          <td className={`${styles.secondary} ${styles.center}`}>{t.date ?? '—'}</td>
                          <td className={`${styles.secondary} ${styles.center}`}>{t.total_entrants ?? '—'}</td>
                          <td className={`${styles.secondary} ${styles.center}`}>{t.entry_count ?? '—'}</td>
                          <td className={styles.actions}>
                            <button
                              className={styles.restoreBtn}
                              onClick={() => handleRestore(t)}
                              disabled={acting === t.id}
                            >
                              {acting === t.id ? '…' : 'Restore'}
                            </button>
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
                </div>
              </div>
            </>
          )}
        </>
      )}
    </section>
  )
}
