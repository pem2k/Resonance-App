import { useState, useEffect } from 'react'
import styles from './AdminForm.module.css'

export default function PlayerAdmin({ activeSeason }) {
  const [teams, setTeams] = useState([])
  const [allPlayers, setAllPlayers] = useState([])
  const [msg, setMsg] = useState(null)

  async function load() {
    if (!activeSeason) return
    const [standingsRes, playersRes] = await Promise.all([
      fetch(`/api/seasons/${activeSeason.id}/standings`).then(r => r.json()),
      fetch(`/api/seasons/${activeSeason.id}/players`).then(r => r.json()),
    ])
    setTeams(standingsRes)
    setAllPlayers(playersRes)
  }

  useEffect(() => { load() }, [activeSeason?.id])

  if (!activeSeason) return <p className={styles.empty}>No season selected.</p>

  return (
    <div className={styles.root}>
      {msg && <p className={styles.msg}>{msg}</p>}

      <CreateTeamForm seasonId={activeSeason.id} onCreated={() => { load(); setMsg('Team created.') }} />

      {teams.map(team => (
        <TeamCard
          key={team.id}
          team={team}
          seasonId={activeSeason.id}
          onUpdate={() => load()}
          setMsg={setMsg}
        />
      ))}
    </div>
  )
}

function CreateTeamForm({ seasonId, onCreated }) {
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [saving, setSaving] = useState(false)

  async function submit(e) {
    e.preventDefault()
    setSaving(true)
    await fetch('/api/admin/teams', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, season_id: seasonId }),
    })
    setSaving(false)
    setName('')
    setOpen(false)
    onCreated()
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
        <button className={styles.saveBtn} type="submit" disabled={saving}>Create</button>
        <button className={styles.cancelBtn} type="button" onClick={() => setOpen(false)}>Cancel</button>
      </div>
    </form>
  )
}

function TeamCard({ team, seasonId, onUpdate, setMsg }) {
  const [addingPlayer, setAddingPlayer] = useState(false)
  const [newPlayer, setNewPlayer] = useState({ display_name: '', startgg_slug: '' })
  const [slugEdits, setSlugEdits] = useState({})
  const [saving, setSaving] = useState(false)

  async function addPlayer(e) {
    e.preventDefault()
    setSaving(true)
    // Create the player globally, then add to roster
    const res = await fetch('/api/admin/players', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newPlayer),
    })
    const player = await res.json()
    if (res.ok) {
      await fetch(`/api/admin/teams/${team.id}/roster`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ player_id: player.id }),
      })
      setMsg(`${player.display_name} added to ${team.name}.`)
      setNewPlayer({ display_name: '', startgg_slug: '' })
      setAddingPlayer(false)
      onUpdate()
    }
    setSaving(false)
  }

  async function saveSlug(player) {
    const slug = slugEdits[player.id]
    if (!slug) return
    await fetch(`/api/admin/players/${player.id}`, {
      method: 'PUT',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ startgg_slug: slug }),
    })
    setMsg(`Slug updated for ${player.display_name}.`)
    setSlugEdits(s => { const n = { ...s }; delete n[player.id]; return n })
    onUpdate()
  }

  async function removeFromRoster(player) {
    await fetch(`/api/admin/teams/${team.id}/roster/${player.id}`, {
      method: 'DELETE',
      credentials: 'include',
    })
    setMsg(`${player.display_name} removed from ${team.name}.`)
    onUpdate()
  }

  async function setCaptain(player) {
    await fetch(`/api/admin/teams/${team.id}`, {
      method: 'PUT',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ captain_id: player.id }),
    })
    setMsg(`${player.display_name} set as captain.`)
    onUpdate()
  }

  return (
    <div className={styles.card}>
      <div className={styles.cardHeader}>
        <span className={styles.cardTitle}>{team.name}</span>
        <span className={styles.muted}>{team.roster?.length ?? 0}/5 players</span>
      </div>

      <div className={styles.tableWrap}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>Player</th>
            <th>start.gg slug</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {(team.roster ?? []).map(player => (
            <tr key={player.id}>
              <td>
                {player.display_name}
                {team.captain?.id === player.id && <span className={styles.captainBadge}>captain</span>}
              </td>
              <td>
                <input
                  className={styles.slugInput}
                  value={slugEdits[player.id] ?? player.startgg_slug ?? ''}
                  onChange={e => setSlugEdits(s => ({ ...s, [player.id]: e.target.value }))}
                  placeholder="user/abc123"
                />
              </td>
              <td className={styles.actions}>
                {slugEdits[player.id] !== undefined && (
                  <button className={styles.saveSmall} onClick={() => saveSlug(player)}>Save</button>
                )}
                {team.captain?.id !== player.id && (
                  <button className={styles.mutedBtn} onClick={() => setCaptain(player)}>Captain</button>
                )}
                <button className={styles.deleteSmall} onClick={() => removeFromRoster(player)}>✕</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      </div>

      {addingPlayer ? (
        <form className={styles.inlineForm} onSubmit={addPlayer}>
          <input
            value={newPlayer.display_name}
            onChange={e => setNewPlayer(p => ({ ...p, display_name: e.target.value }))}
            placeholder="Display name"
            required
          />
          <input
            value={newPlayer.startgg_slug}
            onChange={e => setNewPlayer(p => ({ ...p, startgg_slug: e.target.value }))}
            placeholder="start.gg slug (user/abc123)"
          />
          <button className={styles.saveBtn} type="submit" disabled={saving}>Add</button>
          <button className={styles.cancelBtn} type="button" onClick={() => setAddingPlayer(false)}>Cancel</button>
        </form>
      ) : (
        <button className={styles.addBtnSmall} onClick={() => setAddingPlayer(true)}>+ Add player</button>
      )}
    </div>
  )
}
