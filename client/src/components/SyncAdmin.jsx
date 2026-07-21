import { useState, useEffect } from 'react'
import { requestJson } from '../api'
import styles from './AdminForm.module.css'

export default function SyncAdmin({ activeSeason, onSyncStart, onSyncEnd }) {
  const [status, setStatus] = useState(null)
  const [syncing, setSyncing] = useState(false)
  const [result, setResult] = useState(null)

  async function loadStatus() {
    if (!activeSeason) return
    try {
      const data = await requestJson(`/api/admin/sync/season/${activeSeason.id}/status`, {
        credentials: 'include',
      })
      setStatus(data)
    } catch (err) {
      setResult({ error: err.message })
    }
  }

  useEffect(() => { loadStatus() }, [activeSeason?.id])

  // Sync runs as a background job on the server (it can take minutes).
  // POST returns 202 immediately; poll the job endpoint until it finishes.
  async function pollJob() {
    for (;;) {
      await new Promise(r => setTimeout(r, 3000))
      const job = await requestJson(`/api/admin/sync/season/${activeSeason.id}/job`, {
        credentials: 'include',
      })
      if (!job.running) {
        return job.error ? { error: job.error } : (job.result ?? {})
      }
    }
  }

  async function startJob(url) {
    setSyncing(true)
    setResult(null)
    onSyncStart?.()
    try {
      await requestJson(url, { method: 'POST', credentials: 'include' })
      setResult(await pollJob())
    } catch (e) {
      setResult({ error: e.message })
    } finally {
      setSyncing(false)
      onSyncEnd?.()
      loadStatus()
    }
  }

  const runSync = () => startJob(`/api/admin/sync/season/${activeSeason.id}`)
  const syncPlayer = (playerId) =>
    startJob(`/api/admin/sync/season/${activeSeason.id}/player/${playerId}`)

  if (!activeSeason) return <p className={styles.empty}>No season selected.</p>

  const missingSlug = status?.players?.filter(p => !(p.has_source ?? p.has_slug)) ?? []
  const ready = status?.players?.filter(p => p.has_source ?? p.has_slug) ?? []

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
          Pulls each rostered player's Melee singles results from start.gg and Parry.gg within the sync window.
          Tournaments are created automatically. Already-synced entries are updated in place.
        </p>
        <button className={styles.syncBtn} onClick={runSync} disabled={syncing || !status?.sync_from}>
          {syncing ? 'Syncing…' : 'Sync now'}
        </button>

        {syncing && (
          <p className={styles.hint}>Fetching results from start.gg and Parry.gg — this can take a minute or two.</p>
        )}

        {result && (
          result.error
            ? <p className={styles.error} role="alert">✗ {result.error}</p>
            : <div className={styles.resultBox} role="status" aria-live="polite">
                <p>✓ Players synced: <strong>{result.players_synced}</strong></p>
                <p>✓ Tournaments created: <strong>{result.tournaments_created}</strong></p>
                <p>✓ Entries upserted: <strong>{result.entries_upserted}</strong></p>
                {result.tournaments_auto_removed > 0 && <p>✓ Duplicate brackets auto-removed: <strong>{result.tournaments_auto_removed}</strong></p>}
                {result.players_skipped > 0 && <p className={styles.warn}>⚠ Players skipped (no tournament profile): {result.players_skipped}</p>}
                {result.entries_pending > 0 && <p className={styles.warn}>⚠ Events with no finalized results yet: {result.entries_pending}</p>}
                {result.errors?.map((e, i) => (
                  <p key={i} className={styles.error} role="alert">✗ {e.player}{e.source ? ` (${e.source})` : ''}: {e.error}</p>
                ))}
              </div>
        )}
      </div>

      {/* Player coverage */}
      <div className={styles.card}>
        <p className={styles.cardTitle}>Player coverage</p>
        {missingSlug.length > 0 && (
          <div className={styles.warnBox}>
            <p className={styles.warn}>Missing start.gg slug and Parry.gg profile — won't be synced:</p>
            {missingSlug.map(p => <p key={p.id} className={styles.muted}>· {p.display_name}</p>)}
          </div>
        )}
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr><th>Player</th><th>Sources</th><th className={styles.center}>Entries this season</th><th><span className={styles.srOnly}>Actions</span></th></tr>
            </thead>
            <tbody>
              {ready.map(p => (
                <tr key={p.id}>
                  <td>{p.display_name}</td>
                  <td className={styles.muted}>
                    {[p.startgg_slug && 'start.gg', p.parrygg_id && 'Parry.gg'].filter(Boolean).join(' + ')}
                  </td>
                  <td className={styles.center}>{p.entries_this_season}</td>
                  <td className={styles.actions}>
                    <button className={styles.mutedBtn} onClick={() => syncPlayer(p.id)} disabled={syncing}>Re-sync</button>
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
                <tr><th>Tournament</th><th>Sources</th><th className={styles.center}>Entrants</th><th className={styles.center}>League entries</th><th>Synced at</th></tr>
              </thead>
              <tbody>
                {status.tournaments.map(t => (
                  <tr key={t.id}>
                    <td>{t.name}</td>
                    <td className={styles.muted}>{t.sources?.join(' + ') || 'Manual'}</td>
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
