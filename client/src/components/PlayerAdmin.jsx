import { useState, useEffect, useRef } from 'react'
import { requestJson } from '../api'
import styles from './AdminForm.module.css'

export default function PlayerAdmin({ activeSeason }) {
  const [teams, setTeams] = useState([])
  const [allPlayers, setAllPlayers] = useState([])
  const [loading, setLoading] = useState(false)
  const [msg, setMsg] = useState(null)
  const [error, setError] = useState(null)

  async function load() {
    if (!activeSeason) return
    setLoading(true)
    try {
      const [standings, players] = await Promise.all([
        requestJson(`/api/seasons/${activeSeason.id}/standings`),
        requestJson('/api/admin/players', { credentials: 'include' }),
      ])
      setTeams(standings)
      setAllPlayers(players)
      setError(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [activeSeason?.id])

  function showSuccess(message) {
    setError(null)
    setMsg(message)
  }

  function showError(message) {
    setMsg(null)
    setError(message)
  }

  if (!activeSeason) return <p className={styles.empty}>No season selected.</p>

  return (
    <div className={styles.root}>
      {msg && <p className={styles.msg} role="status" aria-live="polite">{msg}</p>}
      {error && <p className={styles.error} role="alert">{error}</p>}

      <CreateTeamForm
        seasonId={activeSeason.id}
        onCreated={async team => { showSuccess(`${team.name} created.`); await load() }}
        onError={showError}
      />

      {loading && teams.length === 0 && <p className={styles.muted}>Loading…</p>}
      {teams.map(team => (
        <TeamCard
          key={team.id}
          team={team}
          allPlayers={allPlayers}
          onUpdate={load}
          setMsg={showSuccess}
          setError={showError}
        />
      ))}
    </div>
  )
}

function CreateTeamForm({ seasonId, onCreated, onError }) {
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [saving, setSaving] = useState(false)

  async function submit(e) {
    e.preventDefault()
    setSaving(true)
    try {
      const team = await requestJson('/api/admin/teams', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, season_id: seasonId }),
      })
      setName('')
      setOpen(false)
      await onCreated(team)
    } catch (err) {
      onError(err.message)
    } finally {
      setSaving(false)
    }
  }

  if (!open) return <button className={styles.addBtn} onClick={() => setOpen(true)}>+ New team</button>

  return (
    <form className={styles.card} onSubmit={submit}>
      <p className={styles.cardTitle}>New Team</p>
      <div className={styles.grid}>
        <label>Team name
          <input value={name} onChange={e => setName(e.target.value)} placeholder="Team Graves" required />
        </label>
      </div>
      <div className={styles.row}>
        <button className={styles.saveBtn} type="submit" disabled={saving}>{saving ? 'Creating…' : 'Create'}</button>
        <button className={styles.cancelBtn} type="button" onClick={() => setOpen(false)} disabled={saving}>Cancel</button>
      </div>
    </form>
  )
}

