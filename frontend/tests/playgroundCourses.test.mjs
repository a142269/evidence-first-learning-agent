import assert from 'node:assert/strict'
import { dirname, join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const url = pathToFileURL(join(here, '../integrated-map-src/src/data/playgroundCourses.js'))
const {
  DEFAULT_PLAYGROUND_COURSE,
  FALLBACK_PLAYGROUND_COURSES,
  getPlaygroundCourseConfig,
  getPlaygroundCourseLabel,
} = await import(url)

assert.equal(DEFAULT_PLAYGROUND_COURSE, 'artificial_intelligence')
assert.deepEqual(FALLBACK_PLAYGROUND_COURSES, ['artificial_intelligence', 'python_programming'])
assert.equal(getPlaygroundCourseLabel('python_programming'), 'Python 程序设计')

for (const id of FALLBACK_PLAYGROUND_COURSES) {
  const profile = getPlaygroundCourseConfig(id)
  assert.equal(profile.id, id)
  assert.equal(profile.nodes.length, 6)
  assert.equal(profile.areas.length, 7)
  assert.equal(profile.scenes.length, 6)
  assert.equal(profile.dailyTasks.length, 5)
  assert.ok(profile.challenges.length >= 6)
  assert.ok(profile.leaderboardLabel.includes(profile.shortLabel))
  assert.ok(profile.leaderboard.length >= 5)
  assert.equal(new Set(profile.leaderboard.map((item) => item.playerId)).size, profile.leaderboard.length)
  assert.ok(profile.leaderboard.every((item) =>
    Number.isFinite(item.points) && Number.isFinite(item.weeklyDelta)))
  assert.ok(profile.challenges.every((item) =>
    item.correctIndex >= 0 && item.correctIndex < item.options.length))
}

const ai = getPlaygroundCourseConfig('artificial_intelligence')
const python = getPlaygroundCourseConfig('python_programming')
assert.deepEqual(
  ai.dailyTasks.map((item) => item.title),
  [
    '画像驱动的图文概念课',
    '多模态资源精读与标注',
    'CLIP 图文检索微实验',
    '图文错题复盘与再闯关',
    '多模态学习方案评测',
  ],
)
assert.match(
  ai.dailyTasks.map((item) => `${item.description} ${item.steps.map((step) => step.label).join(' ')}`).join(' '),
  /多模态.*视觉.*文本.*CLIP.*检索.*错因.*画像.*推送/,
)
assert.notDeepEqual(ai.dailyTasks, python.dailyTasks)
assert.notDeepEqual(
  ai.leaderboard.map((item) => item.points),
  python.leaderboard.map((item) => item.points),
)
assert.match(ai.nodes.find((node) => node.id === 'tutor').desc, /线性回归|决策树/)
assert.match(python.nodes.find((node) => node.id === 'tutor').desc, /函数|类与对象|语法/)
assert.match(python.areas.find((area) => area.id === 'lab').desc, /文件|异常|代码/)

assert.equal(ai.challenges.length, 10)
assert.ok(ai.challenges.every((item) => item.modalities && item.kpId))
assert.ok(ai.challenges.some((item) => item.kpId === 'AI_006_03'))
assert.ok(ai.challenges.filter((item) => item.visual).length >= 4)

ai.dailyTasks[0].title = 'mutated'
assert.notEqual(
  getPlaygroundCourseConfig('artificial_intelligence').dailyTasks[0].title,
  'mutated',
  'course profiles must be returned as independent clones',
)

const generic = getPlaygroundCourseConfig('computer_vision')
assert.equal(generic.id, 'computer_vision')
assert.equal(generic.label, 'computer vision')
assert.equal(generic.dailyTasks.length, 5)

console.log('playgroundCourses: AI, Python, cloning, and generic fallback contracts passed.')
