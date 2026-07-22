import { useEffect, useRef, useState } from 'react'
import styles from './Leaderboard.module.css'
import { formatPointsPerEvent } from './leaderboardFormatting.mjs'

function AveragePoints({ value }) {
  const className = value == null ? styles.muted : styles.averagePoints
  return <span className={className}>{formatPointsPerEvent(value)}</span>
}

function RankCell({ rank }) {
  if (rank === 1) return <span className={styles.gold}>1</span>
  if (rank === 2) return <span className={styles.silver}>2</span>
  if (rank === 3) return <span className={styles.bronze}>3</span>
  return <span className={styles.muted}>{rank}</span>
}

function captainLabel(captain) {
  if (!captain) return '—'
  return captain.display_name.toLowerCase() === 'no captain' ? 'n/a' : captain.display_name
}

function TeamRosterDialog({ team, onClose }) {
  const closeButtonRef = useRef(null)
  const roster = team.roster ?? []

  useEffect(() => {
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    closeButtonRef.current?.focus()

    return () => {
      document.body.style.overflow = previousOverflow
    }
  }, [])

  function handleKeyDown(event) {
    if (event.key === 'Escape') {
      event.preventDefault()
      event.stopPropagation()
      onClose()
      return
    }

    // Close is the dialog's only interactive control, so keep Tab focus there.
    if (event.key === 'Tab') {
      event.preventDefault()
      closeButtonRef.current?.focus()
    }
  }

  function handleBackdropClick(event) {
    if (event.target === event.currentTarget) onClose()
  }

  return (
    <div
      className={styles.rosterBackdrop}
      data-testid="team-roster-backdrop"
      onClick={handleBackdropClick}
    >
      <section
        id="team-roster-dialog"
        className={styles.rosterDialog}
        role="dialog"
        aria-modal="true"
        aria-labelledby="team-roster-title"
        aria-describedby="team-roster-summary"
        onKeyDown={handleKeyDown}
      >
        <div className={styles.rosterHeader}>
          <div>
            <p className={styles.rosterEyebrow}>Team roster</p>
            <h2 id="team-roster-title" className={styles.rosterTitle}>{team.name}</h2>
          </div>
          <button
            ref={closeButtonRef}
            type="button"
            className={styles.rosterClose}
            aria-label={`Close ${team.name} roster`}
            onClick={onClose}
          >
            ×
          </button>
        </div>

        <div id="team-roster-summary" className={styles.rosterSummary}>
          <span>{roster.length} {roster.length === 1 ? 'member' : 'members'}</span>
          <span className={styles.rosterPoints}>
            {team.total_points} {team.total_points === 1 ? 'point' : 'points'}
          </span>
        </div>

        {roster.length > 0 ? (
          <ul className={styles.rosterList}>
            {roster.map(member => {
              const isCaptain = team.captain?.id === member.id
              return (
                <li key={member.id} className={styles.rosterMember}>
                  <span className={styles.rosterMemberName}>{member.display_name}</span>
                  {isCaptain && <span className={styles.captainBadge}>Captain</span>}
                </li>
              )
            })}
          </ul>
        ) : (
          <p className={styles.rosterEmpty}>No members are assigned to this team yet.</p>
        )}
      </section>
    </div>
  )
}

