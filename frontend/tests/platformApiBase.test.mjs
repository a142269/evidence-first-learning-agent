// Ensure embedded lab dialogue APIs default to the real backend instead of the hosting frontend origin.

import assert from 'node:assert/strict'
import { dirname, join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const platformApiPath = join(__dirname, '../integrated-map-src/src/api/platformApi.js')
const platformApi = await import(pathToFileURL(platformApiPath).href)

assert.equal(
  platformApi.getApiBaseUrl(),
  'http://127.0.0.1:8000',
  'platformApi should default to backend API base when VITE_API_BASE_URL is not set',
)

assert.equal(
  platformApi.artifactDownloadUrl('demo-rid', 'png'),
  'http://127.0.0.1:8000/api/v1/artifacts/demo-rid/png',
  'artifact URLs should use the same backend API base',
)

let capturedUrl = ''
globalThis.fetch = (url) => {
  capturedUrl = String(url)
  return new Promise(() => {})
}

const controller = platformApi.streamChat({ message: '你好' })
controller.abort()

assert.equal(
  capturedUrl,
  'http://127.0.0.1:8000/api/v1/chat/stream',
  'streamChat should post to the backend chat stream endpoint by default',
)

console.log('platformApiBase: platformApi defaults embedded dialogue requests to the backend API base.')
