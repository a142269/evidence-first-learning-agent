import assert from 'node:assert/strict'
import { dirname, join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const values = new Map()
globalThis.window = {
  localStorage: {
    getItem(key) { return values.has(key) ? values.get(key) : null },
    setItem(key, value) { values.set(key, String(value)) },
    removeItem(key) { values.delete(key) },
  },
}

const here = dirname(fileURLToPath(import.meta.url))
const dataUrl = pathToFileURL(join(here, '../integrated-map-src/src/data/playgroundCourses.js'))
const progressUrl = pathToFileURL(join(here, '../integrated-map-src/src/utils/labGameProgress.js'))
const { getPlaygroundCourseConfig } = await import(dataUrl)
const { initState, loadState, saveState } = await import(progressUrl)

const ai = getPlaygroundCourseConfig('artificial_intelligence')
const python = getPlaygroundCourseConfig('python_programming')
const aiState = initState({ courseId: ai.id, tasks: ai.dailyTasks })
const pythonState = initState({ courseId: python.id, tasks: python.dailyTasks })
aiState.player.points = 120
pythonState.player.points = 35
saveState(aiState.player, aiState.tasks, [], [], ai.id)
saveState(pythonState.player, pythonState.tasks, [], [], python.id)

assert.equal(loadState(ai.id).player.points, 120)
assert.equal(loadState(python.id).player.points, 35)
assert.ok(loadState(ai.id).tasks.every((item) => item.id.startsWith('ai-')))
assert.ok(loadState(python.id).tasks.every((item) => item.id.startsWith('py-')))
assert.equal(ai.learningFocus.weakness, '多模态大模型')
assert.equal(ai.learningFocus.mastery, '74%')
assert.equal(ai.challenges.length, 10)
assert.equal(ai.challenges.filter((item) => item.kpId === 'AI_015').length, 9)
assert.ok(ai.challenges.some((item) => item.kpId === 'AI_006_03'))
assert.ok(ai.challenges.some((item) => item.visual?.imageSrc))

values.clear()
const legacy = {
  version: 2,
  player: { ...aiState.player, points: 88 },
  tasks: ai.dailyTasks,
  attempts: [],
  weeklyTrend: [],
}
values.set('lab-game:state-v2', JSON.stringify(legacy))
assert.equal(loadState('artificial_intelligence').player.points, 88)
assert.ok(values.has('lab-game:state-v2:artificial_intelligence'))
assert.equal(loadState('python_programming'), null)

values.clear()
values.set('lab-game:state-v2:artificial_intelligence', JSON.stringify({
  version: 2,
  player: { ...aiState.player, displayName: '示例同学', level: 9, points: 2308 },
  tasks: ai.dailyTasks,
  attempts: [],
  weeklyTrend: [],
}))
const renamedLegacyStudent = initState({
  courseId: 'artificial_intelligence',
  tasks: ai.dailyTasks,
})
assert.equal(renamedLegacyStudent.player.displayName, '杜同学')
assert.equal(renamedLegacyStudent.player.level, 9)
assert.equal(renamedLegacyStudent.player.points, 2308)

values.set('lab-game:state-v2:python_programming', JSON.stringify({
  version: 2,
  player: { ...pythonState.player, displayName: '李四' },
  tasks: python.dailyTasks,
  attempts: [],
  weeklyTrend: [],
}))
assert.equal(loadState('python_programming').player.displayName, '杜同学')

values.clear()
values.set('lab-game:state-v2:artificial_intelligence', JSON.stringify({
  version: 2,
  player: aiState.player,
  tasks: [{
    ...ai.dailyTasks[0],
    title: '旧版任务标题',
    description: '旧版任务描述',
    status: 'in-progress',
    currentStep: 1,
  }],
  attempts: [],
  weeklyTrend: [],
}))
const reconciledTasks = initState({
  courseId: 'artificial_intelligence',
  tasks: ai.dailyTasks,
}).tasks
assert.equal(reconciledTasks.length, 5)
assert.equal(reconciledTasks[0].title, '画像驱动的图文概念课')
assert.equal(reconciledTasks[0].status, 'in-progress')
assert.equal(reconciledTasks[0].currentStep, 1)
assert.ok(reconciledTasks.slice(1).every((item) => item.status === 'available'))

values.set('lab-game:state-v2:python_programming', '{broken')
const recovered = initState({
  courseId: 'python_programming',
  tasks: python.dailyTasks,
})
assert.equal(recovered.fromStorage, false)
assert.ok(recovered.tasks.every((item) => item.id.startsWith('py-')))

console.log('labGameCourseProgress: course isolation, AI migration, and corruption fallback passed.')
