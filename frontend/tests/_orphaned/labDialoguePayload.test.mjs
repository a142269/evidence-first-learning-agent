// B · 实验场单 Agent 对话载荷测试
// 断言 LabView.jsx 的普通对话和热点流式对话都传 target_agent 和 dm_session_id，
// 且 dm_session_id 按课程隔离为 lab-dm-${courseId}-${sceneId}-${agentId}-${userId}。

import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const labViewSource = readFileSync(
  join(__dirname, '../integrated-map-src/src/views/LabView.jsx'),
  'utf8',
)

// ── 1. 断言 LabView.jsx 包含 buildDmSessionId 辅助函数 ──
assert.match(
  labViewSource,
  /function buildDmSessionId\(/,
  'LabView should define a buildDmSessionId helper function',
)

// ── 2. 断言 dm_session_id 使用课程隔离格式 ──
assert.match(
  labViewSource,
  /lab-dm-\$\{courseId\}-\$\{sceneId\}-\$\{agentId\}-\$\{userId\}/,
  'LabView should isolate dm_session_id by course, scene, agent, and user',
)

// ── 3. 断言普通对话 (handleDialogueSend) 传 target_agent ──
// 找到 handleDialogueSend 函数体，验证其中包含 target_agent
const handleDialogueSendMatch = labViewSource.match(
  /function handleDialogueSend[\s\S]*?(?=\n  function )/,
)
assert.ok(handleDialogueSendMatch, 'Should find handleDialogueSend function')
assert.match(
  handleDialogueSendMatch[0],
  /target_agent:\s*targetAgent/,
  'handleDialogueSend should pass target_agent in streamChat params',
)
assert.match(
  handleDialogueSendMatch[0],
  /dm_session_id:\s*dmSessionId/,
  'handleDialogueSend should pass dm_session_id in streamChat params',
)
assert.match(
  handleDialogueSendMatch[0],
  /course:\s*courseId/,
  'handleDialogueSend should pass the active experiment-field course',
)

// ── 4. 断言热点流式对话 (handleInteriorHotspot) 也传 target_agent ──
const handleInteriorHotspotMatch = labViewSource.match(
  /function handleInteriorHotspot[\s\S]*?(?=\n  function |;\s*$)/,
)
assert.ok(handleInteriorHotspotMatch, 'Should find handleInteriorHotspot function')
assert.match(
  handleInteriorHotspotMatch[0],
  /target_agent:\s*targetAgent/,
  'handleInteriorHotspot should pass target_agent in streamChat params',
)
assert.match(
  handleInteriorHotspotMatch[0],
  /dm_session_id:\s*dmSessionId/,
  'handleInteriorHotspot should pass dm_session_id in streamChat params',
)
assert.match(
  handleInteriorHotspotMatch[0],
  /course:\s*courseId/,
  'handleInteriorHotspot should pass the active experiment-field course',
)

// ── 5. 断言两处 streamChat 调用都使用了 getSceneAgentConfig 获取 agentConfig ──
assert.match(
  handleDialogueSendMatch[0],
  /getSceneAgentConfig\(sceneId\)/,
  'handleDialogueSend should call getSceneAgentConfig to get agent config',
)
assert.match(
  handleInteriorHotspotMatch[0],
  /getSceneAgentConfig\(sceneId\)/,
  'handleInteriorHotspot should call getSceneAgentConfig to get agent config',
)

// ── 6. 断言 session_id 优先使用 dmSessionId ──
assert.match(
  handleDialogueSendMatch[0],
  /session_id:\s*dmSessionId\s*\|\|\s*getChatSessionId\(\)/,
  'handleDialogueSend should use dmSessionId as session_id, falling back to getChatSessionId()',
)
assert.match(
  handleInteriorHotspotMatch[0],
  /session_id:\s*dmSessionId\s*\|\|\s*getChatSessionId\(\)/,
  'handleInteriorHotspot should use dmSessionId as session_id, falling back to getChatSessionId()',
)

// ── 7. 断言 buildSceneContextMessage 最小化，不含能力清单/默认 prompt ──
const buildSceneContextMessageMatch = labViewSource.match(
  /function buildSceneContextMessage[\s\S]*?(?=\n  function )/,
)
assert.ok(buildSceneContextMessageMatch, 'Should find buildSceneContextMessage function')
// 应包含场景上下文标记
assert.match(
  buildSceneContextMessageMatch[0],
  /\[实验场/,
  'buildSceneContextMessage should include a scene context tag',
)
// 不应依赖 @提及 触发路由
assert.doesNotMatch(
  buildSceneContextMessageMatch[0],
  /@智狐|@智灵|@阿匠|@小龙|@团团|@球球/,
  'buildSceneContextMessage should not rely on @mentions for routing',
)
// 不应包含能力清单（capabilityDesc），避免 ResourceGeneratorAgent 误触发
assert.doesNotMatch(
  buildSceneContextMessageMatch[0],
  /capabilityDesc|capabilities\.map|能力链路/,
  'buildSceneContextMessage should not include capability descriptions to avoid keyword false-positives',
)
// 不应包含 defaultPrompt
assert.doesNotMatch(
  buildSceneContextMessageMatch[0],
  /defaultPrompt|角色指引/,
  'buildSceneContextMessage should not include defaultPrompt to avoid keyword false-positives',
)

console.log('labDialoguePayload: LabView.jsx correctly sends target_agent and dm_session_id in both normal and hotspot streaming dialogues.')
