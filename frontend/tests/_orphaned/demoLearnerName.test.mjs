import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "..");

const learnerNameSources = [
  "src/constants/companion.ts",
  "src/components/layout/AppShell.vue",
  "src/utils/companion/cockpitChat.ts",
  "src/views/LoginView.vue",
  "src/views/PathView.vue",
  "src/views/ProfileView.vue",
  "src/views/SettingsView.vue",
  "integrated-map-src/src/components/Shell.jsx",
  "integrated-map-src/src/data/labGame.js",
  "integrated-map-src/src/views/CockpitView.jsx",
  "integrated-map-src/src/views/ProfileView.jsx",
];

for (const relativePath of learnerNameSources) {
  const source = readFileSync(join(root, relativePath), "utf8");
  assert.match(source, /张三/, `${relativePath} should use 张三 as the example student name`);
  assert.doesNotMatch(
    source,
    /示例同学|张同学|演示学习者/,
    `${relativePath} should not retain a legacy example student name`,
  );
}
