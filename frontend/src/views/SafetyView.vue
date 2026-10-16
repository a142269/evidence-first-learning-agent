<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import {
  BookMarked,
  BookOpen,
  CheckCircle2,
  ChevronRight,
  Database,
  FlaskConical,
  Gavel,
  History,
  Library,
  Loader2,
  Network,
  RefreshCcw,
  ShieldCheck,
  ShieldAlert,
  XCircle,
} from "lucide-vue-next";

import ArtCard from "@/components/companion/ArtCard.vue";
import SectionTitle from "@/components/companion/SectionTitle.vue";
import ProgressRing from "@/components/companion/ProgressRing.vue";
import Avatar from "@/components/companion/Avatar.vue";
import { partners } from "@/constants/companion";
import { useSession } from "@/composables/useSession";
import { fetchCockpit } from "@/api/cockpit";
import { chatWithCov, getCovDemoCases, type CovResult } from "@/api/chat";
import {
  runAdversarialLeakage,
  listInducerStrategies,
  type AdversarialLeakageResult,
} from "@/api/safety";

const { userId } = useSession();

const loading = ref(true);
const error = ref("");

// ---- cockpit 子块 ----
interface SafetyBlock {
  scaffolding_score?: number;
  answer_leak_risk?: number;
  misconception_reinforcement_risk?: number;
  student_uptake_prompt?: string;
  overall_risk?: number;
  evidence?: string[];
  error?: string;
}

interface LedgerClaim {
  claim: string;
  text?: string;
  confidence?: number;
  is_supported?: boolean;
  sources?: Array<{ type: string; ref: string; confidence?: number }>;
  conflict_warning?: boolean;
  conflict_note?: string;
}

interface LedgerBlock {
  claims?: LedgerClaim[];
  total_claims?: number;
  supported_claims?: number;
  unsupported_claims?: number;
  conflicts?: number;
  support_rate?: number;
  source_distribution?: Record<string, number>;
  error?: string;
}

interface DebateTrace {
  round?: number;
  expert?: string;
  critic?: string;
  verdict?: string;
  [key: string]: unknown;
}

const safety = ref<SafetyBlock>({});
const ledger = ref<LedgerBlock>({});
const covClaims = ref<Array<{ claim: string; verified?: boolean; sources?: string[] }>>([]);
const debateTraces = ref<DebateTrace[]>([]);

const SOURCE_LABELS: Record<string, string> = {
  textbook: "教材",
  kg: "知识图谱",
  rag_chunk: "RAG 切片",
  mistake: "错题记录",
  history: "学习历史",
};

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const data: any = await fetchCockpit(userId.value);
    safety.value = data?.safety ?? {};
    ledger.value = data?.ledger ?? {};
    covClaims.value = data?.cov?.recent_claims ?? [];
    debateTraces.value = data?.debate?.recent_traces ?? [];
  } catch (e: any) {
    error.value = "安全评估服务未连接，请先启动后端。";
  }
  loading.value = false;
}

const supportRate = computed(() => Math.round((ledger.value.support_rate ?? 0) * 100));
const scaffoldPct = computed(() => Math.round((safety.value.scaffolding_score ?? 0) * 100));
const overallRiskPct = computed(() => Math.round((safety.value.overall_risk ?? 0) * 100));

const riskRows = computed<Array<[string, number]>>(() => [
  ["答案泄漏风险", Math.round((safety.value.answer_leak_risk ?? 0) * 100)],
  ["误概念强化风险", Math.round((safety.value.misconception_reinforcement_risk ?? 0) * 100)],
  ["综合风险", overallRiskPct.value],
]);

const sourceRows = computed(() => {
  const dist = ledger.value.source_distribution ?? {};
  const max = Math.max(1, ...Object.values(dist));
  // 固定顺序：教材 → 知识图谱 → RAG 切片 → 错题记录 → 学习历史
  const orderedKeys = ["textbook", "kg", "rag_chunk", "mistake", "history"];
  return orderedKeys
    .filter((k) => dist[k] != null)
    .map((type) => ({
      type,
      label: SOURCE_LABELS[type] ?? type,
      count: dist[type] ?? 0,
      pct: Math.round(((dist[type] ?? 0) / max) * 100),
    }));
});

function sourceIcon(type: string) {
  switch (type) {
    case "textbook":
      return BookOpen;
    case "kg":
      return Network;
    case "rag_chunk":
      return Database;
    case "mistake":
      return Library;
    case "history":
      return History;
    default:
      return BookMarked;
  }
}

// ---- CoV 交互核验 ----
const covText = ref("");
const covLoading = ref(false);
const covResult = ref<CovResult | null>(null);
const demoCases = ref<Array<Record<string, any>>>([]);

const covAxes = computed(() => covResult.value?.axes ?? covResult.value?.results ?? []);

async function runCov(text?: string) {
  const t = (text ?? covText.value).trim();
  if (!t || covLoading.value) return;
  covText.value = t;
  covLoading.value = true;
  covResult.value = null;
  try {
    covResult.value = await chatWithCov(t);
  } catch (e: any) {
    error.value = `CoV 核验失败：${e?.detail ?? e?.message ?? e}`;
  }
  covLoading.value = false;
}

async function loadDemoCases() {
  try {
    const { cases } = await getCovDemoCases();
    demoCases.value = cases ?? [];
  } catch {
    demoCases.value = [];
  }
}

const AXIS_LABELS: Record<string, string> = {
  factual: "事实性",
  pedagogical: "教学法",
  bloom: "Bloom 适配",
  citation: "引用完整",
  safety: "答案安全",
  difficulty: "难度适配",
};

type AxisState = "pass" | "uncertain" | "fail";

/** 后端轴对象形如 {axis, verdict, confidence, issue, correction} */
function axisState(axis: Record<string, any>): AxisState {
  const v = String(axis.verdict ?? "").toLowerCase();
  if (["pass", "ok", "verified", "supported", "safe"].includes(v)) return "pass";
  if (["fail", "reject", "unsafe", "error"].includes(v)) return "fail";
  if (typeof axis.passed === "boolean") return axis.passed ? "pass" : "fail";
  return "uncertain";
}

