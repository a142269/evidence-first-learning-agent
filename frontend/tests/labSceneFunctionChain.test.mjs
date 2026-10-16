// B · 实验场场景 Agent 功能链路测试
// 断言 6 个场景都有 agent 配置、后端能力描述、默认 prompt。
// 断言教学楼/闯关场景包含 next-best-question 和 generate/multi quiz。

import assert from 'node:assert/strict'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const modulePath = join(__dirname, '../integrated-map-src/src/data/sceneAgentActions.js')

const { SCENE_AGENT_ACTIONS, getSceneAgentConfig, getAllSceneAgentConfigs, getHotspotAction } =
  await import(`file://${modulePath}`)

// ── 1. 断言 6 个场景都存在 ──
const EXPECTED_SCENES = ['library', 'teaching', 'lab', 'study', 'life', 'lawn']

assert.equal(
  Object.keys(SCENE_AGENT_ACTIONS).length,
  EXPECTED_SCENES.length,
  `Should have exactly ${EXPECTED_SCENES.length} scene configs`,
)

for (const sceneId of EXPECTED_SCENES) {
  assert.ok(SCENE_AGENT_ACTIONS[sceneId], `Scene "${sceneId}" should exist in SCENE_AGENT_ACTIONS`)
}

// ── 2. 断言每个场景都有 agentId / agentName / agentTitle / capabilities / defaultPrompt ──
const allConfigs = getAllSceneAgentConfigs()
assert.equal(allConfigs.length, EXPECTED_SCENES.length, 'getAllSceneAgentConfigs should return all 6 configs')

for (const { sceneId, config } of allConfigs) {
  assert.ok(config.agentId, `Scene "${sceneId}" should have agentId`)
  assert.ok(config.agentName, `Scene "${sceneId}" should have agentName`)
  assert.ok(config.agentTitle, `Scene "${sceneId}" should have agentTitle`)
  assert.ok(Array.isArray(config.capabilities) && config.capabilities.length > 0,
    `Scene "${sceneId}" should have non-empty capabilities array`)
  assert.ok(typeof config.defaultPrompt === 'string' && config.defaultPrompt.length > 0,
    `Scene "${sceneId}" should have a non-empty defaultPrompt`)
  assert.ok(config.hotspotActions && typeof config.hotspotActions === 'object',
    `Scene "${sceneId}" should have hotspotActions mapping`)

  // 断言每个 capability 都有 endpoint / method / description
  for (const cap of config.capabilities) {
    assert.ok(cap.id, `Capability in scene "${sceneId}" should have id`)
    assert.ok(cap.endpoint, `Capability "${cap.id}" in scene "${sceneId}" should have endpoint`)
    assert.ok(cap.method, `Capability "${cap.id}" in scene "${sceneId}" should have method`)
    assert.ok(cap.description, `Capability "${cap.id}" in scene "${sceneId}" should have description`)
  }
}

// ── 3. 断言教学楼/闯关场景包含 next-best-question 和 generate/multi quiz ──
const teachingConfig = getSceneAgentConfig('teaching')
assert.ok(teachingConfig, 'Teaching scene config should exist')

const teachingEndpoints = teachingConfig.capabilities.map((c) => c.endpoint)
assert.ok(
  teachingEndpoints.some((ep) => ep.includes('/cognitive/next-best-question')),
  'Teaching scene should include /cognitive/next-best-question capability',
)
assert.ok(
  teachingEndpoints.some((ep) => ep.includes('/artifacts/generate/multi')),
  'Teaching scene should include /artifacts/generate/multi capability',
)

// 断言教学楼有 quiz 类型生成
const teachingQuizCap = teachingConfig.capabilities.find((c) =>
  c.endpoint.includes('/artifacts/generate/multi')
)
assert.ok(teachingQuizCap, 'Teaching scene should have a generate/multi capability')

// ── 4. 断言图书馆场景包含 plan_path、path/generate、recommendations ──
const libraryConfig = getSceneAgentConfig('library')
const libraryEndpoints = libraryConfig.capabilities.map((c) => c.endpoint)
assert.ok(
  libraryEndpoints.some((ep) => ep.includes('/chat/stream')),
  'Library scene should include /chat/stream for plan_path intent',
)
assert.ok(
  libraryEndpoints.some((ep) => ep.includes('/insights/path/generate')),
  'Library scene should include /insights/path/generate',
)
assert.ok(
  libraryEndpoints.some((ep) => ep.includes('/insights/recommendations')),
  'Library scene should include /insights/recommendations',
)

// ── 5. 断言自习空间包含 chat/with-cov 和 safety/adversarial-leakage ──
const studyConfig = getSceneAgentConfig('study')
const studyEndpoints = studyConfig.capabilities.map((c) => c.endpoint)
assert.ok(
  studyEndpoints.some((ep) => ep.includes('/chat/with-cov')),
  'Study scene should include /chat/with-cov',
)
assert.ok(
  studyEndpoints.some((ep) => ep.includes('/safety/adversarial-leakage')),
  'Study scene should include /safety/adversarial-leakage',
)

