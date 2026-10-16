<script setup lang="ts">
/**
 * 新手引导 v3（2026-07-17 质量增强）
 *
 * 双栏向导式引导（对标 Coursera / 企业产品全局导览的 wizard 形态）：
 * 左栏 = 品牌区 + 步骤目录（当前高亮、已完成打勾），右栏 = Agent 形象图 +
 * 大标题 + 叙述 + 「本步亮点」功能清单。
 *
 * 打开时机：
 * 1. 首次访问自动弹出（localStorage 去重）
 * 2. 顶栏「?」帮助按钮随时重启（window 事件 tripleu:open-tour，
 *    或跨页跳转时的 sessionStorage 标记 tripleu.tour.request）
 */
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { ArrowLeft, ArrowRight, Check, CheckCircle2, Sparkles, X } from "lucide-vue-next";

export interface TourPoint {
  /** 功能名，如 "错题本" */
  label: string;
  /** 在哪里 + 怎么用的一句话 */
  text: string;
}

export interface TourStep {
  /** 步骤徽标，如 "①" 或 emoji */
  badge: string;
  /** 左栏目录里的短标题（缺省取 title 前 8 字） */
  nav?: string;
  title: string;
  desc: string;
  /** 右上角形象图（如 Agent 头像 PNG） */
  image?: string;
  /** 本步亮点：功能名 + 在哪里/怎么用 */
  points?: TourPoint[];
  /** 最后一步的 CTA 文案（可选，默认"开始使用"） */
  cta?: string;
}

const props = defineProps<{
  /** localStorage 去重 key，如 tripleu.tour.student.v1 */
  storageKey: string;
  /** 引导标题，如 "三步开始今天的学习" */
  heading: string;
  /** 副标题（可选） */
  subheading?: string;
  steps: TourStep[];
}>();

const emit = defineEmits<{ (e: "finish"): void }>();

const visible = ref(false);
const current = ref(0);

const step = computed(() => props.steps[current.value]);
const isLast = computed(() => current.value >= props.steps.length - 1);

function navLabel(item: TourStep): string {
  return item.nav || item.title.slice(0, 8);
}

function markDone() {
  try {
    localStorage.setItem(props.storageKey, new Date().toISOString());
  } catch {
    /* 隐私模式忽略 */
  }
}

function openTour() {
  current.value = 0;
  visible.value = true;
}

function next() {
  if (isLast.value) {
    visible.value = false;
    markDone();
    emit("finish");
    return;
  }
  current.value += 1;
}

function back() {
  if (current.value > 0) current.value -= 1;
}

function jumpTo(index: number) {
  current.value = index;
}

function skip() {
  visible.value = false;
  markDone();
}

function handleReopen() {
  openTour();
}

onMounted(() => {
  window.addEventListener("tripleu:open-tour", handleReopen);
  try {
    // 顶栏「?」按钮跨页跳转后的重启请求
    if (sessionStorage.getItem("tripleu.tour.request")) {
      sessionStorage.removeItem("tripleu.tour.request");
      openTour();
      return;
    }
  } catch {
    /* 隐私模式忽略 */
  }
  try {
    visible.value = !localStorage.getItem(props.storageKey);
  } catch {
    visible.value = false;
  }
});

onBeforeUnmount(() => {
  window.removeEventListener("tripleu:open-tour", handleReopen);
});
</script>

