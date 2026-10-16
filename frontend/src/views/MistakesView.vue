<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  BarChart3,
  Bell,
  BookOpen,
  BookX,
  Check,
  CheckCircle2,
  ChevronDown,
  Clock,
  ExternalLink,
  Filter,
  Grid3x3,
  Heart,
  Lightbulb,
  List,
  Loader2,
  Plus,
  RefreshCcw,
  Search,
  Sparkles,
  Star,
  Stethoscope,
  Target,
  TrendingUp,
  Wand2,
  Zap,
} from "lucide-vue-next";

import { useSession } from "@/composables/useSession";
import {
  analyzeMistake,
  getMistakeCategories,
  getMistakesHeatmap,
  getRemediation,
  getVariantDemoSamples,
  generateVariantSystem,
  listMistakes,
  makeVariants,
  recordMistake,
  resolveMistake,
  type HeatmapResponse,
  type MistakeInsights,
  type MistakeItem,
  type VariantQuestion,
  getMistakeInsights,
} from "@/api/mistakes";
import { addXp } from "@/api/gamification";
import { updateBkt } from "@/api/cognitive";
import {
  enqueueReview,
  fetchReviewHistory,
  submitReview,
  type ReviewHistoryItem,
} from "@/api/spacedRepetition";
import { getStudentOverview, type StudentOverviewResponse } from "@/api/insights";

const { userId } = useSession();
const route = useRoute();
const router = useRouter();

// 课程筛选项由 /knowledge/courses 动态下发（平台化改造，去除写死的两课枚举）
type MistakeCourse = string;
const COURSE_OPTIONS = ref<Array<{ value: MistakeCourse; label: string }>>([
  { value: "", label: "全部课程" },
  { value: "artificial_intelligence", label: "人工智能导论" },
]);
const routeCourse = typeof route.query.course === "string" ? route.query.course : "";
const activeCourse = ref<MistakeCourse>(routeCourse);

async function loadCourseOptions() {
  try {
    const { listCourses } = await import("@/api/knowledge");
    const response = await listCourses();
    const options = response.courses
      .map((item) => {
        if (typeof item === "string") {
          return { value: item, label: item.replace(/_/g, " ") };
        }
        const value = String((item as any).id || (item as any).name || "");
        return {
          value,
          label: String((item as any).display_name || "") || value.replace(/_/g, " "),
        };
      })
      .filter((item) => Boolean(item.value));
    if (options.length) {
      COURSE_OPTIONS.value = [{ value: "", label: "全部课程" }, ...options];
    }
  } catch {
    /* 后端未连接时保留默认选项 */
  }
}

function courseLabel(course?: string): string {
  return COURSE_OPTIONS.value.find((item) => item.value === course)?.label || "未归属课程";
}

function setActiveCourse(course: MistakeCourse) {
  activeCourse.value = course;
}

// 从知识图谱"开始练习"跳转时，预填知识点筛选
const kpFilterId = ref<string>("");
const kpFilterName = ref<string>("");

const loading = ref(true);
const mistakes = ref<MistakeItem[]>([]);
const categories = ref<string[]>([]);
const heatmap = ref<HeatmapResponse | null>(null);
const activeCategory = ref("");
const busyId = ref("");
const busyAction = ref("");
const error = ref("");
const viewMode = ref<"grid" | "list">("grid");
const searchKeyword = ref("");
const sortBy = ref<"最近" | "最旧" | "掌握度">("最近");
const starredIds = ref<Set<string>>(new Set());

// 分页
const currentPage = ref(1);
const pageSize = ref(12);

// 每条错题的 AI 产出（归因/变式/补救）
interface MistakeInsight {
  analysis?: { error_type: string; detail: string; confidence?: number };
  variants?: VariantQuestion[];
  remediationNote?: string;
  revealedAnswers: Set<number>;
}
const insights = ref<Record<string, MistakeInsight>>({});
const expandedIds = ref<Set<string>>(new Set());

// AI 智能诊断（LLM 驱动）
const aiInsights = ref<MistakeInsights | null>(null);
const aiInsightsLoading = ref(false);
const overview = ref<StudentOverviewResponse | null>(null);
const reviewLog = ref<ReviewHistoryItem[]>([]);

const ERROR_LABELS: Record<string, string> = {
  conceptual_misunderstanding: "概念理解偏差",
  calculation_error: "计算错误",
  application_transfer: "迁移应用困难",
  careless_error: "审题疏忽",
  reading_comprehension: "题意理解偏差",
  memory_gap: "知识记忆缺口",
  strategy_error: "解题策略不当",
  incomplete_answer: "作答不完整",
  concept: "概念理解偏差",
  application: "迁移应用困难",
  calculation: "计算错误",
  careless: "审题疏忽",
  unknown: "待进一步诊断",
};

const KP_DISPLAY_NAMES: Record<string, string> = {
  "ml_fundamentals/regularization": "L1 与 L2 正则化",
  "ml_fundamentals/gradient_descent": "批量梯度下降与随机梯度下降",
  "ml_fundamentals/overfitting": "过拟合诊断",
  "ml_fundamentals/bias_variance": "偏差与方差权衡",
  "ml_fundamentals/cross_validation": "K 折交叉验证",
  "neural_networks/dropout": "Dropout 训练与推理",
  "neural_networks/backprop": "反向传播",
  "neural_networks/activation": "激活函数",
  "transformer/attention": "缩放点积注意力",
  "transformer/multi_head": "多头注意力",
  "transformer/positional_encoding": "位置编码",
  "transformer/layer_norm": "Layer Normalization",
  "cnn/convolution": "CNN 卷积计算",
  "cnn/pooling": "CNN 池化",
  "cnn/receptive_field": "CNN 感受野",
  "cnn/batch_norm": "Batch Normalization",
  "rag/retrieval": "RAG 检索与重排",
  "rag/chunking": "RAG 文本分块",
  "rag/embedding": "RAG 语义向量检索",
  "rag/hybrid_search": "RAG 混合检索",
  "rag/eval": "RAG 忠实度评估",
};

function errorLabel(code?: string): string {
  return ERROR_LABELS[code || "unknown"] || code || "待进一步诊断";
}

function knowledgePointName(kpId?: string): string {
  const id = kpId || "综合知识点";
  return overview.value?.profile.knowledge_points.find((item) => item.kp_id === id)?.kp_name
    || KP_DISPLAY_NAMES[id]
    || id.split("/").pop()?.replace(/_/g, " ")
    || id;
}

function toggleExpand(id: string) {
  if (expandedIds.value.has(id)) {
    expandedIds.value.delete(id);
  } else {
    expandedIds.value.add(id);
  }
  // 触发响应式更新
  expandedIds.value = new Set(expandedIds.value);
}

// ===== 错题详情弹窗：点击卡片直接打开该卡（代替行内展开） =====
const activeMistake = ref<MistakeItem | null>(null);

function openMistakeModal(m: MistakeItem) {
  activeMistake.value = m;
  expandedIds.value.add(m.id); // AI 产出区依赖此标记
  expandedIds.value = new Set(expandedIds.value);
}

function closeMistakeModal() {
  activeMistake.value = null;
}

/** 最近复习记录点击：定位到对应错题并打开详情 */
function openLogEntry(entry: { question: string; kp_id?: string | null }) {
  const prefix = entry.question.replace(/\.\.\.$/, "");
  const hit = mistakes.value.find(
    (m) => m.question.startsWith(prefix) || (entry.kp_id && m.kp_id === entry.kp_id && !m.resolved),
  );
  if (hit) {
    openMistakeModal(hit);
  } else {
    error.value = "该记录对应的错题已被解决或删除。";
  }
}

// 记录错题表单
const showForm = ref(false);
const form = ref({ question: "", student_answer: "", correct_answer: "", kp_id: "" });
const submitting = ref(false);
const importing = ref(false);

const unresolvedCount = computed(() => mistakes.value.filter((m) => !m.resolved).length);
const resolvedCount = computed(() => mistakes.value.filter((m) => m.resolved).length);
const highFreqCount = computed(
  () => mistakes.value.filter((m) => (m as any).review_count > 2).length,
);
const recentCount = computed(() => {
  const weekAgo = Date.now() / 1000 - 7 * 24 * 60 * 60;
  return mistakes.value.filter((m) => m.created_at && m.created_at > weekAgo).length;
});

const reviewMasteryRate = computed(() =>
  mistakes.value.length ? Math.round((resolvedCount.value / mistakes.value.length) * 100) : 0,
);

const weeklyFocus = computed(() => {
  const unresolved = mistakes.value.filter((mistake) => !mistake.resolved);
  const candidates = unresolved.length ? unresolved : mistakes.value;
  if (!candidates.length) {
    return {
      kpId: "",
      title: "暂无待攻克专题",
      description: "当前还没有错题数据，完成练习后系统会根据真实错题自动生成本周重点。",
    };
  }

  const grouped = new Map<string, { count: number; latest: number; sample: MistakeItem }>();
  for (const mistake of candidates) {
    const kpId = mistake.kp_id || "综合知识点";
    const current = grouped.get(kpId);
    if (!current) {
      grouped.set(kpId, { count: 1, latest: mistake.created_at || 0, sample: mistake });
      continue;
    }
    current.count += 1;
    if ((mistake.created_at || 0) > current.latest) {
      current.latest = mistake.created_at || 0;
      current.sample = mistake;
    }
  }

  const [kpId, focus] = [...grouped.entries()].sort(
    (a, b) => b[1].count - a[1].count || b[1].latest - a[1].latest,
  )[0];
  const kpName = knowledgePointName(kpId);
  const statusText = unresolved.length ? "未解决错题" : "历史错题";
  return {
    kpId,
    title: `${kpName}易错专题`,
    description: `根据当前${statusText}，本周优先复习「${kpName}」，重点改善${errorLabel(focus.sample.error_type)}。`,
  };
});

