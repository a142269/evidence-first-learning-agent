<script setup lang="ts">
/**
 * ResourceCard · Plan D · 1.2 — 按 content_type 分发的资源卡片
 *
 * 设计目标：
 * - 取代 ResourcesView 当前的"统一文本预览 + 折叠"显示方式
 * - 每种 resource content_type 用匹配的可视组件渲染：
 *   * code      → 高亮 + 复制按钮
 *   * quiz      → 题干 + 选项 + 折叠答案（答题互动）
 *   * mindmap   → Mermaid 内联渲染
 *   * pptx / doc → 文件卡片 + 下载按钮
 *   * learning_path → 时间线
 *   * evaluation → 雷达图占位
 *   * default   → 文本预览
 *
 * 数据契约（与 api/resources.ts Resource 一致）
 */
import { computed, ref } from "vue";

import type { Resource } from "@/api/resources";

const props = withDefaults(
  defineProps<{
    resource: Resource;
    expanded?: boolean;
    /** 演示时是否在 SSE 推送中（用于特殊交互动画） */
    interactive?: boolean;
  }>(),
  { expanded: true, interactive: false },
);

const quizAnswerVisible = ref(false);
const copied = ref(false);

const ct = computed(() => (props.resource.content_type || "").toLowerCase());
const rt = computed(() => (props.resource.type || "").toLowerCase());

// pptx/document/code/mindmap/quiz/learning_path/evaluation
const isCode = computed(() => ct.value === "code" || rt.value === "code");
const isQuiz = computed(() => ct.value === "quiz" || rt.value === "quiz");
const isMindmap = computed(
  () =>
    ct.value === "mindmap" ||
    rt.value === "mindmap" ||
    ct.value === "mermaid" ||
    rt.value === "mermaid",
);
const isVideo = computed(() =>
  [ct.value, rt.value].some((value) => ["video", "manim", "mp4"].some((token) => value.includes(token))),
);
const isAudio = computed(() =>
  [ct.value, rt.value].some((value) => ["audio", "tts", "mp3"].some((token) => value.includes(token))),
);
const isFile = computed(() =>
  ["pptx", "document", "doc", "pdf"].includes(ct.value) ||
  ["pptx", "document", "doc", "pdf"].includes(rt.value),
);
const isLearningPath = computed(
  () =>
    ct.value === "learning_path" ||
    rt.value === "learning_path" ||
    ct.value === "path",
);
const isEvaluation = computed(
  () => ct.value === "evaluation" || rt.value === "evaluation",
);

async function copyCode() {
  if (!navigator?.clipboard) return;
  try {
    await navigator.clipboard.writeText(props.resource.content || "");
    copied.value = true;
    setTimeout(() => (copied.value = false), 1500);
  } catch (e) {
    // fallback: 不致命
    copied.value = false;
  }
}

const downloadUrl = computed(() => {
  const meta = props.resource.metadata || {};
  const downloads = Array.isArray(meta.downloads) ? meta.downloads : [];
  const downloadable = downloads.find((item: any) => item && item.exists !== false && item.url);
  const explicitUrl = downloadable?.url || meta.url || meta.download_url || "";
  if (explicitUrl || isVideo.value || isAudio.value) return explicitUrl;
  return `/api/v1/artifacts/${props.resource.id}/download`;
});
</script>

