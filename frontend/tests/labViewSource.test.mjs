import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import assert from 'node:assert/strict'

const __dirname = dirname(fileURLToPath(import.meta.url))
const labViewSource = readFileSync(
  join(__dirname, '../integrated-map-src/src/views/LabView.jsx'),
  'utf8',
)

assert.match(
  labViewSource,
  /function openSceneChat\(scene\)[\s\S]*setInteractionMode\('chat'\)/,
  'LabView should expose a scene-entry helper that opens chat mode immediately.',
)

assert.match(
  labViewSource,
  /function enterActiveZone\(\)[\s\S]*openSceneChat\(scene\)/,
  'Entering a lab scene from the campus should open the dialogue panel directly.',
)

assert.doesNotMatch(
  labViewSource,
  /onOpenStatus|actionKey === 'q'|setInteractionMode\(actionKey === 'e' \? 'chat' : 'status'\)/,
  'Interior scenes should no longer expose a status-button or Q-key status flow.',
)

console.log('LabView scene-entry dialogue behavior looks correct.')
