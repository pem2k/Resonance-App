import assert from 'node:assert/strict'
import { readdirSync, readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'


const componentsDirectory = dirname(fileURLToPath(import.meta.url))
const sourceDirectory = dirname(componentsDirectory)
const globalCss = readFileSync(join(sourceDirectory, 'index.css'), 'utf8')


function parseRootTokens(css) {
  const rootBlock = css.match(/:root\s*{([\s\S]*?)}/)?.[1] ?? ''
  return Object.fromEntries(
    [...rootBlock.matchAll(/--([\w-]+):\s*(#[\da-fA-F]{6}|var\(--[\w-]+\))\s*;/g)]
      .map(([, name, value]) => [name, value.toLowerCase()]),
  )
}


function resolveTokens(rawTokens) {
  function resolve(name, seen = new Set()) {
    assert.ok(!seen.has(name), `Theme token cycle detected at --${name}`)
    const value = rawTokens[name]
    assert.ok(value, `Theme token --${name} is not defined`)
    if (!value.startsWith('var(')) return value

    const referencedName = value.match(/var\(--([\w-]+)\)/)?.[1]
    return resolve(referencedName, new Set([...seen, name]))
  }

  return Object.fromEntries(Object.keys(rawTokens).map(name => [name, resolve(name)]))
}


function relativeLuminance(hex) {
  const channels = hex.slice(1).match(/.{2}/g).map(channel => {
    const value = Number.parseInt(channel, 16) / 255
    return value <= 0.04045
      ? value / 12.92
      : ((value + 0.055) / 1.055) ** 2.4
  })

  return (0.2126 * channels[0]) + (0.7152 * channels[1]) + (0.0722 * channels[2])
}


function contrastRatio(first, second) {
  const firstLuminance = relativeLuminance(first)
  const secondLuminance = relativeLuminance(second)
  const lighter = Math.max(firstLuminance, secondLuminance)
  const darker = Math.min(firstLuminance, secondLuminance)
  return (lighter + 0.05) / (darker + 0.05)
}


const rawTokens = parseRootTokens(globalCss)
const tokens = resolveTokens(rawTokens)


test('defines the approved Resonance palette as the theme source of truth', () => {
  assert.deepEqual(
    {
      primary: tokens['resonance-primary'],
      deep: tokens['resonance-deep'],
      neutral: tokens['resonance-neutral'],
      white: tokens['resonance-white'],
      black: tokens['resonance-black'],
    },
    {
      primary: '#85151d',
      deep: '#460912',
      neutral: '#e6e6e6',
      white: '#ffffff',
      black: '#010101',
    },
  )

  assert.equal(rawTokens['bg-primary'], 'var(--resonance-black)')
  assert.equal(rawTokens['bg-secondary'], 'var(--resonance-deep)')
  assert.equal(rawTokens['bg-hover'], 'var(--resonance-primary)')
  assert.equal(rawTokens['text-primary'], 'var(--resonance-white)')
  assert.equal(rawTokens['text-secondary'], 'var(--resonance-neutral)')
  assert.equal(rawTokens['action-bg'], 'var(--resonance-primary)')
})


test('uses a dark Resonance theme with accessible text and controls', () => {
  const surfaces = ['bg-primary', 'bg-secondary', 'bg-tertiary', 'bg-card', 'bg-hover']
  const textTokens = ['text-primary', 'text-secondary', 'text-muted']

  for (const surface of surfaces) {
    assert.ok(relativeLuminance(tokens[surface]) < 0.15, `${surface} should remain dark`)
    for (const textToken of textTokens) {
      assert.ok(
        contrastRatio(tokens[textToken], tokens[surface]) >= 4.5,
        `${textToken} must reach 4.5:1 against ${surface}`,
      )
    }
    assert.ok(
      contrastRatio(tokens.border, tokens[surface]) >= 3,
      `border must reach 3:1 against ${surface}`,
    )
    assert.ok(
      contrastRatio(tokens['focus-ring'], tokens[surface]) >= 3,
      `focus-ring must reach 3:1 against ${surface}`,
    )
  }

  assert.ok(contrastRatio(tokens['action-text'], tokens['action-bg']) >= 4.5)
  assert.ok(contrastRatio(tokens['action-text'], tokens['action-hover']) >= 4.5)
  assert.ok(contrastRatio(tokens['action-border'], tokens['bg-secondary']) >= 3)
  assert.ok(contrastRatio(tokens['action-border'], tokens['action-hover']) >= 3)
  assert.ok(contrastRatio(tokens['link-text'], tokens['bg-primary']) >= 4.5)

  for (const medal of ['medal-gold', 'medal-silver', 'medal-bronze']) {
    assert.ok(contrastRatio(tokens[medal], tokens['bg-secondary']) >= 4.5)
    assert.ok(contrastRatio(tokens[medal], tokens['bg-hover']) >= 4.5)
  }

  assert.ok(contrastRatio(tokens['status-draft'], tokens['status-draft-bg']) >= 4.5)
  assert.ok(contrastRatio(tokens['status-completed'], tokens['status-completed-bg']) >= 4.5)

  for (const state of ['success', 'warning', 'danger']) {
    assert.ok(
      contrastRatio(tokens[state], tokens[`${state}-bg`]) >= 4.5,
      `${state} text must reach 4.5:1 against its feedback surface`,
    )
    assert.ok(
      contrastRatio(tokens[`${state}-border`], tokens[`${state}-bg`]) >= 3,
      `${state} border must reach 3:1 against its feedback surface`,
    )
  }
})


test('keeps component colors centralized in semantic theme tokens', () => {
  const cssFiles = readdirSync(componentsDirectory)
    .filter(fileName => fileName.endsWith('.css'))

  for (const fileName of cssFiles) {
    const css = readFileSync(join(componentsDirectory, fileName), 'utf8')
    assert.doesNotMatch(
      css,
      /#[\da-fA-F]{3,8}\b|\brgba?\s*\(|\bhsla?\s*\(/,
      `${fileName} should reference semantic tokens instead of literal colors`,
    )
  }
})


test('keeps disabled controls visually distinct from interactive controls', () => {
  const adminFormCss = readFileSync(join(componentsDirectory, 'AdminForm.module.css'), 'utf8')

  assert.match(globalCss, /button:disabled,[\s\S]*?cursor:\s*not-allowed;[\s\S]*?opacity:\s*0\.5;/)
  for (const className of ['saveBtn', 'cancelBtn', 'addBtn', 'addBtnSmall', 'syncBtn', 'mutedBtn', 'deleteSmall']) {
    assert.match(
      adminFormCss,
      new RegExp(`\\.${className}:hover:not\\(:disabled\\)`),
      `${className} must not expose a hover affordance while disabled`,
    )
  }
})
