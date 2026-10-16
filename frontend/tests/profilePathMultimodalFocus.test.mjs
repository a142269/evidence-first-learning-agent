import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const profile = readFileSync(resolve(here, "../src/views/ProfileView.vue"), "utf8");
const path = readFileSync(resolve(here, "../src/views/PathView.vue"), "utf8");

assert.match(
  profile,
  /const \{ userId, course \} = useSession\(\)/,
  "画像页应读取当前课程，避免跨课程推荐污染",
);
assert.match(
  profile,
  /getRecommendations\(uid, 5, course\.value\)/,
  "画像页推荐应限定到当前课程",
);
assert.match(
  profile,
  /getPersonalizationChain\(uid, course\.value\)/,
  "画像页实时薄弱点应来自当前课程的个性化推理链",
);
assert.match(profile, /const currentWeaknesses = computed/, "画像页应派生当前 BKT 薄弱知识点");
assert.match(profile, /title="当前薄弱知识点"/, "画像页应直接展示当前薄弱知识点卡片");
assert.match(profile, /BKT 实时诊断 · 随学随新/, "薄弱点卡片应说明动态画像依据");
assert.match(
  profile,
  /void fetchCockpit\(uid\)[\s\S]*?const results = await Promise\.allSettled/,
  "驾驶舱慢请求不应阻塞画像、BKT 与推荐的核心数据加载",
);

assert.match(
  path,
  /getRecommendations\(userId\.value, 5, course\.value\)/,
  "路径页资源推荐应限定到当前课程",
);
assert.match(
  path,
  /nextBestQuestion\(\{ user_id: userId\.value, kp_id: primaryWeaknessId\.value \|\| undefined, top_k: 3 \}\)/,
  "路径页下一道题应优先限定到第一薄弱知识点",
);
assert.match(
  path,
  /getAdaptiveStrategy\(userId\.value, course\.value\)/,
  "路径页自适应策略应限定到当前课程",
);

console.log("profilePathMultimodalFocus tests passed");
