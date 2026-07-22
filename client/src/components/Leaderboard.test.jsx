import React from 'react'
import { act, create } from 'react-test-renderer'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import Leaderboard from './Leaderboard'

const season = { id: 2, name: 'Season 2', status: 'active' }

function team(overrides = {}) {
  return {
    id: 10,
    name: 'Team Alpha',
    captain: { id: 1, display_name: 'Captain' },
    roster: [
      { id: 1, display_name: 'Captain' },
      { id: 2, display_name: 'Member' },
    ],
    total_points: 17,
    ...overrides,
  }
}

function leaderboardElement(standings, selectedSeason = season) {
  return (
    <Leaderboard
      season={selectedSeason}
      seasons={[selectedSeason]}
      onSeasonChange={() => {}}
      standings={standings}
      players={[]}
      tournaments={[]}
      loading={false}
      error={null}
    />
  )
}

function renderLeaderboard(standings = [team()]) {
  const focusByLabel = new Map()
  const inertStateWhenFocused = new Map()
  let view

  act(() => {
    view = create(
      leaderboardElement(standings),
      {
        createNodeMock: element => {
          if (element.type !== 'button') return null
          const label = element.props['aria-label'] ?? element.props.children
          const node = {
            focus: vi.fn(() => {
              if (!view) return
              const background = view.root.findByProps({ 'data-testid': 'leaderboard-content' })
              inertStateWhenFocused.set(label, background.props.inert)
            }),
          }
          focusByLabel.set(label, node)
          return node
        },
      },
    )
  })

  function rerender(nextStandings, nextSeason) {
    act(() => view.update(leaderboardElement(nextStandings, nextSeason)))
  }

  return { view, focusByLabel, inertStateWhenFocused, rerender }
}

function teamButton(view, name = 'Team Alpha') {
  return view.root.findAllByType('button').find(button => button.children.join('') === name)
}

function dialog(view) {
  return view.root.findByProps({ role: 'dialog' })
}

function textContent(node) {
  return node.findAll(() => true)
    .flatMap(child => child.children)
    .filter(value => typeof value === 'string')
    .join(' ')
    .replace(/\s+/g, ' ')
    .trim()
}