function axisIcon(state: AxisState) {
  return state === "pass" ? CheckCircle2 : XCircle;
}

// ---- 答案泄露对抗测试 ----
const advQuestion = ref("2x + 3 = 7，求 x");
const advAnswer = ref("x = 2");
const advLoading = ref(false);
const advResult = ref<AdversarialLeakageResult | null>(null);
const advStrategies = ref<Array<{ strategy: string; inducer: string }>>([]);

async function loadAdvStrategies() {
  try {
    const r = await listInducerStrategies();
    advStrategies.value = r.strategies ?? [];
  } catch {
    advStrategies.value = [];
  }
}

async function runAdv() {
  if (!advQuestion.value.trim() || !advAnswer.value.trim() || advLoading.value) return;
  advLoading.value = true;
  advResult.value = null;
  try {
    advResult.value = await runAdversarialLeakage({
      question: advQuestion.value.trim(),
      correct_answer: advAnswer.value.trim(),
    });
  } catch (e: any) {
    error.value = `对抗测试失败：${e?.detail ?? e?.message ?? e}`;
  }
  advLoading.value = false;
}

const STRATEGY_LABELS: Record<string, string> = {
  direct_demand: "直接索要",
  spoof_teacher: "伪装老师",
  emotional_pressure: "情绪施压",
  option_only: "索取选项",
  rule_override: "忽略规则",
};

onMounted(() => {
  void load();
  void loadDemoCases();
  void loadAdvStrategies();
});
</script>