const filtered = computed(() => {
  let list = mistakes.value;

  // 特殊筛选 pill
  if (activeCategory.value === "review") {
    list = list.filter((m) => !m.resolved);
  } else if (activeCategory.value === "mastered") {
    list = list.filter((m) => m.resolved);
  } else if (activeCategory.value === "frequent") {
    list = list.filter((m) => (m as any).review_count > 2 || !m.resolved);
  } else if (activeCategory.value === "recent") {
    const weekAgo = Date.now() / 1000 - 7 * 24 * 60 * 60;
    list = list.filter((m) => m.created_at && m.created_at > weekAgo);
  } else if (activeCategory.value === "starred") {
    list = list.filter((m) => starredIds.value.has(m.id));
  } else if (activeCategory.value) {
    // 按错因分类筛选
    list = list.filter((m) => m.error_type === activeCategory.value);
  }

  // 知识点筛选（从图谱跳转时生效）
  if (kpFilterId.value) {
    const kid = kpFilterId.value.toLowerCase();
    list = list.filter(
      (m) =>
        m.kp_id?.toLowerCase().includes(kid),
    );
  }
  if (searchKeyword.value.trim()) {
    const kw = searchKeyword.value.trim().toLowerCase();
    list = list.filter(
      (m) =>
        m.question?.toLowerCase().includes(kw) ||
        m.kp_id?.toLowerCase().includes(kw) ||
        m.error_type?.toLowerCase().includes(kw),
    );
  }

  // 排序
  if (sortBy.value === "最旧") {
    list = [...list].sort((a, b) => (a.created_at || 0) - (b.created_at || 0));
  } else if (sortBy.value === "掌握度") {
    list = [...list].sort((a, b) => getMastery(a) - getMastery(b));
  } else {
    list = [...list].sort((a, b) => (b.created_at || 0) - (a.created_at || 0));
  }

  return list;
});

// 分页后的列表
const paged = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value;
  return filtered.value.slice(start, start + pageSize.value);
});

const totalPages = computed(() => Math.max(1, Math.ceil(filtered.value.length / pageSize.value)));

const distribution = computed<Record<string, number>>(() => {
  const dist: Record<string, number> = {};
  for (const m of mistakes.value) {
    dist[m.error_type || "unknown"] = (dist[m.error_type || "unknown"] ?? 0) + 1;
  }
  return dist;
});

const heatTopRows = computed(() => {
  if (!heatmap.value?.matrix) return [];
  return [...heatmap.value.matrix].sort((a, b) => b.total - a.total).slice(0, 6);
});
const heatMax = computed(() => Math.max(1, ...heatTopRows.value.map((r) => r.total)));

const distributionList = computed(() => {
  const total = mistakes.value.length || 1;
  return Object.entries(distribution.value)
    .map(([k, v]) => ({ code: k, name: errorLabel(k), count: v, percent: Math.round((v / total) * 100) }))
    .sort((a, b) => b.count - a.count);
});

const showAllReviewLog = ref(false);

function findReviewMistake(itemId: string): MistakeItem | undefined {
  return mistakes.value.find((item) => item.id === itemId || item.kp_id === itemId);
}

const recentReview = computed(() => {
  const scopedLog = activeCourse.value
    ? reviewLog.value.filter((entry) => Boolean(findReviewMistake(entry.item_id)))
    : reviewLog.value;
  return scopedLog.slice(0, showAllReviewLog.value ? 12 : 4).map((entry) => {
    const mistake = findReviewMistake(entry.item_id);
    return {
      id: `review-${entry.id}`,
      question: mistake?.question || `复习记录：${entry.item_id}`,
      kp_id: mistake?.kp_id || entry.item_id,
      created_at: entry.reviewed_at,
      logResult: entry.rating >= 5 ? "掌握" : entry.rating >= 3 ? "模糊" : "不会",
      error_type: mistake?.error_type || "",
      user_id: userId.value,
      student_answer: "",
      correct_answer: "",
      analysis: "",
      resolved: Boolean(mistake?.resolved),
    } as MistakeItem & { logResult?: string };
  });
});

const todoReview = computed(() => overview.value?.review.due_today ?? 0);
const expiringReview = computed(() => overview.value?.review.due_today ?? 0);
const highPriority = computed(() => Math.min(3, mistakes.value.filter((m) => !m.resolved).length));

function toggleStar(id: string) {
  if (starredIds.value.has(id)) starredIds.value.delete(id);
  else starredIds.value.add(id);
  starredIds.value = new Set(starredIds.value);
}

function goToPage(page: number) {
  if (page < 1 || page > totalPages.value) return;
  currentPage.value = page;
}

function cycleSort() {
  const opts: typeof sortBy.value[] = ["最近", "最旧", "掌握度"];
  const idx = opts.indexOf(sortBy.value);
  sortBy.value = opts[(idx + 1) % opts.length];
}

// ===== 今日复习会话（真实闭环：自评 → SM-2 间隔复习 + BKT 掌握度双上报） =====
interface ReviewLogEntry {
  title: string;
  kp_id: string;
  result: "掌握" | "模糊" | "不会";
  ts: number;
}

const reviewOpen = ref(false);
const reviewQueue = ref<MistakeItem[]>([]);
const reviewIndex = ref(0);
const reviewRevealed = ref(false);
const reviewGrading = ref(false);
const reviewStartedAt = ref(0);
const reviewResults = ref<ReviewLogEntry[]>([]);
const reviewCurrent = computed(() => reviewQueue.value[reviewIndex.value] ?? null);
const reviewFinished = computed(
  () => reviewOpen.value && reviewIndex.value >= reviewQueue.value.length,
);

async function loadReviewHistory() {
  try {
    const response = await fetchReviewHistory(userId.value, 50);
    reviewLog.value = response.items;
  } catch {
    reviewLog.value = [];
  }
}

function startTodayReview() {
  const queue = mistakes.value.filter((m) => !m.resolved).slice(0, 10);
  if (!queue.length) {
    error.value = "太棒了，当前没有待复习的错题！";
    return;
  }
  reviewQueue.value = queue;
  reviewIndex.value = 0;
  reviewRevealed.value = false;
  reviewResults.value = [];
  reviewStartedAt.value = Date.now();
  reviewOpen.value = true;
}

/** 自评上报：quality 5=掌握 / 3=模糊 / 1=不会 → SM-2 调度 + BKT 掌握度 */
async function gradeReview(quality: 5 | 3 | 1) {
  const m = reviewCurrent.value;
  if (!m || reviewGrading.value) return;
  reviewGrading.value = true;
  const resultLabel = quality === 5 ? "掌握" : quality === 3 ? "模糊" : "不会";
  reviewResults.value.push({
    title: m.question.slice(0, 24),
    kp_id: m.kp_id || "综合",
    result: resultLabel,
    ts: Date.now() / 1000,
  });
  // 双上报 best-effort：SM-2 间隔复习（团团调度） + BKT 掌握度（评估反馈）
  await Promise.allSettled([
    submitReview({
      user_id: userId.value,
      item_id: m.id,
      item_type: "mistake",
      quality,
      duration_minutes: Math.max(0.1, (Date.now() - reviewStartedAt.value) / 60000),
    }),
    updateBkt(userId.value, m.kp_id || "general", quality >= 4),
    quality === 5 ? addXp(userId.value, "correct_answer") : Promise.resolve(),
  ]);
  if (quality === 5 && !m.resolved) {
    // 完全掌握 → 顺手标记解决
    try {
      await resolveMistake(m.id);
      m.resolved = true;
    } catch { /* 后端未连接时忽略 */ }
  }
  reviewIndex.value += 1;
  reviewStartedAt.value = Date.now();
  reviewRevealed.value = false;
  reviewGrading.value = false;
}

function closeReview() {
  reviewOpen.value = false;
  void loadReviewHistory();
}

const reviewSummary = computed(() => {
  const total = reviewResults.value.length;
  const mastered = reviewResults.value.filter((r) => r.result === "掌握").length;
  return { total, mastered };
});

function startHeroReview() {
  startTodayReview();
}

let loadRequestId = 0;
let insightRequestId = 0;

async function load() {
  const requestId = ++loadRequestId;
  loading.value = true;
  error.value = "";
  const uid = userId.value;

  const results = await Promise.allSettled([
    listMistakes(uid, "", 100, activeCourse.value),
    getMistakeCategories(),
    getMistakesHeatmap(uid, activeCourse.value),
    fetchReviewHistory(uid, 50),
    getStudentOverview(uid),
  ]);
  if (requestId !== loadRequestId) return;
  if (results[0].status === "fulfilled") {
    // 过滤掉乱码数据（含 ???? 或 � 的记录）
    mistakes.value = [...results[0].value.mistakes]
      .filter((m) => {
        const q = m.question || "";
        return !q.includes("???") && !q.includes("\ufffd");
      })
      .reverse();
  } else {
    mistakes.value = [];
    heatmap.value = null;
    error.value = "错题服务未连接，请先启动后端。";
  }
  if (results[1].status === "fulfilled") categories.value = results[1].value.categories;
  if (results[2].status === "fulfilled") heatmap.value = results[2].value;
  if (results[3].status === "fulfilled") reviewLog.value = results[3].value.items;
  if (results[4].status === "fulfilled") overview.value = results[4].value;
  loading.value = false;
  currentPage.value = 1;
}

async function loadInsights() {
  const requestId = ++insightRequestId;
  aiInsightsLoading.value = true;
  try {
    const result = await getMistakeInsights(userId.value, activeCourse.value);
    if (requestId === insightRequestId) aiInsights.value = result;
  } catch {
    // 后端未连接时静默失败
  } finally {
    if (requestId === insightRequestId) aiInsightsLoading.value = false;
  }
}

function ensureInsight(id: string): MistakeInsight {
  if (!insights.value[id]) {
    insights.value[id] = { revealedAnswers: new Set() };
  }
  return insights.value[id];
}

async function runAction(m: MistakeItem, action: "analyze" | "variants" | "remediation") {
  if (busyId.value) return;
  busyId.value = m.id;
  busyAction.value = action;
  expandedIds.value.add(m.id);
  const slot = ensureInsight(m.id);
  try {
    if (action === "analyze") {
      const { analysis } = await analyzeMistake(m.id);
      slot.analysis = analysis as MistakeInsight["analysis"];
      m.error_type = analysis.error_type;
      m.analysis = analysis.detail;
    } else if (action === "variants") {
      try {
        const { variants } = await makeVariants(m.id);
        slot.variants = normalizeVariants(variants);
      } catch {
        // B 端点失败时降级到 A 的独立变式端点
        const pkg = await generateVariantSystem(m.id, {
          question: m.question,
          correct_answer: m.correct_answer,
          student_answer: m.student_answer,
          kp_id: m.kp_id,
          user_id: userId.value,
        });
        slot.variants = normalizeVariants(pkg.variants);
      }
    } else {
      const pkg = await getRemediation(m.id, 3);
      slot.analysis = pkg.attribution as MistakeInsight["analysis"];
      slot.variants = normalizeVariants(pkg.variants);
      const reason = (pkg as any).recommendation_reason ?? "";
      const actions = Array.isArray((pkg as any).next_actions)
        ? (pkg as any).next_actions
            .map((a: any) => (typeof a === "string" ? a : a?.label ?? a?.action ?? ""))
            .filter(Boolean)
            .join("；")
        : "";
      slot.remediationNote = [reason, actions].filter(Boolean).join(" · ");
      m.error_type = pkg.attribution.error_type;
    }
    insights.value = { ...insights.value, [m.id]: slot };
  } catch (e: any) {
    error.value = `操作失败：${e?.detail ?? e?.message ?? e}`;
  }
  busyId.value = "";
  busyAction.value = "";
}

