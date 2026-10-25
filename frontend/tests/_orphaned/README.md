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

## QWEN-343 正式处置结论（2026-10-25，分支 `qwen/wave3-nightly`）

**结论：保留隔离（不删除、不恢复、不纳入 CI），17 个文件保持原样。**

复核事实（2026-10-25 实测）：

- `git ls-files frontend/integrated-map-src` 仍为 **0 个文件**；仓库根仍无 `.gitmodules`；
  `frontend/src/views/CockpitView.vue` 仍未提交——三处缺失依赖无一恢复。
- CI 排除机制保持有效：`ci.yml` frontend job 的 `node --test tests/*.test.mjs`
  （单层 glob，`ci.yml:34`）不会递归进 `_orphaned/`，注释已注明（`ci.yml:31-32`）。

处置理由：

1. **不能恢复运行**：依赖源码不在仓库，任何"在本工作树跑通"的尝试都是假装恢复，违背台账诚实原则；
2. **不删除**：这 17 个文件是只移动、未改内容的真实行为测试资产，对应源码一旦提交即可按上文"恢复办法"
   用 `git mv` 移回并先本地验证；删除是不可逆损失；
3. **不纳入 CI**：目录隔离 + 单层 glob 已保证它们不进入任何 CI/nightly 路径，无需额外配置；
4. `demoLearnerName.test.mjs` 的 `演示学习者` 断言与现实现冲突的备注（见上表）在恢复前需重新裁定，本处置不改动它。

后续跟踪仍归 QWEN-401（生产 Runbook/发布材料）。