// ── 6. 断言学生活动中心包含 assessment 和 adaptive-strategy ──
const lifeConfig = getSceneAgentConfig('life')
const lifeEndpoints = lifeConfig.capabilities.map((c) => c.endpoint)
assert.ok(
  lifeEndpoints.some((ep) => ep.includes('/assessment/')),
  'Life scene should include /assessment/{user_id}',
)
assert.ok(
  lifeEndpoints.some((ep) => ep.includes('/insights/adaptive-strategy/')),
  'Life scene should include /insights/adaptive-strategy/{user_id}',
)

// ── 7. 断言中央草坪包含 smart-tutor/ask ──
const lawnConfig = getSceneAgentConfig('lawn')
const lawnEndpoints = lawnConfig.capabilities.map((c) => c.endpoint)
assert.ok(
  lawnEndpoints.some((ep) => ep.includes('/smart-tutor/ask')),
  'Lawn scene should include /smart-tutor/ask',
)

// ── 8. 断言 getHotspotAction 正常工作 ──
const planHotspot = getHotspotAction('library', 'plan')
assert.ok(planHotspot, 'Library "plan" hotspot should have an action')
assert.ok(planHotspot.capability, 'Library "plan" hotspot action should have a capability')

const quizHotspot = getHotspotAction('teaching', 'quiz')
assert.ok(quizHotspot, 'Teaching "quiz" hotspot should have an action')
assert.equal(quizHotspot.capability, 'next_best_question',
  'Teaching "quiz" hotspot should map to next_best_question capability')

// ── 9. 断言 6 个场景身份与标准伙伴表 (partners.js) 一致 ──
//   图书馆=智狐/planner, 教学楼A=小龙/quiz, 实验楼=阿匠/content,
//   自习空间=球球/safety, 生活活动中心=团团/evaluation, 中心花坛=智灵/tutor
const EXPECTED_IDENTITIES = {
  library:    { agentId: 'planner',    agentName: '智狐', agentTitle: '学习规划师' },
  teaching:   { agentId: 'quiz',       agentName: '小龙', agentTitle: '小龙挑战' },
  lab:        { agentId: 'content',    agentName: '阿匠', agentTitle: '内容工匠' },
  study:      { agentId: 'safety',     agentName: '球球', agentTitle: '刺猬守护' },
  life:       { agentId: 'evaluation', agentName: '团团', agentTitle: '熊猫评分' },
  lawn:       { agentId: 'tutor',      agentName: '智灵', agentTitle: '知识讲师' },
}

for (const [sceneId, expected] of Object.entries(EXPECTED_IDENTITIES)) {
  const config = getSceneAgentConfig(sceneId)
  assert.equal(config.agentId, expected.agentId,
    `Scene "${sceneId}" agentId should be ${expected.agentId}`)
  assert.equal(config.agentName, expected.agentName,
    `Scene "${sceneId}" agentName should be ${expected.agentName}`)
  assert.equal(config.agentTitle, expected.agentTitle,
    `Scene "${sceneId}" agentTitle should be ${expected.agentTitle}`)
}

// ── 10. 断言隐藏能力配置已补全 ──
// teaching 应有 mistakes_review 能力
const teachingCaps = teachingConfig.capabilities.map((c) => c.id)
assert.ok(teachingCaps.includes('mistakes_review'),
  'Teaching scene should include mistakes_review capability')

// life 应有 gamification 能力
const lifeCaps = lifeConfig.capabilities.map((c) => c.id)
assert.ok(lifeCaps.includes('gamification'),
  'Life scene should include gamification capability')

// lawn 应有 generate_multi 能力
const lawnCaps = lawnConfig.capabilities.map((c) => c.id)
assert.ok(lawnCaps.includes('generate_multi'),
  'Lawn scene should include generate_multi capability')

// ── 9. 断言 LabView 源码中导入了 sceneAgentActions ──
import { readFileSync } from 'node:fs'
const labViewSource = readFileSync(
  join(__dirname, '../integrated-map-src/src/views/LabView.jsx'),
  'utf8',
)
assert.match(
  labViewSource,
  /from '\.\.\/data\/sceneAgentActions'/,
  'LabView should import from sceneAgentActions',
)
assert.match(
  labViewSource,
  /getSceneAgentConfig/,
  'LabView should use getSceneAgentConfig',
)
assert.match(
  labViewSource,
  /getHotspotAction/,
  'LabView should use getHotspotAction',
)

console.log('labSceneFunctionChain: all 6 scenes have agent config, capabilities, default prompts, correct identities, and hidden capabilities.')
