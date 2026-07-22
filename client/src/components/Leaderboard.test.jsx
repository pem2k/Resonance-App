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

function renderLeaderboard(standings = [team()]) {
  const focusByLabel = new Map()
  let view

  act(() => {
    view = create(
      <Leaderboard
        season={season}
        seasons={[season]}
        onSeasonChange={() => {}}
        standings={standings}
        players={[]}
        tournaments={[]}
        loading={false}
        error={null}
      />,
      {
        createNodeMock: element => {
          if (element.type !== 'button') return null
          const node = { focus: vi.fn() }
          const label = element.props['aria-label'] ?? element.props.children
          focusByLabel.set(label, node)
          return node
        },
      },
    )
  })

  return { view, focusByLabel }
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

  it('shows a clear empty state for a team with no members', () => {
    const { view } = renderLeaderboard([team({ roster: [], captain: null })])

    act(() => teamButton(view).props.onClick())

    expect(textContent(dialog(view))).toContain('No members are assigned to this team yet.')
  })

  it('closes on Escape, restores page scrolling, and returns focus to the team button', () => {
    const { view, focusByLabel } = renderLeaderboard()
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
