import { useState, useEffect } from 'react'
import styles from './AdminForm.module.css'

export default function SyncAdmin({ activeSeason, onSyncStart, onSyncEnd }) {
  const [status, setStatus] = useState(null)
  const [syncing, setSyncing] = useState(false)
  const [result, setResult] = useState(null)

  async function loadStatus() {
    if (!activeSeason) return
    const data = await fetch(`/api/admin/sync/season/${activeSeason.id}/status`, {
      credentials: 'include',
    }).then(r => r.json())
    setStatus(data)
  }

  useEffect(() => { loadStatus() }, [activeSeason?.id])

  async function runSync() {
    setSyncing(true)
    setResult(null)
    onSyncStart?.()
    try {
      const res = await fetch(`/api/admin/sync/season/${activeSeason.id}`, {
        method: 'POST',
        credentials: 'include',
      })
      const data = await res.json()
      if (!res.ok) {
        setResult({ error: data.error ?? `Server error ${res.status}` })
      } else {
        setResult(data)
      }
    } catch (e) {
      setResult({ error: String(e) })
    } finally {
      setSyncing(false)
      onSyncEnd?.()
      loadStatus()
    }
  }

  async function syncPlayer(playerId) {
    await fetch(`/api/admin/sync/season/${activeSeason.id}/player/${playerId}`, {
      method: 'POST',
      credentials: 'include',
    })
    loadStatus()
  }

  if (!activeSeason) return <p className={styles.empty}>No season selected.</p>

  const missingSlug = status?.players?.filter(p => !p.has_slug) ?? []
  const ready = status?.players?.filter(p => p.has_slug) ?? []

  return (
    <div className={styles.root}>
      {/* Sync window */}
      <div className={styles.card}>
        <p className={styles.cardTitle}>Sync window</p>
        <div className={styles.infoRow}>
          <span className={styles.muted}>From</span>
          <span>{status?.sync_from ?? <em className={styles.muted}>not set — update in Seasons tab</em>}</span>
        </div>
        <div className={styles.infoRow}>
          <span className={styles.muted}>To</span>
          <span>{status?.sync_to ?? <em className={styles.muted}>not set — update in Seasons tab</em>}</span>
        </div>
      </div>

      {/* Run sync */}
      <div className={styles.card}>
        <p className={styles.cardTitle}>Run sync</p>
        <p className={styles.hint}>
          Pulls each rostered player's Melee singles results from start.gg within the sync window.
          Tournaments are created automatically. Already-synced entries are updated in place.
        </p>
        <button className={styles.syncBtn} onClick={runSync} disabled={syncing || !status?.sync_from}>
          {syncing ? 'Syncing…' : 'Sync now'}
        </button>

        {syncing && (
          <p className={styles.hint}>Fetching results from start.gg — this can take a minute or two.</p>
        )}

        {result && (
          result.error
            ? <p className={styles.error}>✗ {result.error}</p>
            : <div className={styles.resultBox}>
                <p>✓ Players synced: <strong>{result.players_synced}</strong></p>
                <p>✓ Tournaments created: <strong>{result.tournaments_created}</strong></p>
                <p>✓ Entries upserted: <strong>{result.entries_upserted}</strong></p>
                {result.tournaments_auto_removed > 0 && <p>✓ Duplicate brackets auto-removed: <strong>{result.tournaments_auto_removed}</strong></p>}
                {result.players_skipped > 0 && <p className={styles.warn}>⚠ Players skipped (no slug): {result.players_skipped}</p>}
                {result.entries_pending > 0 && <p className={styles.warn}>⚠ Events with no finalized results yet: {result.entries_pending}</p>}
                {result.errors?.map((e, i) => (
                  <p key={i} className={styles.error}>✗ {e.player}: {e.error}</p>
                ))}
              </div>
        )}
      </div>

      {/* Player coverage */}
      <div className={styles.card}>
        <p className={styles.cardTitle}>Player coverage</p>
        {missingSlug.length > 0 && (
          <div className={styles.warnBox}>
            <p className={styles.warn}>Missing start.gg slug — won't be synced:</p>
            {missingSlug.map(p => <p key={p.id} className={styles.muted}>· {p.display_name}</p>)}
          </div>
        )}
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr><th>Player</th><th className={styles.center}>Entries this season</th><th></th></tr>
            </thead>
            <tbody>
              {ready.map(p => (
                <tr key={p.id}>
                  <td>{p.display_name}</td>
                  <td className={styles.center}>{p.entries_this_season}</td>
                  <td className={styles.actions}>
                    <button className={styles.mutedBtn} onClick={() => syncPlayer(p.id)}>Re-sync</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Synced tournaments */}
      {status?.tournaments?.length > 0 && (
        <div className={styles.card}>
          <p className={styles.cardTitle}>Synced tournaments</p>
          <div className={styles.tableWrap}>
            <table className={styles.table}>
              <thead>
                <tr><th>Tournament</th><th className={styles.center}>Entrants</th><th className={styles.center}>League entries</th><th>Synced at</th></tr>
              </thead>
              <tbody>
                {status.tournaments.map(t => (
                  <tr key={t.id}>
                    <td>{t.name}</td>
                    <td className={styles.center}>{t.total_entrants ?? '—'}</td>
                    <td className={styles.center}>{t.entry_count}</td>
                    <td className={styles.muted}>{t.synced_at ? new Date(t.synced_at).toLocaleDateString() : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