function TeamCard({ team, allPlayers, onUpdate, setMsg, setError }) {
  const [addMode, setAddMode] = useState(null)
  const [selectedPlayerId, setSelectedPlayerId] = useState('')
  const [newPlayer, setNewPlayer] = useState({ display_name: '', startgg_slug: '', parrygg_id: '' })
  const [playerEdits, setPlayerEdits] = useState({})
  const [renaming, setRenaming] = useState(false)
  const [teamName, setTeamName] = useState(team.name)
  const [deleting, setDeleting] = useState(false)
  const [deleteConfirmName, setDeleteConfirmName] = useState('')
  const [action, setAction] = useState(null)
  const deleteTriggerRef = useRef(null)
  const busy = action !== null
  const deleteFormId = `delete-team-${team.id}`

  function editPlayer(player, key, value) {
    setPlayerEdits(edits => ({
      ...edits,
      [player.id]: {
        display_name: edits[player.id]?.display_name ?? player.display_name,
        startgg_slug: edits[player.id]?.startgg_slug ?? player.startgg_slug ?? '',
        parrygg_id: edits[player.id]?.parrygg_id ?? player.parrygg_id ?? '',
        [key]: value,
      },
    }))
  }

  async function runAction(key, task) {
    if (busy) return
    setAction(key)
    try {
      await task()
    } catch (err) {
      setError(err.message)
    } finally {
      setAction(null)
    }
  }

  async function attachPlayer(playerId, displayName) {
    await requestJson(`/api/admin/teams/${team.id}/roster`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ player_id: Number(playerId) }),
    })
    setMsg(`${displayName} added to ${team.name}.`)
    setSelectedPlayerId('')
    setAddMode(null)
    await onUpdate()
  }

  function addExisting(e) {
    e.preventDefault()
    const player = allPlayers.find(candidate => candidate.id === Number(selectedPlayerId))
    if (!player) return
    runAction('add-existing', () => attachPlayer(player.id, player.display_name))
  }

  function createPlayer(e) {
    e.preventDefault()
    runAction('create-player', async () => {
      const player = await requestJson('/api/admin/players', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newPlayer),
      })
      try {
        await attachPlayer(player.id, player.display_name)
        setNewPlayer({ display_name: '', startgg_slug: '', parrygg_id: '' })
      } catch (err) {
        await onUpdate()
        throw new Error(`${player.display_name} was created, but could not be added to ${team.name}: ${err.message}`)
      }
    })
  }

  function savePlayer(player) {
    const edits = playerEdits[player.id]
    if (!edits) return
    runAction(`player-${player.id}`, async () => {
      const updated = await requestJson(`/api/admin/players/${player.id}`, {
        method: 'PUT',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(edits),
      })
      setPlayerEdits(current => {
        const next = { ...current }
        delete next[player.id]
        return next
      })
      setMsg(`${updated.display_name} updated globally.`)
      await onUpdate()
    })
  }

  function removeFromRoster(player) {
    if (!window.confirm(`Remove ${player.display_name} from ${team.name}? Their global record and results will be preserved.`)) return
    runAction(`remove-${player.id}`, async () => {
      await requestJson(`/api/admin/teams/${team.id}/roster/${player.id}`, {
        method: 'DELETE',
        credentials: 'include',
      })
      setMsg(`${player.display_name} removed from ${team.name}.`)
      await onUpdate()
    })
  }

  function changeCaptain(player) {
    runAction(`captain-${player?.id ?? 'none'}`, async () => {
      await requestJson(`/api/admin/teams/${team.id}`, {
        method: 'PUT',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ captain_id: player?.id ?? null }),
      })
      setMsg(player ? `${player.display_name} set as captain.` : `Captain unset for ${team.name}.`)
      await onUpdate()
    })
  }

  function renameTeam(e) {
    e.preventDefault()
    runAction('rename', async () => {
      const updated = await requestJson(`/api/admin/teams/${team.id}`, {
        method: 'PUT',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: teamName }),
      })
      setRenaming(false)
      setTeamName(updated.name)
      setMsg(`${team.name} renamed to ${updated.name}.`)
      await onUpdate()
    })
  }

  function deleteTeam(e) {
    e.preventDefault()
    if (deleteConfirmName !== team.name) {
      setError('Team name did not match. Nothing was deleted.')
      return
    }
    runAction('delete-team', async () => {
      await requestJson(`/api/admin/teams/${team.id}`, {
        method: 'DELETE',
        credentials: 'include',
      })
      setMsg(`${team.name} deleted. Player records and results were preserved.`)
      setDeleting(false)
      setDeleteConfirmName('')
      await onUpdate()
    })
  }

  function cancelDelete() {
    setDeleting(false)
    setDeleteConfirmName('')
    requestAnimationFrame(() => deleteTriggerRef.current?.focus())
  }

  const rosterIds = new Set((team.roster ?? []).map(player => player.id))
  const attachablePlayers = allPlayers.filter(player => !rosterIds.has(player.id))
  const captainOnRoster = team.captain ? rosterIds.has(team.captain.id) : true

  return (
    <div className={styles.card}>
      <div className={styles.cardHeader}>
        {renaming && !deleting ? (
          <form className={styles.inlineForm} onSubmit={renameTeam}>
            <input value={teamName} onChange={e => setTeamName(e.target.value)} aria-label={`New name for ${team.name}`} required autoFocus />
            <button className={styles.saveSmall} type="submit" disabled={busy}>Save name</button>
            <button className={styles.cancelBtn} type="button" disabled={busy} onClick={() => { setRenaming(false); setTeamName(team.name) }}>Cancel</button>
          </form>
        ) : (
          <span className={styles.cardTitle}>{team.name}</span>
        )}
        <div className={styles.row}>
          <span className={styles.muted}>{team.roster?.length ?? 0} players</span>
          {!renaming && !deleting && <button className={styles.mutedBtn} onClick={() => setRenaming(true)} disabled={busy}>Rename</button>}
          <button
            ref={deleteTriggerRef}
            className={styles.deleteSmall}
            onClick={() => { setDeleting(true); setDeleteConfirmName('') }}
            disabled={busy || deleting || renaming}
            aria-expanded={deleting}
            aria-controls={deleteFormId}
          >
            Delete team
          </button>
        </div>
      </div>

      {deleting && (
        <form id={deleteFormId} className={styles.inlineForm} onSubmit={deleteTeam}>
          <label>
            Type <strong>{team.name}</strong> to confirm deletion
            <input
              value={deleteConfirmName}
              onChange={e => setDeleteConfirmName(e.target.value)}
              aria-label={`Type ${team.name} to confirm deletion`}
              autoFocus
            />
          </label>
          <button className={styles.deleteSmall} type="submit" disabled={busy || deleteConfirmName !== team.name}>Confirm delete</button>
          <button
            className={styles.cancelBtn}
            type="button"
            disabled={busy}
            onClick={cancelDelete}
          >
            Cancel
          </button>
        </form>
      )}

      {!deleting && <>
      {!captainOnRoster && (
        <div className={styles.warnBox}>
          <p className={styles.warn}>
            Legacy data issue: {team.captain.display_name} is assigned as captain but is not on this roster.
          </p>
          <button className={styles.mutedBtn} onClick={() => changeCaptain(null)} disabled={busy}>
            Clear invalid captain
          </button>
        </div>
      )}

      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead><tr><th>Global display name</th><th>start.gg slug</th><th>Parry.gg profile</th><th><span className={styles.srOnly}>Actions</span></th></tr></thead>
          <tbody>
            {(team.roster ?? []).map(player => {
              const edits = playerEdits[player.id]
              return (
                <tr key={player.id}>
                  <td>
                    <input
                      className={styles.slugInput}
                      value={edits?.display_name ?? player.display_name}
                      onChange={e => editPlayer(player, 'display_name', e.target.value)}
                      aria-label={`Display name for ${player.display_name}`}
                    />
                    {team.captain?.id === player.id && <span className={styles.captainBadge}>captain</span>}
                  </td>
                  <td>
                    <input
                      className={styles.slugInput}
                      value={edits?.startgg_slug ?? player.startgg_slug ?? ''}
                      onChange={e => editPlayer(player, 'startgg_slug', e.target.value)}
                      placeholder="user/abc123"
                      aria-label={`start.gg slug for ${player.display_name}`}
                    />
                  </td>
                  <td>
                    <input
                      className={styles.slugInput}
                      value={edits?.parrygg_id ?? player.parrygg_id ?? ''}
                      onChange={e => editPlayer(player, 'parrygg_id', e.target.value)}
                      placeholder="Profile URL or UUID"
                      aria-label={`Parry.gg profile for ${player.display_name}`}
                    />
                  </td>
                  <td className={styles.actions}>
                    {edits && <button className={styles.saveSmall} onClick={() => savePlayer(player)} disabled={busy}>Save</button>}
                    {team.captain?.id !== player.id
                      ? <button className={styles.mutedBtn} onClick={() => changeCaptain(player)} disabled={busy}>Captain</button>
                      : <button className={styles.mutedBtn} onClick={() => changeCaptain(null)} disabled={busy}>Unset captain</button>
                    }
                    <button className={styles.deleteSmall} onClick={() => removeFromRoster(player)} disabled={busy} aria-label={`Remove ${player.display_name} from ${team.name}`}>✕</button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {addMode === 'existing' && (
        <form className={styles.inlineForm} onSubmit={addExisting}>
          <select value={selectedPlayerId} onChange={e => setSelectedPlayerId(e.target.value)} aria-label={`Existing player for ${team.name}`} required>
            <option value="">Choose an existing global player…</option>
            {attachablePlayers.map(player => (
              <option key={player.id} value={player.id}>
                {player.display_name}
                {player.startgg_slug ? ` — ${player.startgg_slug}` : ''}
                {player.parrygg_id ? ' — Parry.gg linked' : ''}
              </option>
            ))}
          </select>
          <button className={styles.saveBtn} type="submit" disabled={busy || !selectedPlayerId}>{busy ? 'Adding…' : 'Add existing'}</button>
          <button className={styles.cancelBtn} type="button" disabled={busy} onClick={() => setAddMode(null)}>Cancel</button>
        </form>
      )}

      {addMode === 'new' && (
        <form className={styles.inlineForm} onSubmit={createPlayer}>
          <input value={newPlayer.display_name} onChange={e => setNewPlayer(player => ({ ...player, display_name: e.target.value }))} placeholder="New display name" aria-label={`New player name for ${team.name}`} required />
          <input value={newPlayer.startgg_slug} onChange={e => setNewPlayer(player => ({ ...player, startgg_slug: e.target.value }))} placeholder="start.gg slug (optional)" aria-label={`New player start.gg slug for ${team.name}`} />
          <input value={newPlayer.parrygg_id} onChange={e => setNewPlayer(player => ({ ...player, parrygg_id: e.target.value }))} placeholder="Parry.gg profile URL or UUID (optional)" aria-label={`New player Parry.gg profile for ${team.name}`} />
          <button className={styles.saveBtn} type="submit" disabled={busy}>{busy ? 'Creating…' : 'Create & add'}</button>
          <button className={styles.cancelBtn} type="button" disabled={busy} onClick={() => setAddMode(null)}>Cancel</button>
        </form>
      )}

      {!addMode && (
        <div className={styles.row}>
          <button className={styles.addBtnSmall} onClick={() => setAddMode('existing')}>+ Add existing player</button>
          <button className={styles.addBtnSmall} onClick={() => setAddMode('new')}>+ Create new player</button>
        </div>
      )}
      </>}
    </div>
  )
}
