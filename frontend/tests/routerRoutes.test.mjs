import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const routerSource = readFileSync(join(__dirname, "../src/router/index.ts"), "utf8");
const cockpitSource = readFileSync(join(__dirname, "../src/views/CockpitView.vue"), "utf8");
const resourcesSource = readFileSync(join(__dirname, "../src/views/ResourcesView.vue"), "utf8");
const playgroundSource = readFileSync(join(__dirname, "../src/views/PlaygroundView.vue"), "utf8");

function assertRoute(path, name) {
  assert.match(
    routerSource,
    new RegExp(String.raw`path:\s*"${path.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}"[\s\S]*?name:\s*"${name}"`),
    `route ${path} should exist with name ${name}`,
  );
}

assertRoute("/cockpit", "cockpit");
assertRoute("/resources", "resources");
assertRoute("/playground", "playground");

assert.match(
  routerSource,
  /path:\s*"\/playground"[\s\S]*?component:\s*\(\)\s*=>\s*import\("@\/views\/PlaygroundView.vue"\)/,
  "/playground should mount PlaygroundView",
);

assert.doesNotMatch(
  routerSource,
  /path:\s*"\/lab"/,
  "/lab standalone challenge game route should be removed",
);

assert.doesNotMatch(
  routerSource,
  /LabGameView/,
  "router should no longer import or mount LabGameView",
);

assert.match(
  playgroundSource,
  /const appUrl = "\/integrated-map\/index\.html\?page=lab&shell=0";/,
  "/playground should open the embedded experiment field directly without the inner shell",
);

assert.match(
  playgroundSource,
  /to="\/home"[\s\S]*?退出实验场/,
  "/playground should expose an exit button back to the home page",
);

assert.match(
  cockpitSource,
  /:src="`\/integrated-map\/index\.html\?page=cockpit&shell=0&user_id=\$\{userId\}`"/,
  "/cockpit should use the React visual surface with the active user id",
);

assert.match(
  resourcesSource,
  /listResources\(\{ user_id: userId\.value, limit: 50 \}\)/,
  "/resources should render the native Vue resource list for the active user",
);

assert.doesNotMatch(
  resourcesSource,
  /\/integrated-map\/index\.html\?page=resources/,
  "/resources should no longer route through the React integrated-map iframe",
);

assert.doesNotMatch(
  playgroundSource,
  /back-float/,
  "/playground should not overlay a duplicate return button on the embedded shell",
);