<template>
  <div class="layout-two safety-page companion-page">
    <ArtCard class="safety-main" deco>
      <SectionTitle title="内容安全 · 防幻觉中心" sub="教学安全评估 · 证据链账本 · CoV 五轴核验 · 多智能体辩论仲裁">
        <template #icon>
          <span class="safety-logo">
            <ShieldCheck :size="16" />
          </span>
        </template>
        <template #action>
          <button class="ghost-btn" type="button" :disabled="loading" @click="load">
            <RefreshCcw :size="14" />刷新
          </button>
        </template>
      </SectionTitle>

      <p v-if="error" class="page-error">{{ error }}</p>

      <!-- 顶部双列：教学安全评估 + CoV 五轴 -->
      <div class="safety-row-2col">
        <!-- 教学安全评估 -->
        <ArtCard class="safety-block">
          <SectionTitle title="教学安全评估" sub="对 AI 讲解回复做「教学法安全」打分">
            <template #action><ShieldCheck :size="16" /></template>
          </SectionTitle>
          <div class="safety-grid">
            <div class="scaffold-ring">
              <ProgressRing :value="scaffoldPct" :label="`${scaffoldPct}%`" />
              <div>
                <strong>脚手架得分</strong>
                <small>引导思考而非直给答案的程度</small>
              </div>
            </div>
            <div class="risk-list">
              <div v-for="[label, pct] in riskRows" :key="label" class="small-progress">
                <span class="dot" />
                <span class="lbl">{{ label }}</span>
                <div class="bar">
                  <i :style="{ width: `${Math.max(pct, 2)}%`, background: pct >= 50 ? 'var(--status-error)' : pct >= 20 ? 'var(--status-queue)' : 'var(--status-running)' }" />
                </div>
                <em>{{ pct }}%</em>
              </div>
              <p v-if="safety.student_uptake_prompt" class="uptake">
                <b>启发式追问示例：</b>「{{ safety.student_uptake_prompt }}」
              </p>
            </div>
          </div>
          <div v-if="safety.evidence?.length" class="evidence-tags">
            <span v-for="e in safety.evidence" :key="e">{{ e }}</span>
          </div>
        </ArtCard>

        <!-- CoV 五轴核验 -->
        <ArtCard class="safety-block">
          <SectionTitle title="CoV-Edu 五轴幻觉检验" sub="事实性 / 答案泄漏 / 误概念 / 引用完整 / 难度适配">
            <template #action><FlaskConical :size="16" /></template>
          </SectionTitle>
          <div class="cov-input">
            <textarea
              v-model="covText"
              rows="1"
              placeholder="粘贴一段 AI 生成的讲解内容，运行五轴核验…"
            />
            <button class="primary-btn" type="button" :disabled="covLoading || !covText.trim()" @click="runCov()">
              <Loader2 v-if="covLoading" :size="14" class="spin" />核验
            </button>
          </div>
          <div v-if="demoCases.length" class="demo-pills">
            <small>演示用例：</small>
            <button
              v-for="(c, i) in demoCases.slice(0, 5)"
              :key="i"
              type="button"
              @click="runCov(String(c.text ?? c.case_text ?? c.content ?? ''))"
            >
              {{ c.label ?? c.axis ?? c.name ?? `用例 ${i + 1}` }}
            </button>
          </div>
          <div v-if="covResult" class="cov-result">
            <p v-if="covResult.summary" class="cov-summary">{{ covResult.summary }}</p>
            <div v-if="covAxes.length" class="axis-grid">
              <div v-for="(axis, i) in covAxes" :key="i" :class="['axis-card', axisState(axis)]">
                <component :is="axisIcon(axisState(axis))" :size="15" />
                <b>
                  {{ AXIS_LABELS[String(axis.axis ?? '')] ?? axis.label ?? axis.axis ?? `轴 ${i + 1}` }}
                  <em v-if="axis.confidence != null">{{ Math.round(Number(axis.confidence) * 100) }}%</em>
                </b>
                <small>{{ axis.issue ?? axis.detail ?? axis.reason ?? "通过" }}</small>
                <small v-if="axis.correction" class="correction">建议：{{ axis.correction }}</small>
              </div>
            </div>
            <p v-if="(covResult as any).revised_text" class="cov-revised">
              <b>修订建议：</b>{{ (covResult as any).revised_text }}
            </p>
            <pre v-if="!covAxes.length" class="cov-raw">{{ JSON.stringify(covResult, null, 2).slice(0, 800) }}</pre>
          </div>
          <!-- 近期核验论断 -->
          <div v-if="covClaims.length" class="claim-list">
            <b class="claim-list-title">近期核验诊断</b>
            <div v-for="(c, i) in covClaims" :key="i" class="claim-row">
              <component :is="c.verified ? CheckCircle2 : XCircle" :size="14" :class="c.verified ? 'ok' : 'bad'" />
              <span class="claim-text">{{ c.claim }}</span>
              <small v-if="c.sources?.length" class="claim-src">{{ c.sources[0] }}</small>
            </div>
          </div>
        </ArtCard>
      </div>

      <!-- 答案泄露对抗测试 -->
      <ArtCard class="safety-block">
        <SectionTitle title="答案泄露对抗测试" sub="5 类诱导策略红队测试 · AI 是否会泄露答案">
          <template #action><ShieldAlert :size="16" /></template>
        </SectionTitle>
        <div class="adv-form">
          <div class="adv-field">
            <label>题目原文</label>
            <input v-model="advQuestion" placeholder="输入一道题目的原文" />
          </div>
          <div class="adv-field">
            <label>正确答案</label>
            <input v-model="advAnswer" placeholder="输入正确答案" />
          </div>
          <button class="primary-btn adv-btn" type="button" :disabled="advLoading || !advQuestion.trim() || !advAnswer.trim()" @click="runAdv">
            <Loader2 v-if="advLoading" :size="14" class="spin" />开始对抗测试
          </button>
        </div>
        <div v-if="advStrategies.length" class="adv-strategies">
          <small>测试策略：</small>
          <span v-for="s in advStrategies" :key="s.strategy" class="adv-strategy-pill">
            {{ STRATEGY_LABELS[s.strategy] ?? s.strategy }}
          </span>
        </div>
        <div v-if="advResult" class="adv-result">
          <div class="adv-scores">
            <div :class="['adv-score-card', advResult.passed ? 'pass' : 'fail']">
              <b>{{ advResult.passed ? '✓ 通过' : '✗ 未通过' }}</b>
              <small>综合判定</small>
            </div>
            <div class="adv-score-card">
              <b>{{ Math.round(advResult.leakage_score * 100) }}%</b>
              <small>泄露风险</small>
            </div>
            <div class="adv-score-card">
              <b>{{ Math.round(advResult.scaffolding_score * 100) }}%</b>
              <small>脚手架分</small>
            </div>
            <div class="adv-score-card">
              <b>{{ Math.round(advResult.misconception_risk * 100) }}%</b>
              <small>误概念风险</small>
            </div>
            <div class="adv-score-card">
              <b>{{ Math.round(advResult.overall_risk * 100) }}%</b>
              <small>综合风险</small>
            </div>
          </div>
          <p v-if="advResult.recommendation" class="adv-recommendation">
            <b>建议：</b>{{ advResult.recommendation }}
          </p>
          <div class="adv-scenarios">
            <div v-for="(sc, i) in advResult.scenarios" :key="i" class="adv-scenario">
              <header>
                <b>{{ STRATEGY_LABELS[sc.strategy] ?? sc.strategy }}</b>
                <em v-if="sc.scores?.answer_leak_risk != null">泄露 {{ Math.round(Number(sc.scores.answer_leak_risk) * 100) }}%</em>
              </header>
              <p class="adv-inducer">诱导：「{{ sc.inducer }}」</p>
              <p v-if="sc.tutor_response" class="adv-tutor-res">AI 回复：{{ String(sc.tutor_response).slice(0, 120) }}{{ String(sc.tutor_response).length > 120 ? '…' : '' }}</p>
              <p v-if="sc.revised_response" class="adv-revised">修订版：{{ sc.revised_response }}</p>
              <div v-if="sc.issues?.length" class="adv-issues">
                <span v-for="(iss, j) in sc.issues" :key="j">⚠️ {{ iss }}</span>
              </div>
            </div>
          </div>
        </div>
      </ArtCard>

      <!-- 证据链账本 -->
      <ArtCard class="safety-block">
        <SectionTitle title="证据链账本" sub="每条学术论断都有出处 · 5 类证据源">
          <template #action><BookMarked :size="16" /></template>
        </SectionTitle>
        <div class="ledger-head">
          <div class="scaffold-ring">
            <ProgressRing :value="supportRate" :label="`${supportRate}%`" />
            <div>
              <strong>论断支撑率</strong>
              <small>{{ ledger.supported_claims ?? 0 }}/{{ ledger.total_claims ?? 0 }} 条有据可查 · 冲突 {{ ledger.conflicts ?? 0 }} 条</small>
            </div>
          </div>
          <div class="source-grid">
            <div v-for="s in sourceRows" :key="s.label" class="source-cell">
              <component :is="sourceIcon(s.type)" :size="14" />
              <span class="src-label">{{ s.label }}</span>
              <em class="src-count">{{ s.count }}</em>
            </div>
          </div>
        </div>
        <div v-for="(c, i) in ledger.claims ?? []" :key="i" class="ledger-claim-row">
          <component :is="c.is_supported ? CheckCircle2 : XCircle" :size="14" :class="c.is_supported ? 'ok' : 'bad'" />
          <strong class="claim-text">{{ c.claim }}</strong>
          <span v-if="c.sources?.length" class="claim-src-tag">
            {{ SOURCE_LABELS[c.sources[0].type] ?? c.sources[0].type }} · {{ c.sources[0].ref }}
          </span>
          <em v-if="c.confidence != null" class="claim-conf">置信 {{ Math.round((c.confidence ?? 0) * 100) }}%</em>
          <ChevronRight :size="14" class="claim-arrow" />
        </div>
      </ArtCard>
    </ArtCard>

    <aside class="right-column">
      <ArtCard class="side-card" deco>
        <SectionTitle title="多智能体辩论仲裁" sub="专家 vs 批判者 · 分歧收敛">
          <template #action><Gavel :size="15" /></template>
        </SectionTitle>
        <p v-if="!debateTraces.length" class="empty-hint">暂无辩论记录。当证据链发现来源冲突时会自动发起辩论。</p>
        <div v-for="(t, i) in debateTraces" :key="i" class="debate-row">
          <b>R{{ (t.round ?? i) + 1 }}</b>
          <div>
            <p v-if="t.expert"><strong>专家：</strong>{{ t.expert }}</p>
            <p v-if="t.critic"><strong>批判：</strong>{{ t.critic }}</p>
            <small>{{ t.verdict ?? "进行中" }}</small>
          </div>
        </div>
      </ArtCard>

      <ArtCard class="side-card" deco>
        <SectionTitle title="安全守护值班" />
        <div class="mini-chat">
          <Avatar :partner="partners[5]" size="sm" pulse />
          <p>球球在此值班：每轮生成内容都会先过教学安全评估与五轴核验，再送达你的群聊。</p>
        </div>
        <div class="mini-chat">
          <Avatar :partner="partners[4]" size="sm" pulse />
          <p>练习题遵循「不泄漏答案」策略；讲解优先给思考路径，脚手架得分低的回复会被打回重写。</p>
        </div>
      </ArtCard>

      <ArtCard class="side-card" deco>
        <SectionTitle title="机制说明" />
        <div class="algo-copy">
          <p><b>教学安全</b>：评估回复的脚手架程度、答案泄漏与误概念强化风险。</p>
          <p><b>证据链</b>：论断绑定教材/知识图谱/RAG/错题/历史五类出处。</p>
          <p><b>CoV-Edu</b>：Chain-of-Verification 教育定制版，五轴复核关键论断。</p>
          <p><b>辩论仲裁</b>：来源冲突时由专家/批判者多轮辩论收敛结论。</p>
        </div>
      </ArtCard>
    </aside>
  </div>
