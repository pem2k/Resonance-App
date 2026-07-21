import assert from 'node:assert/strict'
import test from 'node:test'

import { HEADER_LINKS } from './headerLinks.mjs'


test('places the official Start.gg page beside Discord in the header links', () => {
  assert.deepEqual(HEADER_LINKS, [
    { label: 'Discord', url: 'https://discord.gg/Bd3TxddY8n' },
    { label: 'Start.gg', url: 'https://www.start.gg/RES' },
  ])
})
