import assert from 'node:assert/strict'
import test from 'node:test'

import { formatPointsPerEvent } from './leaderboardFormatting.mjs'


test('formats average points without an SPR-style sign', () => {
  assert.equal(formatPointsPerEvent(3), '3.0')
  assert.equal(formatPointsPerEvent(2.25), '2.3')
  assert.equal(formatPointsPerEvent(0), '0.0')
})


test('formats a missing average as an em dash', () => {
  assert.equal(formatPointsPerEvent(null), '—')
  assert.equal(formatPointsPerEvent(undefined), '—')
})
