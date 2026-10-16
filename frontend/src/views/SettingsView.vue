<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import {
  Activity,
  BookOpen,
  CheckCircle2,
  Database,
  Loader2,
  RefreshCcw,
  ServerCog,
  ShieldCheck,
  XCircle,
} from "lucide-vue-next";

import ArtCard from "@/components/companion/ArtCard.vue";
import SectionTitle from "@/components/companion/SectionTitle.vue";
import { useSession } from "@/composables/useSession";
import { getAuthSession } from "@/utils/auth";
import { getKnowledgeStatus, indexCourse, listCourses, type KnowledgeStatus } from "@/api/knowledge";
import { getMetricsHealth, getMetricsSummary, type MetricsHealth, type MetricsSummary } from "@/api/metrics";
import { getGraphStats } from "@/api/knowledgeGraph";

const { userId, chatSessionId, resetChatSession } = useSession();
const displayName = computed(() => getAuthSession()?.displayName || "杜同学");

const loading = ref(true);
const knowledge = ref<KnowledgeStatus | null>(null);
const courses = ref<string[]>([]);
const health = ref<MetricsHealth | null>(null);
const metrics = ref<MetricsSummary | null>(null);
const graphStats = ref<Record<string, any> | null>(null);
const indexing = ref("");
const indexMessage = ref("");
const backendOk = ref(false);

async function load() {
  loading.value = true;
  const results = await Promise.allSettled([
    getKnowledgeStatus(),
    listCourses(),
    getMetricsHealth(),
    getMetricsSummary(),
    getGraphStats(),
  ]);
  backendOk.value = results.some((r) => r.status === "fulfilled");
  if (results[0].status === "fulfilled") knowledge.value = results[0].value;
  if (results[1].status === "fulfilled") {
    courses.value = (results[1].value.courses ?? []).map((c) =>
      typeof c === "string" ? c : String((c as any).name ?? (c as any).key ?? c),
    );
  }
  if (results[2].status === "fulfilled") health.value = results[2].value;
  if (results[3].status === "fulfilled") metrics.value = results[3].value;
  if (results[4].status === "fulfilled") graphStats.value = results[4].value;
  loading.value = false;
}

async function handleIndex(course: string) {
  if (indexing.value) return;
  indexing.value = course;
  indexMessage.value = "";
  try {
    const r = await indexCourse(course);
    const chunksCount = r?.total_chunks ?? 0;
    indexMessage.value = `「${course}」索引完成，共生成 ${chunksCount} 个知识切片。`;
    await load();
  } catch (e: any) {
    indexMessage.value = `索引失败：${e?.detail ?? e?.message ?? e}`;
  }
  indexing.value = "";
}

const healthChecks = computed(() => Object.entries(health.value?.checks ?? {}));

onMounted(load);
</script>

<template>
  <div class="companion-page settings-page">
    <ArtCard deco class="settings-main-card">
      <SectionTitle title="设置中心" sub="账户信息 · 知识库管理 · 系统健康度">
        <template #action>
          <button class="ghost-btn" type="button" :disabled="loading" @click="load">
            <RefreshCcw :size="14" />刷新
          </button>
        </template>
      </SectionTitle>

      <div class="settings-grid">
        <!-- 账户 -->
        <ArtCard class="settings-card">
          <SectionTitle title="账户信息" />
          <div class="settings-row"><span>登录用户</span><b>{{ displayName }}</b></div>
          <div class="settings-row"><span>学生 ID</span><b>{{ userId }}</b></div>
          <button class="ghost-btn" type="button" @click="resetChatSession()">重置聊天会话</button>
        </ArtCard>

        <!-- 后端状态 -->
        <ArtCard class="settings-card">
          <SectionTitle title="后端服务">
            <template #action><ServerCog :size="15" /></template>
          </SectionTitle>
          <div class="settings-row">
            <span>连接状态</span>
            <b :class="backendOk ? 'ok' : 'bad'">
              <component :is="backendOk ? CheckCircle2 : XCircle" :size="14" />
              {{ backendOk ? "已连接" : "未连接" }}
            </b>
          </div>
          <div class="settings-row"><span>运行时长</span><b>{{ metrics ? `${(metrics.uptime_seconds / 60).toFixed(0)} 分钟` : "—" }}</b></div>
          <div class="settings-row"><span>LLM 调用</span><b>{{ metrics?.llm.calls_total ?? "—" }}</b></div>
          <div class="settings-row"><span>生成产物</span><b>{{ metrics?.artifacts.total ?? "—" }}</b></div>
          <div class="settings-row"><span>Agent 失败数</span><b>{{ metrics?.agents.failures_total ?? "—" }}</b></div>
        </ArtCard>

        <!-- 知识库 -->
        <ArtCard class="settings-card">
          <SectionTitle title="课程知识库">
            <template #action><Database :size="15" /></template>
          </SectionTitle>
          <div class="settings-row">
            <span>索引状态</span>
            <b>{{ knowledge ? (knowledge.indexed ?? knowledge.status ?? "未知") : "—" }}</b>
          </div>
          <div class="settings-row"><span>知识切片</span><b>{{ knowledge?.chunks ?? "—" }}</b></div>
          <div class="settings-row"><span>知识图谱节点</span><b>{{ graphStats?.nodes ?? graphStats?.kp_count ?? "—" }}</b></div>
          <div class="course-list">
            <div v-for="c in courses" :key="c" class="course-row">
              <BookOpen :size="14" />
              <span>{{ c }}</span>
              <button class="ghost-btn" type="button" :disabled="!!indexing" @click="handleIndex(c)">
                <Loader2 v-if="indexing === c" :size="12" class="spin" />
                重建索引
              </button>
            </div>
            <p v-if="!courses.length" class="settings-hint">后端未连接或暂无课程知识库。</p>
          </div>
          <p v-if="indexMessage" class="settings-hint">{{ indexMessage }}</p>
        </ArtCard>

        <!-- 健康检查 -->
        <ArtCard class="settings-card">
          <SectionTitle title="依赖健康检查">
            <template #action><Activity :size="15" /></template>
          </SectionTitle>
          <p v-if="!healthChecks.length" class="settings-hint">后端未连接，无法获取健康检查结果。</p>
          <div v-for="[name, check] in healthChecks" :key="name" class="settings-row">
            <span>{{ name }}</span>
            <b :class="check.ok ? 'ok' : 'bad'">
              <component :is="check.ok ? CheckCircle2 : XCircle" :size="14" />
              {{ check.ok ? "正常" : (check.error ?? "").slice(0, 40) || "异常" }}
            </b>
          </div>
        </ArtCard>

        <!-- 内容安全说明 -->
        <ArtCard class="settings-card wide">
          <SectionTitle title="内容安全与防幻觉机制">
            <template #action><ShieldCheck :size="15" /></template>
          </SectionTitle>
          <div class="safety-copy">
            <p><b>球球（刺猬守护）</b>会对每一轮生成内容做安全审核；证据链账本记录每条学术论断的来源（教材 / 知识图谱 / RAG 切片 / 错题 / 历史），Chain-of-Verification 复核关键论断，多智能体辩论仲裁分歧结论。</p>
            <p>练习题生成遵循「不泄漏答案」的教学安全策略，讲解优先引导思考路径而非直接给出结论。</p>
          </div>
        </ArtCard>
      </div>
    </ArtCard>
  </div>