</template>

<style scoped>
.spin {
  animation: sf-spin 1s linear infinite;
}

@keyframes sf-spin {
  to {
    transform: rotate(360deg);
  }
}

.page-error {
  margin: 0 0 12px;
  padding: 10px 14px;
  border-radius: 10px;
  background: #fdf0ef;
  border: 1px solid #efc7c2;
  color: var(--status-error);
  font-size: 12.5px;
}

.empty-hint {
  padding: 12px;
  border-radius: 10px;
  background: var(--paper-2);
  color: var(--muted);
  font-size: 12.5px;
  line-height: 1.6;
}

.safety-block {
  margin-top: 10px;
  padding: 14px 16px 16px;
}

/* 顶部盾形 logo */
.safety-logo {
  display: inline-grid;
  place-items: center;
  width: 24px;
  height: 24px;
  border-radius: 7px;
  background: linear-gradient(135deg, #ea5a1a 0%, #c8480f 100%);
  color: #fff;
  box-shadow: 0 1px 2px rgba(234, 90, 26, 0.28);
}

/* 顶层 SectionTitle 离左边框一些距离，避免贴边 */
.safety-page .safety-main > .section-head:first-of-type {
  padding-left: 12px;
}

/* 顶部双列：教学安全评估 + CoV 五轴 */
.safety-row-2col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-top: 10px;
}

/* 紧凑 SectionTitle */
.safety-page .section-head {
  margin: 0 0 10px;
}

.safety-page .section-copy h2 {
  font-size: 17px;
  font-weight: 700;
}

.safety-page .section-copy p {
  font-size: 12px;
  margin-top: 2px;
}

.safety-row-2col .safety-block {
  margin-top: 0;
}

.safety-grid,
.ledger-head {
  display: grid;
  grid-template-columns: minmax(160px, 200px) 1fr;
  gap: 14px;
  align-items: center;
}

.ledger-head {
  align-items: center;
  padding: 10px 14px;
  border-radius: 10px;
  background: var(--paper-2);
}

.scaffold-ring {
  display: flex;
  align-items: center;
  gap: 12px;
}

.scaffold-ring strong {
  display: block;
  font-size: 13.5px;
  color: var(--ink);
}

.scaffold-ring small {
  font-size: 11.5px;
  color: var(--muted);
}

.risk-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

/* 风险条左侧橙色圆点（覆盖全局 .small-progress 3 列） */
.safety-page .small-progress {
  display: grid;
  grid-template-columns: 10px 78px minmax(0, 1fr) 40px;
  gap: 8px;
  align-items: center;
  margin: 4px 0;
}

.safety-page .small-progress .dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--orange-500);
  justify-self: center;
}

.safety-page .small-progress .lbl {
  white-space: nowrap;
  color: var(--neutral-700);
  font-size: 12.5px;
}

.uptake {
  margin: 6px 0 0;
  padding: 6px 10px;
  border-radius: 9px;
  background: var(--orange-50);
  border: 1px solid var(--orange-200);
  font-size: 12px;
  line-height: 1.55;
  color: var(--neutral-700);
}

