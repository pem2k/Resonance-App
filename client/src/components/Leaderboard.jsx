import { useEffect, useRef, useState } from 'react'
import styles from './Leaderboard.module.css'
import { formatPointsPerEvent } from './leaderboardFormatting.mjs'

// ─── Small Components ───

function RankCell({ rank }) {
  const rankStyles = {
    1: styles.gold,
    2: styles.silver,
    3: styles.bronze,
  }

  const className = rankStyles[rank] ?? styles.muted
  return <span className={className}>{rank}</span>
}

function AveragePoints({ value }) {
  const className = value == null ? styles.muted : styles.averagePoints
  return <span className={className}>{formatPointsPerEvent(value)}</span>
}

// ─── Dialog Component ───

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

  const handleKeyDown = (event) => {
    if (event.key === 'Escape') {
      event.preventDefault()
      event.stopPropagation()
      onClose()
      return
    }

    if (event.key === 'Tab') {
      event.preventDefault()
      closeButtonRef.current?.focus()
    }
  }

  const handleBackdropClick = (event) => {
    if (event.target === event.currentTarget) onClose()
  }

  const memberCount = roster.length
  const pointsCount = team.total_points

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
          <span>{memberCount} {memberCount === 1 ? 'member' : 'members'}</span>
          <span className={styles.rosterPoints}>
            {pointsCount} {pointsCount === 1 ? 'point' : 'points'}
          </span>
        </div>

        {memberCount > 0 ? (
          <ul className={styles.rosterList} role="list">
            {roster.map(member => (
              <li key={member.id} className={styles.rosterMember}>
                <span className={styles.rosterMemberName}>{member.display_name}</span>
                {team.captain?.id === member.id && (
                  <span className={styles.captainBadge}>Captain</span>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p className={styles.rosterEmpty}>No members are assigned to this team yet.</p>
        )}
      </section>
    </div>
  )
}

// ─── Filter Helpers ───

const createPlayerFilter = (teamFilter, playerQuery, minEvents, maxEvents) => {
  return (player) => {
    // Team filter
    if (teamFilter === 'unassigned' && player.team) return false
    if (teamFilter !== 'all' && teamFilter !== 'unassigned') {
      if (String(player.team?.id) !== teamFilter) return false
    }

    // Name search
    if (playerQuery.trim()) {
      const query = playerQuery.toLowerCase().trim()
      if (!player.display_name?.toLowerCase().includes(query)) return false
    }

    // Event range filters
    const attended = player.events_attended ?? 0
    if (minEvents !== '' && !isNaN(parseInt(minEvents, 10))) {
      if (attended < parseInt(minEvents, 10)) return false
    }
    if (maxEvents !== '' && !isNaN(parseInt(maxEvents, 10))) {
      if (attended > parseInt(maxEvents, 10)) return false
    }

    return true
  }
}

// ─── Main Component ───

export default function Leaderboard({
  season,
  seasons,
  onSeasonChange,
  standings,
  players,
  tournaments,
  loading,
  error,
}) {
  const [selectedTeamId, setSelectedTeamId] = useState(null)
  const [isFilterOpen, setIsFilterOpen] = useState(false)
  const [teamFilter, setTeamFilter] = useState('all')
  const [playerQuery, setPlayerQuery] = useState('')
  const [minEvents, setMinEvents] = useState('')
  const [maxEvents, setMaxEvents] = useState('')

  const teamButtonRefs = useRef(new Map())
  const returnFocusRef = useRef(null)
  const selectedTeam = standings.find(team => team.id === selectedTeamId) ?? null

  const hasActiveFilters =
    teamFilter !== 'all' ||
    playerQuery.trim() !== '' ||
    minEvents !== '' ||
    maxEvents !== ''

  // Reset filters when season changes
  useEffect(() => {
    setSelectedTeamId(null)
    setTeamFilter('all')
    setPlayerQuery('')
    setMinEvents('')
    setMaxEvents('')
    setIsFilterOpen(false)
  }, [season?.id])

  // Restore focus when dialog closes
  useEffect(() => {
    if (selectedTeamId !== null || !returnFocusRef.current) return
    const trigger = returnFocusRef.current
    returnFocusRef.current = null
    trigger.focus()
  }, [selectedTeamId])

  const closeTeamCard = () => {
    returnFocusRef.current = teamButtonRefs.current.get(selectedTeamId) ?? null
    setSelectedTeamId(null)
  }

  const clearAllFilters = () => {
    setTeamFilter('all')
    setPlayerQuery('')
    setMinEvents('')
    setMaxEvents('')
  }

  // Loading states
  if (loading) return <p className={styles.state}>Loading...</p>
  if (error) return <p className={styles.state}>{error}</p>
  if (!season) return <p className={styles.state}>No active season.</p>

  const filteredPlayers = players.filter(
    createPlayerFilter(teamFilter, playerQuery, minEvents, maxEvents)
  )

  return (
    <div className={styles.root}>
      <div
        className={styles.leaderboardContent}
        data-testid="leaderboard-content"
        inert={selectedTeam ? '' : undefined}
        aria-hidden={selectedTeam ? 'true' : undefined}
      >
        {/* Season Selector */}
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

        {/* Team Standings */}
        <section className={styles.section}>
          <h2 className={styles.heading}>Team Standings</h2>
          <div className={styles.tableWrap}>
            <div className={styles.tableScroll}>
              <table className={`${styles.table} ${styles.teamTable}`}>
                <thead>
                  <tr>
                    <th>#</th>
                    <th className={styles.center}>Team</th>
                    <th className={styles.center}>Roster</th>
                    <th className={styles.center}>Points</th>
                  </tr>
                </thead>
                <tbody>
                  {standings.map((team, index) => (
                    <tr
                      key={team.id}
                      className={styles.teamRow}
                      onClick={() => setSelectedTeamId(team.id)}
                    >
                      <td><RankCell rank={index + 1} /></td>
                      <td className={`${styles.teamName} ${styles.center}`}>
                        <button
                          ref={node => {
                            if (node) {
                              teamButtonRefs.current.set(team.id, node)
                            } else {
                              teamButtonRefs.current.delete(team.id)
                            }
                          }}
                          type="button"
                          className={styles.teamButton}
                          aria-haspopup="dialog"
                          aria-controls={selectedTeamId === team.id ? 'team-roster-dialog' : undefined}
                          aria-expanded={selectedTeamId === team.id}
                          onClick={event => {
                            event.stopPropagation()
                            setSelectedTeamId(team.id)
                          }}
                        >
                          {team.name}
                        </button>
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

        {/* Player Leaderboard */}
        <section className={styles.section}>
          <div className={styles.headingWrap}>
            <h2 className={styles.heading}>Player Leaderboard</h2>
            <button
              type="button"
              className={`${styles.filterToggleBtn} ${hasActiveFilters ? styles.filterToggleActive : ''}`}
              onClick={() => setIsFilterOpen(!isFilterOpen)}
              aria-expanded={isFilterOpen}
            >
              <span role="img" aria-label="filter icon">🔍</span>
              <span>Filters</span>
              {hasActiveFilters && <span className={styles.filterBadge}>Active</span>}
            </button>
          </div>

          {/* Filter Panel */}
          {isFilterOpen && (
            <div className={styles.filterBar}>
              <div className={styles.filterGroup}>
                <label htmlFor="player-search" className={styles.filterLabel}>
                  Player Name
                </label>
                <input
                  id="player-search"
                  type="text"
                  className={styles.filterInput}
                  placeholder="Search gamertag..."
                  value={playerQuery}
                  onChange={e => setPlayerQuery(e.target.value)}
                />
              </div>

              <div className={styles.filterGroup}>
                <label htmlFor="team-filter" className={styles.filterLabel}>
                  Team
                </label>
                <select
                  id="team-filter"
                  className={styles.filterSelect}
                  value={teamFilter}
                  onChange={e => setTeamFilter(e.target.value)}
                >
                  <option value="all">All Teams</option>
                  {standings.map(t => (
                    <option key={t.id} value={t.id}>{t.name}</option>
                  ))}
                  <option value="unassigned">Free Agents</option>
                </select>
              </div>

              <div className={styles.filterGroup}>
                <label htmlFor="min-events-filter" className={styles.filterLabel}>
                  Min. Events
                </label>
                <input
                  id="min-events-filter"
                  type="number"
                  min="0"
                  className={styles.filterInput}
                  placeholder="e.g. 1"
                  value={minEvents}
                  onChange={e => setMinEvents(e.target.value)}
                />
              </div>

              <div className={styles.filterGroup}>
                <label htmlFor="max-events-filter" className={styles.filterLabel}>
                  Max. Events
                </label>
                <input
                  id="max-events-filter"
                  type="number"
                  min="0"
                  className={styles.filterInput}
                  placeholder="e.g. 5"
                  value={maxEvents}
                  onChange={e => setMaxEvents(e.target.value)}
                />
              </div>

              {hasActiveFilters && (
                <button
                  type="button"
                  className={styles.clearFilterBtn}
                  onClick={clearAllFilters}
                >
                  Reset
                </button>
              )}
            </div>
          )}

          {/* Players Table */}
          <div className={styles.tableWrap}>
            <div className={`${styles.tableScroll} ${filteredPlayers.length > 10 ? styles.playerScroll : ''}`}>
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
                  {filteredPlayers.length > 0 ? (
                    filteredPlayers.map(player => {
                      const originalRank = players.findIndex(p => p.id === player.id) + 1
                      return (
                        <tr key={player.id}>
                          <td><RankCell rank={originalRank} /></td>
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
                      )
                    })
                  ) : (
                    <tr>
                      <td colSpan={6} className={styles.noResults}>
                        No players match the selected filter criteria.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        {/* Tournaments */}
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
                      .map(t => {
                        const link = t.startgg_slug
                          ? `https://www.start.gg/${t.startgg_slug}`
                          : t.parrygg_slug
                            ? `https://parry.gg/${t.parrygg_slug}`
                            : null

                        return (
                          <tr key={t.id}>
                            <td>
                              {link ? (
                                <a href={link} target="_blank" rel="noreferrer" className={styles.tournamentLink}>
                                  {t.name}
                                </a>
                              ) : (
                                t.name
                              )}
                            </td>
                            <td className={`${styles.secondary} ${styles.center}`}>{t.date ?? '—'}</td>
                            <td className={`${styles.secondary} ${styles.center}`}>{t.total_entrants ?? '—'}</td>
                            <td className={`${styles.secondary} ${styles.center}`}>{t.entry_count ?? '—'}</td>
                          </tr>
                        )
                      })}
                  </tbody>
                </table>
              </div>
            </div>
          </section>
        )}
      </div>

      {/* Roster Dialog */}
      {selectedTeam && <TeamRosterDialog team={selectedTeam} onClose={closeTeamCard} />}
    </div>
  )
}