<template>
  <Teleport to="body">
    <Transition name="tour-fade">
      <div v-if="visible && step" class="tour-mask" role="dialog" aria-modal="true" :aria-label="heading">
        <div class="tour-card">
          <button type="button" class="tour-skip" aria-label="关闭引导" @click="skip"><X :size="18" /></button>

          <!-- 左栏：品牌 + 步骤目录 -->
          <aside class="tour-rail">
            <div class="tour-brand">
              <span class="tour-glow"><Sparkles :size="18" /></span>
              <div>
                <b>{{ heading }}</b>
                <small>{{ subheading || "triple U 新手引导" }}</small>
              </div>
            </div>
            <nav class="tour-steps-nav" aria-label="引导步骤">
              <button
                v-for="(item, index) in steps"
                :key="index"
                type="button"
                :class="{ active: index === current, done: index < current }"
                @click="jumpTo(index)"
              >
                <span class="tsn-marker">
                  <Check v-if="index < current" :size="12" />
                  <template v-else>{{ index + 1 }}</template>
                </span>
                <span class="tsn-label">{{ navLabel(item) }}</span>
              </button>
            </nav>
            <p class="tour-rail-tip">随时可以点顶栏「?」重新打开本引导</p>
          </aside>

          <!-- 右栏：本步内容 -->
          <div class="tour-main">
            <div class="tour-lede">
              <div class="tour-lede-copy">
                <span class="tour-badge">{{ step.badge }}</span>
                <h3>{{ step.title }}</h3>
                <p>{{ step.desc }}</p>
              </div>
              <img v-if="step.image" class="tour-illustration" :src="step.image" alt="" aria-hidden="true" />
            </div>

            <ul v-if="step.points?.length" class="tour-points">
              <li v-for="point in step.points" :key="point.label">
                <CheckCircle2 :size="17" />
                <div><b>{{ point.label }}</b><span>{{ point.text }}</span></div>
              </li>
            </ul>

            <footer class="tour-actions">
              <button type="button" class="tour-text" @click="skip">跳过引导</button>
              <div class="tour-nav-btns">
                <button v-if="current > 0" type="button" class="tour-back" @click="back"><ArrowLeft :size="15" />上一步</button>
                <button type="button" class="tour-next" @click="next">
                  {{ isLast ? (step.cta || "开始使用") : "下一步" }}
                  <ArrowRight :size="16" />
                </button>
              </div>
            </footer>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped lang="scss">
.tour-mask {
  position: fixed;
  inset: 0;
  z-index: 300;
  background: rgba(28, 18, 10, 0.55);
  backdrop-filter: blur(3px);
  display: grid;
  place-items: center;
  padding: 20px;
}

.tour-card {
  position: relative;
  display: grid;
  grid-template-columns: 232px minmax(0, 1fr);
  width: min(860px, 100%);
  min-height: 460px;
  background: #fff;
  border-radius: 24px;
  overflow: hidden;
  box-shadow: 0 30px 80px rgba(30, 16, 6, 0.32);
}

