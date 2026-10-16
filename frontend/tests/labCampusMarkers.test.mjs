import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import assert from 'node:assert/strict'

const __dirname = dirname(fileURLToPath(import.meta.url))
const labViewSource = readFileSync(
  join(__dirname, '../integrated-map-src/src/views/LabView.jsx'),
  'utf8',
)

assert.doesNotMatch(
  labViewSource,
  /id:\s*'notice'|activeId === 'notice'|onSelect\('notice'\)|校园公告/,
  'Campus notice should be removed from the experiment field map.',
)

assert.match(
  labViewSource,
  /id:\s*'lawn'[\s\S]*label:\s*'中心花坛'/,
  'The central flowerbed scene should have a visible map title while keeping the lawn scene id.',
)

console.log('Lab campus markers remove notice and show the central flowerbed scene title.')