function normalizeVariants(raw: unknown): VariantQuestion[] {
  if (Array.isArray(raw)) return raw as VariantQuestion[];
  if (raw && typeof raw === "object") {
    const obj = raw as Record<string, any>;
    if (Array.isArray(obj.variants)) return obj.variants;
    if (Array.isArray(obj.questions)) return obj.questions;
    return Object.values(obj).filter((v) => v && typeof v === "object");
  }
  return [];
}

// 「加入复习」= 真实加入 SM-2 间隔复习队列（此前误绑到补救方案生成）
const enqueueingId = ref("");

async function handleEnqueue(m: MistakeItem) {
  if (enqueueingId.value) return;
  enqueueingId.value = m.id;
  try {
    await enqueueReview({ user_id: userId.value, item_id: m.id });
    error.value = "";
    practiceResult.value = {
      ...practiceResult.value,
      [`enq-${m.id}`]: "已加入今日复习队列",
    };
  } catch (e: any) {
    error.value = `加入复习失败：${e?.detail ?? e?.message ?? e}`;
  }
  enqueueingId.value = "";
}

async function handleResolve(m: MistakeItem) {
  try {
    await resolveMistake(m.id);
    m.resolved = true;
    void addXp(userId.value, "correct_answer").catch(() => undefined);
  } catch (e: any) {
    error.value = `标记失败：${e?.detail ?? e?.message ?? e}`;
  }
}

async function handleSubmit() {
  if (submitting.value) return;
  const f = form.value;
  if (!f.question.trim() || !f.correct_answer.trim()) return;
  submitting.value = true;
  try {
    await recordMistake({
      user_id: userId.value,
      kp_id: f.kp_id.trim(),
      question: f.question.trim(),
      student_answer: f.student_answer.trim(),
      correct_answer: f.correct_answer.trim(),
      course: activeCourse.value || undefined,
    });
    form.value = { question: "", student_answer: "", correct_answer: "", kp_id: "" };
    showForm.value = false;
    await load();
  } catch (e: any) {
    error.value = `记录失败：${e?.detail ?? e?.message ?? e}`;
  }
  submitting.value = false;
}

async function importDemoSamples() {
  if (importing.value) return;
  importing.value = true;
  try {
    const { samples } = await getVariantDemoSamples();
    for (const s of samples.slice(0, 5)) {
      await recordMistake({
        user_id: userId.value,
        kp_id: String(s.kp_id ?? s.kp ?? ""),
        question: String(s.question ?? ""),
        student_answer: String(s.student_answer ?? ""),
        correct_answer: String(s.correct_answer ?? ""),
        error_type: String(s.error_type ?? ""),
        course: activeCourse.value || undefined,
      });
    }
    await load();
  } catch (e: any) {
    error.value = `导入演示样例失败：${e?.detail ?? e?.message ?? e}`;
  }
  importing.value = false;
}

// 变式练习 → BKT 闭环
const practiceResult = ref<Record<string, string>>({});

async function reportVariantResult(m: MistakeItem, idx: number, correct: boolean) {
  const key = `${m.id}-${idx}`;
  if (practiceResult.value[key]) return;
  practiceResult.value = { ...practiceResult.value, [key]: "…" };
  try {
    const kp = m.kp_id || "general";
    const r = await updateBkt(userId.value, kp, correct);
    void addXp(userId.value, correct ? "correct_answer" : "complete_quiz").catch(() => undefined);
    practiceResult.value = {
      ...practiceResult.value,
      [key]: `掌握度 → ${Math.round(r.p_learned * 100)}%（${correct ? "+经验" : "已记录"}）`,
    };
  } catch {
    practiceResult.value = { ...practiceResult.value, [key]: "上报失败（后端未连接）" };
  }
}

function toggleAnswer(mistakeId: string, idx: number) {
  const slot = ensureInsight(mistakeId);
  if (slot.revealedAnswers.has(idx)) slot.revealedAnswers.delete(idx);
  else slot.revealedAnswers.add(idx);
  insights.value = { ...insights.value, [mistakeId]: slot };
}

function formatTs(ts?: number): string {
  if (!ts) return "";
  return new Date(ts * 1000).toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
  });
}

function formatRelative(ts?: number): string {
  if (!ts) return "";
  const diff = Date.now() / 1000 - ts;
  const days = Math.floor(diff / 86400);
  if (days === 0) return "今天";
  if (days === 1) return "1天前";
  if (days < 7) return `${days}天前`;
  if (days < 30) return `${Math.floor(days / 7)}周前`;
  return `${Math.floor(days / 30)}个月前`;
}

function getSubjectIcon(kpId?: string) {
  if (!kpId) return BookOpen;
  const k = kpId.toLowerCase();
  if (k.includes("math") || k.includes("数学") || k.includes("线性") || k.includes("微积分")) return BarChart3;
  if (k.includes("english") || k.includes("英语") || k.includes("阅读")) return BookOpen;
  if (k.includes("code") || k.includes("算法") || k.includes("程序")) return Wand2;
  if (k.includes("物理")) return Zap;
  return BookOpen;
}

// 沿用 companion-design 的资源类型色（暖色纸张风格）
function getSubjectColor(kpId?: string) {
  if (!kpId) return "#ea5a1a"; // orange-500
  const k = kpId.toLowerCase();
  if (k.includes("math") || k.includes("数学") || k.includes("线性") || k.includes("微积分")) return "#ea5a1a"; // orange-500
  if (k.includes("english") || k.includes("英语") || k.includes("阅读")) return "#2f9f6b"; // status-running
  if (k.includes("code") || k.includes("算法") || k.includes("程序")) return "#3d3830"; // type-code
  if (k.includes("物理")) return "#d89229"; // status-queue
  return "#ea5a1a";
}

function getMastery(m: MistakeItem): number {
  if ((m as any).mastery != null) return (m as any).mastery;
  // 基于错题 ID 的确定性哈希，避免每次渲染值不同
  const hash = m.id.split('').reduce((acc, c) => ((acc << 5) - acc + c.charCodeAt(0)) | 0, 0);
  return 40 + (Math.abs(hash) % 50);
}

function getTags(m: MistakeItem): string[] {
  const kp = m.kp_id || "";
  const tags = kp.split(/[/.]/).filter(Boolean).slice(0, 3);
  return tags.length ? tags : ["综合"];
}

onMounted(() => {
  void loadCourseOptions();
  // 读取知识图谱跳转参数
  const qKpId = route.query.kp_id;
  const qKpName = route.query.kp_name;
  const qMode = route.query.mode;
  if (typeof qKpId === "string" && qKpId.trim()) kpFilterId.value = qKpId.trim();
  if (typeof qKpName === "string" && qKpName.trim()) kpFilterName.value = qKpName.trim();
  if (qMode === "practice") {
    // 练习模式：自动展开表单并预填知识点
    showForm.value = true;
    form.value.kp_id = kpFilterId.value;
  }
  load();
  loadInsights();
});

watch(activeCourse, async (course) => {
  currentPage.value = 1;
  mistakes.value = [];
  heatmap.value = null;
  error.value = "";
  activeMistake.value = null;
  kpFilterId.value = "";
  kpFilterName.value = "";
  aiInsights.value = null;
  const query = { ...route.query };
  if (course) query.course = course;
  else delete query.course;
  await router.replace({ query });
  await Promise.all([load(), loadInsights()]);
});
</script>