</template>

<style scoped>
.settings-page {
  width: min(1450px, calc(100% - 32px));
  max-width: 1450px;
  margin: 0 auto;
  padding: 28px 28px 72px;
  background: transparent;
}

.settings-main-card {
  padding: 28px;
  border-color: #eadbd3;
  background: #fffefd;
}

.settings-card {
  padding: 22px;
  border-color: #eadbd3;
  background: #fffaf6;
  transition: transform 200ms cubic-bezier(.16, 1, .3, 1), border-color 180ms ease-out, background-color 180ms ease-out;
}

.settings-card:hover {
  transform: translateY(-2px);
  border-color: #dfbda9;
  background: #fffefd;
}

.settings-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 14px;
}

.settings-card.wide {
  grid-column: 1 / -1;
}

.settings-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 0;
  border-bottom: 1px dashed var(--neutral-200);
  font-size: 13px;
}

.settings-row span {
  color: var(--muted);
}

.settings-row b {
  display: flex;
  align-items: center;
  gap: 5px;
  color: var(--ink);
  font-weight: 600;
  max-width: 65%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.settings-row b.ok {
  color: var(--status-running);
}

.settings-row b.bad {
  color: var(--status-error);
}

.course-list {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.course-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 9px;
  border: 1px solid transparent;
  background: #fff4ed;
  font-size: 12.5px;
  transition: transform 190ms cubic-bezier(.16, 1, .3, 1), border-color 170ms ease-out, background-color 170ms ease-out;
}

.course-row:hover {
  transform: translateX(3px);
  border-color: #edc8b5;
  background: #fffefd;
}

.course-row span {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.settings-hint {
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--muted);
  line-height: 1.6;
}

.safety-copy p {
  margin: 0 0 8px;
  font-size: 13px;
  line-height: 1.7;
  color: var(--neutral-600);
}

.spin {
  animation: st-spin 1s linear infinite;
}

@keyframes st-spin {
  to {
    transform: rotate(360deg);
  }
}

.settings-page :is(button, input, select, textarea):focus-visible {
  outline: 3px solid rgba(233, 85, 20, .28);
  outline-offset: 2px;
}

@media (max-width: 760px) {
  .settings-page {
    width: calc(100% - 16px);
    padding: 18px 12px 48px;
  }

  .settings-main-card {
    padding: 18px;
  }
}

/* ============================================================
 * v4 全站视觉收敛（2026-07-12）· 基准 = 教学概览
 * 去外层大卡 / 中性细边框 / 衬线页头 / 无默认阴影
 * ============================================================ */
.settings-page {
  width: 100%;
  max-width: none;
  padding: 0 0 48px;
}

.settings-main-card {
  padding: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
}
.settings-main-card:hover { box-shadow: none; }

.settings-main-card > .section-head:first-of-type h2 {
  color: #171512;
  font-family: "Source Han Serif SC", "Noto Serif SC", "Songti SC", Georgia, serif;
  font-size: 34px;
  font-weight: 600;
  line-height: 1.2;
  letter-spacing: -0.01em;
}
.settings-main-card > .section-head:first-of-type .section-copy p {
  color: #625f58;
  font-size: 15px;
  line-height: 1.6;
}

.settings-card {
  border-color: #e5e1d9;
  border-radius: 12px;
  background: #fff;
}
.settings-card:hover {
  transform: translateY(-1px);
  border-color: #d7d1c7;
  background: #fff;
  box-shadow: 0 8px 24px rgba(35, 31, 25, 0.05);
}

.settings-row { border-bottom: 1px solid #ece8e1; font-size: 13.5px; }
.settings-row span { color: #625f58; }
.settings-row b { color: #1f1d1a; }

.course-row { background: #f5f3ee; }
.course-row:hover { border-color: #d7d1c7; background: #fff; }

.settings-hint { color: #89857d; }
.safety-copy p { color: #625f58; font-size: 13.5px; }

.settings-page :is(button, input, select, textarea):focus-visible {
  outline: 3px solid rgba(232, 93, 22, 0.28);
}
</style>