<template>
  <article class="resource-card" :data-type="ct || rt">
    <header class="rc-head">
      <span class="rc-type-badge" :data-kind="ct || rt || 'default'">
        {{ ct || rt || "resource" }}
      </span>
      <div class="rc-title">
        <strong>{{ resource.title || resource.id }}</strong>
        <small>{{ resource.agent_name }} · {{ new Date(resource.created_at).toLocaleString("zh-CN", { hour12: false }) }}</small>
      </div>
    </header>

    <!-- code 类型：高亮 + 复制 -->
    <section v-if="isCode" class="rc-code">
      <button class="rc-copy-btn" :class="{ ok: copied }" type="button" @click="copyCode">
        {{ copied ? '✓ 已复制' : '复制' }}
      </button>
      <pre><code>{{ resource.content }}</code></pre>
    </section>

    <!-- quiz 类型：题干 + 选项 + 折叠答案 -->
    <section v-else-if="isQuiz" class="rc-quiz">
      <p class="rc-quiz-stem">{{ (resource.metadata?.stem) || resource.content }}</p>
      <ol v-if="resource.metadata?.options" class="rc-quiz-options">
        <li v-for="(opt, i) in resource.metadata.options" :key="i">{{ opt }}</li>
      </ol>
      <button
        v-if="resource.metadata?.answer || resource.metadata?.expected_keywords"
        class="rc-quiz-toggle"
        type="button"
        @click="quizAnswerVisible = !quizAnswerVisible"
      >
        {{ quizAnswerVisible ? '收起答案' : '查看答案' }}
      </button>
      <div v-if="quizAnswerVisible && (resource.metadata?.answer || resource.metadata?.expected_keywords)" class="rc-quiz-answer">
        <strong>答案:</strong> {{ resource.metadata?.answer || '见 expected_keywords' }}
        <div v-if="resource.metadata?.expected_keywords?.length" class="rc-quiz-keywords">
          <span v-for="k in resource.metadata.expected_keywords" :key="k" class="kw-pill">{{ k }}</span>
        </div>
      </div>
    </section>

    <!-- mindmap: 内联 Mermaid 渲染 -->
    <section v-else-if="isMindmap" class="rc-mindmap">
      <div class="mermaid">
        <pre>{{ resource.content }}</pre>
      </div>
    </section>

    <!-- 视频/语音：只展示真实媒体，不把脚本或说明文字降级成文档 -->
    <section v-else-if="isVideo" class="rc-media">
      <video v-if="downloadUrl" :src="downloadUrl" controls preload="metadata" />
      <div v-else class="rc-media-empty">视频文件尚未生成完成，请重新生成。</div>
    </section>

    <section v-else-if="isAudio" class="rc-media">
      <audio v-if="downloadUrl" :src="downloadUrl" controls preload="metadata" />
      <div v-else class="rc-media-empty">语音文件尚未生成完成，请重新生成。</div>
    </section>

    <!-- 文件类: 文件卡片 + 下载 -->
    <section v-else-if="isFile" class="rc-file">
      <span class="emoji">📄</span>
      <strong>{{ resource.title || resource.id }}.{{ rt || ct }}</strong>
      <a class="rc-download" :href="downloadUrl" target="_blank" rel="noopener" download>
        ⬇ 下载
      </a>
    </section>

    <!-- learning_path: 简单时间线 -->
    <section v-else-if="isLearningPath" class="rc-path">
      <ol class="rc-path-steps">
        <li v-for="(item, i) in (resource.metadata?.stages || [])" :key="i">
          <span class="rc-path-num">{{ i + 1 }}</span>
          {{ typeof item === 'string' ? item : (item.name || item.title || JSON.stringify(item)) }}
        </li>
      </ol>
    </section>

    <!-- evaluation: 雷达图占位 -->
    <section v-else-if="isEvaluation" class="rc-eval">
      <div class="rc-eval-skill" v-for="(v, k) in (resource.metadata?.dimensions || {})" :key="k">
        <label>{{ k }}</label>
        <div class="bar"><i :style="{ width: `${Math.min(100, Math.round(Number(v)*100))}%` }" /></div>
        <em>{{ Math.round(Number(v)*100) }}%</em>
      </div>
    </section>

    <!-- 默认: 文本预览 -->
    <section v-else class="rc-text">
      <pre>{{ (resource.content || '').slice(0, 600) }}{{ (resource.content || '').length > 600 ? '…' : '' }}</pre>
    </section>
  </article>
</template>