<template>
  <div class="mistakes-page-redesign teacher-skin">
    <!-- 顶部 Header -->
    <div class="mk-header">
      <div class="mk-header-left">
        <h1 class="mk-title">错题本</h1>
        <p class="mk-subtitle">集中整理薄弱题目，支持标注原因、分类复习与智能巩固</p>
        <div class="mk-course-switcher" aria-label="错题课程筛选">
          <button
            v-for="item in COURSE_OPTIONS"
            :key="item.value || 'all'"
            type="button"
            :class="{ active: activeCourse === item.value }"
            @click="setActiveCourse(item.value)"
          >
            {{ item.label }}
          </button>
        </div>
      </div>
      <div class="mk-header-right">
        <div class="mk-search-box">
          <Search :size="15" />
          <input v-model="searchKeyword" placeholder="搜索题目 / 知识点 / 标签" />
        </div>
        <button class="mk-tool-btn" @click="importDemoSamples" :disabled="importing">
          <Loader2 v-if="importing" :size="14" class="spin" />
          <Plus v-else :size="14" />导入演示
        </button>
        <button class="mk-tool-btn primary" @click="showForm = !showForm">
          <Plus :size="14" />添加错题
        </button>
        <button class="mk-tool-btn" @click="activeCategory = activeCategory ? '' : 'review'">
          <Filter :size="14" />{{ activeCategory ? '清除筛选' : '智能筛选' }}
        </button>
        <button class="mk-tool-btn" @click="viewMode = viewMode === 'grid' ? 'list' : 'grid'">
          <List :size="14" />切换视图
        </button>
      </div>
    </div>

    <!-- 知识点筛选横幅（从知识图谱跳转时显示） -->
    <div v-if="kpFilterId" class="mk-kp-banner">
      <span class="kp-banner-icon">🎯</span>
      <span class="kp-banner-text">
        正在筛选知识点 <b>{{ kpFilterName || kpFilterId }}</b> 的相关错题，共 {{ filtered.length }} 条
      </span>
      <button type="button" class="kp-banner-clear" @click="kpFilterId = ''; kpFilterName = '';">✕ 清除筛选</button>
    </div>

    <!-- 分类筛选行 -->
    <div class="mk-filter-row">
      <div class="mk-pills">
        <button type="button" :class="['mk-pill', activeCategory === '' ? 'active' : '']" @click="activeCategory = ''">
          全部错题 <span class="mk-pill-count">{{ mistakes.length }}</span>
        </button>
        <button type="button" :class="['mk-pill', activeCategory === 'review' ? 'active' : '']" @click="activeCategory = activeCategory === 'review' ? '' : 'review'">
          待复习 <span class="mk-pill-count">{{ unresolvedCount }}</span>
        </button>
        <button type="button" :class="['mk-pill', activeCategory === 'mastered' ? 'active' : '']" @click="activeCategory = activeCategory === 'mastered' ? '' : 'mastered'">
          已掌握 <span class="mk-pill-count">{{ resolvedCount }}</span>
        </button>
        <button type="button" :class="['mk-pill', activeCategory === 'frequent' ? 'active' : '']" @click="activeCategory = activeCategory === 'frequent' ? '' : 'frequent'">
          高频易错 <span class="mk-pill-count">{{ highFreqCount }}</span>
        </button>
        <button type="button" :class="['mk-pill', activeCategory === 'recent' ? 'active' : '']" @click="activeCategory = activeCategory === 'recent' ? '' : 'recent'">
          近7天新增 <span class="mk-pill-count">{{ recentCount }}</span>
        </button>
        <button type="button" :class="['mk-pill', activeCategory === 'starred' ? 'active' : '']" @click="activeCategory = activeCategory === 'starred' ? '' : 'starred'">
          收藏题目 <span class="mk-pill-count">{{ starredIds.size }}</span>
        </button>
      </div>
      <div class="mk-view-controls">
        <div class="mk-sort" @click="cycleSort" style="cursor: pointer;">
          <span>{{ sortBy }}</span>
          <ChevronDown :size="13" />
        </div>
        <div class="mk-view-toggle">
          <button :class="{ active: viewMode === 'grid' }" @click="viewMode = 'grid'">
            <Grid3x3 :size="14" />
          </button>
          <button :class="{ active: viewMode === 'list' }" @click="viewMode = 'list'">
            <List :size="14" />
          </button>
        </div>
      </div>
    </div>

    <p v-if="error" class="mk-page-error">{{ error }}</p>

    <!-- 记录表单 -->
    <div v-if="showForm" class="record-form">
      <textarea v-model="form.question" rows="2" placeholder="题目内容 *" />
      <div class="form-row">
        <input v-model="form.student_answer" placeholder="我的答案" />
        <input v-model="form.correct_answer" placeholder="正确答案 *" />
        <input v-model="form.kp_id" placeholder="知识点（可选）" />
      </div>
      <div class="form-actions">
        <button class="ghost-btn" type="button" @click="showForm = false">取消</button>
        <button
          class="primary-btn"
          type="button"
          :disabled="submitting || !form.question.trim() || !form.correct_answer.trim()"
          @click="handleSubmit"
        >
          <Loader2 v-if="submitting" :size="14" class="spin" />提交并进入复习队列
        </button>
      </div>
    </div>

    <!-- 主体两列布局 -->
    <div class="mk-main">
      <!-- 主内容区 -->
      <div class="mk-content">
        <!-- 本周重点攻克 -->
        <div class="mk-hero">
          <div class="mk-hero-text">
            <div class="mk-hero-header">
              <Target :size="22" class="mk-hero-icon" />
              <h2>本周重点攻克：<span class="mk-hero-title">{{ weeklyFocus.title }}</span></h2>
              <span class="mk-hero-tag">AI推荐</span>
            </div>
            <p class="mk-hero-desc">
              {{ weeklyFocus.description }}
            </p>
            <div class="mk-hero-stats">
              <div>
                <b>{{ unresolvedCount }}</b>
                <small>待攻克</small>
              </div>
              <div>
                <b>{{ reviewMasteryRate }}<sup>%</sup></b>
                <small>复习掌握率</small>
              </div>
              <div>
                <b>{{ overview?.summary.streak_days ?? 0 }}<sup>天</sup></b>
                <small>连续复习</small>
              </div>
            </div>
            <button class="mk-hero-btn" @click="startHeroReview">
              立即复习 <ExternalLink :size="14" />
            </button>
          </div>
          <div class="mk-hero-diagnosis" aria-live="polite">
            <div class="mk-hero-diagnosis-head">
              <span><Lightbulb :size="15" />AI诊断建议</span>
              <span v-if="aiInsights" class="mk-ai-source" :class="aiInsights.source">
                {{ aiInsights.source === 'llm' ? 'LLM' : '智能分析' }}
              </span>
            </div>
            <div class="mk-ai-content">
              <Loader2 v-if="aiInsightsLoading" :size="18" class="spin" />
              <template v-else-if="aiInsights">
                <p class="mk-ai-summary">{{ aiInsights.summary }}</p>
                <div class="mk-hero-ai-grid">
                  <div v-if="aiInsights.weak_points?.length" class="mk-ai-section">
                    <b>薄弱知识点</b>
                    <ul class="mk-ai-list">
                      <li v-for="wp in aiInsights.weak_points.slice(0, 3)" :key="wp.kp_id">
                        <span class="mk-ai-kp">{{ knowledgePointName(wp.kp_id) }}</span>
                        <span class="mk-ai-kp-count">{{ wp.error_count }}道</span>
                      </li>
                    </ul>
                  </div>
                  <div v-if="aiInsights.evaluation?.suggestions?.length" class="mk-ai-section">
                    <b>改进建议</b>
                    <ul class="mk-ai-list">
                      <li v-for="(suggestion, index) in aiInsights.evaluation.suggestions.slice(0, 2)" :key="index">
                        {{ suggestion }}
                      </li>
                    </ul>
                  </div>
                </div>
              </template>
              <p v-else class="mk-ai-summary">暂无诊断结果，点击刷新后生成。</p>
              <button class="mk-ai-refresh mk-ai-refresh-inline" type="button" @click="loadInsights" :disabled="aiInsightsLoading">
                <RefreshCcw :size="12" />刷新分析
              </button>
            </div>
          </div>
        </div>

        <!-- 加载状态 -->
        <div v-if="loading" class="mk-loading">
          <Loader2 :size="28" class="spin" />
          <p>正在加载错题数据…</p>
        </div>

        <!-- 空状态 -->
        <div v-else-if="!filtered.length" class="mk-empty">
          <BookX :size="28" />
          <p>{{ activeCourse ? `${courseLabel(activeCourse)}暂无错题，可完成练习或添加错题后再来复习。` : '暂无错题。点「导入演示」快速体验闭环，或在群聊做题后自动沉淀。' }}</p>
        </div>

        <!-- 错题卡片网格 -->
        <div v-else :class="['mk-grid', viewMode === 'list' ? 'list-view' : '']">
          <div
            v-for="m in paged"
            :key="m.id"
            :class="['mk-card', m.resolved ? 'resolved' : '', expandedIds.has(m.id) ? 'expanded' : '']"
          >
            <!-- 精简卡片头：点击直接打开该卡片详情弹窗 -->
            <div class="mk-card-compact" @click="openMistakeModal(m)">
              <div
                class="mk-subject-icon"
                :style="{ background: getSubjectColor(m.kp_id) + '18', color: getSubjectColor(m.kp_id) }"
              >
                <component :is="getSubjectIcon(m.kp_id)" :size="16" />
              </div>
              <div class="mk-card-compact-body">
                <h3 class="mk-card-title">{{ m.question.slice(0, 40) }}{{ m.question.length > 40 ? '...' : '' }}</h3>
                <div class="mk-card-compact-meta">
                  <span class="mk-tag mini">{{ errorLabel(m.error_type) }}</span>
                  <span v-if="m.course" class="mk-course-tag">{{ courseLabel(m.course) }}</span>
                  <span class="mk-mastery-mini">
                    掌握度 {{ getMastery(m) }}%
                    <span class="mk-mastery-bar">
                      <i :style="{ width: getMastery(m) + '%', background: getSubjectColor(m.kp_id) }" />
                    </span>
                  </span>
                  <span class="mk-time-mini">{{ formatRelative(m.created_at) }}</span>
                </div>
              </div>
              <span :class="['mk-status', m.resolved ? 'mastered' : 'review']">
                {{ m.resolved ? "已掌握" : "待复习" }}
              </span>
              <button
                type="button"
                class="mk-icon-btn"
                @click.stop="toggleStar(m.id)"
                :style="{ color: starredIds.has(m.id) ? '#d89229' : '' }"
              >
                <Star :size="14" :fill="starredIds.has(m.id) ? 'currentColor' : 'none'" />
              </button>
              <ChevronDown :size="16" class="mk-expand-chevron" :class="{ rotated: expandedIds.has(m.id) }" />
            </div>

            <!-- 详情改为弹窗呈现（openMistakeModal），不再行内展开 -->
          </div>
        </div>

        <!-- 分页（在内容区内，紧贴卡片底部） -->
        <div v-if="!loading && filtered.length" class="mk-pagination">
          <span class="mk-pagination-info">共 {{ filtered.length }} 道错题 · 第 {{ currentPage }}/{{ totalPages }} 页</span>
          <div class="mk-pagination-controls">
            <button class="mk-page-btn" :disabled="currentPage === 1" @click="goToPage(currentPage - 1)">‹</button>
            <button
              v-for="p in totalPages"
              :key="p"
              :class="['mk-page-btn', p === currentPage ? 'active' : '']"
              @click="goToPage(p)"
            >{{ p }}</button>
            <button class="mk-page-btn" :disabled="currentPage === totalPages" @click="goToPage(currentPage + 1)">›</button>
          </div>
          <div class="mk-page-size">
            每页 {{ pageSize }} 条
          </div>
        </div>
      </div>

      <!-- 右侧栏 -->
      <aside class="mk-aside">
        <!-- 复习概览 -->
        <div class="mk-aside-card">
          <h3 class="mk-aside-title">复习概览</h3>
          <div class="mk-overview-grid">
            <div class="mk-overview-item orange-soft">
              <div class="mk-overview-row">
                <span>总错题</span>
                <span class="mk-overview-icon orange"><BookX :size="13" /></span>
              </div>
              <div class="mk-overview-value">{{ mistakes.length }}</div>
            </div>
            <div class="mk-overview-item queue-soft">
              <div class="mk-overview-row">
                <span>待复习</span>
                <span class="mk-overview-icon queue"><Clock :size="13" /></span>
              </div>
              <div class="mk-overview-value">{{ unresolvedCount }}</div>
            </div>
            <div class="mk-overview-item green-soft">
              <div class="mk-overview-row">
                <span>已掌握</span>
                <span class="mk-overview-icon green"><CheckCircle2 :size="13" /></span>
              </div>
              <div class="mk-overview-value">{{ resolvedCount }}</div>
            </div>
            <div class="mk-overview-item info-soft">
              <div class="mk-overview-row">
                <span>本周新增</span>
                <span class="mk-overview-icon info"><Plus :size="13" /></span>
              </div>
              <div class="mk-overview-value">{{ recentCount }}</div>
            </div>
          </div>
        </div>

        <!-- 错误原因分布 -->
        <div class="mk-aside-card">
          <h3 class="mk-aside-title">错误原因分布</h3>
          <div class="mk-distribution">
            <div class="mk-donut">
              <svg viewBox="0 0 100 100">
                <circle cx="50" cy="50" r="38" fill="none" stroke="var(--neutral-200)" stroke-width="14" />
                <template v-for="(item, idx) in distributionList.slice(0, 5)" :key="item.name">
                  <circle
                    cx="50"
                    cy="50"
                    r="38"
                    fill="none"
                    :stroke="['#ea5a1a', '#2f9f6b', '#d89229', '#b3413a', '#4a6b85'][idx % 5]"
                    stroke-width="14"
                    stroke-dasharray="60 238"
                    :stroke-dashoffset="-idx * 50"
                    transform="rotate(-90 50 50)"
                    stroke-linecap="round"
                  />
                </template>
              </svg>
            </div>
            <ul class="mk-distribution-list">
              <li v-for="(item, idx) in distributionList.slice(0, 5)" :key="item.name">
                <span class="mk-dot-color" :style="{ background: ['#ea5a1a', '#2f9f6b', '#d89229', '#b3413a', '#4a6b85'][idx % 5] }" />
                <span class="mk-dist-name">{{ item.name }}</span>
                <span class="mk-dist-count">{{ item.count }} <em>({{ item.percent }}%)</em></span>
              </li>
            </ul>
          </div>
        </div>

        <!-- 遗忘曲线提醒 -->
        <div class="mk-aside-card">
          <h3 class="mk-aside-title">
            <Bell :size="14" style="vertical-align: -2px; color: #d89229;" />
            遗忘曲线提醒
          </h3>
          <ul class="mk-reminder-list">
            <li>
              <span class="mk-remind-dot red" />
              <span class="mk-remind-label">今日应复习</span>
              <span class="mk-remind-count">{{ todoReview }} <small>题</small></span>
            </li>
            <li>
              <span class="mk-remind-dot yellow" />
              <span class="mk-remind-label">24 小时内到期</span>
              <span class="mk-remind-count">{{ expiringReview }} <small>题</small></span>
            </li>
            <li>
              <span class="mk-remind-dot green" />
              <span class="mk-remind-label">高优先级</span>
              <span class="mk-remind-count">{{ highPriority }} <small>题</small></span>
            </li>
          </ul>
          <button class="mk-start-btn" @click="startTodayReview">
            <span>▶</span> 开始今日复习
          </button>
        </div>

        <!-- 最近复习记录 -->
        <div class="mk-aside-card">
          <h3 class="mk-aside-title">
            <Clock :size="14" style="vertical-align: -2px; color: #ea5a1a;" />
            最近复习记录
            <button
              type="button"
              class="mk-aside-more"
              @click="showAllReviewLog = !showAllReviewLog"
            >{{ showAllReviewLog ? "收起 ‹" : "更多 ›" }}</button>
          </h3>
          <p v-if="!reviewLog.length" class="mk-recent-empty">
            还没有复习记录。点上方「开始今日复习」完成一轮自评，记录会出现在这里。
          </p>
          <ul class="mk-recent-list">
            <!-- 点击直接打开对应错题详情 -->
            <li
              v-for="m in recentReview"
              :key="m.id"
              class="clickable"
              role="button"
              @click="openLogEntry(m)"
            >
              <span
                class="mk-subject-icon sm"
                :style="{ background: getSubjectColor(m.kp_id) + '18', color: getSubjectColor(m.kp_id) }"
              >
                <component :is="getSubjectIcon(m.kp_id)" :size="11" />
              </span>
              <span class="mk-recent-title">{{ m.question.slice(0, 20) }}{{ m.question.length > 20 ? '...' : '' }}</span>
              <span
                v-if="m.logResult"
                :class="['mk-recent-result', m.logResult === '掌握' ? 'good' : m.logResult === '不会' ? 'bad' : '']"
              >{{ m.logResult }}</span>
              <span class="mk-recent-time">{{ formatRelative(m.created_at) }}</span>
            </li>
          </ul>
        </div>
      </aside>
    </div>

    <!-- ===== 错题详情弹窗：点击卡片直接打开该卡 ===== -->
    <div v-if="activeMistake" class="mk-review-mask" @click.self="closeMistakeModal">
      <template v-for="m in [activeMistake]" :key="m.id">
        <div class="mk-review-modal mk-detail-modal">
          <header class="mk-review-head">
            <div>
              <b>{{ m.question.slice(0, 32) }}{{ m.question.length > 32 ? "..." : "" }}</b>
              <small>{{ errorLabel(m.error_type) }} · {{ m.kp_id || "综合" }} · {{ formatTs(m.created_at) }}</small>
            </div>
            <button type="button" class="mk-review-close" @click="closeMistakeModal">✕</button>
          </header>

          <div class="mk-card-detail in-modal">
            <div class="mk-detail-section">
              <b class="mk-detail-label">题目</b>
              <p class="mk-detail-text">{{ m.question }}</p>
            </div>
            <div class="mk-detail-row">
              <div class="mk-detail-section">
                <b class="mk-detail-label">我的答案</b>
                <p class="mk-detail-text student">{{ m.student_answer || '—' }}</p>
              </div>
              <div class="mk-detail-section">
                <b class="mk-detail-label">正确答案</b>
                <p class="mk-detail-text correct">{{ m.correct_answer || '—' }}</p>
              </div>
            </div>
            <div class="mk-card-tags">
              <span v-for="t in getTags(m)" :key="t" class="mk-tag">{{ t }}</span>
              <span class="mk-tag muted">来源：{{ m.kp_id || '综合' }}</span>
            </div>

            <div class="mk-card-actions">
              <button type="button" title="加入 SM-2 间隔复习队列（智狐 · 规划调度）" @click="handleEnqueue(m)">
                <Loader2 v-if="enqueueingId === m.id" :size="12" class="spin" />
                <RefreshCcw v-else :size="12" />加入复习
              </button>
              <button type="button" title="团团（学习评估）对错误原因做八类归因" :disabled="busyId === m.id" @click="runAction(m, 'analyze')">
                <Loader2 v-if="busyId === m.id && busyAction === 'analyze'" :size="12" class="spin" />
                <Stethoscope v-else :size="12" />AI 归因<em class="mk-agent-tag">团团</em>
              </button>
              <button type="button" title="小龙（题库生成）按 Bloom 层级生成针对性变式" :disabled="busyId === m.id" @click="runAction(m, 'variants')">
                <Loader2 v-if="busyId === m.id && busyAction === 'variants'" :size="12" class="spin" />
                <Wand2 v-else :size="12" />生成变式<em class="mk-agent-tag">小龙</em>
              </button>
              <button type="button" title="智灵（讲解）+ 智狐（规划）联合生成补救方案" :disabled="busyId === m.id" @click="runAction(m, 'remediation')">
                <Loader2 v-if="busyId === m.id && busyAction === 'remediation'" :size="12" class="spin" />
                <Sparkles v-else :size="12" />补救方案<em class="mk-agent-tag">智灵</em>
              </button>
              <button v-if="!m.resolved" type="button" class="ok-btn" @click="handleResolve(m)">
                <Check :size="12" />标记解决
              </button>
            </div>

            <p v-if="practiceResult[`enq-${m.id}`]" class="mk-enqueue-note">
              ✓ {{ practiceResult[`enq-${m.id}`] }}（明日「今日复习」可见）
            </p>

            <!-- AI 产出（标注产出智能体，与群聊 6 Agent 同一套分工） -->
            <div v-if="insights[m.id]" class="mk-insight">
              <div v-if="insights[m.id].analysis" class="mk-insight-block">
                <b><Stethoscope :size="12" />归因分析 <em class="mk-agent-tag">团团 · 学习评估</em></b>
                <p>
                  <span class="mk-tag orange">{{ errorLabel(insights[m.id].analysis!.error_type) }}</span>
                  {{ insights[m.id].analysis!.detail }}
                </p>
              </div>
              <div v-if="insights[m.id].remediationNote" class="mk-insight-block">
                <b><Sparkles :size="12" />补救建议 <em class="mk-agent-tag">智灵 · 讲解 + 智狐 · 规划</em></b>
                <p>{{ insights[m.id].remediationNote }}</p>
              </div>
              <div v-if="insights[m.id].variants?.length" class="mk-insight-block">
                <b><Wand2 :size="12" />变式练习（{{ insights[m.id].variants!.length }} 题）<em class="mk-agent-tag">小龙 · 题库生成</em></b>
                <div v-for="(v, i) in insights[m.id].variants" :key="i" class="mk-variant">
                  <div class="mk-variant-head">
                    <span class="mk-tag green">{{ v.bloom_level ?? v.bloom ?? `变式 ${i + 1}` }}</span>
                    <p>{{ v.question ?? JSON.stringify(v).slice(0, 100) }}</p>
                  </div>
                  <button type="button" class="mk-reveal" @click="toggleAnswer(m.id, i)">
                    {{ insights[m.id].revealedAnswers.has(i) ? "收起答案" : "查看答案与解析" }}
                  </button>
                  <div v-if="insights[m.id].revealedAnswers.has(i)" class="mk-variant-answer">
                    <p><b>答案：</b>{{ v.answer ?? "（见解析）" }}</p>
                    <p v-if="v.explanation"><b>解析：</b>{{ v.explanation }}</p>
                    <div class="mk-variant-report">
                      <template v-if="!practiceResult[`${m.id}-${i}`]">
                        <span>做完了？上报结果：</span>
                        <button type="button" class="ok" @click="reportVariantResult(m, i, true)">我做对了</button>
                        <button type="button" class="bad" @click="reportVariantResult(m, i, false)">我做错了</button>
                      </template>
                      <b v-else>{{ practiceResult[`${m.id}-${i}`] }}</b>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </template>
    </div>

    <!-- ===== 今日复习会话（小龙出题 · 团团评估 · 智狐调度） ===== -->
    <div v-if="reviewOpen" class="mk-review-mask" @click.self="closeReview">
      <div class="mk-review-modal">
        <header class="mk-review-head">
          <div>
            <b>今日复习</b>
            <small v-if="!reviewFinished">
              第 {{ reviewIndex + 1 }} / {{ reviewQueue.length }} 题 ·
              自评结果同步到间隔复习计划（SM-2）与掌握度（BKT）
            </small>
          </div>
          <button type="button" class="mk-review-close" @click="closeReview">✕</button>
        </header>

        <!-- 复习中 -->
        <template v-if="!reviewFinished && reviewCurrent">
          <div class="mk-review-progress">
            <i :style="{ width: `${(reviewIndex / reviewQueue.length) * 100}%` }" />
          </div>
          <div class="mk-review-body">
            <span class="mk-tag mini">{{ reviewCurrent.kp_id || "综合" }}</span>
            <p class="mk-review-question">{{ reviewCurrent.question }}</p>

            <template v-if="!reviewRevealed">
              <p class="mk-review-hint">先在心里作答，再核对答案。</p>
              <button type="button" class="mk-start-btn" @click="reviewRevealed = true">
                显示答案
              </button>
            </template>
            <template v-else>
              <div class="mk-review-answer">
                <p><b>正确答案：</b>{{ reviewCurrent.correct_answer || "—" }}</p>
                <p v-if="reviewCurrent.student_answer"><b>当时的错误答案：</b>{{ reviewCurrent.student_answer }}</p>
                <p v-if="reviewCurrent.analysis" class="mk-review-analysis">
                  <b>团团归因：</b>{{ reviewCurrent.analysis }}
                </p>
              </div>
              <div class="mk-review-grade">
                <span>自评掌握程度：</span>
                <button type="button" class="grade good" :disabled="reviewGrading" @click="gradeReview(5)">完全掌握</button>
                <button type="button" class="grade mid" :disabled="reviewGrading" @click="gradeReview(3)">有点模糊</button>
                <button type="button" class="grade bad" :disabled="reviewGrading" @click="gradeReview(1)">还是不会</button>
              </div>
            </template>
          </div>
        </template>

        <!-- 复习完成总结 -->
        <template v-else>
          <div class="mk-review-body summary">
            <CheckCircle2 :size="34" style="color: #2f9f6b;" />
            <h3>本轮复习完成！</h3>
            <p>
              共复习 <b>{{ reviewSummary.total }}</b> 题，
              完全掌握 <b>{{ reviewSummary.mastered }}</b> 题。
              结果已同步：智狐更新复习排期，团团刷新掌握度评估。
            </p>
            <button type="button" class="mk-start-btn" @click="closeReview">完成</button>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.spin {
  animation: mk-spin 1s linear infinite;
}