export default function Leaderboard({ season, seasons, onSeasonChange, standings, players, tournaments, loading, error }) {
  const [selectedTeamId, setSelectedTeamId] = useState(null)
  const teamButtonRefs = useRef(new Map())
  const selectedTeam = standings.find(team => team.id === selectedTeamId) ?? null

  useEffect(() => {
    setSelectedTeamId(null)
  }, [season?.id])

  function closeTeamCard() {
    const trigger = teamButtonRefs.current.get(selectedTeamId)
    setSelectedTeamId(null)
    trigger?.focus()
  }

  if (loading) return <p className={styles.state}>Loading...</p>
  if (error)   return <p className={styles.state}>{error}</p>
  if (!season) return <p className={styles.state}>No active season.</p>

  return (
    <div className={styles.root}>
      <div className={styles.seasonBadge}>
        {seasons?.length > 1 ? (
          <select
            className={styles.seasonSelect}
            value={season.id}
            onChange={e => onSeasonChange(seasons.find(s => s.id === +e.target.value))}
          >
            {seasons.map(s => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        ) : (
          <span className={styles.seasonName}>{season.name}</span>
        )}
        <span className={`${styles.statusPill} ${styles[season.status]}`}>
          {season.status}
        </span>
      </div>

      {/* ── Team Standings ── */}
      <section className={styles.section}>
        <h2 className={styles.heading}>Team Standings</h2>
        <div className={styles.tableWrap}>
          <div className={styles.tableScroll}>
            <table className={`${styles.table} ${styles.teamTable}`}>
              <thead>
                <tr>
                  <th>#</th>
                  <th className={styles.center}>Team</th>
                  <th className={styles.center}>Captain</th>
                  <th className={styles.center}>Roster</th>
                  <th className={styles.center}>Points</th>
                </tr>
              </thead>
              <tbody>
                {standings.map((team, i) => (
                  <tr key={team.id}>
                    <td><RankCell rank={i + 1} /></td>
                    <td className={`${styles.teamName} ${styles.center}`}>
                      <button
                        ref={node => {
                          if (node) teamButtonRefs.current.set(team.id, node)
                          else teamButtonRefs.current.delete(team.id)
                        }}
                        type="button"
                        className={styles.teamButton}
                        aria-haspopup="dialog"
                        aria-controls={selectedTeamId === team.id ? 'team-roster-dialog' : undefined}
                        aria-expanded={selectedTeamId === team.id}
                        onClick={() => setSelectedTeamId(team.id)}
                      >
                        {team.name}
                      </button>
                    </td>
                    <td className={`${styles.secondary} ${styles.center}`}>
                      {captainLabel(team.captain)}
                    </td>
                    <td className={`${styles.secondary} ${styles.center}`}>
                      {team.roster?.length ?? 0}
                    </td>
                    <td className={`${styles.points} ${styles.center}`}>
                      {team.total_points}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* ── Player Leaderboard ── */}
      <section className={styles.section}>
        <h2 className={styles.heading}>Player Leaderboard</h2>
        <div className={styles.tableWrap}>
          <div className={`${styles.tableScroll} ${players.length > 10 ? styles.playerScroll : ''}`}>
            <table className={`${styles.table} ${styles.playerTable}`}>
              <thead>
                <tr>
                  <th>#</th>
                  <th>Player</th>
                  <th>Team</th>
                  <th className={styles.center}>Events</th>
                  <th className={styles.center} title="Average points per event">Avg Points</th>
                  <th className={styles.center}>Points</th>
                </tr>
              </thead>
              <tbody>
                {players.map((player, i) => (
                  <tr key={player.id}>
                    <td><RankCell rank={i + 1} /></td>
                    <td className={styles.playerName}>{player.display_name}</td>
                    <td className={styles.secondary}>{player.team?.name ?? '—'}</td>
                    <td className={`${styles.secondary} ${styles.center}`}>
                      {player.events_attended}
                    </td>
                    <td className={styles.center}>
                      <AveragePoints value={player.points_per_event} />
                    </td>
                    <td className={`${styles.points} ${styles.center}`}>
                      {player.total_points}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>
      {/* ── Tournaments ── */}
      {tournaments?.length > 0 && (
        <section className={styles.section}>
          <h2 className={styles.heading}>Tournaments</h2>
          <div className={styles.tableWrap}>
            <div className={`${styles.tableScroll} ${tournaments.length > 15 ? styles.tournamentScroll : ''}`}>
              <table className={`${styles.table} ${styles.tournamentTable}`}>
                <thead>
                  <tr>
                    <th>Tournament</th>
                    <th className={styles.center}>Date</th>
                    <th className={styles.center}>Entrants</th>
                    <th className={styles.center}>League Entries</th>
                  </tr>
                </thead>
                <tbody>
                  {tournaments
                    .slice()
                    .sort((a, b) => (b.date ?? '').localeCompare(a.date ?? ''))
                    .map(t => (
                      <tr key={t.id}>
                        <td>
                          {t.startgg_slug
                            ? <a href={`https://www.start.gg/${t.startgg_slug}`} target="_blank" rel="noreferrer" className={styles.tournamentLink}>{t.name}</a>
                            : t.parrygg_slug
                              ? <a href={`https://parry.gg/${t.parrygg_slug}`} target="_blank" rel="noreferrer" className={styles.tournamentLink}>{t.name}</a>
                              : t.name}
                        </td>
                        <td className={`${styles.secondary} ${styles.center}`}>{t.date ?? '—'}</td>
                        <td className={`${styles.secondary} ${styles.center}`}>{t.total_entrants ?? '—'}</td>
                        <td className={`${styles.secondary} ${styles.center}`}>{t.entry_count ?? '—'}</td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      )}

      {selectedTeam && <TeamRosterDialog team={selectedTeam} onClose={closeTeamCard} />}
    </div>
  )
}
