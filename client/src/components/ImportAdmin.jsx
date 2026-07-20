import { useState, useRef } from 'react'
import { requestJson } from '../api'
import styles from './ImportAdmin.module.css'

function parseText(text) {
  const blocks = text.trim().split(/^\s*---\s*$/m).map(b => b.trim()).filter(Boolean)
  return blocks.map((block, i) => {
    const lines = block.split('\n').map(l => l.trim()).filter(Boolean)
    if (lines.length < 2) return { error: `Block ${i + 1}: too short`, lines }
    const teamName = lines[0]
    const hasCaptain = lines[1].toLowerCase() !== 'no captain'
    const captainParts = hasCaptain ? lines[1].split(/,(.*)/s).slice(0, 2).map(s => s.trim()) : []
    if (hasCaptain && (captainParts.length < 2 || !captainParts[0])) return { error: `Block ${i + 1} ("${teamName}"): bad captain line`, lines }
    const captain = hasCaptain ? captainParts[0] : null
    const players = []
    for (const line of lines.slice(2)) {
      const parts = line.split(/,(.*)/s).slice(0, 2).map(s => s.trim())
      if (parts.length < 2 || !parts[0]) return { error: `Block ${i + 1} ("${teamName}"): bad player line "${line}"`, lines }
      players.push({ name: parts[0], slug: parts[1] })
    }
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
  const requiredPhrase = activeSeason ? `Confirm import ${activeSeason.name}` : ''
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

    try {
      const body = await requestJson(`/api/admin/seasons/${activeSeason.id}/import`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, overwrite_confirm: confirmInput }),
      })
      setResult(body)
      setText('')
      setConfirmInput('')
      if (fileRef.current) fileRef.current.value = ''
    } catch (err) {
      setError(err.data?.error === 'confirmation_required'
        ? `Type exactly: "${err.data.required}"`
        : err.data?.errors?.join(' ') || err.message)
    } finally {
      setSubmitting(false)
    }
  }

  if (!activeSeason) return <p className={styles.empty}>No season selected.</p>

  return (
    <form className={styles.root} onSubmit={handleSubmit}>
      <div className={styles.card}>
        <h2 className={styles.cardTitle}>Import Teams &amp; Players</h2>
        <p className={styles.hint}>
          Upload a <code>.txt</code> file or paste directly. Teams are separated by <code>---</code>.
          Each block: first line is the team name, second line is <code>Captain Name, startgg-slug</code> or <code>No Captain</code>,
          then one line per player. Every person line needs a comma; the slug after it may be blank.
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
            placeholder={`Team Alpha\nCaptainBob, user/abc123\nPlayerA, user/def456\nPlayerB, user/ghi789\n---\nTeam Beta\nNo Captain\nPlayerC, user/jkl012`}
            rows={10}
            spellCheck={false}
          />
        </label>
      </div>

      {preview.length > 0 && (
        <div className={styles.card}>
          <h3 className={styles.cardTitle}>
            Preview — {validBlocks.length} valid, {parseErrors.length} invalid
          </h3>

          {parseErrors.length > 0 && (
            <div className={styles.errorBox}>
              {parseErrors.map((b, i) => <p key={i}>{b.error}</p>)}
            </div>
          )}

          <div className={styles.teamGrid}>
            {validBlocks.map((b, i) => (
              <div key={i} className={styles.teamPreview}>
                <div className={styles.teamPreviewName}>{b.teamName}</div>
                <div className={styles.teamPreviewCaptain}>Captain: {b.captain ?? '— (none)'}</div>
                <div className={styles.teamPreviewCount}>
                  {b.players.length} player{b.players.length !== 1 ? 's' : ''}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {text.trim() && (
        <div className={styles.warningCard}>
          <p className={styles.warningText}>
            <strong>{activeSeason.name}</strong> is <strong>{activeSeason.status}</strong>.
            Importing replaces the captain and roster only for matching team names, creates new teams,
            and leaves teams omitted from the import unchanged.
          </p>
          {needsConfirm && (
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
          )}
        </div>
      )}

      {error && <p className={styles.errorMsg} role="alert">{error}</p>}

      {result && (
        <div className={styles.resultBox} role="status" aria-live="polite">
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
        disabled={!text.trim() || validBlocks.length === 0 || parseErrors.length > 0 || !confirmOk || submitting}
      >
        {submitting ? 'Importing…' : `Import ${validBlocks.length > 0 ? validBlocks.length + ' team' + (validBlocks.length !== 1 ? 's' : '') : ''}`}
      </button>
    </form>
  )
}
