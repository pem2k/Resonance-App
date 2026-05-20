import { useState, useRef } from 'react'
import styles from './ImportAdmin.module.css'

function parseText(text) {
  const blocks = text.trim().split(/^---$/m).map(b => b.trim()).filter(Boolean)
  return blocks.map((block, i) => {
    const lines = block.split('\n').map(l => l.trim()).filter(Boolean)
    if (lines.length < 2) return { error: `Block ${i + 1}: too short`, lines }
    const teamName = lines[0]
    const captainParts = lines[1].split(',').map(s => s.trim())
    if (captainParts.length < 2) return { error: `Block ${i + 1} ("${teamName}"): bad captain line`, lines }
    const captain = captainParts[0]
    const players = lines.slice(2).map(l => {
      const parts = l.split(',').map(s => s.trim())
      return { name: parts[0], slug: parts[1] ?? '' }
    })
    return { teamName, captain, players }
  })
}

const DANGER_STATUSES = new Set(['active', 'completed'])

export default function ImportAdmin({ activeSeason }) {
  const [text, setText] = useState('')
  const [confirmInput, setConfirmInput] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const fileRef = useRef()

  const preview = text.trim() ? parseText(text) : []
  const parseErrors = preview.filter(b => b.error)
  const validBlocks = preview.filter(b => !b.error)

  const needsConfirm = activeSeason && DANGER_STATUSES.has(activeSeason.status)
  const requiredPhrase = activeSeason ? `Confirm overwrite ${activeSeason.name}` : ''
  const confirmOk = !needsConfirm || confirmInput === requiredPhrase

  function handleFile(e) {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = ev => setText(ev.target.result)
    reader.readAsText(file)
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!activeSeason || !text.trim() || !confirmOk) return
    setSubmitting(true)
    setResult(null)
    setError(null)

    const res = await fetch(`/api/admin/seasons/${activeSeason.id}/import`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, overwrite_confirm: confirmInput }),
    })

    const body = await res.json()
    setSubmitting(false)

    if (!res.ok) {
      setError(body.error === 'confirmation_required'
        ? `Type exactly: "${body.required}"`
        : (body.error ?? 'Import failed'))
      return
    }

    setResult(body)
    setText('')
    setConfirmInput('')
    if (fileRef.current) fileRef.current.value = ''
  }

  if (!activeSeason) return <p className={styles.empty}>No season selected.</p>

  return (
    <form className={styles.root} onSubmit={handleSubmit}>
      <div className={styles.card}>
        <h2 className={styles.cardTitle}>Import Teams &amp; Players</h2>
        <p className={styles.hint}>
          Upload a <code>.txt</code> file or paste directly. Teams are separated by <code>---</code>.
          Each block: first line is the team name, second line is <code>Captain Name, startgg-slug</code>,
          then one line per player.
        </p>

        <label className={styles.fileLabel}>
          <span className={styles.fieldLabel}>Text file</span>
          <input
            ref={fileRef}
            type="file"
            accept=".txt,text/plain"
            className={styles.fileInput}
            onChange={handleFile}
          />
        </label>

        <label className={styles.fieldLabel}>
          Paste / edit
          <textarea
            className={styles.textarea}
            value={text}
            onChange={e => setText(e.target.value)}
            placeholder={`Team Alpha\nCaptainBob, user/abc123\nPlayerA, user/def456\nPlayerB, user/ghi789\n---\nTeam Beta\n...`}
            rows={10}
            spellCheck={false}
          />
        </label>
      </div>

      {preview.length > 0 && (
        <div className={styles.card}>
          <h3 className={styles.cardTitle}>Preview — {validBlocks.length} team{validBlocks.length !== 1 ? 's' : ''} found</h3>

          {parseErrors.length > 0 && (
            <div className={styles.errorBox}>
              {parseErrors.map((b, i) => <p key={i}>{b.error}</p>)}
            </div>
          )}

          <div className={styles.teamGrid}>
            {validBlocks.map((b, i) => (
              <div key={i} className={styles.teamPreview}>
                <div className={styles.teamPreviewName}>{b.teamName}</div>
                <div className={styles.teamPreviewCaptain}>Captain: {b.captain}</div>
                <div className={styles.teamPreviewCount}>
                  {b.players.length} player{b.players.length !== 1 ? 's' : ''}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {needsConfirm && text.trim() && (
        <div className={styles.warningCard}>
          <p className={styles.warningText}>
            <strong>{activeSeason.name}</strong> is <strong>{activeSeason.status}</strong>.
            Importing will overwrite all existing teams and rosters for this season.
          </p>
          <label className={styles.fieldLabel}>
            Type <code>{requiredPhrase}</code> to continue
            <input
              className={`${styles.confirmInput} ${confirmInput && !confirmOk ? styles.confirmBad : ''}`}
              type="text"
              value={confirmInput}
              onChange={e => setConfirmInput(e.target.value)}
              placeholder={requiredPhrase}
              autoComplete="off"
            />
          </label>
        </div>
      )}

      {error && <p className={styles.errorMsg}>{error}</p>}

      {result && (
        <div className={styles.resultBox}>
          <p>Imported {result.teams_imported} team{result.teams_imported !== 1 ? 's' : ''}</p>
          <p>{result.players_created} player{result.players_created !== 1 ? 's' : ''} created, {result.players_found} matched</p>
          {result.errors?.length > 0 && (
            <>
              <p className={styles.warn}>Warnings:</p>
              {result.errors.map((e, i) => <p key={i} className={styles.warn}>— {e}</p>)}
            </>
          )}
        </div>
      )}

      <button
        type="submit"
        className={styles.importBtn}
        disabled={!text.trim() || validBlocks.length === 0 || !confirmOk || submitting}
      >
        {submitting ? 'Importing…' : `Import ${validBlocks.length > 0 ? validBlocks.length + ' team' + (validBlocks.length !== 1 ? 's' : '') : ''}`}
      </button>
    </form>
  )
}
