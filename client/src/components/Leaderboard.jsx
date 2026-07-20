import styles from './Leaderboard.module.css'

function SPRBadge({ value }) {
  if (value == null) return <span className={styles.muted}>—</span>
  const sign = value > 0 ? '+' : ''
  const cls = value > 0 ? styles.sprPositive : value < 0 ? styles.sprNegative : styles.sprNeutral
  return <span className={cls}>{sign}{value.toFixed(1)}</span>
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

export default function Leaderboard({ season, seasons, onSeasonChange, standings, players, tournaments, loading, error }) {
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
                    <td className={`${styles.teamName} ${styles.center}`}>{team.name}</td>
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
                  <th className={styles.center}>Pts/Event</th>
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
                      <SPRBadge value={player.points_per_event} />
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
                            : t.name
                          }
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


    </div>
  )
}
