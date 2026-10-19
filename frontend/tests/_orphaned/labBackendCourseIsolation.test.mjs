import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const source = readFileSync(
  join(here, '../integrated-map-src/src/hooks/useLabBackendState.js'),
  'utf8',
)

assert.match(source, /function useLabBackendState\(courseId, fallbackConfig\)/)
assert.match(source, /initState\(\{\s*courseId,\s*tasks:\s*fallbackConfig\.dailyTasks/)
assert.match(source, /\[courseId, fallbackConfig\.dailyTasks\]/)
assert.doesNotMatch(source, /adaptTasks/)
assert.doesNotMatch(source, /adaptPlayerProgress/)

console.log('labBackendCourseIsolation: remote state stays supplemental to course-local progress.')