button.mk-aside-more {
  border: 0;
  background: transparent;
  cursor: pointer;
  font: inherit;
  color: #ea5a1a;
}

/* ===== 智能体标签 ===== */
.mk-agent-tag {
  font-style: normal;
  font-size: 10px;
  font-weight: 700;
  padding: 1px 6px;
  margin-left: 4px;
  border-radius: 999px;
  background: #fdeee2;
  color: #c2410c;
  white-space: nowrap;
}

.mk-enqueue-note {
  margin: 8px 0 0;
  font-size: 12px;
  color: #157347;
  background: #e8f6ee;
  border-radius: 8px;
  padding: 6px 10px;
}

.mk-recent-empty {
  margin: 4px 0;
  font-size: 11.5px;
  color: #9ca3af;
  line-height: 1.6;
}

.mk-recent-result {
  font-size: 10.5px;
  font-weight: 700;
  padding: 1px 7px;
  border-radius: 999px;
  background: #fff4e0;
  color: #a16207;
  flex: none;
}
.mk-recent-result.good { background: #e8f6ee; color: #157347; }
.mk-recent-result.bad { background: #fef2f2; color: #b91c1c; }

/* ===== 今日复习会话 ===== */
.mk-review-mask {
  position: fixed;
  inset: 0;
  z-index: 320;
  background: rgba(30, 24, 16, 0.45);
  display: grid;
  place-items: center;
}

.mk-review-modal {
  width: min(640px, 92vw);
  max-height: 85vh;
  overflow-y: auto;
  background: #fff;
  border-radius: 16px;
  padding: 22px 24px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.22);
}

.mk-detail-modal {
  width: min(760px, 94vw);
}

.mk-card-detail.in-modal {
  border-top: 0;
  padding-top: 0;
  margin-top: 0;
}

.mk-recent-list li.clickable {
  cursor: pointer;
  border-radius: 8px;
  transition: background 0.12s ease;
}
.mk-recent-list li.clickable:hover {
  background: #fff5ec;
}

.mk-review-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}
.mk-review-head b { font-size: 17px; }
.mk-review-head small { display: block; margin-top: 4px; color: #8a94a3; font-size: 12px; }

.mk-review-close {
  border: 0;
  background: transparent;
  color: #9ca3af;
  cursor: pointer;
  font-size: 15px;
}

.mk-review-progress {
  height: 6px;
  border-radius: 999px;
  background: #f1ede4;
  overflow: hidden;
  margin-bottom: 16px;
}
.mk-review-progress i {
  display: block;
  height: 100%;
  background: linear-gradient(90deg, #f59e0b, #ea5a1a);
  border-radius: 999px;
  transition: width 0.3s ease;
}

.mk-review-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.mk-review-body.summary {
  align-items: center;
  text-align: center;
  padding: 22px 0 8px;
}
.mk-review-body.summary h3 { margin: 4px 0; }
.mk-review-body.summary p { margin: 0 0 10px; color: #4b5563; font-size: 13.5px; line-height: 1.7; }

.mk-review-question {
  margin: 0;
  font-size: 15px;
  line-height: 1.7;
  color: #1f2937;
  font-weight: 600;
}

.mk-review-hint {
  margin: 0;
  color: #8a94a3;
  font-size: 12.5px;
}

.mk-review-answer {
  background: #faf7f0;
  border: 1px solid #efe8da;
  border-radius: 10px;
  padding: 12px 14px;
  font-size: 13px;
  line-height: 1.7;
}
.mk-review-answer p { margin: 0 0 6px; }

.mk-review-analysis { color: #a16207; }

.mk-review-grade {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12.5px;
  color: #4b5563;
  flex-wrap: wrap;
}
.mk-review-grade .grade {
  padding: 7px 16px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 700;
  border: 1px solid transparent;
  cursor: pointer;
}
.mk-review-grade .grade:disabled { opacity: 0.5; cursor: wait; }
.mk-review-grade .grade.good { background: #e8f6ee; color: #157347; border-color: #cdecd9; }
.mk-review-grade .grade.mid { background: #fff4e0; color: #a16207; border-color: #f3e0b8; }
.mk-review-grade .grade.bad { background: #fef2f2; color: #b91c1c; border-color: #f6d3d3; }

@keyframes mk-spin {
  to {
    transform: rotate(360deg);
  }
}

/* 全部沿用 companion-design.css 的设计 token：橙色主色 + 米色纸张 + 衬线 */
.mistakes-page-redesign {
  width: 100%;
  max-width: 1480px;
  margin: 0 auto;
  padding: 8px 4px 40px;
  font-family: var(--sans);
}

/* ===== Header ===== */
.mk-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.mk-header-left {
  flex-shrink: 0;
}

.mk-title {
  font-size: 26px;
  font-weight: 700;
  color: var(--ink);
  margin: 0;
  letter-spacing: -0.3px;
  font-family: var(--serif);
}

.mk-subtitle {
  font-size: 13px;
  color: var(--muted);
  margin: 4px 0 0;
}

.mk-header-right {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  justify-content: flex-end;
}

.mk-search-box {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  border-radius: var(--radius-sm);
  border: var(--border-soft);
  background: var(--paper);
  width: 320px;
  color: var(--muted);
}

.mk-search-box input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-size: 13px;
  color: var(--ink);
}

.mk-search-box input::placeholder {
  color: var(--subtle);
}

.mk-tool-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 8px 14px;
  border-radius: var(--radius-sm);
  border: var(--border-soft);
  background: var(--paper);
  font-size: 12.5px;
  color: var(--neutral-700);
  cursor: pointer;
  transition: all 0.15s;
}

.mk-tool-btn:hover {
  border-color: var(--orange-300);
  color: var(--orange-600);
}

/* ===== KP Filter Banner ===== */
.mk-kp-banner {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  margin-bottom: 14px;
  background: linear-gradient(135deg, rgba(234, 90, 26, 0.08), rgba(216, 146, 41, 0.06));
  border: 1px solid rgba(234, 90, 26, 0.2);
  border-radius: 10px;
  font-size: 13px;
}
.mk-kp-banner .kp-banner-icon { font-size: 16px; }
.mk-kp-banner .kp-banner-text { flex: 1; color: var(--ink-700); }
.mk-kp-banner .kp-banner-text b { color: var(--orange-600); }
.mk-kp-banner .kp-banner-clear {
  border: none;
  background: rgba(234, 90, 26, 0.1);
  color: var(--orange-600);
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
}
.mk-kp-banner .kp-banner-clear:hover {
  background: rgba(234, 90, 26, 0.2);
}

/* ===== Filter Pills ===== */
.mk-filter-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 18px;
  flex-wrap: wrap;
}

.mk-pills {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}

.mk-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 999px;
  border: var(--border-soft);
  background: var(--paper);
  font-size: 12.5px;
  color: var(--neutral-700);
  cursor: pointer;
  transition: all 0.15s;
  font-weight: 500;
}

.mk-pill:hover {
  border-color: var(--neutral-300);
}

.mk-pill.active {
  border-color: var(--orange-500);
  background: var(--orange-50);
  color: var(--orange-700);
}

.mk-pill-count {
  font-size: 11.5px;
  color: var(--muted);
  font-weight: 600;
}

.mk-pill.active .mk-pill-count {
  color: var(--orange-600);
}

.mk-view-controls {
  display: flex;
  align-items: center;
  gap: 12px;
}

.mk-sort {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  border-radius: var(--radius-sm);
  border: var(--border-soft);
  background: var(--paper);
  font-size: 12.5px;
  color: var(--neutral-700);
  cursor: pointer;
}

.mk-view-toggle {
  display: inline-flex;
  border-radius: var(--radius-sm);
  border: var(--border-soft);
  background: var(--paper);
  overflow: hidden;
}

.mk-view-toggle button {
  padding: 7px 10px;
  border: none;
  background: transparent;
  color: var(--muted);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
}

.mk-view-toggle button.active {
  background: var(--orange-500);
  color: #fff;
}

/* ===== Page Error ===== */
.mk-page-error {
  margin: 0 0 14px;
  padding: 10px 14px;
  border-radius: var(--radius-sm);
  background: rgba(179, 65, 58, 0.08);
  border: 1px solid rgba(179, 65, 58, 0.25);
  color: var(--status-error);
  font-size: 12.5px;
}

/* ===== Record Form ===== */
.record-form {
  margin-bottom: 16px;
  padding: 14px;
  border-radius: var(--radius-md);
  border: 1px solid var(--orange-200);
  background: var(--orange-50);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.record-form textarea,
.record-form input {
  padding: 9px 12px;
  border-radius: 9px;
  border: var(--border-soft);
  background: var(--paper);
  font-size: 13px;
  resize: vertical;
  outline: none;
  color: var(--ink);
}

.record-form input:focus,
.record-form textarea:focus {
  border-color: var(--orange-400);
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 8px;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.ghost-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 7px 14px;
  border-radius: var(--radius-sm);
  border: var(--border-soft);
  background: var(--paper);
  color: var(--neutral-700);
  font-size: 12.5px;
  cursor: pointer;
}

.ghost-btn:hover {
  border-color: var(--orange-300);
  color: var(--orange-600);
}

.primary-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 7px 14px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--orange-500);
  background: var(--orange-500);
  color: #fff;
  font-size: 12.5px;
  font-weight: 500;
  cursor: pointer;
}

.primary-btn:hover {
  background: var(--orange-600);
  border-color: var(--orange-600);
}

/* ===== Main Layout ===== */
.mk-main {
  display: grid;
  grid-template-columns: 1fr 280px;
  gap: 18px;
  align-items: start;
}

.mk-content {
  min-width: 0;
  align-self: stretch;
  display: flex;
  flex-direction: column;
}

.mk-course-switcher {
  display: inline-flex;
  gap: 3px;
  margin-top: 10px;
  padding: 3px;
  border: 1px solid var(--paper-400);
  border-radius: 999px;
  background: var(--paper-100);
}

.mk-course-switcher button {
  min-height: 28px;
  padding: 4px 12px;
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: var(--muted);
  font-size: 12px;
  cursor: pointer;
  transition: background .18s ease, color .18s ease, box-shadow .18s ease;
}

.mk-course-switcher button:hover,
.mk-course-switcher button:focus-visible {
  color: var(--orange-700);
  outline: none;
}

.mk-course-switcher button.active {
  background: var(--paper);
  color: var(--orange-700);
  font-weight: 700;
  box-shadow: 0 1px 5px rgba(90, 61, 34, .12);
}

.mk-aside {
  position: sticky;
  top: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

/* ===== Hero Banner ===== */
.mk-hero {
  display: flex;
  align-items: stretch;
  gap: 24px;
  padding: 22px 28px;
  border-radius: var(--radius-lg);
  background: linear-gradient(120deg, var(--orange-50) 0%, #fef6ec 50%, #fdf2e3 100%);
  border: 1px solid var(--orange-100);
  margin-bottom: 18px;
  position: relative;
  overflow: hidden;
  box-shadow: var(--shadow-1);
}

.mk-hero-text {
  flex: 0 1 45%;
  min-width: 360px;
  z-index: 2;
}

.mk-hero-diagnosis {
  flex: 1;
  min-width: 0;
  padding: 15px 17px;
  border: 1px solid rgba(234, 90, 26, 0.16);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.74);
  z-index: 2;
}

.mk-hero-diagnosis-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 8px;
}

.mk-hero-diagnosis-head > span:first-child {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--ink);
  font-size: 13px;
  font-weight: 700;
}

.mk-hero-diagnosis-head svg {
  color: var(--orange-500);
}

.mk-hero-ai-grid {
  display: grid;
  grid-template-columns: minmax(150px, 0.7fr) minmax(220px, 1.3fr);
  gap: 14px;
}

.mk-ai-refresh-inline {
  width: auto;
  min-width: 96px;
  padding-inline: 12px;
}

.mk-hero-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.mk-hero-icon {
  color: var(--orange-500);
}

.mk-hero-header h2 {
  margin: 0;
  font-size: 17px;
  font-weight: 600;
  color: var(--ink);
}

.mk-hero-title {
  color: var(--orange-600);
}

.mk-hero-tag {
  padding: 2px 10px;
  border-radius: 999px;
  background: linear-gradient(90deg, var(--orange-500), var(--orange-400));
  color: #fff;
  font-size: 11px;
  font-weight: 600;
}

.mk-hero-desc {
  margin: 0 0 16px;
  font-size: 13px;
  color: var(--neutral-600);
  line-height: 1.6;
}

.mk-hero-stats {
  display: flex;
  gap: 32px;
  margin-bottom: 16px;
}

.mk-hero-stats > div {
  display: flex;
  flex-direction: column;
}

.mk-hero-stats b {
  font-size: 22px;
  font-weight: 700;
  color: var(--ink);
  line-height: 1;
  margin-bottom: 4px;
  font-family: var(--serif);
}

.mk-hero-stats b sup {
  font-size: 12px;
  font-weight: 500;
  margin-left: 1px;
}

.mk-hero-stats small {
  font-size: 11.5px;
  color: var(--muted);
}

.mk-hero-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 9px 20px;
  border-radius: var(--radius-sm);
  background: var(--orange-500);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  border: none;
  cursor: pointer;
  transition: all 0.15s;
  box-shadow: 0 4px 12px rgba(234, 90, 26, 0.28);
}

