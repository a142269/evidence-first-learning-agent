# `_orphaned/` — 依赖源码未提交的测试（暂不运行）

这些用例**只移动、未删除、未改内容**。它们读取的源码文件不在本仓库：
`git ls-files frontend/integrated-map-src` 无结果，仓库根也没有 `.gitmodules`；
`frontend/src/views/CockpitView.vue` 同样未被提交（后端 `backend/app/api/v1/cockpit.py` 存在）。

在本工作树直接运行会因 `ENOENT` / `ERR_MODULE_NOT_FOUND` 失败，所以从 `frontend/tests/` 移出，
使 CI 的 `node --test tests/*.test.mjs` 不会命中它们（glob 的单层 `*` 不跨目录）。

**恢复办法**：把缺失的 React 源码树 `frontend/integrated-map-src/`（或对应 Vue 视图）提交进本仓库后，
用 `git mv` 把下表文件移回 `frontend/tests/`，先本地跑 `node --test tests/*.test.mjs` 确认通过。

| 文件 | 缺失的依赖路径（相对 `frontend/`） |
|---|---|
| `demoLearnerAvatar.test.mjs` | `integrated-map-src/src/components/LabCompactPlayerHUD.jsx`、`integrated-map-src/src/components/LabGamePlayerHUD.jsx` |
| `demoLearnerName.test.mjs` | `integrated-map-src/src/components/Shell.jsx`、`integrated-map-src/src/data/labGame.js`、`integrated-map-src/src/views/CockpitView.jsx`、`integrated-map-src/src/views/ProfileView.jsx`（另注：它对 `src/constants/companion.ts` 的 `doesNotMatch /演示学习者/` 断言与当前实现冲突——该文件把 `演示学习者`、`张三` 一起放进 `GENERIC_LEARNER_NAMES` 占位名集合，属设计语义差异，移回前需重新判定该断言是否还成立） |
| `labBackendCourseIsolation.test.mjs` | `integrated-map-src/src/hooks/useLabBackendState.js` |
| `labCampusMarkers.test.mjs` | `integrated-map-src/src/views/LabView.jsx` |
| `labChallengeRecommendation.test.mjs` | `integrated-map-src/src/utils/challengeRecommendation.js` |
| `labCourseLeaderboard.test.mjs` | `integrated-map-src/src/data/playgroundCourses.js`、`integrated-map-src/src/utils/labGameProgress.js` |
| `labCourseSwitchingView.test.mjs` | `integrated-map-src/src/components/LabRankSidePanel.jsx`、`integrated-map-src/src/styles/lab-game.css`、`integrated-map-src/src/views/LabView.jsx` |
| `labDialoguePayload.test.mjs` | `integrated-map-src/src/views/LabView.jsx` |
| `labGameCourseProgress.test.mjs` | `integrated-map-src/src/data/playgroundCourses.js`、`integrated-map-src/src/utils/labGameProgress.js` |
| `labInteractionPromptVisuals.test.mjs` | `integrated-map-src/src/styles/design.css`、`integrated-map-src/src/views/LabView.jsx` |
| `labRightTasks.test.mjs` | `integrated-map-src/src/components/LabRankSidePanel.jsx`、`integrated-map-src/src/views/LabView.jsx` |
| `labSceneFunctionChain.test.mjs` | `integrated-map-src/src/data/sceneAgentActions.js`、`integrated-map-src/src/views/LabView.jsx` |
| `labViewSource.test.mjs` | `integrated-map-src/src/views/LabView.jsx` |
| `platformApiBase.test.mjs` | `integrated-map-src/src/api/platformApi.js` |
| `playgroundCourseApi.test.mjs` | `integrated-map-src/src/api/platformApi.js` |
| `playgroundCourses.test.mjs` | `integrated-map-src/src/data/playgroundCourses.js` |
| `routerRoutes.test.mjs` | `src/views/CockpitView.vue`（Vue 视图未提交；`frontend/src/api/cockpit.ts`、`backend/app/api/v1/cockpit.py` 存在） |

来源：Wave 0 收口 QWEN-121，Lead 批准的方案 A（`docs/QWEN_LEAD_DIALOGUE.md` 2026-10-19 [DECISION]）。
台账记录见 `docs/CLAIMS_LEDGER.md` S8；跟踪项见 `docs/QWEN_AGENT_UPGRADE_MASTER_PLAN_2026-10-19.md` 的 QWEN-343 / QWEN-401。
