import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import assert from 'node:assert/strict'

const __dirname = dirname(fileURLToPath(import.meta.url))
const labViewSource = readFileSync(
  join(__dirname, '../integrated-map-src/src/views/LabView.jsx'),
  'utf8',
)
const sidePanelSource = readFileSync(
  join(__dirname, '../integrated-map-src/src/components/LabRankSidePanel.jsx'),
  'utf8',
)

assert.doesNotMatch(
  labViewSource,
  /const taskSummary = tasks\.slice\(0,\s*3\)/,
  'LabView should not limit the right-side task list to the first 3 tasks.',
)

assert.match(
  labViewSource,
  /summary:\s*tasks\.map\(\(t\)\s*=>/,
  'LabView should pass all tasks into the right-side task list.',
)

assert.match(
  sidePanelSource,
  /taskListProps\?\.totalCount\s*>\s*0[\s\S]*\{taskListProps\.totalCount\}/,
  'The task tab badge should show the total task count instead of only pending tasks.',
)

assert.doesNotMatch(
  labViewSource,
  /onOpenFullPanel:\s*\(\)\s*=>\s*setShowTaskPanel\(true\)/,
  'Right-side tasks should not open the full task modal.',
)

assert.match(
  sidePanelSource,
  /const \[expandedTaskIds,\s*setExpandedTaskIds\]\s*=\s*useState\(\(\)\s*=>\s*new Set\(\)\)/,
  'TasksView should keep local expanded task state.',
)

assert.match(
  sidePanelSource,
  /aria-expanded=\{expanded\}/,
  'Each right-side task should expose an expandable control.',
)

assert.match(
  sidePanelSource,
  /lab-rank-panel__task-detail/,
  'Expanded right-side tasks should render inline details.',
)

assert.doesNotMatch(
  sidePanelSource,
  /查看完整任务面板|onOpenFullPanel|lab-rank-panel__task-list-more/,
  'The right-side task list should not include a full-panel entrypoint.',
)

console.log('Lab right-side tasks render all tasks inline with expandable details.')