.mk-hero-btn:hover {
  background: var(--orange-600);
  transform: translateY(-1px);
}

/* ===== Cards Grid ===== */
.mk-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  align-items: stretch;
}

.mk-grid.list-view {
  grid-template-columns: 1fr;
}

.mk-grid.list-view .mk-card {
  height: auto;
  min-height: 120px;
}

.mk-card {
  background: var(--paper);
  border: var(--border-soft);
  border-radius: var(--radius-md);
  padding: 0;
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 156px;
  transition: border-color 0.2s, box-shadow 0.2s;
  box-shadow: var(--shadow-1);
  overflow: hidden;
  width: 100%;
}

.mk-card:not(.expanded) {
  height: 156px;
}

.mk-card:hover {
  border-color: var(--orange-300);
  box-shadow: var(--shadow-2);
}

.mk-card.resolved {
  opacity: 0.72;
}

.mk-card.expanded {
  border-color: var(--orange-400);
  box-shadow: 0 4px 16px rgba(234, 90, 26, 0.12);
  height: auto;
}

/* 精简卡片头 */
.mk-card-compact {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  height: 100%;
  cursor: pointer;
  user-select: none;
}

.mk-card-compact:hover {
  background: rgba(234, 90, 26, 0.03);
}

.mk-card-compact-body {
  flex: 1;
  min-width: 0;
}

