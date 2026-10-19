import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import assert from 'node:assert/strict'

const __dirname = dirname(fileURLToPath(import.meta.url))
const labViewSource = readFileSync(
  join(__dirname, '../integrated-map-src/src/views/LabView.jsx'),
  'utf8',
)
const designCss = readFileSync(
  join(__dirname, '../integrated-map-src/src/styles/design.css'),
  'utf8',
)

const hotspotActiveRule = designCss.match(/\.pixel-hotspot:hover,\s*\.pixel-hotspot\.active\s*\{([\s\S]*?)\}/)
assert.ok(hotspotActiveRule, 'design.css should define the hotspot hover/active rule.')
assert.match(
  hotspotActiveRule[1],
  /background:\s*transparent/,
  'Hovering or selecting a building hotspot should not show a filled square overlay.',
)
assert.match(
  hotspotActiveRule[1],
  /border-color:\s*transparent/,
  'Hovering or selecting a building hotspot should not show a square border.',
)
assert.match(
  hotspotActiveRule[1],
  /box-shadow:\s*none/,
  'Hovering or selecting a building hotspot should not show a shadow frame.',
)

assert.match(
  labViewSource,
  /building-interaction-prompt__status/,
  'The building interaction prompt should expose a clear range status label.',
)
assert.match(
  labViewSource,
  /进入交互范围/,
  'The building interaction prompt should tell the learner they are in range.',
)
assert.match(
  labViewSource,
  /building-interaction-prompt__key/,
  'The building interaction prompt should separate the keyboard hint from the scene label.',
)

console.log('Lab interaction visuals hide hotspot frames and use an optimized range prompt.')
