import { useState, useEffect } from 'react'
import { requestJson } from '../api'
import styles from './TournamentAdmin.module.css'

function tournamentUrl(tournament) {
  if (tournament.startgg_slug) return `https://www.start.gg/${tournament.startgg_slug}`
  if (tournament.parrygg_slug) return `https://parry.gg/${tournament.parrygg_slug}`
  return null
}

function TournamentName({ tournament }) {
  const url = tournamentUrl(tournament)
  return url
    ? <a href={url} target="_blank" rel="noreferrer">{tournament.name}</a>
    : tournament.name
}

export default function TournamentAdmin({ seasonId }) {
  const [tournaments, setTournaments] = useState([])
  const [removed, setRemoved] = useState([])
  const [loading, setLoading] = useState(true)
  const [acting, setActing] = useState(null)
  const [error, setError] = useState(null)

  async function load() {
    setLoading(true)
    try {
      const [active, gone] = await Promise.all([
        requestJson(`/api/seasons/${seasonId}/tournaments`),
        requestJson(`/api/admin/seasons/${seasonId}/removed-tournaments`, { credentials: 'include' }),
      ])
      setTournaments(active)
      setRemoved(gone)
      setError(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [seasonId])

  async function handleRemove(t) {
    if (!window.confirm(`Remove "${t.name}"? It will be excluded from standings and future syncs, but can be restored.`)) return
    setActing(t.id)
    try {
      await requestJson(`/api/admin/tournaments/${t.id}`, {
        method: 'DELETE',
        credentials: 'include',
      })
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setActing(null)
    }
  }

  async function handleRestore(t) {
    setActing(t.id)
    try {
      await requestJson(`/api/admin/tournaments/${t.id}/restore`, {
        method: 'POST',
        credentials: 'include',
      })
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setActing(null)
    }
  }

  return (
    <section className={styles.section}>
      <h2 className={styles.heading}>Tournament Management</h2>
      <p className={styles.hint}>
        Remove online events or tournaments that shouldn't count toward points.
        Removed tournaments are excluded from standings and future syncs but can be restored.
      </p>
      {error && <p className={styles.error} role="alert">{error}</p>}

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
                    <th><span className={styles.srOnly}>Actions</span></th>
                  </tr>
                </thead>
                <tbody>
                  {tournaments
                    .slice()
                    .sort((a, b) => (b.date ?? '').localeCompare(a.date ?? ''))
                    .map(t => (
                      <tr key={t.id}>
                        <td className={styles.name}>
                          <TournamentName tournament={t} />
                        </td>
                        <td className={`${styles.secondary} ${styles.center}`}>{t.date ?? '—'}</td>
                        <td className={`${styles.secondary} ${styles.center}`}>{t.total_entrants ?? '—'}</td>
                        <td className={`${styles.secondary} ${styles.center}`}>{t.entry_count ?? '—'}</td>
                        <td className={styles.actions}>
                          <button
                            className={styles.deleteBtn}
                            onClick={() => handleRemove(t)}
                            disabled={acting !== null}
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
                      <th><span className={styles.srOnly}>Actions</span></th>
                    </tr>
                  </thead>
                  <tbody>
                    {removed
                      .slice()
                      .sort((a, b) => (b.date ?? '').localeCompare(a.date ?? ''))
                      .map(t => (
                        <tr key={t.id}>
                          <td className={`${styles.name} ${styles.removedName}`}>
                            <TournamentName tournament={t} />
                          </td>
                          <td className={`${styles.secondary} ${styles.center}`}>{t.date ?? '—'}</td>
                          <td className={`${styles.secondary} ${styles.center}`}>{t.total_entrants ?? '—'}</td>
                          <td className={`${styles.secondary} ${styles.center}`}>{t.entry_count ?? '—'}</td>
                          <td className={styles.actions}>
                            <button
                              className={styles.restoreBtn}
                              onClick={() => handleRestore(t)}
                              disabled={acting !== null}
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