.evidence-tags {
  margin-top: 6px;
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.evidence-tags span {
  padding: 3px 9px;
  border-radius: 999px;
  background: var(--paper-2);
  border: var(--border-soft);
  font-size: 10.5px;
  color: var(--muted);
  font-family: var(--mono);
}

/* ---------- CoV ---------- */
.cov-input {
  display: flex;
  gap: 8px;
  align-items: stretch;
}

.cov-input textarea {
  flex: 1;
  padding: 7px 12px;
  border-radius: 9px;
  border: var(--border-soft);
  background: var(--paper);
  font-size: 13px;
  resize: vertical;
  min-height: 34px;
  line-height: 1.45;
}

.demo-pills {
  margin-top: 6px;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.demo-pills small {
  color: var(--muted);
  font-size: 11.5px;
}

.demo-pills button {
  padding: 4px 10px;
  border-radius: 999px;
  border: var(--border-soft);
  background: var(--paper);
  font-size: 11.5px;
  color: var(--neutral-600);
}

.demo-pills button:hover {
  border-color: var(--orange-300);
  color: var(--orange-600);
}

.cov-result {
  margin-top: 12px;
}

.axis-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 8px;
}

.axis-card {
  padding: 10px 12px;
  border-radius: 10px;
  border: var(--border-soft);
  background: var(--paper);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.axis-card.pass {
  border-color: #cdecd9;
  background: #f2fbf6;
  color: var(--status-running);
}

.axis-card.fail {
  border-color: #efc7c2;
  background: #fdf4f3;
  color: var(--status-error);
}

.axis-card.uncertain {
  border-color: #f2ddb8;
  background: #fdf9f0;
  color: var(--status-queue);
}

.axis-card b em {
  font-style: normal;
  font-weight: 400;
  font-size: 10.5px;
  color: var(--muted);
  margin-left: 4px;
}

.axis-card .correction {
  color: var(--status-info);
}

.cov-summary {
  margin: 0 0 10px;
  padding: 8px 12px;
  border-radius: 9px;
  background: var(--paper-2);
  font-size: 12.5px;
  color: var(--neutral-700);
  line-height: 1.6;
}

.cov-revised {
  margin: 10px 0 0;
  padding: 10px 12px;
  border-radius: 9px;
  background: #f2fbf6;
  border: 1px solid #cdecd9;
  font-size: 12.5px;
  line-height: 1.65;
  color: var(--neutral-700);
}

.axis-card b {
  font-size: 12.5px;
  color: var(--ink);
}

.axis-card small {
  font-size: 11px;
  color: var(--muted);
  line-height: 1.5;
}

.cov-raw {
  padding: 10px;
  border-radius: 9px;
  background: var(--neutral-800);
  color: #e8e6e1;
  font-size: 11px;
  line-height: 1.5;
  overflow-x: auto;
  font-family: var(--mono);
}

.claim-list {
  margin-top: 12px;
}

.claim-list-title {
  display: block;
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 6px;
}

.claim-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 5px 0;
  border-bottom: 1px dashed var(--neutral-200);
  font-size: 12.5px;
  color: var(--ink);
  line-height: 1.5;
}

.claim-row:last-child {
  border-bottom: 0;
}

.claim-row .claim-text {
  flex: 1;
  min-width: 0;
}

.claim-row .claim-src {
  flex-shrink: 0;
  font-size: 10.5px;
  color: var(--subtle);
  font-family: var(--mono);
  white-space: nowrap;
  margin-left: auto;
  align-self: center;
}

.ok {
  color: var(--status-running);
}

.bad {
  color: var(--status-error);
}

/* ---------- 证据链 ---------- */
/* 来源分布：2 列布局（左 3 行 + 右 2 行） */
.source-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  grid-template-rows: repeat(3, auto);
  grid-auto-flow: column;
  column-gap: 16px;
  row-gap: 4px;
}

.source-cell {
  display: grid;
  grid-template-columns: 18px 1fr auto;
  align-items: center;
  gap: 6px;
  padding: 4px 0;
  color: var(--neutral-500);
}

.source-cell :deep(svg) {
  color: var(--orange-500);
}

.source-cell .src-label {
  font-size: 12px;
  color: var(--neutral-600);
}

.source-cell .src-count {
  font-style: normal;
  font-size: 12.5px;
  color: var(--ink);
  font-weight: 600;
  font-family: var(--mono);
}

/* 论断行（与右侧栏的右侧箭头排版一致） */
.ledger-claim-row {
  display: grid;
  grid-template-columns: 18px minmax(0, 1.4fr) minmax(0, 1fr) auto 14px;
  align-items: center;
  gap: 10px;
  padding: 7px 4px;
  border-bottom: 1px solid var(--neutral-100);
  font-size: 12.5px;
  color: var(--ink);
  cursor: pointer;
  transition: background .15s;
}

.ledger-claim-row:last-child {
  border-bottom: 0;
}

.ledger-claim-row:hover {
  background: var(--paper-2);
}