.mk-card-compact-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 4px;
  flex-wrap: wrap;
}

.mk-tag.mini {
  padding: 1px 7px;
  font-size: 10.5px;
  background: var(--orange-50);
  color: var(--orange-700);
  border-radius: 4px;
  font-weight: 500;
}

.mk-mastery-mini {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  color: var(--muted);
}

.mk-time-mini {
  font-size: 11px;
  color: var(--neutral-400);
}

.mk-expand-chevron {
  color: var(--neutral-400);
  transition: transform 0.2s;
  flex-shrink: 0;
}

.mk-expand-chevron.rotated {
  transform: rotate(180deg);
}

/* 展开后详情 */
.mk-card-detail {
  padding: 0 14px 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  border-top: 1px dashed var(--neutral-200);
  padding-top: 12px;
  margin-top: 0;
}

.mk-detail-section {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.mk-detail-label {
  font-size: 11.5px;
  color: var(--orange-600);
  font-weight: 600;
}

.mk-detail-text {
  margin: 0;
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--neutral-700);
}

.mk-detail-text.student {
  color: var(--status-error);
}

.mk-detail-text.correct {
  color: var(--status-running);
}

.mk-detail-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.mk-tag.muted {
  background: var(--neutral-100);
  color: var(--neutral-600);
  font-size: 10.5px;
}

.ok-btn {
  border-color: var(--status-running) !important;
  color: var(--status-running) !important;
  background: rgba(47, 159, 107, 0.08) !important;
}

.ok-btn:hover {
  background: rgba(47, 159, 107, 0.15) !important;
}

/* 展开动画 */
.mk-expand-enter-active,
.mk-expand-leave-active {
  transition: all 0.25s ease;
  overflow: hidden;
}

.mk-expand-enter-from,
.mk-expand-leave-to {
  opacity: 0;
  max-height: 0;
  padding-top: 0;
  padding-bottom: 0;
}

.mk-expand-enter-to,
.mk-expand-leave-from {
  opacity: 1;
  max-height: 800px;
}

.mk-subject-icon {
  width: 30px;
  height: 30px;
  border-radius: 8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.mk-subject-icon.sm {
  width: 22px;
  height: 22px;
  border-radius: 6px;
}

.mk-card-title {
  flex: 1;
  margin: 0;
  font-size: 13.5px;
  font-weight: 600;
  color: var(--ink);
  line-height: 1.4;
  min-height: 38px;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.mk-status {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  flex-shrink: 0;
}

.mk-status.review {
  background: var(--orange-50);
  color: var(--orange-700);
}

.mk-status.mastered {
  background: rgba(47, 159, 107, 0.12);
  color: var(--status-running);
}

.mk-card-content {
  margin: 0;
  font-size: 12.5px;
  color: var(--neutral-600);
  line-height: 1.6;
  min-height: 38px;
}

.mk-card-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.mk-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  background: var(--orange-50);
  color: var(--orange-700);
  font-size: 11px;
  font-weight: 500;
}

.mk-tag.orange {
  background: var(--orange-100);
  color: var(--orange-700);
}

.mk-tag.green {
  background: rgba(47, 159, 107, 0.12);
  color: var(--status-running);
}

.mk-card-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 11.5px;
  color: var(--muted);
}

.mk-error-reason {
  color: var(--status-error);
}

.mk-mastery {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.mk-mastery-bar {
  display: inline-block;
  width: 60px;
  height: 4px;
  background: var(--neutral-200);
  border-radius: 999px;
  overflow: hidden;
}

.mk-mastery-bar i {
  display: block;
  height: 100%;
  border-radius: 999px;
}

/* footer merged into compact view */

.mk-card-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  margin-top: 4px;
}

.mk-card-actions button {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 5px 10px;
  border-radius: 6px;
  border: var(--border-soft);
  background: var(--paper);
  font-size: 11.5px;
  color: var(--neutral-700);
  cursor: pointer;
  transition: all 0.12s;
}

.mk-card-actions button:hover {
  border-color: var(--orange-300);
  color: var(--orange-600);
}

.mk-card-actions .mk-icon-btn {
  padding: 5px 7px;
}