describe('team roster card', () => {
  beforeEach(() => {
    globalThis.document = { body: { style: { overflow: '' } } }
  })

  afterEach(() => {
    delete globalThis.document
  })

  it('opens from a semantic team button and lists the complete roster', () => {
    const { view } = renderLeaderboard()
    const button = teamButton(view)

    expect(button).toBeDefined()
    expect(button.props['aria-haspopup']).toBe('dialog')
    expect(button.props['aria-expanded']).toBe(false)

    act(() => button.props.onClick())

    const card = dialog(view)
    expect(teamButton(view).props['aria-expanded']).toBe(true)
    expect(card.props['aria-modal']).toBe('true')
    expect(textContent(card)).toContain('Team Alpha')
    expect(textContent(card)).toContain('17 points')
    expect(textContent(card)).toContain('Captain')
    expect(textContent(card)).toContain('Member')
    expect(card.findAllByProps({ children: 'Captain' })).not.toHaveLength(0)
    expect(document.body.style.overflow).toBe('hidden')
  })

  it('supports captainless teams without inventing a captain', () => {
    const { view } = renderLeaderboard([
      team({
        captain: null,
        roster: [
          { id: 4, display_name: 'One' },
          { id: 5, display_name: 'Two' },
        ],
      }),
    ])

    act(() => teamButton(view).props.onClick())

    const card = dialog(view)
    expect(textContent(card)).toContain('One')
    expect(textContent(card)).toContain('Two')
    expect(card.findAllByProps({ children: 'Captain' })).toHaveLength(0)
  })

  it('isolates the background and preserves list semantics while open', () => {
    const { view } = renderLeaderboard()
    act(() => teamButton(view).props.onClick())

    const background = view.root.findByProps({ 'data-testid': 'leaderboard-content' })
    expect(background.props.inert).toBe('')
    expect(background.props['aria-hidden']).toBe('true')
    expect(dialog(view).findByType('ul').props.role).toBe('list')
  })

  it('shows a clear empty state for a team with no members', () => {
    const { view } = renderLeaderboard([team({ roster: [], captain: null })])

    act(() => teamButton(view).props.onClick())

    expect(textContent(dialog(view))).toContain('No members are assigned to this team yet.')
  })

  it('treats a missing roster as an empty team instead of crashing', () => {
    const { view } = renderLeaderboard([team({ roster: undefined, captain: null })])

    act(() => teamButton(view).props.onClick())

    expect(textContent(dialog(view))).toContain('No members are assigned to this team yet.')
  })

  it('opens the roster belonging to the selected team', () => {
    const beta = team({
      id: 11,
      name: 'Team Beta',
      captain: null,
      roster: [{ id: 9, display_name: 'Beta Member' }],
      total_points: 1,
    })
    const { view } = renderLeaderboard([team(), beta])

    act(() => teamButton(view, 'Team Beta').props.onClick())

    expect(textContent(dialog(view))).toContain('Team Beta')
    expect(textContent(dialog(view))).toContain('Beta Member')
    expect(textContent(dialog(view))).not.toContain('Team Alpha')
  })

  it('closes an open roster when the selected season changes', () => {
    const { view, rerender } = renderLeaderboard()
    act(() => teamButton(view).props.onClick())

    rerender(
      [team({ id: 20, name: 'New Season Team' })],
      { id: 3, name: 'Season 3', status: 'active' },
    )

    expect(view.root.findAllByProps({ role: 'dialog' })).toHaveLength(0)
    expect(document.body.style.overflow).toBe('')
  })

  it('closes on Escape, restores page scrolling, and returns focus to the team button', () => {
    const { view, focusByLabel, inertStateWhenFocused } = renderLeaderboard()
    const button = teamButton(view)

    act(() => button.props.onClick())
    const teamButtonNode = focusByLabel.get('Team Alpha')
    const card = dialog(view)
    const escapeEvent = { key: 'Escape', preventDefault: vi.fn(), stopPropagation: vi.fn() }

    act(() => card.props.onKeyDown(escapeEvent))

    expect(view.root.findAllByProps({ role: 'dialog' })).toHaveLength(0)
    expect(document.body.style.overflow).toBe('')
    expect(escapeEvent.preventDefault).toHaveBeenCalled()
    expect(teamButtonNode.focus).toHaveBeenCalled()
    expect(inertStateWhenFocused.get('Team Alpha')).toBeUndefined()
  })

  it('traps Tab on the labeled close button', () => {
    const { view, focusByLabel } = renderLeaderboard()
    act(() => teamButton(view).props.onClick())
    const closeButtonNode = focusByLabel.get('Close Team Alpha roster')
    closeButtonNode.focus.mockClear()
    const tabEvent = { key: 'Tab', preventDefault: vi.fn() }

    act(() => dialog(view).props.onKeyDown(tabEvent))

    expect(tabEvent.preventDefault).toHaveBeenCalled()
    expect(closeButtonNode.focus).toHaveBeenCalled()
    expect(view.root.findAllByProps({ role: 'dialog' })).toHaveLength(1)
  })

  it('closes from its labeled button and restores the prior body overflow', () => {
    document.body.style.overflow = 'clip'
    const { view, focusByLabel } = renderLeaderboard()
    act(() => teamButton(view).props.onClick())
    const teamButtonNode = focusByLabel.get('Team Alpha')
    const closeButton = view.root.findByProps({ 'aria-label': 'Close Team Alpha roster' })

    act(() => closeButton.props.onClick())

    expect(view.root.findAllByProps({ role: 'dialog' })).toHaveLength(0)
    expect(document.body.style.overflow).toBe('clip')
    expect(teamButtonNode.focus).toHaveBeenCalled()
  })

  it('closes only when the backdrop itself is clicked', () => {
    const { view, focusByLabel } = renderLeaderboard()
    act(() => teamButton(view).props.onClick())
    const teamButtonNode = focusByLabel.get('Team Alpha')
    const backdrop = view.root.findByProps({ 'data-testid': 'team-roster-backdrop' })

    act(() => backdrop.props.onClick({ target: {}, currentTarget: {} }))
    expect(view.root.findAllByProps({ role: 'dialog' })).toHaveLength(1)

    const backdropTarget = {}
    act(() => backdrop.props.onClick({ target: backdropTarget, currentTarget: backdropTarget }))
    expect(view.root.findAllByProps({ role: 'dialog' })).toHaveLength(0)
    expect(teamButtonNode.focus).toHaveBeenCalled()
  })
})