.tour-skip {
  position: absolute;
  top: 14px;
  right: 14px;
  z-index: 2;
  border: none;
  background: rgba(255, 255, 255, 0.9);
  color: #9ca3af;
  cursor: pointer;
  padding: 7px;
  border-radius: 10px;
  &:hover { background: #f5f0ec; color: #6b7280; }
}

/* ============ 左栏 ============ */
.tour-rail {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 26px 20px 20px;
  background: linear-gradient(170deg, #fff4ec 0%, #fdf7f2 55%, #fbf6f1 100%);
  border-right: 1px solid #f3e7dc;
}

.tour-brand {
  display: flex;
  align-items: flex-start;
  gap: 11px;

  > div { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
  b { font-size: 16.5px; color: #171512; line-height: 1.35; }
  small { color: #a08a76; font-size: 12px; }
}

.tour-glow {
  display: grid;
  place-items: center;
  width: 38px;
  height: 38px;
  border-radius: 12px;
  background: linear-gradient(135deg, #ff8a3d, #e95514);
  color: #fff;
  flex-shrink: 0;
  box-shadow: 0 6px 16px rgba(233, 85, 20, 0.32);
}

.tour-steps-nav {
  display: flex;
  flex-direction: column;
  gap: 5px;

  button {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 11px 12px;
    border: 1.5px solid transparent;
    border-radius: 12px;
    background: transparent;
    cursor: pointer;
    text-align: left;
    transition: background-color 160ms ease-out, border-color 160ms ease-out;

    &:hover { background: rgba(255, 255, 255, 0.85); }
    &.active {
      background: #fff;
      border-color: #f2cdb2;
      box-shadow: 0 4px 14px rgba(233, 85, 20, 0.1);
      .tsn-marker { background: #e95514; color: #fff; }
      .tsn-label { color: #171512; font-weight: 700; }
    }
    &.done .tsn-marker { background: #f6ddc9; color: #c2410c; }
  }

  .tsn-marker {
    display: grid;
    place-items: center;
    width: 26px;
    height: 26px;
    border-radius: 9px;
    background: #f4e6da;
    color: #a08a76;
    font-size: 12.5px;
    font-weight: 800;
    flex-shrink: 0;
    transition: background-color 160ms ease-out;
  }

  .tsn-label {
    color: #6f6559;
    font-size: 13.5px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
}

.tour-rail-tip {
  margin: auto 2px 0;
  color: #b39c86;
  font-size: 11.5px;
  line-height: 1.6;
}

/* ============ 右栏 ============ */
.tour-main {
  display: flex;
  flex-direction: column;
  padding: 30px 30px 22px;
}

.tour-lede {
  display: flex;
  align-items: flex-start;
  gap: 18px;
}

.tour-lede-copy {
  flex: 1;
  min-width: 0;

  h3 { margin: 12px 0 10px; font-size: 23px; color: #171512; letter-spacing: -0.01em; }
  p { margin: 0; color: #5d594f; font-size: 14.5px; line-height: 1.8; }
}

.tour-badge {
  display: inline-grid;
  place-items: center;
  min-width: 44px;
  height: 44px;
  padding: 0 10px;
  border-radius: 14px;
  background: #fff2ea;
  color: #d9460b;
  font-weight: 800;
  font-size: 20px;
}

.tour-illustration {
  width: 108px;
  height: 108px;
  object-fit: contain;
  border-radius: 18px;
  background: linear-gradient(160deg, #fff4ec, #fef9f5);
  border: 1px solid #f6e5d6;
  padding: 8px;
  flex-shrink: 0;
}

.tour-points {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin: 20px 0 0;
  padding: 0;
  list-style: none;

  li {
    display: flex;
    gap: 10px;
    align-items: flex-start;
    padding: 13px 15px;
    border: 1px solid #f0e8e0;
    border-radius: 13px;
    background: #fdfbf8;
    transition: border-color 160ms ease-out, transform 160ms ease-out;

    &:hover { border-color: #f2cdb2; transform: translateY(-1px); }
    > svg { color: #e95514; flex-shrink: 0; margin-top: 2px; }
    div { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
    b { color: #1f1d1a; font-size: 13.5px; }
    span { color: #857e73; font-size: 12px; line-height: 1.6; }
  }
}

.tour-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: auto;
  padding-top: 20px;
}

.tour-nav-btns { display: flex; gap: 10px; }

.tour-text {
  border: none;
  background: transparent;
  color: #a5a09a;
  font-size: 13.5px;
  cursor: pointer;
  padding: 10px 10px;
  &:hover { color: #6b7280; }
}

.tour-back {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 1px solid #e8e1d8;
  background: #fff;
  color: #625f58;
  font-size: 14px;
  font-weight: 600;
  border-radius: 12px;
  padding: 12px 18px;
  cursor: pointer;
  &:hover { border-color: #d0c8bc; }
}

.tour-next {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: none;
  background: #e95514;
  color: #fff;
  font-size: 15px;
  font-weight: 700;
  border-radius: 12px;
  padding: 13px 26px;
  cursor: pointer;
  box-shadow: 0 6px 18px rgba(233, 85, 20, 0.3);
  transition: transform 0.15s ease, box-shadow 0.15s ease;
  &:hover { transform: translateY(-1px); box-shadow: 0 9px 24px rgba(233, 85, 20, 0.36); }
}

@media (max-width: 760px) {
  .tour-card { grid-template-columns: 1fr; min-height: 0; }
  .tour-rail { flex-direction: row; align-items: center; gap: 12px; padding: 16px 18px; border-right: 0; border-bottom: 1px solid #f3e7dc; }
  .tour-brand small { display: none; }
  .tour-steps-nav { flex-direction: row; margin-left: auto; .tsn-label { display: none; } }
  .tour-rail-tip { display: none; }
  .tour-main { padding: 20px 18px 16px; }
  .tour-points { grid-template-columns: 1fr; }
  .tour-illustration { width: 72px; height: 72px; }
}

.tour-fade-enter-active,
.tour-fade-leave-active { transition: opacity 0.22s ease; }
.tour-fade-enter-from,
.tour-fade-leave-to { opacity: 0; }
</style>
