import { useState } from 'react'
import styles from './AdminForm.module.css'

export default function SeasonAdmin({ seasons, activeSeason, setActiveSeason, onSeasonsChange, onSyncStart, onSyncEnd }) {
  const [creating, setCreating] = useState(false)
  const [form, setForm] = useState({ name: '', start_date: '', end_date: '', sync_from: '', sync_to: '', status: 'draft' })
  const [editing, setEditing] = useState({})
  const [saving, setSaving] = useState(false)
  const [syncing, setSyncing] = useState(null)   // season id currently syncing
  const [syncResults, setSyncResults] = useState({})  // season id → result
  const [msg, setMsg] = useState(null)

  function field(key, value) {
    setForm(f => ({ ...f, [key]: value }))
  }

  async function createSeason(e) {
    e.preventDefault()
    setSaving(true)
    const res = await fetch('/api/admin/seasons', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form),
    })
    const data = await res.json()
    setSaving(false)
    if (res.ok) {
      setMsg('Season created.')
      setCreating(false)
      setForm({ name: '', start_date: '', end_date: '', sync_from: '', sync_to: '', status: 'draft' })
      onSeasonsChange()
    } else {
      setMsg(data.error ?? 'Error creating season.')
    }
  }

  async function updateSeason(season) {
    setSaving(true)
    const patch = editing[season.id] ?? {}
    const res = await fetch(`/api/admin/seasons/${season.id}`, {
      method: 'PUT',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patch),
    })
    setSaving(false)
    if (res.ok) {
      setMsg(`${season.name} updated.`)
      onSeasonsChange()
    }
  }

  async function runSync(season) {
    setSyncing(season.id)
    setSyncResults(r => ({ ...r, [season.id]: null }))
    onSyncStart?.()
    try {
      const res = await fetch(`/api/admin/sync/season/${season.id}`, {
        method: 'POST',
        credentials: 'include',
      })
      const data = await res.json()
      setSyncResults(r => ({ ...r, [season.id]: res.ok ? data : { error: data.error ?? `Server error ${res.status}` } }))
    } catch (e) {
      setSyncResults(r => ({ ...r, [season.id]: { error: String(e) } }))
    } finally {
      setSyncing(null)
      onSyncEnd?.()
    }
  }

  function editField(seasonId, key, value) {
    setEditing(e => ({ ...e, [seasonId]: { ...(e[seasonId] ?? {}), [key]: value } }))
  }

  function val(season, key) {
    return editing[season.id]?.[key] ?? season[key] ?? ''
  }

  return (
    <div className={styles.root}>
      {msg && <p className={styles.msg}>{msg}</p>}

      {/* Existing seasons */}
      {seasons.map(season => (
        <div key={season.id} className={styles.card}>
          <div className={styles.cardHeader}>
            <span className={styles.cardTitle}>{season.name}</span>
            <span className={`${styles.pill} ${styles[season.status]}`}>{season.status}</span>
          </div>
          <div className={styles.grid}>
            <label>Status
              <select value={val(season, 'status')} onChange={e => editField(season.id, 'status', e.target.value)}>
                <option value="draft">draft</option>
                <option value="active">active</option>
                <option value="completed">completed</option>
              </select>
            </label>
            <label>Start date
              <input type="date" value={val(season, 'start_date')} onChange={e => editField(season.id, 'start_date', e.target.value)} />
            </label>
            <label>End date
              <input type="date" value={val(season, 'end_date')} onChange={e => editField(season.id, 'end_date', e.target.value)} />
            </label>
            <label>Sync from
              <input type="date" value={val(season, 'sync_from')} onChange={e => editField(season.id, 'sync_from', e.target.value)} />
            </label>
            <label>Sync to
              <input type="date" value={val(season, 'sync_to')} onChange={e => editField(season.id, 'sync_to', e.target.value)} />
            </label>
          </div>
          <div className={styles.row}>
            <button className={styles.saveBtn} onClick={() => updateSeason(season)} disabled={saving}>
              Save changes
            </button>
            <button
              className={styles.syncBtn}
              onClick={() => runSync(season)}
              disabled={syncing === season.id || !season.sync_from}
              title={!season.sync_from ? 'Set sync dates first' : undefined}
            >
              {syncing === season.id ? 'Syncing…' : 'Sync now'}
            </button>
          </div>

          {syncing === season.id && (
            <p className={styles.hint}>Fetching results from start.gg — this can take a minute or two.</p>
          )}

          {syncResults[season.id] && (
            syncResults[season.id].error
              ? <p className={styles.error}>✗ {syncResults[season.id].error}</p>
              : <div className={styles.resultBox}>
                  <p>✓ Players synced: <strong>{syncResults[season.id].players_synced}</strong></p>
                  <p>✓ Tournaments created: <strong>{syncResults[season.id].tournaments_created}</strong></p>
                  <p>✓ Entries upserted: <strong>{syncResults[season.id].entries_upserted}</strong></p>
                  {syncResults[season.id].tournaments_auto_removed > 0 && (
                    <p>✓ Duplicate brackets auto-removed: <strong>{syncResults[season.id].tournaments_auto_removed}</strong></p>
                  )}
                  {syncResults[season.id].players_skipped > 0 && (
                    <p className={styles.warn}>⚠ Players skipped (no slug): {syncResults[season.id].players_skipped}</p>
                  )}
                  {syncResults[season.id].entries_pending > 0 && (
                    <p className={styles.warn}>⚠ Events with no finalized results yet: {syncResults[season.id].entries_pending}</p>
                  )}
                  {syncResults[season.id].errors?.map((e, i) => (
                    <p key={i} className={styles.error}>✗ {e.player}: {e.error}</p>
                  ))}
                </div>
          )}
        </div>
      ))}

      {/* New season form */}
      {creating ? (
        <form className={styles.card} onSubmit={createSeason}>
          <p className={styles.cardTitle}>New Season</p>
          <div className={styles.grid}>
            <label>Name
              <input value={form.name} onChange={e => field('name', e.target.value)} placeholder="Season 1" required />
            </label>
            <label>Status
              <select value={form.status} onChange={e => field('status', e.target.value)}>
                <option value="draft">draft</option>
                <option value="active">active</option>
              </select>
            </label>
            <label>Start date
              <input type="date" value={form.start_date} onChange={e => field('start_date', e.target.value)} />
            </label>
            <label>End date
              <input type="date" value={form.end_date} onChange={e => field('end_date', e.target.value)} />
            </label>
            <label>Sync from
              <input type="date" value={form.sync_from} onChange={e => field('sync_from', e.target.value)} />
            </label>
            <label>Sync to
              <input type="date" value={form.sync_to} onChange={e => field('sync_to', e.target.value)} />
            </label>
          </div>
          <div className={styles.row}>
            <button className={styles.saveBtn} type="submit" disabled={saving}>Create</button>
            <button className={styles.cancelBtn} type="button" onClick={() => setCreating(false)}>Cancel</button>
          </div>
        </form>
      ) : (
        <button className={styles.addBtn} onClick={() => setCreating(true)}>+ New season</button>
      )}
    </div>
  )
}