.ledger-claim-row .claim-text {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.ledger-claim-row .claim-src-tag {
  font-size: 10.5px;
  color: var(--muted);
  font-family: var(--mono);
  padding: 1px 6px;
  border-radius: 4px;
  background: var(--paper-2);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.ledger-claim-row .claim-conf {
  font-style: normal;
  font-size: 11px;
  color: var(--muted);
  white-space: nowrap;
}

.ledger-claim-row .claim-arrow {
  color: var(--neutral-300);
}

.ledger-claim-row:hover .claim-arrow {
  color: var(--orange-500);
}

.conflict {
  color: var(--status-queue) !important;
}

/* ---------- 辩论 ---------- */
.debate-row {
  display: flex;
  gap: 10px;
  padding: 9px 0;
  border-bottom: 1px dashed var(--neutral-200);
}

.debate-row b {
  display: grid;
  place-items: center;
  width: 26px;
  height: 26px;
  border-radius: 8px;
  background: var(--orange-100);
  color: var(--orange-600);
  font-size: 11px;
  flex-shrink: 0;
}

.debate-row p {
  margin: 0 0 3px;
  font-size: 12px;
  line-height: 1.55;
  color: var(--neutral-600);
}

.debate-row small {
  font-size: 11px;
  color: var(--status-running);
}

.algo-copy p {
  margin: 0 0 8px;
  font-size: 12px;
  line-height: 1.65;
  color: var(--neutral-600);
}

@media (max-width: 1100px) {
  .safety-row-2col {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 900px) {
  .safety-grid,
  .ledger-head,
  .source-grid,
  .adv-form {
    grid-template-columns: 1fr;
  }

  .ledger-claim-row {
    grid-template-columns: 18px minmax(0, 1fr) auto 14px;
  }

  .ledger-claim-row .claim-src-tag {
    display: none;
  }
}

/* ---------- 对抗测试 ---------- */
.adv-form {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) auto;
  gap: 10px;
  align-items: end;
}

.adv-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.adv-field label {
  font-size: 11.5px;
  color: var(--muted);
}

.adv-field input {
  height: 36px;
  padding: 0 12px;
  border-radius: 9px;
  border: var(--border-soft);
  background: var(--paper);
  font-size: 13px;
}

.adv-btn {
  height: 36px;
}

.adv-strategies {
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.adv-strategies small {
  font-size: 11.5px;
  color: var(--muted);
}

.adv-strategy-pill {
  padding: 3px 10px;
  border-radius: 999px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  font-size: 11px;
  color: #dc2626;
}

.adv-result {
  margin-top: 14px;
}

.adv-scores {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 8px;
  margin-bottom: 12px;
}

.adv-score-card {
  padding: 10px 12px;
  border-radius: 10px;
  border: var(--border-soft);
  background: var(--paper);
  text-align: center;
}

.adv-score-card.pass {
  background: #f2fbf6;
  border-color: #cdecd9;
}

.adv-score-card.fail {
  background: #fdf4f3;
  border-color: #efc7c2;
}

.adv-score-card b {
  display: block;
  font-size: 16px;
  color: var(--ink);
}

.adv-score-card small {
  font-size: 11px;
  color: var(--muted);
}

.adv-recommendation {
  padding: 10px 12px;
  border-radius: 9px;
  background: var(--orange-50);
  border: 1px solid var(--orange-200);
  font-size: 12.5px;
  color: var(--neutral-700);
  line-height: 1.6;
  margin: 0 0 12px;
}

.adv-scenarios {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.adv-scenario {
  padding: 10px 12px;
  border-radius: 10px;
  border: var(--border-soft);
  background: var(--paper);
}

.adv-scenario header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.adv-scenario header b {
  font-size: 13px;
  color: var(--ink);
}

.adv-scenario header em {
  font-style: normal;
  font-size: 11px;
  color: var(--status-error);
  margin-left: auto;
}

.adv-inducer {
  margin: 0 0 4px;
  font-size: 12px;
  color: var(--neutral-600);
  line-height: 1.55;
}

.adv-tutor-res {
  margin: 0 0 4px;
  font-size: 12px;
  color: var(--muted);
  line-height: 1.55;
}

.adv-revised {
  margin: 4px 0 0;
  padding: 6px 10px;
  border-radius: 7px;
  background: #f2fbf6;
  font-size: 12px;
  color: var(--status-running);
  line-height: 1.55;
}

.adv-issues {
  margin-top: 6px;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.adv-issues span {
  font-size: 11.5px;
  color: var(--status-queue);
}

.primary-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0 16px;
  height: 34px;
  border-radius: 9px;
  background: var(--orange-500);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  border: none;
  cursor: pointer;
  flex-shrink: 0;
}

.primary-btn:hover:not(:disabled) {
  background: var(--orange-600);
}

.primary-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* ============================================================
 * v2 · SafetyView 排版修复层（2026-07-11）
 * 目标：卡片等高对齐 + 5 score card 网格化 + 右侧栏内容加密度
 * 保持既有色系与结构，仅调整间距/网格/字阶
 * ============================================================ */
.safety-page {
  --sf-line: #e8e4dc;
  --sf-line-2: #d6d0c4;
  --sf-panel-2: #fbf9f4;
  --sf-brand: #F97316;
  --sf-brand-soft: #FFF3E8;
  --sf-brand-line: #FDBA74;
  --sf-brand-ink: #C2410C;
  --sf-ok: #16A34A;
  --sf-warn: #F59E0B;
  --sf-err: #DC2626;
  --sf-info: #2563EB;
  gap: 20px;
}

/* ---------- 顶部双列等高 ---------- */
.safety-page .safety-row-2col {
  gap: 16px;
  align-items: stretch;
}

.safety-page .safety-row-2col > .safety-block {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 20px 22px;
  border-radius: 16px;
  border: 1px solid var(--sf-line);
  box-shadow: 0 1px 2px rgba(20, 24, 28, 0.04), 0 8px 24px -20px rgba(20, 24, 28, 0.12);
}

.safety-page .safety-row-2col > .safety-block > .section-head {
  flex-shrink: 0;
}

/* 让每个卡片的"内容"占满剩余空间，从而实现等高 */
.safety-page .safety-row-2col > .safety-block > *:not(.section-head):last-child {
  margin-top: auto;
}

.safety-page .safety-block {
  padding: 20px 22px;
  border-radius: 16px;
  border: 1px solid var(--sf-line);
  box-shadow: 0 1px 2px rgba(20, 24, 28, 0.04), 0 8px 24px -20px rgba(20, 24, 28, 0.12);
  transition: box-shadow 220ms cubic-bezier(0.2, 0, 0, 1);
}

.safety-page .safety-block:hover {
  box-shadow: 0 2px 4px rgba(20, 24, 28, 0.06), 0 20px 40px -22px rgba(20, 24, 28, 0.16);
}

/* ---------- 教学安全评估 · 环 + 3 风险条更宽松 ---------- */
.safety-page .safety-grid {
  grid-template-columns: 180px 1fr;
  gap: 20px;
  padding: 8px 4px;
}

.safety-page .scaffold-ring strong {
  font-size: 14px;
  font-weight: 700;
  color: #1a1d21;
}

.safety-page .small-progress {
  grid-template-columns: 10px 86px minmax(0, 1fr) 44px;
  padding: 6px 8px;
  border-radius: 8px;
  transition: background 220ms;
}

.safety-page .small-progress:hover {
  background: var(--sf-panel-2);
}

.safety-page .uptake {
  margin-top: 12px;
  padding: 12px 14px;
  border-radius: 12px;
  background: var(--sf-brand-soft);
  border: 1px solid var(--sf-brand-line);
  color: var(--sf-brand-ink);
}

/* ---------- CoV 五轴 · demo pills 换行 + 近期核验清晰 ---------- */
.safety-page .demo-pills {
  flex-wrap: wrap;
  gap: 6px;
  padding: 8px 0;
}

.safety-page .demo-pills small {
  display: block;
  width: 100%;
  margin-bottom: 4px;
  font-size: 11.5px;
  font-weight: 600;
  color: #6b7480;
}

.safety-page .demo-pills button {
  padding: 5px 12px;
  border-radius: 999px;
  border: 1px solid var(--sf-line-2);
  background: #fff;
  font-size: 11.5px;
  font-family: var(--mono, monospace);
  color: #45505c;
  cursor: pointer;
  transition: all 220ms;
}

.safety-page .demo-pills button:hover {
  border-color: var(--sf-brand-line);
  background: var(--sf-brand-soft);
  color: var(--sf-brand-ink);
}

.safety-page .claim-list {
  margin-top: auto;
  padding: 12px 14px;
  border-radius: 12px;
  background: var(--sf-panel-2);
  border: 1px solid var(--sf-line);
}

.safety-page .claim-list-title {
  display: block;
  margin-bottom: 8px;
  font-size: 12.5px;
  font-weight: 650;
  color: #1a1d21;
}

.safety-page .claim-row {
  display: grid;
  grid-template-columns: 16px minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
  padding: 6px 0;
  border-bottom: 1px dashed var(--sf-line);
  font-size: 12px;
}

.safety-page .claim-row:last-child {
  border-bottom: none;
}

.safety-page .claim-row .ok { color: var(--sf-ok); }
.safety-page .claim-row .bad { color: var(--sf-err); }

.safety-page .claim-text {
  color: #1a1d21;
  line-height: 1.5;
}

.safety-page .claim-src {
  font-family: var(--mono, monospace);
  color: #98a1ab;
  font-size: 10.5px;
}

/* ---------- 答案泄露对抗测试：5 score card 自适应网格 ---------- */
.safety-page .adv-form {
  display: grid;
  grid-template-columns: 1fr 1fr auto;
  gap: 12px;
  align-items: end;
  padding: 4px 0 12px;
}

.safety-page .adv-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.safety-page .adv-field label {
  font-size: 11.5px;
  font-weight: 600;
  color: #6b7480;
  letter-spacing: 0.02em;
}

.safety-page .adv-field input {
  height: 40px;
  padding: 0 14px;
  border-radius: 10px;
  border: 1px solid var(--sf-line-2);
  background: #fff;
  font-size: 13px;
  color: #1a1d21;
  transition: border-color 220ms, box-shadow 220ms;
}

.safety-page .adv-field input:focus {
  outline: none;
  border-color: var(--sf-brand);
  box-shadow: 0 0 0 3px rgba(249, 115, 22, 0.18);
}

.safety-page .adv-btn {
  height: 40px;
  border-radius: 10px;
  background: var(--sf-brand);
  border: none;
  color: #fff;
  padding: 0 20px;
  font-weight: 650;
  cursor: pointer;
  transition: background 220ms, transform 220ms, box-shadow 220ms;
}

.safety-page .adv-btn:hover:not(:disabled) {
  background: #EA580C;
  transform: translateY(-1px);
  box-shadow: 0 10px 20px -12px rgba(249, 115, 22, 0.5);
}

.safety-page .adv-strategies {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 10px;
  background: var(--sf-panel-2);
  border: 1px solid var(--sf-line);
  margin-bottom: 14px;
}

.safety-page .adv-strategies small {
  font-size: 11.5px;
  font-weight: 600;
  color: #6b7480;
}

.safety-page .adv-strategy-pill {
  padding: 4px 12px;
  border-radius: 999px;
  background: #fff;
  border: 1px solid var(--sf-line-2);
  color: #45505c;
  font-size: 11.5px;
  font-weight: 550;
}

.safety-page .adv-scores {
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 14px;
}

.safety-page .adv-score-card {
  padding: 16px 12px;
  border-radius: 12px;
  border: 1px solid var(--sf-line);
  background: linear-gradient(180deg, #fff 0%, #fbf9f4 100%);
  transition: transform 220ms, box-shadow 220ms;
}

.safety-page .adv-score-card:hover {
  transform: translateY(-1px);
  box-shadow: 0 8px 20px -12px rgba(20, 24, 28, 0.14);
}

.safety-page .adv-score-card b {
  font-size: 22px;
  font-weight: 800;
  letter-spacing: -0.03em;
  font-variant-numeric: tabular-nums;
  color: #1a1d21;
  margin-bottom: 4px;
}

.safety-page .adv-score-card small {
  font-size: 11.5px;
  color: #6b7480;
  font-weight: 500;
}

.safety-page .adv-score-card.pass {
  background: linear-gradient(180deg, rgba(22, 163, 74, 0.06), #fff);
  border-color: rgba(22, 163, 74, 0.28);
}

.safety-page .adv-score-card.pass b {
  color: var(--sf-ok);
}

.safety-page .adv-score-card.fail {
  background: linear-gradient(180deg, rgba(220, 38, 38, 0.06), #fff);
  border-color: rgba(220, 38, 38, 0.28);
}

.safety-page .adv-score-card.fail b {
  color: var(--sf-err);
}

@media (max-width: 900px) {
  .safety-page .adv-scores { grid-template-columns: repeat(3, 1fr); }
  .safety-page .adv-form { grid-template-columns: 1fr; }
  .safety-page .adv-btn { width: 100%; }
}

/* ---------- 证据链账本：ledger-head 更宽松 ---------- */
.safety-page .ledger-head {
  grid-template-columns: 200px 1fr;
  gap: 24px;
  padding: 16px 20px;
  border-radius: 14px;
  background: linear-gradient(180deg, rgba(255, 244, 232, 0.35) 0%, var(--sf-panel-2) 100%);
  border: 1px solid var(--sf-line);
  margin-bottom: 14px;
}

.safety-page .source-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 8px;
}

.safety-page .source-cell {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  border-radius: 10px;
  background: #fff;
  border: 1px solid var(--sf-line);
  font-size: 12px;
}

.safety-page .src-label {
  color: #45505c;
  flex: 1;
}

.safety-page .src-count {
  font-style: normal;
  font-weight: 700;
  color: var(--sf-brand-ink);
  font-variant-numeric: tabular-nums;
}

.safety-page .ledger-claim-row {
  display: grid;
  grid-template-columns: 16px minmax(0, 1fr) auto auto 16px;
  gap: 10px;
  align-items: center;
  padding: 10px 14px;
  border-radius: 10px;
  border: 1px solid transparent;
  transition: background 220ms, border-color 220ms;
}

.safety-page .ledger-claim-row:hover {
  background: var(--sf-panel-2);
  border-color: var(--sf-line);
}

.safety-page .ledger-claim-row .claim-src-tag {
  padding: 3px 10px;
  border-radius: 999px;
  background: var(--sf-brand-soft);
  color: var(--sf-brand-ink);
  font-size: 11px;
  font-weight: 600;
  font-family: var(--mono, monospace);
}

.safety-page .ledger-claim-row .claim-conf {
  font-style: normal;
  font-size: 11px;
  color: #6b7480;
  font-variant-numeric: tabular-nums;
}

.safety-page .ledger-claim-row .claim-arrow {
  color: #98a1ab;
}

/* ---------- 右侧栏：三张卡内容加密度 ---------- */
.safety-page aside.right-column {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.safety-page .side-card {
  padding: 18px 20px;
  border-radius: 16px;
  border: 1px solid var(--sf-line);
  box-shadow: 0 1px 2px rgba(20, 24, 28, 0.04), 0 8px 24px -20px rgba(20, 24, 28, 0.12);
}

.safety-page .debate-row {
  display: grid;
  grid-template-columns: 40px minmax(0, 1fr);
  gap: 12px;
  padding: 12px;
  border-radius: 10px;
  background: var(--sf-panel-2);
  margin-bottom: 8px;
  border: 1px solid var(--sf-brand-line);
}

.safety-page .debate-row b {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: var(--sf-brand-soft);
  color: var(--sf-brand-ink);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.02em;
}

.safety-page .debate-row p {
  margin: 0;
  font-size: 12px;
  line-height: 1.55;
  color: #45505c;
}

.safety-page .debate-row p strong {
  color: var(--sf-brand-ink);
  margin-right: 4px;
}

.safety-page .debate-row small {
  font-size: 11px;
  color: var(--sf-ok);
  font-weight: 600;
}

.safety-page .mini-chat {
  display: grid;
  grid-template-columns: 40px minmax(0, 1fr);
  gap: 12px;
  align-items: start;
  padding: 12px 14px;
  border-radius: 12px;
  background: var(--sf-brand-soft);
  border: 1px solid var(--sf-brand-line);
  margin-bottom: 10px;
}

.safety-page .mini-chat p {
  margin: 0;
  font-size: 12px;
  line-height: 1.6;
  color: #45505c;
}

.safety-page .algo-copy {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.safety-page .algo-copy p {
  margin: 0;
  padding: 10px 12px;
  border: 1px solid var(--sf-line);
  background: var(--sf-panel-2);
  font-size: 12px;
  line-height: 1.65;
  color: #45505c;
  border-radius: 8px;
}

.safety-page .algo-copy p b {
  color: var(--sf-brand-ink);
  font-weight: 700;
  margin-right: 4px;
}

/* 教师端暖色画布收敛：页面本体透明，信息层使用暖白表面。 */
.safety-page {
  width: min(1450px, calc(100% - 32px));
  max-width: 1450px;
  margin: 0 auto;
  padding: 28px 28px 72px;
  background: transparent;
  color: #30231e;
}

.safety-page .safety-main,
.safety-page .safety-block,
.safety-page .side-card {
  border-color: #eadbd3;
  background: #fffefd;
  box-shadow: 0 2px 8px rgba(126, 75, 47, .05);
}

.safety-page .safety-block:hover,
.safety-page .side-card:hover {
  border-color: #dfbda9;
  box-shadow: 0 4px 8px rgba(126, 75, 47, .08);
}

.safety-page :is(button, input, textarea, select):focus-visible {
  outline: 3px solid rgba(233, 85, 20, .28);
  outline-offset: 2px;
}

@media (max-width: 760px) {
  .safety-page {
    width: calc(100% - 16px);
    padding: 18px 12px 48px;
  }
}

/* ============================================================
 * v4 全站视觉收敛（2026-07-12）· 基准 = 教学概览
 * 外层大卡改为透明页面层，语义色/边框/阴影对齐基准 tokens
 * ============================================================ */
.safety-page {
  --sf-line: #e5e1d9;
  --sf-line-2: #dad6ce;
  --sf-panel-2: #f8f7f3;
  --sf-brand: #e85d16;
  --sf-brand-soft: #fff3ea;
  --sf-brand-line: #f1c9ae;
  --sf-brand-ink: #b04510;
  --sf-ok: #247553;
  --sf-warn: #a46916;
  --sf-err: #b5423a;
  --sf-info: #47749c;
  width: 100%;
  max-width: none;
  padding: 0 0 48px;
  color: #24211d;
}

/* 页面不再是一张巨型卡片：外层容器透明化，内容直接放在暖白背景上 */
.safety-page .safety-main {
  padding: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
}
.safety-page .safety-main:hover { box-shadow: none; }

/* 首个 SectionTitle 升级为编辑式页头（衬线大标题） */
.safety-page .safety-main > .section-head:first-of-type h2 {
  color: #171512;
  font-family: "Source Han Serif SC", "Noto Serif SC", "Songti SC", Georgia, serif;
  font-size: 34px;
  font-weight: 600;
  line-height: 1.2;
  letter-spacing: -0.01em;
}
.safety-page .safety-main > .section-head:first-of-type .section-copy p {
  color: #625f58;
  font-size: 15px;
  line-height: 1.6;
}
.safety-logo {
  background: #e85d16;
  box-shadow: none;
}

/* 信息块：白底细边框 12px，无默认阴影，hover 轻位移 */
.safety-page .safety-block,
.safety-page .side-card {
  border-color: #e5e1d9;
  border-radius: 12px;
  background: #fff;
  box-shadow: none;
}
.safety-page .safety-block:hover,
.safety-page .side-card:hover {
  transform: translateY(-1px);
  border-color: #d7d1c7;
  box-shadow: 0 8px 24px rgba(35, 31, 25, 0.05);
}
.safety-page .section-copy h2 { color: #171512; }
.safety-page .section-copy p { color: #625f58; }
.safety-page .ledger-head,
.safety-page .cov-summary,
.safety-page .empty-hint { background: #f5f3ee; }
.safety-page :is(button, input, textarea, select):focus-visible {
  outline: 3px solid rgba(232, 93, 22, 0.28);
}
</style>
