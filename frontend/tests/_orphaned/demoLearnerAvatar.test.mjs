import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "..");

const avatarPath = join(root, "public/avatars/demo-learner.png");
const companionSource = readFileSync(join(root, "src/constants/companion.ts"), "utf8");
const appShellSource = readFileSync(join(root, "src/components/layout/AppShell.vue"), "utf8");
const pathSource = readFileSync(join(root, "src/views/PathView.vue"), "utf8");
const profileSource = readFileSync(join(root, "src/views/ProfileView.vue"), "utf8");
const chatSource = readFileSync(join(root, "src/views/ChatView.vue"), "utf8");
const chatBubbleSource = readFileSync(join(root, "src/components/shared/ChatBubble.vue"), "utf8");
const labPlayerHudSource = readFileSync(join(root, "integrated-map-src/src/components/LabGamePlayerHUD.jsx"), "utf8");
const labCompactPlayerHudSource = readFileSync(join(root, "integrated-map-src/src/components/LabCompactPlayerHUD.jsx"), "utf8");

assert.equal(
  existsSync(avatarPath),
  true,
  "The demo learner avatar image should be available from public/avatars/demo-learner.png",
);
assert.match(
  companionSource,
  /export const demoLearner[\s\S]*avatar: "\/avatars\/demo-learner\.png"/,
  "The demo learner avatar path should be centralized in companion constants",
);
assert.match(
  appShellSource,
  /import \{ demoLearner, partners \}/,
  "AppShell should import the centralized demo learner profile",
);
assert.match(
  appShellSource,
  /<Avatar :partner="learnerPartner" size="md" \/>/,
  "AppShell topbar should render the learner image avatar",
);
assert.match(
  pathSource,
  /<Avatar :partner="learnerPartner" size="lg" \/>/,
  "PathView learner banner should render the demo learner image avatar",
);
assert.match(
  profileSource,
  /<img :src="learnerPartner\.avatar" :alt="learnerPartner\.name" class="pd-avatar-img" \/>/,
  "ProfileView learner card should render the demo learner image avatar",
);
assert.match(
  chatSource,
  /avatar: demoLearner\.avatar/,
  "ChatView student member should use the demo learner avatar",
);
assert.match(
  chatBubbleSource,
  /:src="demoLearner\.avatar"/,
  "User chat bubbles should render the demo learner avatar",
);
assert.match(
  labPlayerHudSource,
  /src="\/avatars\/demo-learner\.png"/,
  "Lab game player HUD should render the demo learner avatar",
);
assert.match(
  labCompactPlayerHudSource,
  /src="\/avatars\/demo-learner\.png"/,
  "Lab compact player HUD should render the demo learner avatar",
);
