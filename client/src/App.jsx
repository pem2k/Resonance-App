import { useState, useEffect } from 'react'
import Header from './components/Header'
import Leaderboard from './components/Leaderboard'
import About from './components/About'
import AdminPanel from './components/AdminPanel'

export default function App() {
  const [tab, setTab] = useState('leaderboard')
  const [isAdmin, setIsAdmin] = useState(false)
  const [seasons, setSeasons] = useState([])
  const [season, setSeason] = useState(null)
  const [standings, setStandings] = useState([])
  const [players, setPlayers] = useState([])
  const [tournaments, setTournaments] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Check if already logged in (persisted session)
  useEffect(() => {
    fetch('/api/auth/me', { credentials: 'include' })
      .then(r => r.json())
      .then(data => setIsAdmin(data.is_admin))
      .catch(() => {})
  }, [])

  async function loadSeasonData() {
    try {
      const seasonsData = await fetch('/api/seasons').then(r => r.json())
      setSeasons(seasonsData)
      const active = seasonsData.find(s => s.status === 'active') ?? seasonsData[0]
      if (!active) { setLoading(false); return }
      await loadSeason(active, seasonsData)
    } catch (e) {
      setError('Failed to load season data.')
      setLoading(false)
    }
  }

  async function loadSeason(target, seasonsData) {
    setLoading(true)
    setError(null)
    try {
      const [standingsData, playersData, tournamentsData] = await Promise.all([
        fetch(`/api/seasons/${target.id}/standings`).then(r => r.json()),
        fetch(`/api/seasons/${target.id}/players`).then(r => r.json()),
        fetch(`/api/seasons/${target.id}/tournaments`).then(r => r.json()),
      ])
      if (seasonsData) setSeasons(seasonsData)
      setSeason(target)
      setStandings(standingsData)
      setPlayers(playersData)
      setTournaments(tournamentsData)
    } catch (e) {
      setError('Failed to load season data.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadSeasonData() }, [])

  function handleLogout() {
    setIsAdmin(false)
    if (tab === 'admin') setTab('leaderboard')
  }

  return (
    <div>
      <Header
        tab={tab}
        onTabChange={setTab}
        isAdmin={isAdmin}
        onLogin={() => setIsAdmin(true)}
        onLogout={handleLogout}
      />
      <main style={{ maxWidth: 960, margin: '0 auto', padding: 'clamp(16px, 4vw, 32px) clamp(12px, 3vw, 24px)' }}>
        {tab === 'leaderboard' && (
          <Leaderboard
            season={season}
            seasons={seasons}
            onSeasonChange={s => loadSeason(s)}
            standings={standings}
            players={players}
            tournaments={tournaments}
            loading={loading}
            error={error}
          />
        )}
        {tab === 'about' && <About />}
        {tab === 'admin' && isAdmin && (
          <AdminPanel seasons={seasons} onSeasonsChange={loadSeasonData} />
        )}
      </main>
    </div>
  )
}
