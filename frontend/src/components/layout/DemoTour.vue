<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { Check, ChevronRight, Clapperboard, X } from "lucide-vue-next";

// 7 分钟评委演示动线（固化进 UI，评委/答辩双用）
interface TourStep {
  route: string;
  title: string;
  duration: string;
  script: string;
  action?: string;
}

const steps: TourStep[] = [
  {
    route: "/chat",
    title: "群聊协作 · 多智能体生成",
    duration: "2 分钟",
    script: "点快捷指令「生成全套资料」，展示 SSE 流式输出、六伙伴任务调度、画像随对话更新、实时学情面板。",
    action: "点击快捷指令 → 看任务流 tab",
  },
  {
    route: "/resources",
    title: "资源库 · 多模态生成中心",
    duration: "1.5 分钟",
    script: "生成中心「一键全套」：PPT + 思维导图 + 代码沙箱 + TTS 真实生成并下载，强调 5+ 类个性化资源。",
    action: "一键全套 → 下载 PPT",
  },
  {
    route: "/path",
    title: "学习路径",
    duration: "1 分钟",
    script: "展示路径阶段时间线、当前学习进度与推荐下一步。",
    action: "展示学习路径与下一步推荐",
  },
  {
    route: "/safety",
    title: "安全中心 · 防幻觉证据",
    duration: "1 分钟",
    script: "证据链账本支撑率 + 现场 CoV 核验一句误概念（「梯度下降一定找到全局最优」），看五轴当场抓错。",
    action: "CoV 演示用例一键触发",
  },
  {
    route: "/evidence",
    title: "学习工具箱 · 实用工具集",
    duration: "1 分钟",
    script: "题目认知层级分析器（Bloom 分类）+ 知识点验证助手（多维度核验说法）+ 学习质量保障面板，工具直接面向学生可用。",
    action: "现场输入题目分析认知层级",
  },
  {
    route: "/playground",
    title: "桃园学宫 · 像素校园",
    duration: "30 秒",
    script: "游戏化学习收尾：进入桃园学宫，WASD 探索场景、进建筑与对应 AI 伙伴互动。",
    action: "WASD 走两步进图书馆",
  },
];

const open = ref(false);
const closed = ref(false); // To completely hide the FAB
const doneSteps = ref<Set<number>>(new Set());
const router = useRouter();

const progress = computed(() => Math.round((doneSteps.value.size / steps.length) * 100));

function goStep(i: number) {
  doneSteps.value = new Set([...doneSteps.value, i]);
  void router.push(steps[i].route);
}

function resetTour() {
  doneSteps.value = new Set();
}

function handleExternalOpen() {
  open.value = true;
}
onMounted(() => window.addEventListener("a3:open-demo-tour", handleExternalOpen));
onBeforeUnmount(() => window.removeEventListener("a3:open-demo-tour", handleExternalOpen));
</script>

<template>
  <div class="demo-tour" v-if="!closed">
    <div v-if="!open" class="tour-fab-container">
      <button type="button" class="tour-fab" title="7 分钟评委演示动线" @click="open = true">
        <Clapperboard :size="16" />演示动线
      </button>
      <button class="tour-fab-close" title="隐藏" @click="closed = true"><X :size="12" /></button>
    </div>

    <div v-else class="tour-panel">
      <header>
        <b><Clapperboard :size="15" />7 分钟演示动线</b>
        <small>{{ progress }}%</small>
        <button type="button" aria-label="关闭" @click="open = false"><X :size="15" /></button>
      </header>
      <div class="tour-bar"><i :style="{ width: `${progress}%` }" /></div>
      <ol>
        <li v-for="(s, i) in steps" :key="s.route" :class="doneSteps.has(i) ? 'done' : ''">
          <span class="step-no">
            <Check v-if="doneSteps.has(i)" :size="11" :stroke-width="3" />
            <template v-else>{{ i + 1 }}</template>
          </span>
          <div class="step-copy">
            <b>{{ s.title }} <em>{{ s.duration }}</em></b>
            <p>{{ s.script }}</p>
            <small v-if="s.action">▶ {{ s.action }}</small>
          </div>
          <button type="button" class="step-go" @click="goStep(i)">
            前往<ChevronRight :size="12" />
          </button>
        </li>
      </ol>
      <footer>
        <button type="button" @click="resetTour">重置进度</button>
        <span>登录 → 群聊 → 资源 → 路径 → 安全 → 工具箱 → 桃园学宫</span>
      </footer>
    </div>
  </div>