<style scoped lang="scss">
.resource-card {
  border: 1px solid var(--border-soft, #e5d4be);
  border-radius: 12px;
  background: var(--paper, #fdf6e3);
  overflow: hidden;
  font-size: 13px;
  color: #4b3414;
}

.rc-head {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.6rem 0.9rem;
  background: var(--paper-2, #fff8e8);
}

.rc-type-badge {
  display: inline-flex;
  align-items: center;
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  font-size: 11px;
  background: rgba(217, 119, 6, 0.12);
  color: #b45309;
  text-transform: lowercase;
  &[data-kind="code"]    { background: #1e293b; color: #cbd5e1; }
  &[data-kind="quiz"]    { background: rgba(220, 38, 38, 0.12); color: #b91c1c; }
  &[data-kind="mermaid"],
  &[data-kind="mindmap"] { background: rgba(14, 165, 233, 0.12); color: #0369a1; }
  &[data-kind="pptx"],
  &[data-kind="document"]{ background: rgba(139, 92, 246, 0.12); color: #6d28d9; }
  &[data-kind="learning_path"] { background: rgba(16, 185, 129, 0.12); color: #047857; }
  &[data-kind="evaluation"]    { background: rgba(245, 158, 11, 0.12); color: #b45309; }
}

.rc-title {
  flex: 1;
  display: flex;
  flex-direction: column;
  > small { color: var(--muted, #6b4f2f); font-size: 11px; }
}

.rc-code, .rc-quiz, .rc-mindmap, .rc-file, .rc-path, .rc-eval, .rc-text {
  padding: 0.6rem 0.9rem;
}

.rc-media {
  padding: 0.8rem 0.9rem;
  background: #171b24;
  video, audio { display: block; width: 100%; }
  video { max-height: 360px; border-radius: 8px; background: #000; }
}
.rc-media-empty {
  padding: 1.4rem;
  border: 1px dashed rgba(255, 255, 255, 0.24);
  border-radius: 8px;
  color: #d9dee8;
  text-align: center;
}

// code
.rc-code {
  position: relative;
  pre {
    margin: 0;
    background: #1e293b;
    color: #e2e8f0;
    border-radius: 8px;
    padding: 0.6rem 0.7rem 0.6rem 0.7rem;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 12px;
    overflow: auto;
  }
}
.rc-copy-btn {
  position: absolute;
  top: 8px;
  right: 8px;
  font-size: 11px;
  border-radius: 6px;
  border: 1px solid rgba(255,255,255,0.3);
  background: rgba(0,0,0,0.4);
  color: #fff;
  padding: 2px 8px;
  cursor: pointer;
  &.ok { background: #16a34a; border-color: transparent; }
}

// quiz
.rc-quiz-stem {
  font-weight: 600;
  margin: 0 0 0.4rem;
}
.rc-quiz-options {
  list-style: upper-alpha inside;
  padding: 0;
  margin: 0 0 0.4rem;
  > li {
    padding: 2px 0;
  }
}
.rc-quiz-toggle {
  border: 1px solid var(--border-soft);
  background: var(--paper-2);
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  cursor: pointer;
}
.rc-quiz-answer {
  margin-top: 0.5rem;
  padding: 0.5rem;
  background: rgba(254, 243, 199, 0.6);
  border-radius: 6px;
}
.rc-quiz-keywords {
  margin-top: 0.3rem;
  display: flex;
  gap: 0.25rem;
  flex-wrap: wrap;
}
.kw-pill {
  font-size: 11px;
  padding: 1px 6px;
  background: rgba(245, 158, 11, 0.18);
  border-radius: 999px;
}

// file
.rc-file {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  > .emoji { font-size: 22px; }
  > strong { flex: 1; }
}
.rc-download {
  background: #f59e0b;
  color: #fff;
  padding: 4px 12px;
  border-radius: 6px;
  font-size: 12px;
  text-decoration: none;
}

// path
.rc-path-steps {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  > li {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
}
.rc-path-num {
  display: inline-grid;
  place-items: center;
  width: 1.4rem;
  height: 1.4rem;
  border-radius: 999px;
  background: rgba(16,185,129,0.15);
  color: #047857;
  font-size: 11px;
  font-weight: 700;
}

// eval
.rc-eval-skill {
  display: grid;
  grid-template-columns: 6rem 1fr 2.4rem;
  align-items: center;
  gap: 0.4rem;
  margin-bottom: 0.3rem;
  > label { color: var(--muted); font-size: 12px; }
  > .bar {
    height: 6px;
    background: rgba(217, 119, 6, 0.15);
    border-radius: 4px;
    overflow: hidden;
    > i {
      display: block;
      height: 100%;
      background: linear-gradient(90deg, #f59e0b, #d97706);
    }
  }
  > em { font-size: 11px; color: var(--muted); text-align: right; }
}

// text
.rc-text pre {
  margin: 0;
  white-space: pre-wrap;
  font-family: inherit;
  font-size: 12.5px;
  color: #4b3414;
}
</style>
