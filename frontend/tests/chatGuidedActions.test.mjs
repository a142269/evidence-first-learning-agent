import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "..");

const chatViewSource = readFileSync(join(root, "src/views/ChatView.vue"), "utf8");
const messageListSource = readFileSync(join(root, "src/components/chat/ChatMessageList.vue"), "utf8");
const bubbleSource = readFileSync(join(root, "src/components/shared/ChatBubble.vue"), "utf8");

assert.match(
  chatViewSource,
  /生成「机器学习基础」PPT/,
  "The group welcome should offer a concrete PPT generation example",
);
assert.match(
  chatViewSource,
  /生成「反向传播」视频/,
  "The group welcome should offer a concrete video generation example",
);
assert.match(
  chatViewSource,
  /function buildPrivateWelcomeMessage[\s\S]*suggestedActions: guidedActionsForAgent\(partner\.key\)/,
  "Private Agent greetings should include role-aware guided actions",
);
assert.match(
  chatViewSource,
  /@suggestion-click="handleSuggestedAction"/,
  "The chat page should receive guided-action clicks",
);
assert.match(
  chatViewSource,
  /handleSend\(action\.prompt, \{ focusTab \}\)/,
  "Guided actions should reuse the real chat sending pipeline",
);
assert.match(
  chatViewSource,
  /messages\.value\.some\(\(message\) => message\.role === "user"\)/,
  "A welcome bubble alone should not mark the task as already synchronized",
);
assert.match(
  messageListSource,
  /:suggested-actions="m\.suggestedActions"/,
  "The message list should pass guided actions into the Agent bubble",
);
assert.match(
  bubbleSource,
  /class="guided-action-card"[\s\S]*@click="emit\('suggestion-click', action\)"/,
  "Guided cards should be semantic buttons with a working click event",
);
assert.match(
  bubbleSource,
  /\.guided-action-card:focus-visible/,
  "Guided cards should expose a visible keyboard focus state",
);
