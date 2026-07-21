import assert from 'node:assert/strict'
import test from 'node:test'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'

import HeaderExternalLinks from './HeaderExternalLinks.mjs'


test('renders safe and accessible Discord and Start.gg header links in order', () => {
  const markup = renderToStaticMarkup(
    createElement(HeaderExternalLinks, { className: 'tab' }),
  )

  const discordPosition = markup.indexOf('https://discord.gg/Bd3TxddY8n')
  const startggPosition = markup.indexOf('https://www.start.gg/RES')

  assert.ok(discordPosition >= 0)
  assert.ok(startggPosition > discordPosition)
  assert.equal((markup.match(/target="_blank"/g) ?? []).length, 2)
  assert.equal((markup.match(/rel="noreferrer"/g) ?? []).length, 2)
  assert.match(markup, /aria-label="Discord \(opens in a new tab\)"/)
  assert.match(markup, /aria-label="Start\.gg \(opens in a new tab\)"/)
  assert.equal((markup.match(/aria-hidden="true"/g) ?? []).length, 2)
})