.mk-card-actions .mk-icon-btn:last-child {
  border: none;
  background: transparent;
  font-weight: 700;
}

/* ===== Insight ===== */
.mk-insight {
  margin-top: 6px;
  padding: 12px;
  border-radius: 10px;
  background: var(--paper-2);
  border: var(--border-soft);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.mk-insight-block b {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  color: var(--orange-600);
  margin-bottom: 4px;
}

.mk-insight-block p {
  margin: 0;
  font-size: 12px;
  line-height: 1.6;
  color: var(--neutral-700);
}

.mk-variant {
  margin-top: 8px;
  padding: 10px;
  border-radius: 8px;
  border: var(--border-soft);
  background: var(--paper);
}

.mk-variant-head {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.mk-variant-head p {
  margin: 0;
  font-size: 12px;
  line-height: 1.6;
  color: var(--ink);
}

.mk-reveal {
  margin-top: 6px;
  font-size: 11px;
  color: var(--orange-600);
  text-decoration: underline;
  text-underline-offset: 3px;
  background: none;
  border: none;
  cursor: pointer;
  padding: 0;
}

.mk-variant-answer {
  margin-top: 6px;
  padding: 8px 10px;
  border-radius: 6px;
  background: rgba(47, 159, 107, 0.08);
  border: 1px solid rgba(47, 159, 107, 0.22);
}

.mk-variant-answer p {
  margin: 0 0 4px;
  font-size: 12px;
  line-height: 1.6;
}

.mk-variant-report {
  margin-top: 6px;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  font-size: 11px;
  color: var(--muted);
}

.mk-variant-report button {
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  border: 1px solid;
  cursor: pointer;
  background: var(--paper);
}

.mk-variant-report button.ok {
  color: var(--status-running);
  border-color: var(--status-running);
  background: rgba(47, 159, 107, 0.08);
}

.mk-variant-report button.bad {
  color: var(--status-error);
  border-color: var(--status-error);
  background: rgba(179, 65, 58, 0.06);
}

.mk-variant-report b {
  color: var(--status-running);
  font-size: 11.5px;
}

/* insight actions merged into card-actions */

/* ===== Empty ===== */
.mk-empty {
  padding: 40px;
  text-align: center;
  color: var(--muted);
  background: var(--paper);
  border-radius: var(--radius-md);
  border: 1px dashed var(--neutral-200);
}

.mk-empty p {
  margin: 8px 0 0;
  font-size: 12.5px;
}

/* ===== Pagination ===== */
.mk-pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: auto;
  padding: 22px 4px 4px;
  flex-wrap: wrap;
  gap: 10px;
  border-top: var(--border-soft);
}

.mk-course-tag {
  padding: 1px 7px;
  border-radius: 4px;
  background: #eef5f2;
  color: #2f7959;
  font-size: 10.5px;
  font-weight: 600;
}

.mk-pagination-info {
  font-size: 12.5px;
  color: var(--muted);
}

.mk-pagination-controls {
  display: flex;
  gap: 4px;
}

.mk-page-btn {
  min-width: 32px;
  height: 32px;
  padding: 0 8px;
  border-radius: 6px;
  border: var(--border-soft);
  background: var(--paper);
  font-size: 12.5px;
  color: var(--neutral-700);
  cursor: pointer;
}

.mk-page-btn:hover:not(:disabled) {
  border-color: var(--orange-300);
  color: var(--orange-600);
}

.mk-page-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.mk-page-btn.active {
  background: var(--orange-500);
  border-color: var(--orange-500);
  color: #fff;
}

.mk-page-dots {
  padding: 0 4px;
  color: var(--muted);
}

.mk-page-size {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12.5px;
  color: var(--neutral-700);
  cursor: pointer;
}

/* ===== Aside Cards ===== */
.mk-aside-card {
  background: var(--paper);
  border: var(--border-soft);
  border-radius: var(--radius-md);
  padding: 14px 14px 12px;
  box-shadow: var(--shadow-1);
}

.mk-aside-title {
  margin: 0 0 12px;
  font-size: 13.5px;
  font-weight: 600;
  color: var(--ink);
  display: flex;
  align-items: center;
  gap: 6px;
  font-family: var(--serif);
}

.mk-aside-more {
  margin-left: auto;
  font-size: 11.5px;
  color: var(--orange-600);
  font-weight: 400;
  cursor: pointer;
}

/* Overview */
.mk-overview-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.mk-overview-item {
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px solid;
}

.mk-overview-item.orange-soft {
  background: var(--orange-50);
  border-color: var(--orange-100);
}

.mk-overview-item.queue-soft {
  background: rgba(216, 146, 41, 0.10);
  border-color: rgba(216, 146, 41, 0.25);
}

.mk-overview-item.green-soft {
  background: rgba(47, 159, 107, 0.08);
  border-color: rgba(47, 159, 107, 0.22);
}

.mk-overview-item.info-soft {
  background: rgba(74, 107, 133, 0.08);
  border-color: rgba(74, 107, 133, 0.22);
}

.mk-overview-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 11.5px;
  color: var(--neutral-700);
  margin-bottom: 4px;
}

.mk-overview-icon {
  width: 22px;
  height: 22px;
  border-radius: 6px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.mk-overview-icon.orange {
  background: var(--orange-100);
  color: var(--orange-600);
}

.mk-overview-icon.queue {
  background: rgba(216, 146, 41, 0.22);
  color: var(--status-queue);
}

.mk-overview-icon.green {
  background: rgba(47, 159, 107, 0.18);
  color: var(--status-running);
}

.mk-overview-icon.info {
  background: rgba(74, 107, 133, 0.18);
  color: var(--status-info);
}

.mk-overview-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--ink);
  line-height: 1;
  font-family: var(--serif);
}

/* Distribution */
.mk-distribution {
  display: flex;
  align-items: center;
  gap: 12px;
}

.mk-donut {
  width: 90px;
  height: 90px;
  flex-shrink: 0;
}

.mk-donut svg {
  width: 100%;
  height: 100%;
}

.mk-distribution-list {
  flex: 1;
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.mk-distribution-list li {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11.5px;
}

.mk-dot-color {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.mk-dist-name {
  flex: 1;
  color: var(--neutral-700);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.mk-dist-count {
  color: var(--ink);
  font-weight: 600;
}

.mk-dist-count em {
  font-style: normal;
  color: var(--muted);
  font-weight: 400;
}

/* Reminder */
.mk-reminder-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.mk-reminder-list li {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12.5px;
}

.mk-remind-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.mk-remind-dot.red {
  background: var(--status-error);
}

.mk-remind-dot.yellow {
  background: var(--status-queue);
}

.mk-remind-dot.green {
  background: var(--status-running);
}

.mk-remind-label {
  flex: 1;
  color: var(--neutral-700);
}

.mk-remind-count {
  font-size: 16px;
  font-weight: 700;
  color: var(--ink);
  font-family: var(--serif);
}

.mk-remind-count small {
  font-size: 11px;
  font-weight: 400;
  color: var(--muted);
  margin-left: 2px;
}

.mk-start-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  width: 100%;
  margin-top: 12px;
  padding: 9px;
  border: none;
  border-radius: var(--radius-sm);
  background: linear-gradient(90deg, var(--orange-500), var(--orange-400));
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(234, 90, 26, 0.28);
}

.mk-start-btn:hover {
  filter: brightness(1.05);
}

/* AI Card */
.mk-ai-card {
  background: linear-gradient(135deg, var(--orange-50) 0%, #fef6ec 100%);
  border-color: var(--orange-100);
}

.mk-ai-content p {
  margin: 0;
  font-size: 12px;
  color: var(--neutral-700);
  line-height: 1.6;
}

.mk-ai-source {
  margin-left: auto;
  padding: 1px 7px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 600;
  background: var(--orange-100);
  color: var(--orange-700);
}

.mk-ai-source.llm {
  background: linear-gradient(90deg, var(--orange-500), var(--orange-400));
  color: #fff;
}

.mk-ai-summary {
  margin: 0 0 8px;
  font-size: 12px;
  color: var(--neutral-700);
  line-height: 1.6;
}

.mk-ai-section {
  margin-top: 8px;
}

.mk-ai-section b {
  font-size: 11.5px;
  color: var(--orange-600);
  display: block;
  margin-bottom: 4px;
}

.mk-ai-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.mk-ai-list li {
  font-size: 11.5px;
  color: var(--neutral-700);
  line-height: 1.5;
  padding-left: 10px;
  position: relative;
}

.mk-ai-list li::before {
  content: "·";
  position: absolute;
  left: 0;
  color: var(--orange-500);
  font-weight: 700;
}

.mk-ai-kp {
  font-weight: 600;
  color: var(--ink);
}

.mk-ai-kp-count {
  margin-left: 6px;
  font-size: 10.5px;
  color: var(--muted);
}

.mk-ai-refresh {
  margin-top: 10px;
  width: 100%;
  padding: 6px;
  border: 1px solid var(--orange-200);
  border-radius: 6px;
  background: var(--paper);
  color: var(--orange-600);
  font-size: 11.5px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  transition: all 0.15s;
}

.mk-ai-refresh:hover {
  background: var(--orange-50);
}

.mk-ai-refresh:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Recent */
.mk-recent-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 9px;
}

.mk-recent-list li {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.mk-recent-title {
  flex: 1;
  color: var(--ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.mk-recent-time {
  color: var(--muted);
  font-size: 11px;
  flex-shrink: 0;
}

/* ===== Responsive ===== */
@media (max-width: 1280px) {
  .mk-main {
    grid-template-columns: 1fr 260px;
  }

  .mk-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 980px) {
  .mk-main {
    grid-template-columns: 1fr;
  }

  .mk-aside {
    position: static;
  }

  .mk-grid {
    grid-template-columns: 1fr;
  }

  .mk-hero {
    flex-direction: column;
    align-items: flex-start;
  }

  .mk-hero-text,
  .mk-hero-diagnosis {
    width: 100%;
    min-width: 0;
  }

  .mk-hero-ai-grid {
    grid-template-columns: 1fr;
  }
}

/* ============================================================
 * teacher-skin 页级修正（配色由全局皮肤接管，这里只调排版）
 * ============================================================ */
.mistakes-page-redesign.teacher-skin {
  max-width: none;
  padding: 0 0 40px;
}
.mistakes-page-redesign.teacher-skin .mk-title {
  font-family: "Source Han Serif SC", "Noto Serif SC", "Songti SC", Georgia, serif;
  font-size: 32px;
  font-weight: 600;
  letter-spacing: -0.01em;
  color: #181612;
}
</style>