</template>

<style scoped>
.demo-tour {
  position: fixed;
  right: 18px;
  bottom: 18px;
  z-index: 80;
}

.tour-fab-container {
  display: flex;
  align-items: center;
  gap: 4px;
}

.tour-fab {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 10px 16px;
  border-radius: 999px;
  background: linear-gradient(135deg, var(--orange-500), var(--orange-400));
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  box-shadow: var(--shadow-3);
  transition: transform 0.12s ease;
}

.tour-fab:hover {
  transform: translateY(-2px);
}

.tour-fab-close {
  display: grid;
  place-items: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--paper-2);
  color: var(--muted);
  border: 1px solid var(--border-soft);
  cursor: pointer;
  box-shadow: var(--shadow-1);
}

.tour-fab-close:hover {
  background: var(--neutral-100);
  color: var(--ink);
}

.tour-panel {
  width: 360px;
  max-height: 72vh;
  overflow-y: auto;
  border-radius: var(--radius-lg);
  background: var(--paper);
  border: var(--border-soft);
  box-shadow: var(--shadow-3);
}

.tour-panel header {
  position: sticky;
  top: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 14px;
  background: var(--paper);
  border-bottom: var(--border-soft);
}

.tour-panel header b {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 13.5px;
  color: var(--ink);
}

.tour-panel header small {
  font-size: 11px;
  color: var(--orange-600);
  font-weight: 700;
}

.tour-bar {
  height: 3px;
  background: var(--neutral-200);
}

.tour-bar i {
  display: block;
  height: 100%;
  background: linear-gradient(90deg, var(--orange-400), var(--orange-500));
  transition: width 0.3s ease;
}

.tour-panel ol {
  list-style: none;
  margin: 0;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.tour-panel li {
  display: flex;
  gap: 10px;
  padding: 10px;
  border-radius: 10px;
  border: var(--border-soft);
  background: var(--paper);
}

.tour-panel li.done {
  background: var(--orange-50);
  border-color: var(--orange-200);
}

.step-no {
  display: grid;
  place-items: center;
  width: 22px;
  height: 22px;
  border-radius: 999px;
  background: var(--orange-100);
  color: var(--orange-600);
  font-size: 11.5px;
  font-weight: 700;
  flex-shrink: 0;
}

.step-copy {
  flex: 1;
  min-width: 0;
}

.step-copy b {
  display: block;
  font-size: 12.5px;
  color: var(--ink);
}

.step-copy b em {
  font-style: normal;
  font-weight: 400;
  font-size: 10.5px;
  color: var(--muted);
  margin-left: 5px;
}

.step-copy p {
  margin: 3px 0 0;
  font-size: 11.5px;
  line-height: 1.55;
  color: var(--neutral-600);
}

.step-copy small {
  display: block;
  margin-top: 3px;
  font-size: 10.5px;
  color: var(--orange-600);
}

.step-go {
  align-self: center;
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 5px 9px;
  border-radius: 8px;
  background: var(--orange-500);
  color: #fff;
  font-size: 11px;
  white-space: nowrap;
  flex-shrink: 0;
}

.tour-panel footer {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-top: var(--border-soft);
}

.tour-panel footer button {
  font-size: 11px;
  color: var(--muted);
  text-decoration: underline;
  text-underline-offset: 3px;
}

.tour-panel footer span {
  flex: 1;
  font-size: 10px;
  color: var(--subtle);
  text-align: right;
}
</style>
