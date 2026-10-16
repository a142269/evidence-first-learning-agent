import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const source = readFileSync(
  join(here, '../integrated-map-src/src/views/LabView.jsx'),
  'utf8',
)
const styles = readFileSync(
  join(here, '../integrated-map-src/src/styles/lab-game.css'),
  'utf8',
)
const rankPanelSource = readFileSync(
  join(here, '../integrated-map-src/src/components/LabRankSidePanel.jsx'),
  'utf8',
)

assert.match(source, /loadAvailableCourses\(\)/)
assert.match(source, /setCourse\(nextCourseId\)/)
assert.match(source, /initState\(\{\s*courseId:\s*nextCourseId,\s*tasks:\s*nextConfig\.dailyTasks/)
assert.match(source, /getPlaygroundCourseConfig\(courseId\)/)
assert.match(source, /courseConfig\.nodes/)
assert.match(source, /courseConfig\.areas/)
assert.match(source, /courseConfig\.scenes/)
assert.match(source, /courseConfig\.dailyTasks/)
assert.match(source, /courseConfig\.challenges/)
assert.match(source, /<select[\s\S]*value=\{courseId\}/)
assert.match(source, /aria-label="切换实验场课程"/)
assert.match(source, /saveState\([\s\S]*courseId/)
assert.match(source, /initState\(\{[\s\S]*courseId[\s\S]*tasks:/)
assert.match(source, /dialogueAbortRef\.current\?\.abort\(\)/)
assert.match(source, /course:\s*courseId/g)
assert.match(source, /lab-dm-\$\{courseId\}-/)
assert.doesNotMatch(source, /course:\s*getCourse\(\)/)
assert.match(source, /getRecommendations\(\{\s*user_id:\s*userId,\s*course\s*\}\)/)
assert.match(source, /nextBestQuestion\(\{\s*user_id:\s*userId,\s*course\s*\}\)/)
assert.match(source, /smartTutorAsk\(\{[\s\S]*?course,[\s\S]*?\}\)/)
assert.match(source, /buildLeaderboard\(playerProgress, courseConfig\.leaderboard\)/)
assert.match(source, /buildWeeklyLeaderboard\(playerProgress, courseConfig\.leaderboard\)/)
assert.doesNotMatch(source, /backendState\.leaderboard\?\.length/)
assert.doesNotMatch(source, /backendState\.weeklyLeaderboard\?\.length/)
assert.match(source, /leaderboardLabel=\{courseConfig\.leaderboardLabel\}/)
assert.match(rankPanelSource, /leaderboardLabel/)
assert.match(rankPanelSource, /lab-rank-panel__course-label/)
assert.match(styles, /\.lab-course-switcher\s*\{/)
assert.match(styles, /\.lab-course-switcher select\s*\{[\s\S]*min-height:\s*36px/)
assert.match(styles, /\.lab-course-switcher select:focus-visible/)
assert.match(styles, /@media[^\{]*\(max-width:[^\)]*\)[\s\S]*\.lab-course-switcher\s*>\s*span/)

console.log('labCourseSwitchingView: selector, course content, persistence, and request wiring passed.')
