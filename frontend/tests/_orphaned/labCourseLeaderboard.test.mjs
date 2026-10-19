import assert from 'node:assert/strict'
import { dirname, join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const progressUrl = pathToFileURL(join(here, '../integrated-map-src/src/utils/labGameProgress.js'))
const coursesUrl = pathToFileURL(join(here, '../integrated-map-src/src/data/playgroundCourses.js'))
const { buildLeaderboard, buildWeeklyLeaderboard } = await import(progressUrl)
const { getPlaygroundCourseConfig } = await import(coursesUrl)

const player = {
  playerId: 'u-101',
  displayName: '当前同学',
  level: 4,
  points: 3300,
  weeklyPoints: 230,
}
const aiPeers = getPlaygroundCourseConfig('artificial_intelligence').leaderboard
const pythonPeers = getPlaygroundCourseConfig('python_programming').leaderboard

const aiTotal = buildLeaderboard(player, aiPeers)
const pythonTotal = buildLeaderboard(player, pythonPeers)
assert.equal(aiTotal.filter((item) => item.playerId === player.playerId).length, 1)
assert.equal(aiTotal.find((item) => item.playerId === player.playerId).points, 3300)
assert.deepEqual(aiTotal.map((item) => item.rank), aiTotal.map((_, index) => index + 1))
assert.deepEqual(aiTotal.map((item) => item.points), [...aiTotal.map((item) => item.points)].sort((a, b) => b - a))
assert.notDeepEqual(
  aiTotal.map((item) => `${item.playerId}:${item.rank}`),
  pythonTotal.map((item) => `${item.playerId}:${item.rank}`),
)

const aiWeekly = buildWeeklyLeaderboard(player, aiPeers)
assert.deepEqual(
  aiWeekly.map((item) => item.weeklyDelta),
  [...aiWeekly.map((item) => item.weeklyDelta)].sort((a, b) => b - a),
)
assert.equal(aiWeekly.find((item) => item.playerId === player.playerId).weeklyDelta, 230)

assert.deepEqual(buildLeaderboard(player, []), [{
  rank: 1,
  playerId: 'u-101',
  displayName: '当前同学',
  level: 4,
  points: 3300,
  weeklyDelta: 230,
  isCurrentPlayer: true,
}])

console.log('labCourseLeaderboard: course peers, replacement, sorting, and empty baseline passed.')
