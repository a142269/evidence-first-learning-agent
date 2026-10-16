import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const registerSource = readFileSync(join(__dirname, "../src/views/RegisterView.vue"), "utf8");
const loginSource = readFileSync(join(__dirname, "../src/views/LoginView.vue"), "utf8");
const routerSource = readFileSync(join(__dirname, "../src/router/index.ts"), "utf8");
const authSource = readFileSync(join(__dirname, "../src/api/auth.ts"), "utf8");

assert.match(routerSource, /path:\s*"\/register"[\s\S]*?name:\s*"register"/);
assert.match(routerSource, /to\.name === "login" \|\| to\.name === "register"/);
assert.match(loginSource, /router\.push\("\/register"\)/);
assert.match(loginSource, />\s*注册\s*</);

for (const dimension of [
  "academic",
  "goal",
  "foundation",
  "errors",
  "cognition",
  "resources",
  "habits",
  "autonomy",
]) {
  assert.match(registerSource, new RegExp(`answers\\.${dimension}`));
}

assert.match(registerSource, /role="progressbar"/);
assert.match(registerSource, /暂时跳过/);
assert.match(registerSource, /初始画像来自学生自述|自述型初始画像/);
assert.match(registerSource, /profile_answers:\s*profileAnswers\.value/);
assert.match(registerSource, /learningSubject = computed/);
assert.match(registerSource, /goalTarget = computed/);
assert.match(registerSource, /difficultyFocus = computed/);
assert.match(registerSource, /学习「\$\{learningSubject\.value\}」时/);
assert.match(registerSource, /目标是「\$\{goalTarget\.value\}」/);
assert.match(registerSource, /你提到容易在「\$\{difficultyFocus\.value\}」卡住/);
assert.match(registerSource, /现在投入学习，最主要的动力是什么/);
assert.match(registerSource, /哪些情况会反复出现/);
assert.match(registerSource, /最可能打断计划的因素/);
assert.match(registerSource, /你希望系统怎样介入/);
assert.match(authSource, /profile_answers\?: Record<string, unknown>/);

console.log("registration onboarding source contract passed");
