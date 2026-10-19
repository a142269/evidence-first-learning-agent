import assert from 'node:assert/strict'
import { dirname, join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const values = new Map()
const localStorage = {
  getItem(key) { return values.has(key) ? values.get(key) : null },
  setItem(key, value) { values.set(key, String(value)) },
  removeItem(key) { values.delete(key) },
}
globalThis.window = { localStorage }

const here = dirname(fileURLToPath(import.meta.url))
const url = pathToFileURL(join(here, '../integrated-map-src/src/api/platformApi.js'))
const api = await import(url)

assert.equal(api.getCourse(), 'artificial_intelligence')
assert.equal(api.setCourse('python_programming'), 'python_programming')
assert.equal(api.getCourse(), 'python_programming')
assert.equal(values.get('tripleu.playground.course'), 'python_programming')
assert.equal(values.has('tripleu.teacher.course'), false)

globalThis.fetch = async () => new Response(JSON.stringify({
  courses: [
    { name: 'artificial_intelligence', file_count: 42 },
    { name: 'python_programming', file_count: 38 },
    'python_programming',
    { name: '' },
  ],
}), { status: 200, headers: { 'content-type': 'application/json' } })

assert.deepEqual(await api.listCourses(), [
  'artificial_intelligence',
  'python_programming',
])

globalThis.fetch = async () => { throw new Error('offline') }
assert.deepEqual(await api.loadAvailableCourses(), [
  'artificial_intelligence',
  'python_programming',
])

console.log('playgroundCourseApi: isolated state, course normalization, and fallback passed.')
