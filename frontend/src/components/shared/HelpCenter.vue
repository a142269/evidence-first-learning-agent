<script setup lang="ts">
/**
 * 帮助中心（2026-07-17）—— 顶栏「?」按钮的完整答案。
 *
 * 平台的完整说明书：平台介绍 / 快速上手 / 逐页功能手册 / AI 学习小队 /
 * 安全与防幻觉 / 常见问题，全部内容来自 constants/platformGuide.ts 唯一真源。
 * 左栏目录 + 右栏滚动内容，学生端与教师端内容按角色切换。
 */
import { computed, ref } from "vue";
import { useRouter } from "vue-router";
import {
  ArrowRight,
  BookOpenCheck,
  Bot,
  Compass,
  HelpCircle,
  ListChecks,
  PlayCircle,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-vue-next";

import {
  AGENT_INTROS,
  STUDENT_CHECKLIST,
  STUDENT_FAQS,
  STUDENT_PAGE_GUIDES,
  STUDENT_SCENARIOS,
  STUDENT_VALUE_PROPS,
  TEACHER_CHECKLIST,
  TEACHER_FAQS,
  TEACHER_PAGE_GUIDES,
  TEACHER_SCENARIOS,
  TEACHER_VALUE_PROPS,
} from "@/constants/platformGuide";

const props = defineProps<{ role: "student" | "teacher" }>();
const emit = defineEmits<{ (e: "close"): void; (e: "replay-tour"): void }>();

const router = useRouter();

type SectionKey = "intro" | "quickstart" | "manual" | "agents" | "safety" | "faq";
const activeSection = ref<SectionKey>("intro");

const sections: Array<{ key: SectionKey; label: string; icon: any }> = [
  { key: "intro", label: "平台介绍", icon: Sparkles },
  { key: "quickstart", label: "快速上手", icon: PlayCircle },
  { key: "manual", label: "功能手册", icon: BookOpenCheck },
  { key: "agents", label: "AI 学习小队", icon: Bot },
  { key: "safety", label: "安全与防幻觉", icon: ShieldCheck },
  { key: "faq", label: "常见问题", icon: HelpCircle },
];

const isTeacher = computed(() => props.role === "teacher");
const pageGuides = computed(() => (isTeacher.value ? TEACHER_PAGE_GUIDES : STUDENT_PAGE_GUIDES));
const valueProps = computed(() => (isTeacher.value ? TEACHER_VALUE_PROPS : STUDENT_VALUE_PROPS));
const faqs = computed(() => (isTeacher.value ? TEACHER_FAQS : STUDENT_FAQS));

// 快速上手：首日清单 + 场景速查（与「播放分步引导」互补——
// 引导讲平台脉络，这里给"现在马上能做的事"和"遇到 X 该去哪"）
const checklist = computed(() => (isTeacher.value ? TEACHER_CHECKLIST : STUDENT_CHECKLIST));
const scenarios = computed(() => (isTeacher.value ? TEACHER_SCENARIOS : STUDENT_SCENARIOS));

function goTo(to: string) {
  emit("close");
  void router.push(to);
}

function replayTour() {
  emit("replay-tour");
}
</script>

<template>
  <Teleport to="body">
    <div class="help-mask" role="dialog" aria-modal="true" aria-label="帮助中心" @click.self="emit('close')">
      <div class="help-card">
        <button type="button" class="help-close" aria-label="关闭帮助中心" @click="emit('close')"><X :size="19" /></button>

        <!-- 左栏目录 -->
        <aside class="help-rail">
          <div class="help-brand">
            <span class="help-glow"><Compass :size="19" /></span>
            <div>
              <b>帮助中心</b>
              <small>{{ isTeacher ? "教师管理台使用手册" : "triple U 学习手册" }}</small>
            </div>
          </div>
          <nav class="help-nav" aria-label="帮助目录">
            <button
              v-for="section in sections"
              :key="section.key"
              type="button"
              :class="{ active: activeSection === section.key }"
              @click="activeSection = section.key"
            >
              <component :is="section.icon" :size="16" />
              <span>{{ section.label }}</span>
            </button>
          </nav>
          <button type="button" class="help-replay" @click="replayTour">
            <PlayCircle :size="16" />播放分步引导
          </button>
        </aside>

        <!-- 右栏内容 -->
        <div class="help-body">
          <!-- 平台介绍 -->
          <section v-if="activeSection === 'intro'">
            <h2>{{ isTeacher ? "这是一个什么样的管理台？" : "triple U 是什么？" }}</h2>
            <p class="help-lede">
              {{ isTeacher
                ? "triple U 教师管理台是基于多智能体的教学指挥中心：课程知识库自助建课、学情数据证据化呈现、干预动作一键直达学生。你负责教学决策，6 个 AI Agent 负责数据归因、内容生成与安全把关。"
                : "triple U 是基于大模型多智能体的个性化学习平台：6 个 AI Agent 组成你的专属学习小队，根据你的画像与认知诊断，自动完成「资源生成 → 路径规划 → 答疑讲解 → 练习评估」的完整闭环，让你专注学习本身。" }}
            </p>
            <div class="help-props">
              <article v-for="prop in valueProps" :key="prop.label">
                <b>{{ prop.label }}</b>
                <span>{{ prop.text }}</span>
              </article>
            </div>
            <div class="help-callout">
              <ListChecks :size="17" />
              <p>
                {{ isTeacher
                  ? "第一次使用？点左下角「播放分步引导」，3 步带你走完「备课 → 观察 → 干预」工作流；「功能手册」里有全部 9 个页面的详细用法。"
                  : "第一次使用？点左下角「播放分步引导」，4 步带你认识平台；「功能手册」里有全部 12 个页面的详细用法；右下角的桌宠小狐随时能讲解当前页面。" }}
              </p>
            </div>
          </section>

          <!-- 快速上手：首日清单 + 场景速查（与分步引导互补，不重复） -->
          <section v-else-if="activeSection === 'quickstart'">
            <h2>{{ isTeacher ? "第一次使用？先做这 5 件事" : "第一次使用？5 分钟做这几件事" }}</h2>
            <p class="help-lede">{{ isTeacher ? "每件事都是一次完整的功能体验，做完你就掌握了管理台的核心工作流。" : "每件事都能马上做、马上看到结果，做完你就会用整个平台了。" }}</p>
            <ol class="help-checklist">
              <li v-for="(item, index) in checklist" :key="index">
                <span class="hs-num">{{ index + 1 }}</span>
                <p>{{ item.text }}</p>
                <button type="button" @click="goTo(item.to)">{{ item.label }}<ArrowRight :size="13" /></button>
              </li>
            </ol>

            <h2 class="help-subhead">我想…就…（场景速查）</h2>
            <p class="help-lede">遇到具体需求时查这张表，每一行都能直达。</p>
            <div class="help-scenarios">
              <button v-for="item in scenarios" :key="item.want" type="button" @click="goTo(item.to)">
                <div class="hs-copy">
                  <b>{{ item.want }}</b>
                  <span>{{ item.how }}</span>
                </div>
                <ArrowRight :size="16" class="hs-arrow" />
              </button>
            </div>
          </section>

          <!-- 功能手册（逐页） -->
          <section v-else-if="activeSection === 'manual'">
            <h2>功能手册 · 全部 {{ pageGuides.length }} 个页面</h2>
            <p class="help-lede">每个页面：它是干什么的、怎么用、然后去哪。点「带我去」直接跳转。</p>
            <article v-for="guide in pageGuides" :key="guide.prefix" class="help-page">
              <header>
                <div>
                  <h3>{{ guide.name }}</h3>
                  <small>{{ guide.where }}</small>
                </div>
                <button type="button" @click="goTo(guide.prefix)">带我去<ArrowRight :size="14" /></button>
              </header>
              <p class="hp-purpose">{{ guide.purpose }}</p>
              <ol class="hp-howto">
                <li v-for="(step, index) in guide.howto" :key="index">{{ step }}</li>
              </ol>
              <p class="hp-next">下一步建议：<b>{{ guide.next.label }}</b> —— {{ guide.next.reason }}</p>
            </article>
          </section>

          <!-- AI 学习小队 -->
          <section v-else-if="activeSection === 'agents'">
            <h2>你的 6 个 AI Agent</h2>
            <p class="help-lede">每个 Agent 专职一件事，群聊里 @名字 即可召唤；它们也会在后台协同工作。</p>
            <article v-for="agent in AGENT_INTROS" :key="agent.name" class="help-agent">
              <b>{{ agent.name }} <small>{{ agent.title }}</small></b>
              <p>{{ agent.role }}</p>
              <span><Compass :size="13" />{{ agent.summon }}</span>
            </article>
          </section>

          <!-- 安全与防幻觉 -->
          <section v-else-if="activeSection === 'safety'">
            <h2>为什么可以相信 AI 的回答？</h2>
            <p class="help-lede">刺猬守护（球球）构筑了三道防线，保证学术内容无事实性错误、无敏感违规信息。</p>
            <ol class="help-steps">
              <li><span class="hs-num">1</span><div><b>入库审核（KnowledgeGuard）</b><p>老师上传的每份资料先经过内容安全扫描、注入攻击检测与学术质量审查，不合规拒绝入库——从源头阻断错误知识。</p></div></li>
              <li><span class="hs-num">2</span><div><b>检索溯源（RAG）</b><p>AI 回答基于课程知识库检索生成，每个片段带来源出处，可在证据链账本中查证。</p></div></li>
              <li><span class="hs-num">3</span><div><b>生成验证（CoV 验证链）</b><p>回答中的关键论断被逐条抽取，对照知识库核验，标注「已验证 / 不确定 / 已纠正」。</p></div></li>
            </ol>
            <div class="help-callout">
              <ShieldCheck :size="17" />
              <p>{{ isTeacher ? "上传文档被拒绝时，点文档行的审核意见可查看具体原因；安全中心可查看全部拦截与验证记录。" : "对任何回答有疑问，去「学习工具箱 → 证据链」查它的知识来源；越界或敏感问题会被礼貌拒答。" }}</p>
            </div>
          </section>

          <!-- 常见问题 -->
          <section v-else>
            <h2>常见问题</h2>
            <article v-for="faq in faqs" :key="faq.q" class="help-faq">
              <b>{{ faq.q }}</b>
              <p>{{ faq.a }}</p>
            </article>
          </section>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped lang="scss">
.help-mask {
  position: fixed;
  inset: 0;
  z-index: 320;
  background: rgba(28, 18, 10, 0.55);
  backdrop-filter: blur(3px);
  display: grid;
  place-items: center;
  padding: 24px;
}

.help-card {
  position: relative;
  display: grid;
  grid-template-columns: 230px minmax(0, 1fr);
  width: min(980px, 100%);
  height: min(680px, calc(100vh - 48px));
  background: #fff;
  border-radius: 24px;
  overflow: hidden;
  box-shadow: 0 30px 80px rgba(30, 16, 6, 0.32);
}

.help-close {
  position: absolute;
  top: 14px;
  right: 14px;
  z-index: 2;
  border: none;
  background: rgba(255, 255, 255, 0.92);
  color: #9ca3af;
  cursor: pointer;
  padding: 7px;
  border-radius: 10px;
  &:hover { background: #f5f0ec; color: #6b7280; }
}

/* ===== 左栏 ===== */
.help-rail {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 24px 18px 18px;
  background: linear-gradient(170deg, #fff4ec 0%, #fdf7f2 60%, #fbf6f1 100%);
  border-right: 1px solid #f3e7dc;
}

.help-brand {
  display: flex;
  align-items: flex-start;
  gap: 11px;
  > div { display: flex; flex-direction: column; gap: 3px; }
  b { font-size: 17px; color: #171512; }
  small { color: #a08a76; font-size: 12px; }
}

.help-glow {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  border-radius: 12px;
  background: linear-gradient(135deg, #ff8a3d, #e95514);
  color: #fff;
  flex-shrink: 0;
  box-shadow: 0 6px 16px rgba(233, 85, 20, 0.32);
}

.help-nav {
  display: flex;
  flex-direction: column;
  gap: 4px;

  button {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 11px 13px;
    border: 1.5px solid transparent;
    border-radius: 12px;
    background: transparent;
    color: #6f6559;
    font-size: 14px;
    cursor: pointer;
    text-align: left;
    transition: background-color 160ms ease-out, border-color 160ms ease-out;

    svg { color: #b39c86; flex-shrink: 0; }
    &:hover { background: rgba(255, 255, 255, 0.85); }
    &.active {
      background: #fff;
      border-color: #f2cdb2;
      color: #171512;
      font-weight: 700;
      box-shadow: 0 4px 14px rgba(233, 85, 20, 0.1);
      svg { color: #e95514; }
    }
  }
}

.help-replay {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-top: auto;
  padding: 12px 14px;
  border: none;
  border-radius: 12px;
  background: #e95514;
  color: #fff;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 6px 16px rgba(233, 85, 20, 0.28);
  transition: transform 0.15s ease;
  &:hover { transform: translateY(-1px); }
}

/* ===== 右栏 ===== */
.help-body {
  overflow-y: auto;
  padding: 28px 32px 26px;

  h2 { margin: 0 0 10px; font-size: 22px; color: #171512; letter-spacing: -0.01em; }
  .help-lede { margin: 0 0 18px; color: #5d594f; font-size: 14.5px; line-height: 1.8; }
}

.help-props {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;

  article {
    display: flex;
    flex-direction: column;
    gap: 5px;
    padding: 15px 17px;
    border: 1px solid #f0e8e0;
    border-radius: 14px;
    background: #fdfbf8;
    b { color: #d9460b; font-size: 14.5px; }
    span { color: #6f6a61; font-size: 13px; line-height: 1.65; }
  }
}

.help-callout {
  display: flex;
  gap: 11px;
  align-items: flex-start;
  margin-top: 16px;
  padding: 14px 16px;
  border: 1px solid #f2cdb2;
  border-radius: 13px;
  background: linear-gradient(150deg, #fff6ef, #fff);
  svg { color: #e95514; flex-shrink: 0; margin-top: 2px; }
  p { margin: 0; color: #6f6a61; font-size: 13px; line-height: 1.7; }
}

.help-steps {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin: 0;
  padding: 0;
  list-style: none;

  li { display: flex; gap: 13px; align-items: flex-start; }
  .hs-num {
    display: grid;
    place-items: center;
    width: 32px;
    height: 32px;
    border-radius: 11px;
    background: #fff2ea;
    color: #d9460b;
    font-weight: 800;
    font-size: 15px;
    flex-shrink: 0;
  }
  b { color: #1f1d1a; font-size: 15px; }
  p { margin: 4px 0 0; color: #6f6a61; font-size: 13.5px; line-height: 1.7; }
}

.help-subhead { margin-top: 26px !important; }

.help-checklist {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin: 0;
  padding: 0;
  list-style: none;

  li {
    display: flex;
    gap: 12px;
    align-items: center;
    padding: 12px 15px;
    border: 1px solid #f0e8e0;
    border-radius: 13px;
    background: #fdfbf8;
    p { flex: 1; margin: 0; color: #55514a; font-size: 13.5px; line-height: 1.6; }
    button {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      flex-shrink: 0;
      padding: 8px 14px;
      border: 1px solid #f1c9ae;
      border-radius: 10px;
      background: #fff;
      color: #d9460b;
      font-size: 13px;
      font-weight: 700;
      cursor: pointer;
      &:hover { background: #fff2ea; }
    }
  }
}

.help-scenarios {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;

  button {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 13px 15px;
    border: 1px solid #f0e8e0;
    border-radius: 13px;
    background: #fdfbf8;
    text-align: left;
    cursor: pointer;
    transition: border-color 160ms ease-out, transform 160ms ease-out;

    .hs-copy { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px; }
    b { color: #171512; font-size: 14px; font-weight: 700; }
    span { color: #857e73; font-size: 12.5px; line-height: 1.65; }
    .hs-arrow { flex-shrink: 0; color: #d9a06b; }

    &:hover { border-color: #f2cdb2; transform: translateY(-1px); b { color: #d9460b; } }
  }
}

@media (max-width: 760px) {
  .help-scenarios { grid-template-columns: 1fr; }
}

.help-page {
  margin-bottom: 16px;
  padding: 17px 19px;
  border: 1px solid #f0e8e0;
  border-radius: 15px;
  background: #fdfbf8;

  header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
    h3 { margin: 0; font-size: 16.5px; color: #171512; }
    small { display: block; margin-top: 3px; color: #b08946; font-size: 12px; font-weight: 700; }
    button {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      flex-shrink: 0;
      padding: 8px 14px;
      border: 1px solid #f1c9ae;
      border-radius: 10px;
      background: #fff;
      color: #d9460b;
      font-size: 13px;
      font-weight: 700;
      cursor: pointer;
      &:hover { background: #fff2ea; }
    }
  }

  .hp-purpose { margin: 10px 0 8px; color: #55514a; font-size: 13.5px; line-height: 1.7; }
  .hp-howto { margin: 0; padding-left: 20px; display: flex; flex-direction: column; gap: 4px; li { color: #6f6a61; font-size: 13px; line-height: 1.65; } }
  .hp-next { margin: 10px 0 0; color: #8a8378; font-size: 12.5px; b { color: #d9460b; } }
}

.help-agent {
  margin-bottom: 12px;
  padding: 14px 17px;
  border: 1px solid #f0e8e0;
  border-radius: 14px;
  background: #fdfbf8;

  b { color: #171512; font-size: 15px; small { margin-left: 7px; color: #b08946; font-size: 12px; font-weight: 700; } }
  p { margin: 6px 0; color: #6f6a61; font-size: 13.5px; line-height: 1.65; }
  span { display: inline-flex; align-items: center; gap: 5px; color: #8a8378; font-size: 12.5px; svg { color: #d9a06b; } }
}

.help-faq {
  margin-bottom: 14px;
  padding: 14px 17px;
  border: 1px solid #f0e8e0;
  border-radius: 14px;
  background: #fdfbf8;
  b { color: #171512; font-size: 14.5px; }
  p { margin: 7px 0 0; color: #6f6a61; font-size: 13.5px; line-height: 1.7; }
}

@media (max-width: 760px) {
  .help-card { grid-template-columns: 1fr; height: calc(100vh - 32px); }
  .help-rail { flex-direction: column; gap: 12px; padding: 16px; border-right: 0; border-bottom: 1px solid #f3e7dc; }
  .help-nav { flex-direction: row; flex-wrap: wrap; button { padding: 8px 10px; font-size: 12.5px; span { white-space: nowrap; } } }
  .help-replay { margin-top: 4px; }
  .help-body { padding: 18px; }
  .help-props { grid-template-columns: 1fr; }
}
</style>
