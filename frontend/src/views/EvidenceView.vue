<script setup lang="ts">
/**
 * EvidenceView — AI 学习工具箱
 *
 * 面向学生的实用学习工具集（10 项）：
 *   1. 题目认知层级分析器（Bloom 分类）
 *   2. 知识点验证助手（CoV 防幻觉核验）
 *   3. 学习质量保障面板（教学安全 + 论断溯源）
 *   4. 智能辅导引擎
 *   5. 间隔复习计划器（SM2 + BKT 融合优先级）
 *   6. 下一题智能推荐（Active Learning）
 *   7. 反事实推演器（不同练习强度对比）
 *   8. 反向学习规划（目标倒推每日练习量）
 *   9. 每日签到 + 成就系统
 *  10. 学习同伴推荐
 */
import { computed, onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import {
  ArrowRight,
  Award,
  BookMarked,
  Brain,
  Calendar,
  Activity,
  CheckCircle2,
  ClipboardCheck,
  Flame,
  FlaskConical,
  Layers,
  Image as ImageIcon,
  Tags,
  Newspaper,
  Loader2,
  Play,
  RotateCcw,
  ShieldCheck,
  Sparkles,
  Target,
  ThumbsUp,
  TrendingUp,
  Users,
  XCircle,
  Zap,
} from "lucide-vue-next";

import ProgressRing from "@/components/companion/ProgressRing.vue";
import { useSession } from "@/composables/useSession";
import { getBloomDetail, type BloomDetail } from "@/api/cognitive";
import { fetchCockpit } from "@/api/cockpit";
import { chatWithCov, getCovDemoCases, type CovResult } from "@/api/chat";
import { analyzeLearningImage, askSmartTutor, getSmartTutorRecords, type ImageAnalysisResult, type SmartTutorResponse, type SmartTutorRecord } from "@/api/smartTutor";
import {
  fetchDailyReview,
  submitReview,
  type SpacedItem,
  type SpacedStats,
} from "@/api/spacedRepetition";
import { nextBestQuestion, getCounterfactual, reversePlan, type NextBestQuestionResult, type CounterfactualResponse, type ReversePlanResponse } from "@/api/cognitive";
import { getGamification, dailyCheckin, type GamificationProfile } from "@/api/gamification";
import { getPeerSuggestions, getTutorSuggestions, type SocialSuggestionsResponse } from "@/api/social";
import { getLearnerState, type LearnerStateSnapshot } from "@/api/learner_state";
import { getRecommendations, type RecommendationsResponse } from "@/api/insights";
import { searchKnowledgeGraph } from "@/api/knowledgeGraph";

const { userId, course } = useSession();
const route = useRoute();

// ============================================================
// 工具箱框架 v2：注册表 + 目录 + 单工具工作区（业务逻辑零改动）
// ============================================================
type ToolId =
  | "image"
  | "tags"
  | "state"
  | "bloom"
  | "cov"
  | "quality"
  | "tutor"
  | "review"
  | "recommend"
  | "nbq"
  | "cf"
  | "rp"
  | "checkin"
  | "peers";

interface ToolMeta {
  id: ToolId;
  name: string;
  desc: string;
  hint: string;
  icon: typeof Brain;
  category: string;
}

const TOOL_REGISTRY: ToolMeta[] = [
  { id: "image", name: "图片认知与解析", desc: "OCR 题目、公式与知识点", hint: "上传题目截图或教材页面，系统会识别文字、公式、知识点和认知层级。", icon: ImageIcon, category: "诊断与核验" },
  { id: "tags", name: "知识点标签助手", desc: "匹配课程知识点与先修关系", hint: "输入题目或学习内容，从当前知识图谱中匹配标签、课程与关联知识。", icon: Tags, category: "诊断与核验" },
  { id: "state", name: "学习状态监测", desc: "掌握、错题、复习与任务状态", hint: "汇总真实学习状态，查看当前风险、复习压力和下一步建议。", icon: Activity, category: "诊断与核验" },
  { id: "bloom", name: "题目认知层级分析器", desc: "判断题目考查的认知深度", hint: "基于 Bloom 分类法分析题目层级，输入题目文本即可开始（已预填一个示例）。", icon: ClipboardCheck, category: "诊断与核验" },
  { id: "cov", name: "知识点验证助手", desc: "CoV 多维核验，防幻觉", hint: "输入一个学术说法，五个维度核验其可靠性；下方示例用例可直接点击体验。", icon: ShieldCheck, category: "诊断与核验" },
  { id: "quality", name: "学习质量保障", desc: "论断溯源与教学安全", hint: "查看 AI 讲解的论断支撑率与脚手架引导度，数据来自你的真实学习记录。", icon: BookMarked, category: "诊断与核验" },
  { id: "tutor", name: "智能辅导引擎", desc: "多 Agent 协同答疑", hint: "输入学习问题，多个 Agent 协同生成讲解、图示与练习；最近记录可一键复用。", icon: Brain, category: "诊断与核验" },
  { id: "review", name: "间隔复习计划器", desc: "SM2 + BKT 的今日复习队列", hint: "按遗忘曲线与掌握度融合排序，告诉你今天最该先复习什么。", icon: Calendar, category: "复习与推荐" },
  { id: "recommend", name: "下一篇智能推荐", desc: "推荐下一知识点与学习资源", hint: "根据当前课程、薄弱点和资源库，推荐接下来最值得学习的内容。", icon: Newspaper, category: "复习与推荐" },
  { id: "nbq", name: "下一题智能推荐", desc: "选最有信息量的题", hint: "Active Learning 策略：推荐模型最不确定的题目，让每道题的学习收益最大。", icon: Target, category: "复习与推荐" },
  { id: "cf", name: "反事实推演器", desc: "对比不同练习强度的收益", hint: "通过反向假设推演：如果每天多练一点，30 天后掌握度会怎样？帮你量化选择。", icon: TrendingUp, category: "复习与推荐" },
  { id: "rp", name: "反向学习规划", desc: "从目标倒推每日练习量", hint: "设定目标掌握度和期限，用 BKT 前向模拟倒推最小每日练习强度。", icon: Zap, category: "目标与成长" },
  { id: "checkin", name: "每日签到与成就", desc: "打卡、经验值与成就", hint: "每日签到累计经验，连续打卡有额外奖励；成就随学习行为解锁。", icon: Award, category: "目标与成长" },
  { id: "peers", name: "学习同伴推荐", desc: "画像互补找伙伴和导师", hint: "基于画像互补度与行为协同推荐学习伙伴，所有推荐需双方同意后生效。", icon: Users, category: "协作关系" },
];

const TOOL_CATEGORIES = ["诊断与核验", "复习与推荐", "目标与成长", "协作关系"];
const RECENT_TOOLS_KEY = "tripleu.toolbox.recent";

function readRecentTools(): ToolId[] {
  try {
    const raw = JSON.parse(localStorage.getItem(RECENT_TOOLS_KEY) || "[]") as string[];
    return raw.filter((id): id is ToolId => TOOL_REGISTRY.some((tool) => tool.id === id));
  } catch {
    return [];
  }
}

const recentToolIds = ref<ToolId[]>(readRecentTools());
const activeTool = ref<ToolId>(recentToolIds.value[0] ?? "review");
const toolSearch = ref("");

const activeMeta = computed(
  () => TOOL_REGISTRY.find((tool) => tool.id === activeTool.value) ?? TOOL_REGISTRY[0],
);

const catalogGroups = computed(() => {
  const keyword = toolSearch.value.trim().toLowerCase();
  const pool = keyword
    ? TOOL_REGISTRY.filter((tool) => `${tool.name} ${tool.desc} ${tool.category}`.toLowerCase().includes(keyword))
    : TOOL_REGISTRY;
  return TOOL_CATEGORIES.map((category) => ({
    category,
    tools: pool.filter((tool) => tool.category === category),
  })).filter((group) => group.tools.length);
});

/** 快捷入口：最近使用优先，不足 3 个用推荐工具补齐 */
const quickTools = computed(() => {
  const picked: ToolMeta[] = [];
  for (const id of recentToolIds.value) {
    const meta = TOOL_REGISTRY.find((tool) => tool.id === id);
    if (meta && !picked.includes(meta)) picked.push(meta);
    if (picked.length >= 3) break;
  }
  for (const id of ["review", "recommend", "tutor"] as ToolId[]) {
    if (picked.length >= 3) break;
    const meta = TOOL_REGISTRY.find((tool) => tool.id === id)!;
    if (!picked.includes(meta)) picked.push(meta);
  }
  return picked.map((meta) => ({
    ...meta,
    reason: recentToolIds.value.includes(meta.id) ? "最近使用" : "为你推荐",
  }));
});

function openTool(id: ToolId) {
  activeTool.value = id;
  recentToolIds.value = [id, ...recentToolIds.value.filter((item) => item !== id)].slice(0, 6);
  try {
    localStorage.setItem(RECENT_TOOLS_KEY, JSON.stringify(recentToolIds.value));
  } catch {
    /* 忽略持久化失败 */
  }
  // 打开即加载：复习队列 / 同伴推荐等按需拉取真实数据
  if (id === "review" && !reviewItems.value.length && !reviewLoading.value) void loadReviewQueue();
  if (id === "peers" && !peerData.value && !peerLoading.value) void loadSocialSuggestions();
  if (id === "state" && !learnerState.value && !stateLoading.value) void loadLearnerState();
  if (id === "recommend" && !nextRecommendation.value && !recommendLoading.value) void loadNextRecommendation();
  if (id === "nbq" && !nbqResult.value && !nbqLoading.value) void runNextBestQuestion();
  if (id === "cf" && !cfResult.value && !cfLoading.value) void runCounterfactual();
  if (id === "quality" && !qualityLoading.value) void loadQuality();
  if (id === "checkin" && !gamifyData.value) void loadGamification();
}

// ============================================================
// 图片解析 / 知识标签 / 学习状态 / 下一篇推荐
// ============================================================
const imageFile = ref<File | null>(null);
const imagePreview = ref("");
const imageResult = ref<ImageAnalysisResult | null>(null);
const imageLoading = ref(false);
const imageError = ref("");

function chooseImage(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0] || null;
  imageFile.value = file;
  imageResult.value = null;
  imageError.value = "";
  if (imagePreview.value) URL.revokeObjectURL(imagePreview.value);
  imagePreview.value = file ? URL.createObjectURL(file) : "";
}

async function runImageAnalysis() {
  if (!imageFile.value || imageLoading.value) return;
  imageLoading.value = true;
  imageError.value = "";
  try {
    imageResult.value = await analyzeLearningImage(imageFile.value);
    if (imageResult.value.error) imageError.value = imageResult.value.error;
  } catch (error: any) {
    imageResult.value = null;
    imageError.value = error?.detail ?? error?.message ?? "图片解析失败";
  }
  imageLoading.value = false;
}

const tagInput = ref("");
const tagLoading = ref(false);
const tagResults = ref<Array<Record<string, any>>>([]);
const tagError = ref("");

async function runTagAssistant() {
  const text = tagInput.value.trim();
  if (!text || tagLoading.value) return;
  tagLoading.value = true;
  tagError.value = "";
  try {
    const result = await searchKnowledgeGraph(text, 8);
    tagResults.value = result.results || [];
    if (!tagResults.value.length) tagError.value = "当前课程图谱中没有找到匹配知识点。";
  } catch (error: any) {
    tagResults.value = [];
    tagError.value = error?.detail ?? error?.message ?? "标签匹配失败";
  }
  tagLoading.value = false;
}

const learnerState = ref<LearnerStateSnapshot | null>(null);
const stateLoading = ref(false);
const stateError = ref("");
async function loadLearnerState() {
  stateLoading.value = true;
  stateError.value = "";
  try {
    learnerState.value = await getLearnerState(userId.value);
  } catch (error: any) {
    learnerState.value = null;
    stateError.value = error?.detail ?? error?.message ?? "学习状态加载失败";
  }
  stateLoading.value = false;
}

const nextRecommendation = ref<RecommendationsResponse | null>(null);
const recommendLoading = ref(false);
const recommendError = ref("");
async function loadNextRecommendation() {
  recommendLoading.value = true;
  recommendError.value = "";
  try {
    nextRecommendation.value = await getRecommendations(userId.value, 6, course.value);
  } catch (error: any) {
    nextRecommendation.value = null;
    recommendError.value = error?.detail ?? error?.message ?? "推荐生成失败";
  }
  recommendLoading.value = false;
}

// ============================================================
// 工具 1：题目认知层级分析器
// ============================================================
const bloomInput = ref("设计一个实验对比 K-Means 与 DBSCAN 的聚类效果");
const bloomResult = ref<BloomDetail | null>(null);
const bloomLoading = ref(false);
const bloomError = ref("");

const BLOOM_COLORS: Record<string, string> = {
  remember: "#6b7280",
  understand: "#0ea5e9",
  apply: "#2f9f6b",
  analyze: "#d89229",
  evaluate: "#dc2626",
  create: "#7c3aed",
};

async function runBloom() {
  const text = bloomInput.value.trim();
  if (!text || bloomLoading.value) return;
  bloomLoading.value = true;
  bloomError.value = "";
  try {
    bloomResult.value = await getBloomDetail(text);
  } catch (error: any) {
    bloomResult.value = null;
    bloomError.value = error?.detail ?? error?.message ?? "认知层级分析失败，请重试。";
  }
  bloomLoading.value = false;
}

// ============================================================
// 工具 2：知识点验证助手
// ============================================================
const covText = ref("");
const covResult = ref<CovResult | null>(null);
const covLoading = ref(false);
const covError = ref("");
const demoCases = ref<Array<Record<string, any>>>([]);

const AXIS_LABELS: Record<string, string> = {
  factual: "事实正确性",
  pedagogical: "教学法合理性",
  bloom: "难度适配",
  citation: "引用完整性",
  safety: "答案安全性",
  difficulty: "难度适配",
};

type AxisState = "pass" | "uncertain" | "fail";

function axisState(axis: Record<string, any>): AxisState {
  const v = String(axis.verdict ?? "").toLowerCase();
  if (["pass", "ok", "verified", "supported", "safe"].includes(v)) return "pass";
  if (["fail", "reject", "unsafe", "error"].includes(v)) return "fail";
  if (typeof axis.passed === "boolean") return axis.passed ? "pass" : "fail";
  return "uncertain";
}

const covAxes = computed(() => covResult.value?.axes ?? covResult.value?.results ?? []);

/** 后端 summary 是 dict（{total_axes, verified, uncertain, refuted, risk_rate}），格式化为可读字符串 */
interface CovSummaryMetrics {
  total_axes?: number;
  verified?: number;
  uncertain?: number;
  refuted?: number;
  risk_rate?: number;
}

const covSummaryText = computed(() => {
  const s = covResult.value?.summary as string | CovSummaryMetrics | undefined;
  if (!s) return "";
  if (typeof s === "string") return s;
  const parts: string[] = [];
  if (s.total_axes != null) parts.push(`共 ${s.total_axes} 个维度`);
  if (s.verified != null) parts.push(`通过 ${s.verified}`);
  if (s.uncertain != null) parts.push(`待定 ${s.uncertain}`);
  if (s.refuted != null) parts.push(`不通过 ${s.refuted}`);
  if (s.risk_rate != null) parts.push(`风险率 ${Math.round(s.risk_rate * 100)}%`);
  return parts.join(" · ");
});

async function runCov(text?: string) {
  const t = (text ?? covText.value).trim();
  if (!t || covLoading.value) return;
  covText.value = t;
  covLoading.value = true;
  covResult.value = null;
  covError.value = "";
  try {
    covResult.value = await chatWithCov(t);
  } catch (error: any) {
    covResult.value = null;
    covError.value = error?.detail ?? error?.message ?? "知识点核验失败，请重试。";
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

// ============================================================
// 工具 3：学习质量保障面板
// ============================================================
const qualityLoading = ref(true);
const supportRate = ref(0);
const supportedClaims = ref(0);
const totalClaims = ref(0);
const scaffoldScore = ref(0);
const overallRisk = ref(0);
const qualityError = ref("");
const qualityHasData = computed(() => totalClaims.value > 0 || scaffoldScore.value > 0 || overallRisk.value > 0);

async function loadQuality() {
  qualityLoading.value = true;
  qualityError.value = "";
  try {
    const data: any = await fetchCockpit(userId.value);
    supportRate.value = Math.round((data?.ledger?.support_rate ?? 0) * 100);
    supportedClaims.value = data?.ledger?.supported_claims ?? 0;
    totalClaims.value = data?.ledger?.total_claims ?? 0;
    scaffoldScore.value = Math.round((data?.safety?.scaffolding_score ?? 0) * 100);
    overallRisk.value = Math.round((data?.safety?.overall_risk ?? 0) * 100);
  } catch (error: any) {
    qualityError.value = error?.detail ?? error?.message ?? "质量数据加载失败，请重试。";
  }
  qualityLoading.value = false;
}

// ============================================================
// 工具 4：更多学习工具导航
// ============================================================
interface ToolNav {
  icon: typeof Brain;
  title: string;
  desc: string;
  to: string;
  color: string;
}

const toolNavs: ToolNav[] = [
  { icon: FlaskConical, title: "错题归因分析", desc: "8 类归因 + 分层变式 + 间隔复习", to: "/mistakes", color: "#dc2626" },
  { icon: Layers, title: "知识图谱探索", desc: "查看课程聚类、掌握状态与知识关系", to: "/graph", color: "#7c3aed" },
  { icon: Activity, title: "完整学习画像", desc: "掌握变化、学习行为与个性化建议", to: "/profile", color: "#059669" },
];

// ============================================================
// 工具 6：间隔复习计划器
// ============================================================
const reviewItems = ref<SpacedItem[]>([]);
const reviewStats = ref<SpacedStats | null>(null);
const reviewLoading = ref(false);
const reviewQuality = ref<Record<string, number>>({}); // item_id → quality

async function loadReviewQueue() {
  reviewLoading.value = true;
  try {
    const data = await fetchDailyReview(userId.value, 10);
    reviewItems.value = data.items ?? [];
    reviewStats.value = data.stats ?? null;
  } catch {
    reviewItems.value = [];
    reviewStats.value = null;
  }
  reviewLoading.value = false;
}

async function doReview(itemId: string) {
  const quality = reviewQuality.value[itemId] ?? 3;
  try {
    await submitReview({ user_id: userId.value, item_id: itemId, quality });
    reviewItems.value = reviewItems.value.filter((i) => i.item_id !== itemId);
  } catch {
    // ignore
  }
}

// ============================================================
// 工具 7：下一题智能推荐
// ============================================================
const nbqLoading = ref(false);
const nbqResult = ref<NextBestQuestionResult | null>(null);
const nbqKp = ref("");
const nbqError = ref("");

async function runNextBestQuestion() {
  nbqLoading.value = true;
  nbqResult.value = null;
  nbqError.value = "";
  try {
    nbqResult.value = await nextBestQuestion({
      user_id: userId.value,
      kp_id: nbqKp.value.trim() || undefined,
      top_k: 5,
      strategy: "entropy",
    });
    if (nbqResult.value.error) nbqError.value = nbqResult.value.error;
  } catch (error: any) {
    nbqResult.value = null;
    nbqError.value = error?.detail ?? error?.message ?? "题目推荐失败，请重试。";
  }
  nbqLoading.value = false;
}

const nbqQuestions = computed(() => {
  const raw = nbqResult.value?.questions ?? nbqResult.value?.recommendations ?? [];
  // 后端 recommendation 中 question 是对象（题库原题），展平为可显示结构
  return raw.map((item: any) => {
    const qObj = item.question;
    const isObj = qObj && typeof qObj === "object";
    return {
      ...item,
      // question 文本：优先从嵌套对象取 stem/text/title/question_text
      question: isObj
        ? qObj.stem ?? qObj.text ?? qObj.title ?? qObj.question_text ?? JSON.stringify(qObj).slice(0, 120)
        : item.question ?? item.stem ?? item.text,
      kp_id: item.kp_id ?? (isObj ? qObj.kp_id : undefined) ?? "",
      bloom_level: item.bloom ?? item.bloom_level ?? (isObj ? qObj.bloom : undefined) ?? "",
      uncertainty: item.score ?? item.uncertainty ?? item.p_correct,
      reason: item.reason ?? `${item.score ?? "?"} 不确定度`,
    };
  });
})

// ============================================================
// 工具 8：反事实推演器
// ============================================================
const cfLoading = ref(false);
const cfResult = ref<CounterfactualResponse | null>(null);
const cfError = ref("");

async function runCounterfactual() {
  cfLoading.value = true;
  cfResult.value = null;
  cfError.value = "";
  try {
    cfResult.value = await getCounterfactual(userId.value, "", 30);
    if ((cfResult.value as any).error) cfError.value = String((cfResult.value as any).error);
    else if (!(cfResult.value.scenarios?.length)) cfError.value = String((cfResult.value as any).note || "暂无可推演的掌握度数据。");
  } catch (error: any) {
    cfResult.value = null;
    cfError.value = error?.detail ?? error?.message ?? "反事实推演失败，请重试。";
  }
  cfLoading.value = false;
}

const cfScenarios = computed(() => (cfResult.value?.scenarios ?? []).map((scenario) => ({
  dailyRate: Number(scenario.daily_practice_rate ?? scenario.daily_rate ?? 0),
  finalMastery: Number(scenario.final_mastery ?? 0),
})));

// ============================================================
// 工具 9：反向学习规划
// ============================================================
const rpLoading = ref(false);
const rpResult = ref<ReversePlanResponse | null>(null);
const rpCurrent = ref(0.3);
const rpTarget = ref(0.8);
const rpDays = ref(30);
const rpError = ref("");

async function runReversePlan() {
  rpLoading.value = true;
  rpResult.value = null;
  rpError.value = "";
  try {
    rpResult.value = await reversePlan({
      current_mastery: rpCurrent.value,
      target_mastery: rpTarget.value,
      horizon_days: rpDays.value,
    });
  } catch (error: any) {
    rpResult.value = null;
    rpError.value = error?.detail ?? error?.message ?? "计划计算失败，请重试。";
  }
  rpLoading.value = false;
}

// ============================================================
// 工具 10：每日签到 + 成就
// ============================================================
const gamifyData = ref<GamificationProfile | null>(null);
const checkinLoading = ref(false);
const checkinResult = ref<{ status?: "checked_in" | "already_checked_in"; streak_days: number; bonus_xp: number; total_xp: number; level: number } | null>(null);
const checkinError = ref("");

async function loadGamification() {
  try {
    gamifyData.value = await getGamification(userId.value);
  } catch {
    gamifyData.value = null;
  }
}

async function doCheckin() {
  checkinLoading.value = true;
  checkinError.value = "";
  try {
    checkinResult.value = await dailyCheckin(userId.value);
    await loadGamification();
    // 通知 AppShell / 其它监听者刷新等级显示，防止顶栏 Lv.4 而工具箱 Lv.5
    window.dispatchEvent(new CustomEvent("gamify:refresh", { detail: { userId: userId.value } }));
  } catch (error: any) {
    checkinResult.value = null;
    checkinError.value = error?.detail ?? error?.message ?? "签到失败，请重试。";
  }
  checkinLoading.value = false;
}

// ============================================================
// 工具 11：学习同伴推荐
// ============================================================
const peerLoading = ref(false);
const peerData = ref<SocialSuggestionsResponse | null>(null);
const tutorData = ref<SocialSuggestionsResponse | null>(null);
const peerError = ref("");

async function loadSocialSuggestions() {
  peerLoading.value = true;
  peerError.value = "";
  try {
    const [peers, tutors] = await Promise.all([
      getPeerSuggestions(userId.value, 5),
      getTutorSuggestions(userId.value, 3),
    ]);
    peerData.value = peers;
    tutorData.value = tutors;
  } catch (error: any) {
    peerData.value = null;
    tutorData.value = null;
    peerError.value = error?.detail ?? error?.message ?? "协作推荐加载失败，请重试。";
  }
  peerLoading.value = false;
}

onMounted(() => {
  void loadQuality();
  void loadDemoCases();
  void loadTutorRecords();
  void loadGamification();
  const requestedTool = String(route.query.tool || "") as ToolId;
  if (TOOL_REGISTRY.some((tool) => tool.id === requestedTool)) {
    openTool(requestedTool);
  } else {
    // 默认展开的工具按需预取真实数据
    openTool(activeTool.value);
  }
});

// ============================================================
// 工具 5：智能辅导引擎
// ============================================================
const tutorQuestion = ref("");
const tutorLoading = ref(false);
const tutorResult = ref<SmartTutorResponse | null>(null);
const tutorRecords = ref<SmartTutorRecord[]>([]);

async function askTutor() {
  if (!tutorQuestion.value.trim() || tutorLoading.value) return;
  tutorLoading.value = true;
  tutorResult.value = null;
  try {
    const raw = await askSmartTutor({
      user_id: userId.value,
      question: tutorQuestion.value.trim(),
    });
    // 适配后端返回结构：knowledge_point → kp_id, used_agents → agents_used,
    // outputs.text_answer → answer, outputs.diagram → explanation
    const outputs = (raw as any)?.outputs ?? {};
    tutorResult.value = {
      ...raw,
      kp_id: (raw as any).knowledge_point ?? (raw as any).kp_id,
      agents_used: (raw as any).used_agents ?? (raw as any).agents_used,
      answer: outputs.text_answer ?? (raw as any).answer,
      explanation: outputs.diagram?.code
        ? `流程图（${outputs.diagram.format}）：\n${outputs.diagram.code}`
        : (raw as any).explanation,
      examples: outputs.practice ? [outputs.practice.prompt] : (raw as any).examples,
    } as SmartTutorResponse;
    void loadTutorRecords();
  } catch {
    tutorResult.value = null;
  }
  tutorLoading.value = false;
}

async function loadTutorRecords() {
  try {
    const r = await getSmartTutorRecords(userId.value, 5);
    // 后端记录不含 question 字段，用 knowledge_point 或 question_id 兜底显示
    tutorRecords.value = (r.records ?? []).map((rec: any) => ({
      ...rec,
      question: rec.question ?? rec.knowledge_point ?? rec.question_id ?? "(辅导记录)",
      kp_id: rec.kp_id ?? rec.knowledge_point ?? "",
    }));
  } catch {
    tutorRecords.value = [];
  }
}
</script>

<template>
  <div class="toolbox-v2 teacher-skin">
    <!-- 页面标题：直接放在背景上，不套 Card -->
    <header class="page-heading">
      <div>
        <h1>AI 学习工具箱</h1>
        <p class="lede">使用诊断、规划、复习、推荐与协作工具，从学习问题快速进入下一步行动。</p>
      </div>
    </header>

    <!-- Metadata Bar：真实数据（工具数 / 等级 / 连续天数 / 最近工具） -->
    <div class="meta-bar" aria-label="工具箱上下文">
      <div><small>可用工具</small><b>{{ TOOL_REGISTRY.length }} 个</b></div>
      <div v-if="gamifyData"><small>当前等级</small><b>Lv.{{ gamifyData.level }} · 连续 {{ gamifyData.streak_days }} 天</b></div>
      <div><small>最近工具</small><b>{{ quickTools[0]?.name ?? "—" }}</b></div>
      <div><small>AI Agent</small><b>6 个在线</b></div>
    </div>

    <!-- 快捷入口：最近使用 + 推荐 -->
    <section class="quick-tools" aria-label="最近使用与推荐工具">
      <button
        v-for="tool in quickTools"
        :key="tool.id"
        type="button"
        :class="{ active: activeTool === tool.id }"
        @click="openTool(tool.id)"
      >
        <span class="quick-icon"><component :is="tool.icon" :size="18" /></span>
        <span class="quick-copy">
          <b>{{ tool.name }}</b>
          <small>{{ tool.desc }}</small>
        </span>
        <em :class="{ ai: tool.reason === '为你推荐' }">{{ tool.reason }}</em>
      </button>
    </section>

    <!-- 工作区：左目录 + 右当前工具（同一时间只展开一个工具） -->
    <div class="toolbox-workspace">
      <aside class="tool-catalog" aria-label="工具目录">
        <label class="catalog-search">
          <Sparkles :size="14" />
          <input v-model="toolSearch" placeholder="搜索工具" aria-label="搜索工具" />
        </label>
        <div v-for="group in catalogGroups" :key="group.category" class="catalog-group">
          <small>{{ group.category }}</small>
          <button
            v-for="tool in group.tools"
            :key="tool.id"
            type="button"
            :class="{ active: activeTool === tool.id }"
            @click="openTool(tool.id)"
          >
            <component :is="tool.icon" :size="16" />
            <span><b>{{ tool.name }}</b><small>{{ tool.desc }}</small></span>
          </button>
        </div>
        <p v-if="!catalogGroups.length" class="catalog-empty">没有匹配「{{ toolSearch }}」的工具</p>
      </aside>

      <section class="tool-stage" aria-live="polite">
        <header class="stage-header">
          <span class="stage-icon"><component :is="activeMeta.icon" :size="20" /></span>
          <div>
            <h2>{{ activeMeta.name }}</h2>
            <p>{{ activeMeta.hint }}</p>
          </div>
        </header>

        <!-- 图片认知与解析 -->
        <section v-if="activeTool === 'image'" class="stage-body">
          <div class="image-tool-layout">
            <label class="image-dropzone">
              <input type="file" accept="image/*" @change="chooseImage" />
              <img v-if="imagePreview" :src="imagePreview" alt="待解析图片预览" />
              <template v-else><ImageIcon :size="30" /><strong>上传题目截图或教材页面</strong><span>支持 PNG、JPG、WebP，最大 12MB</span></template>
            </label>
            <div class="tool-input-actions">
              <span>{{ imageFile?.name || '尚未选择图片' }}</span>
              <button class="primary-btn" type="button" :disabled="!imageFile || imageLoading" @click="runImageAnalysis">
                <Loader2 v-if="imageLoading" :size="14" class="spin" /><Play v-else :size="14" />解析图片
              </button>
            </div>
          </div>
          <p v-if="imageError" class="tool-error">{{ imageError }}</p>
          <div v-if="imageResult" class="structured-result">
            <header><div><small>识别结果 · {{ imageResult.ocr_method }}</small><h3>{{ imageResult.title || imageResult.filename }}</h3></div><span>{{ Math.round(imageResult.elapsed_ms) }} ms</span></header>
            <p v-if="imageResult.summary">{{ imageResult.summary }}</p>
            <div v-if="imageResult.topics.length" class="result-tags"><span v-for="topic in imageResult.topics" :key="topic">{{ topic }}</span></div>
            <section v-if="imageResult.blocks.length"><strong>识别内容</strong><p v-for="block in imageResult.blocks.slice(0, 6)" :key="block.id">{{ block.content }}</p></section>
            <section v-if="imageResult.formulas.length"><strong>公式</strong><code v-for="formula in imageResult.formulas" :key="formula">{{ formula }}</code></section>
          </div>
        </section>

        <!-- 知识点标签助手 -->
        <section v-else-if="activeTool === 'tags'" class="stage-body">
          <div class="cov-input">
            <textarea v-model="tagInput" rows="4" placeholder="粘贴题目、笔记或学习内容，匹配课程知识点" />
            <button class="primary-btn" type="button" :disabled="tagLoading || !tagInput.trim()" @click="runTagAssistant">
              <Loader2 v-if="tagLoading" :size="14" class="spin" /><Tags v-else :size="14" />匹配标签
            </button>
          </div>
          <p v-if="tagError" class="tool-error">{{ tagError }}</p>
          <div v-if="tagResults.length" class="tag-result-list">
            <article v-for="(item, index) in tagResults" :key="String(item.id || item.kp_id || item.source || index)">
              <span>{{ String(index + 1).padStart(2, '0') }}</span>
              <div>
                <strong>{{ item.name || item.title_hint || item.label || item.kp_name || item.kp_id || item.id || `召回片段 #${index + 1}` }}</strong>
                <p>{{ item.description || item.content || item.reason || '来自当前课程知识图谱' }}</p>
              </div>
              <div class="result-tags">
                <span v-if="item.course">{{ item.course }}</span>
                <span v-if="item.bloom_level">{{ item.bloom_level }}</span>
                <span v-if="item.score != null">匹配 {{ Math.round(Number(item.score) * 100) }}%</span>
                <span v-if="item.source">出处 {{ item.source }}</span>
              </div>
            </article>
          </div>
        </section>

        <!-- 学习状态监测 -->
        <section v-else-if="activeTool === 'state'" class="stage-body">
          <div class="tool-action-bar"><button class="primary-btn" type="button" :disabled="stateLoading" @click="loadLearnerState"><Loader2 v-if="stateLoading" :size="14" class="spin" /><RotateCcw v-else :size="14" />刷新状态</button></div>
          <p v-if="stateError" class="tool-error">{{ stateError }}</p>
          <div v-if="learnerState" class="state-monitor">
            <dl>
              <div><dt>知识点状态</dt><dd>{{ learnerState.mastery.total }}</dd></div>
              <div><dt>未解决错题</dt><dd>{{ learnerState.mistakes.latest.filter(item => !item.resolved).length }}</dd></div>
              <div><dt>待复习</dt><dd>{{ learnerState.review_schedule.total }}</dd></div>
              <div><dt>可用资源</dt><dd>{{ learnerState.resources.total_resources }}</dd></div>
            </dl>
            <section><span>小狐建议</span><h3>{{ learnerState.recommendation.why || '继续按当前路径完成今日任务' }}</h3><p>重点知识：{{ learnerState.recommendation.focus_kps.map(item => item.kp_id).join('、') || '暂无风险知识点' }}</p></section>
          </div>
          <div v-else-if="!stateLoading && !stateError" class="empty-hint">点击“刷新状态”汇总掌握度、错题、复习与资源数据。</div>
        </section>

        <!-- ===== 工具 1：题目认知层级分析器 ===== -->
        <section v-else-if="activeTool === 'bloom'" class="stage-body">
        <div class="bloom-input">
          <input
            v-model="bloomInput"
            placeholder="输入题目文本"
            @keydown.enter="runBloom"
          />
          <button class="primary-btn" type="button" :disabled="bloomLoading" @click="runBloom">
            <Loader2 v-if="bloomLoading" :size="14" class="spin" />
            <Play v-else :size="14" />分析
          </button>
        </div>
        <p v-if="bloomError" class="tool-error">{{ bloomError }}</p>

        <div v-if="bloomResult" class="bloom-result">
          <div class="bloom-tags">
            <span class="bloom-pill" :style="{ background: BLOOM_COLORS[bloomResult.level] ?? 'var(--orange-500)' }">
              {{ bloomResult.level_label }}
            </span>
            <span class="bloom-pill sub">{{ bloomResult.sub_level_label }}</span>
            <span class="bloom-pill dim">{{ bloomResult.knowledge_dim_label }}知识</span>
          </div>
          <p class="bloom-def">{{ bloomResult.definition }}</p>
          <div v-if="bloomResult.examples?.length" class="bloom-examples">
            <small>同层级典型题目：</small>
            <ul>
              <li v-for="ex in bloomResult.examples.slice(0, 3)" :key="ex">{{ ex }}</li>
            </ul>
          </div>
        </div>
      </section>

        <!-- ===== 工具 2：知识点验证助手 ===== -->
        <section v-else-if="activeTool === 'cov'" class="stage-body">
        <div class="cov-input">
          <textarea
            v-model="covText"
            rows="2"
            placeholder="输入要验证的说法"
          />
          <button class="primary-btn" type="button" :disabled="covLoading || !covText.trim()" @click="runCov()">
            <Loader2 v-if="covLoading" :size="14" class="spin" />验证
          </button>
        </div>
        <p v-if="covError" class="tool-error">{{ covError }}</p>
        <div v-if="demoCases.length" class="demo-pills">
          <button
            v-for="(c, i) in demoCases.slice(0, 4)"
            :key="i"
            type="button"
            @click="runCov(String(c.text ?? c.case_text ?? c.content ?? ''))"
          >
            {{ c.label ?? c.axis ?? c.name ?? `用例 ${i + 1}` }}
          </button>
        </div>

        <div v-if="covResult" class="cov-result">
          <p v-if="covSummaryText" class="cov-summary">{{ covSummaryText }}</p>
          <div v-if="covAxes.length" class="axis-grid">
            <div v-for="(axis, i) in covAxes" :key="i" :class="['axis-card', axisState(axis)]">
              <component :is="axisState(axis) === 'pass' ? CheckCircle2 : XCircle" :size="16" />
              <b>{{ AXIS_LABELS[String(axis.axis ?? '')] ?? axis.label ?? axis.axis ?? `维度 ${i + 1}` }}</b>
              <small>{{ axis.issue ?? axis.detail ?? axis.reason ?? "通过" }}</small>
              <small v-if="axis.correction" class="correction">建议：{{ axis.correction }}</small>
            </div>
          </div>
          <p v-if="(covResult as any).revised_text" class="cov-revised">
            <b>修订建议：</b>{{ (covResult as any).revised_text }}
          </p>
        </div>
      </section>

        <!-- ===== 工具 3：学习质量保障面板 ===== -->
        <section v-else-if="activeTool === 'quality'" class="stage-body">
        <div class="tool-action-bar">
          <button class="primary-btn" type="button" :disabled="qualityLoading" @click="loadQuality">
            <Loader2 v-if="qualityLoading" :size="14" class="spin" /><RotateCcw v-else :size="14" />刷新质量数据
          </button>
        </div>
        <p v-if="qualityError" class="tool-error">{{ qualityError }}</p>
        <div v-if="qualityLoading" class="empty-hint"><Loader2 :size="14" class="spin" /> 正在汇总论断支撑与教学安全数据…</div>
        <div v-else-if="qualityHasData" class="quality-grid">
          <div class="quality-card">
            <ProgressRing :value="supportRate" :label="`${supportRate}%`" />
            <div class="quality-info">
              <strong>论断支撑率</strong>
              <small>{{ supportedClaims }}/{{ totalClaims }} 条讲解有据可查</small>
            </div>
          </div>
          <div class="quality-card">
            <ProgressRing :value="scaffoldScore" :label="`${scaffoldScore}%`" />
            <div class="quality-info">
              <strong>脚手架引导度</strong>
              <small>综合教学风险 {{ overallRisk }}%</small>
            </div>
          </div>
        </div>
        <div v-else-if="!qualityError" class="empty-hint">完成一次 AI 讲解或资源生成后，这里会显示论断支撑率与教学风险。</div>
      </section>

        <!-- ===== 工具 4：智能辅导引擎 ===== -->
        <section v-else-if="activeTool === 'tutor'" class="stage-body">
        <div class="bloom-input">
          <input
            v-model="tutorQuestion"
            placeholder="输入你的学习问题"
            @keydown.enter="askTutor"
          />
          <button class="primary-btn" type="button" :disabled="tutorLoading || !tutorQuestion.trim()" @click="askTutor">
            <Loader2 v-if="tutorLoading" :size="14" class="spin" />
            <Play v-else :size="14" />提问
          </button>
        </div>
        <div v-if="tutorResult" class="tutor-result">
          <div v-if="tutorResult.kp_id" class="tutor-kp">
            <span class="bloom-pill" style="background: #0ea5e9">{{ tutorResult.kp_id }}</span>
          </div>
          <p v-if="tutorResult.answer" class="tutor-answer">{{ tutorResult.answer }}</p>
          <p v-if="tutorResult.explanation" class="tutor-explanation">{{ tutorResult.explanation }}</p>
          <div v-if="tutorResult.examples?.length" class="tutor-examples">
            <small>示例：</small>
            <ul>
              <li v-for="(ex, i) in tutorResult.examples.slice(0, 3)" :key="i">{{ ex }}</li>
            </ul>
          </div>
          <div v-if="tutorResult.agents_used?.length" class="tutor-agents">
            <small>参与 Agent：</small>
            <span v-for="a in tutorResult.agents_used" :key="a" class="agent-tag">{{ a }}</span>
          </div>
        </div>
        <div v-if="tutorRecords.length" class="tutor-history">
          <small>最近辅导记录：</small>
          <div v-for="(r, i) in tutorRecords" :key="i" class="tutor-record-row" @click="tutorQuestion = r.question">
            <span>{{ r.question }}</span>
            <em v-if="r.kp_id">{{ r.kp_id }}</em>
          </div>
        </div>
      </section>

        <!-- 下一篇智能推荐 -->
        <section v-else-if="activeTool === 'recommend'" class="stage-body">
          <div class="tool-action-bar"><button class="primary-btn" type="button" :disabled="recommendLoading" @click="loadNextRecommendation"><Loader2 v-if="recommendLoading" :size="14" class="spin" /><Sparkles v-else :size="14" />生成推荐</button><span>当前课程：{{ course }}</span></div>
          <p v-if="recommendError" class="tool-error">{{ recommendError }}</p>
          <div v-if="nextRecommendation?.items.length" class="recommend-result-list">
            <article v-for="(item, index) in nextRecommendation.items" :key="String(item.resource_id || item.kp_id || index)">
              <span class="recommend-rank">{{ index + 1 }}</span>
              <div><small>{{ item.kind === 'resource' ? '推荐资源' : '推荐知识点' }}</small><h3>{{ item.title || item.topic || item.kp_id }}</h3><p>{{ item.reason }}</p></div>
              <router-link :to="item.kind === 'resource' ? `/resources?q=${encodeURIComponent(String(item.title || item.kp_id))}` : `/graph?kp=${encodeURIComponent(item.kp_id)}`">开始学习<ArrowRight :size="13" /></router-link>
            </article>
          </div>
          <div v-else-if="nextRecommendation && !recommendLoading" class="empty-hint">完成一次学习或练习后会生成下一篇推荐。</div>
        </section>

        <!-- ===== 工具 6：间隔复习计划器 ===== -->
        <section v-else-if="activeTool === 'review'" class="stage-body">
        <div class="tool-action-bar">
          <button class="primary-btn" type="button" :disabled="reviewLoading" @click="loadReviewQueue">
            <Loader2 v-if="reviewLoading" :size="14" class="spin" />
            <RotateCcw v-else :size="14" />刷新复习队列
          </button>
          <span v-if="reviewStats" class="review-stats">
            共 {{ reviewStats.total_items }} 项 · 今日到期 {{ reviewStats.due_today }} 项
          </span>
        </div>
        <div v-if="reviewItems.length" class="review-list">
          <div v-for="item in reviewItems" :key="item.item_id" class="review-item">
            <div class="review-item-head">
              <span class="review-kp">
                <strong>{{ item.knowledge_point?.name ?? item.item_id }}</strong>
                <small>{{ item.item_id }}</small>
              </span>
              <span class="review-priority" :class="item.priority_score && item.priority_score >= 0.6 ? 'high' : 'normal'">
                优先级 {{ Math.round((item.priority_score ?? 0) * 100) }}%
              </span>
            </div>
            <div v-if="item.question?.stem" class="review-question">
              <div class="review-question-label">
                <span>题库练习</span>
                <small>{{ item.question.id }}<template v-if="item.question.bloom"> · {{ item.question.bloom }}</template></small>
              </div>
              <p>{{ item.question.stem }}</p>
              <ol v-if="item.question.options?.length" class="review-options">
                <li v-for="(option, optionIndex) in item.question.options" :key="`${item.question.id}-${optionIndex}`">
                  <span>{{ String.fromCharCode(65 + optionIndex) }}</span>{{ option }}
                </li>
              </ol>
            </div>
            <div v-else class="review-question review-objective">
              <div class="review-question-label"><span>复习目标</span><small>题库暂未覆盖</small></div>
              <p>{{ item.knowledge_point?.description || "围绕该知识点完成概念回顾与自我检测。" }}</p>
            </div>
            <p class="review-reason">{{ item.priority_reason || "按 SM2 调度到期" }}</p>
            <div class="review-meta">
              <span>间隔 {{ item.interval_days }}天</span>
              <span>已复习 {{ item.repetitions }}次</span>
              <span>难度 {{ item.easiness.toFixed(1) }}</span>
            </div>
            <div class="review-quality">
              <small>复习后自评：</small>
              <div class="quality-btns">
                <button v-for="q in [0, 2, 3, 5]" :key="q"
                  :class="['q-btn', reviewQuality[item.item_id] === q ? 'active' : '']"
                  @click="reviewQuality[item.item_id] = q"
                >{{ ["不会", "模糊", "一般", "精通"][[0,2,3,5].indexOf(q)] }}</button>
              </div>
              <button class="primary-btn sm" type="button" @click="doReview(item.item_id)">提交</button>
            </div>
          </div>
        </div>
        <div v-else-if="!reviewLoading" class="empty-hint">暂无到期复习项，去练习新知识吧！</div>
      </section>

        <!-- ===== 工具 7：下一题智能推荐 ===== -->
        <section v-else-if="activeTool === 'nbq'" class="stage-body">
        <div class="bloom-input">
          <input
            v-model="nbqKp"
            placeholder="知识点 ID（可选，如 AI_005），留空则全局推荐"
            @keydown.enter="runNextBestQuestion"
          />
          <button class="primary-btn" type="button" :disabled="nbqLoading" @click="runNextBestQuestion">
            <Loader2 v-if="nbqLoading" :size="14" class="spin" />
            <Play v-else :size="14" />推荐
          </button>
        </div>
        <p v-if="nbqError" class="tool-error">{{ nbqError }}</p>
        <div v-if="nbqQuestions.length" class="nbq-list">
          <div v-for="(q, i) in nbqQuestions" :key="i" class="nbq-card">
            <div class="nbq-head">
              <span class="nbq-idx">#{{ i + 1 }}</span>
              <span v-if="q.kp_id" class="bloom-pill sm" style="background: #0ea5e9">{{ q.kp_id }}</span>
              <span v-if="q.bloom_level" class="bloom-pill sm sub">{{ q.bloom_level }}</span>
              <span v-if="q.uncertainty !== undefined" class="nbq-uncertainty">
                不确定度 {{ Math.round(q.uncertainty * 100) }}%
              </span>
            </div>
            <p class="nbq-text">{{ q.question ?? q.stem ?? q.text ?? JSON.stringify(q).slice(0, 120) }}</p>
            <p v-if="q.reason" class="nbq-reason">{{ q.reason }}</p>
          </div>
        </div>
        <div v-else-if="nbqResult && !nbqQuestions.length && !nbqError" class="empty-hint">当前筛选条件下暂无题目，清空知识点 ID 后可进行全局推荐。</div>
      </section>

        <!-- ===== 工具 8：反事实推演器 ===== -->
        <section v-else-if="activeTool === 'cf'" class="stage-body">
        <button class="primary-btn" type="button" :disabled="cfLoading" @click="runCounterfactual">
          <Loader2 v-if="cfLoading" :size="14" class="spin" />
          <Play v-else :size="14" />开始推演
        </button>
        <p v-if="cfError" class="tool-error">{{ cfError }}</p>
        <div v-if="cfScenarios.length" class="cf-grid">
          <div v-for="sc in cfScenarios" :key="sc.dailyRate" class="cf-card">
            <div class="cf-rate">每日 {{ Math.round(sc.dailyRate * 100) }}%</div>
            <div class="cf-final" :style="{ color: sc.finalMastery >= 0.7 ? '#2f9f6b' : '#d89229' }">
              {{ Math.round(sc.finalMastery * 100) }}%
            </div>
            <small>30天后预测掌握度</small>
          </div>
        </div>
        <p v-if="cfResult?.expected_gain !== undefined" class="cf-gain">
          额外收益：高强度 vs 低强度可多提升
          <strong>{{ Math.round((cfResult.expected_gain ?? 0) * 100) }}%</strong> 掌握度
        </p>
        <p v-if="cfResult?.risk_warning" class="cf-risk">{{ cfResult.risk_warning }}</p>
      </section>

        <!-- ===== 工具 9：反向学习规划 ===== -->
        <section v-else-if="activeTool === 'rp'" class="stage-body">
        <div class="rp-inputs">
          <label>
            当前掌握度
            <input type="range" min="0.1" max="0.9" step="0.05" v-model.number="rpCurrent" />
            <span>{{ Math.round(rpCurrent * 100) }}%</span>
          </label>
          <label>
            目标掌握度
            <input type="range" min="0.5" max="0.95" step="0.05" v-model.number="rpTarget" />
            <span>{{ Math.round(rpTarget * 100) }}%</span>
          </label>
          <label>
            期限（天）
            <input type="range" min="7" max="90" step="1" v-model.number="rpDays" />
            <span>{{ rpDays }} 天</span>
          </label>
        </div>
        <button class="primary-btn" type="button" :disabled="rpLoading" @click="runReversePlan">
          <Loader2 v-if="rpLoading" :size="14" class="spin" />
          <Play v-else :size="14" />计算计划
        </button>
        <p v-if="rpError" class="tool-error">{{ rpError }}</p>
        <div v-if="rpResult" class="rp-result">
          <div class="rp-status" :class="['feasible', 'achievable'].includes(rpResult.status) ? 'ok' : 'warn'">
            {{ ['feasible', 'achievable'].includes(rpResult.status) ? "目标可达" : "目标可能难以达成" }}
          </div>
          <p v-if="rpResult.narrative" class="rp-narrative">{{ rpResult.narrative }}</p>
          <div class="rp-metrics">
            <div class="rp-metric">
              <strong>{{ rpResult.daily_questions ?? "-" }}</strong>
              <small>每日题量</small>
            </div>
            <div class="rp-metric">
              <strong>{{ rpResult.daily_practice_rate ? Math.round(rpResult.daily_practice_rate * 100) + "%" : "-" }}</strong>
              <small>每日练习强度</small>
            </div>
            <div class="rp-metric">
              <strong>{{ Math.round(rpResult.projected_mastery * 100) }}%</strong>
              <small>预测最终掌握度</small>
            </div>
          </div>
          <div v-if="rpResult.milestones?.length" class="rp-milestones">
            <small class="rp-section-title">里程碑</small>
            <div class="rp-milestone-row">
              <div v-for="m in rpResult.milestones" :key="m.label" class="rp-milestone">
                <strong>{{ m.label }}</strong>
                <span>第 {{ m.day }} 天</span>
                <em>{{ Math.round(m.target * 100) }}%</em>
              </div>
            </div>
          </div>
          <div v-if="rpResult.schedule?.length" class="rp-schedule">
            <small class="rp-section-title">进度预测</small>
            <table>
              <thead>
                <tr><th>Day</th><th>掌握度</th><th>累计题量</th></tr>
              </thead>
              <tbody>
                <tr v-for="p in rpResult.schedule" :key="p.day">
                  <td>{{ p.day }}</td>
                  <td>{{ Math.round(p.expected_mastery * 100) }}%</td>
                  <td>{{ p.cumulative_questions }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>

        <!-- ===== 工具 10：每日签到 + 成就 ===== -->
        <section v-else-if="activeTool === 'checkin'" class="stage-body">
        <div class="gamify-grid">
          <div v-if="gamifyData" class="gamify-card">
            <div class="gamify-level">Lv.{{ gamifyData.level }}</div>
            <div class="gamify-xp">
              <div class="xp-bar">
                <div class="xp-fill" :style="{ width: Math.min(100, ((gamifyData.xp % (gamifyData.level * 100)) / Math.max(gamifyData.level * 100, 1)) * 100) + '%' }"></div>
              </div>
              <small>{{ gamifyData.xp }} XP · 距下级 {{ gamifyData.xp_to_next_level }} XP</small>
            </div>
          </div>
          <div v-if="gamifyData" class="gamify-card">
            <div class="gamify-streak">
              <Flame :size="24" />
              <strong>{{ gamifyData.streak_days }}</strong>
              <small>天连续</small>
            </div>
          </div>
          <div v-if="gamifyData" class="gamify-card">
            <div class="gamify-ach">
              <strong>{{ gamifyData.achievements_earned }}/{{ gamifyData.achievements_total }}</strong>
              <small>成就解锁</small>
            </div>
            <div v-if="gamifyData.achievements?.length" class="ach-tags">
              <span v-for="a in gamifyData.achievements" :key="a" class="ach-tag">{{ a }}</span>
            </div>
          </div>
        </div>
        <button class="primary-btn" type="button" :disabled="checkinLoading || gamifyData?.checked_in_today" @click="doCheckin">
          <Loader2 v-if="checkinLoading" :size="14" class="spin" />
          <CheckCircle2 v-else-if="gamifyData?.checked_in_today" :size="14" />
          <Calendar v-else :size="14" />{{ gamifyData?.checked_in_today ? '今日已签到' : '今日签到' }}
        </button>
        <p v-if="checkinError" class="tool-error">{{ checkinError }}</p>
        <div v-if="checkinResult" class="checkin-result">
          <CheckCircle2 :size="16" />
          {{ checkinResult.status === 'already_checked_in' ? '今天已经签到。' : '签到成功！' }}连续 {{ checkinResult.streak_days }} 天
          <span v-if="checkinResult.bonus_xp > 0">· 额外奖励 {{ checkinResult.bonus_xp }} XP</span>
          · 总经验 {{ checkinResult.total_xp }} · 等级 Lv.{{ checkinResult.level }}
        </div>
      </section>

        <!-- ===== 工具 11：学习同伴推荐 ===== -->
        <section v-else-if="activeTool === 'peers'" class="stage-body">
        <button class="primary-btn" type="button" :disabled="peerLoading" @click="loadSocialSuggestions">
          <Loader2 v-if="peerLoading" :size="14" class="spin" />
          <Users v-else :size="14" />获取推荐
        </button>
        <p v-if="peerError" class="tool-error">{{ peerError }}</p>
        <div v-if="peerData?.suggestions?.length || tutorData?.suggestions?.length" class="social-grid">
          <div v-if="peerData?.suggestions?.length" class="social-section">
            <div class="social-title"><Users :size="14" /> 互补学习伙伴</div>
            <div v-for="s in peerData.suggestions" :key="s.user_id ?? s.peer_id ?? JSON.stringify(s)" class="social-card">
              <div class="social-head">
                <span class="social-id">{{ s.display_name ?? s.user_id ?? s.peer_id ?? "匿名" }}</span>
                <span v-if="s.score !== undefined" class="social-score">匹配度 {{ Math.round((s.score ?? 0) * 100) }}%</span>
              </div>
              <p class="social-reason">{{ s.reason ?? s.explanation ?? "画像互补推荐" }}</p>
            </div>
          </div>
          <div v-if="tutorData?.suggestions?.length" class="social-section">
            <div class="social-title"><ThumbsUp :size="14" /> 推荐导师</div>
            <div v-for="s in tutorData.suggestions" :key="s.user_id ?? s.peer_id ?? JSON.stringify(s)" class="social-card">
              <div class="social-head">
                <span class="social-id">{{ s.display_name ?? s.user_id ?? s.peer_id ?? "匿名" }}</span>
                <span v-if="s.score !== undefined" class="social-score">匹配度 {{ Math.round((s.score ?? 0) * 100) }}%</span>
              </div>
              <small v-if="s.role" class="social-role">{{ s.role }}</small>
              <p class="social-reason">{{ s.reason ?? s.explanation ?? "单向导师推荐" }}</p>
            </div>
          </div>
        </div>
        <div v-else-if="(peerData || tutorData) && !peerLoading && !peerError" class="empty-hint">暂未找到合适的协作对象；完善画像或完成更多学习活动后再试。</div>
        <p v-if="peerData?.privacy_note" class="privacy-note">{{ peerData.privacy_note }}</p>
      </section>
      </section>
    </div>

    <!-- 更多 AI 入口：轻量列表，不用大卡片 -->
    <section class="more-tools" aria-label="更多智能功能入口">
      <header class="section-head"><h2>更多入口</h2><p>直达系统内的其他智能功能</p></header>
      <div class="nav-grid">
        <router-link v-for="t in toolNavs" :key="t.title" :to="t.to" class="nav-card" :style="{ '--nav-color': t.color }">
          <div class="nav-icon"><component :is="t.icon" :size="20" /></div>
          <div class="nav-body">
            <strong>{{ t.title }}</strong>
            <p>{{ t.desc }}</p>
          </div>
          <ArrowRight :size="15" class="nav-arrow" />
        </router-link>
      </div>
    </section>
  </div>
</template>

<style scoped>
/* ============================================================
 * 工具箱 v2 · 目录 + 单工具工作区（基准 = 教师端教学概览）
 * ============================================================ */
.toolbox-v2 {
  /* Tokens 对齐《前端提示词/前端教师风格.md》 */
  --tb-bg: #fbfaf7;
  --tb-subtle: #f9f7f3;
  --tb-muted: #f6f4ef;
  --tb-heading: #181612;
  --tb-ink: #24211d;
  --tb-ink2: #68635b;
  --tb-ink3: #918b82;
  --tb-line: #e7e2da;
  --tb-brand: #e85d16;
  --tb-brand-hover: #d75011;
  --tb-brand-container: #fff1e8;
  --tb-brand-border: #f3c5a8;
  --tb-ai: #6757d9;
  --tb-ai-container: #f7f5ff;
  --tb-ai-border: #e4dff8;
  /* 兼容下方工具组件仍在使用的第一版 token 名。此前根节点已改为
     toolbox-v2，但这些变量只定义在不存在的 .toolbox-page 上，导致
     primary-btn 的背景声明失效、白色文字落在白底上，看起来像“没有按钮”。 */
  --tb-ink-2: var(--tb-ink2);
  --tb-faint: var(--tb-ink3);
  --tb-line-strong: #d7d1c7;
  --tb-panel: #fff;
  --tb-panel-2: var(--tb-subtle);
  --tb-accent: var(--tb-brand);
  --tb-accent-deep: var(--tb-brand-hover);
  --tb-accent-ink: #9a3608;
  --tb-accent-soft: var(--tb-brand-container);
  --tb-accent-line: var(--tb-brand-border);
  --tb-ok: #1f8a5b;
  --tb-ok-soft: #eefaf3;
  --tb-ok-line: #c6ecd8;
  --tb-warn: #b97a0a;
  --tb-warn-soft: #fdf7ea;
  --tb-warn-line: #f0dfb4;
  --tb-err: #c93a2e;
  --tb-err-soft: #fdf1ef;
  --tb-err-line: #f3cfc9;
  --tb-info: #0e7490;
  --tb-elev-1: 0 1px 2px rgba(103, 62, 22, 0.05), 0 8px 22px -18px rgba(103, 62, 22, 0.18);
  --tb-elev-2: 0 2px 4px rgba(103, 62, 22, 0.06), 0 16px 32px -20px rgba(103, 62, 22, 0.24);
  --tb-ease: cubic-bezier(0.2, 0, 0, 1);
  --tb-dur: 220ms;
  --tb-r-lg: 20px;
  --tb-r-md: 16px;
  --tb-r-sm: 12px;
  --tb-r-xs: 8px;
  /* 宽度交给壳层统一限制（1540 网格），页面不再自行收窄 */
  width: 100%;
  margin: 0 auto;
  padding: 0 0 40px;
  color: var(--tb-ink);
  font-family: Inter, "PingFang SC", "Microsoft YaHei", "Noto Sans SC", system-ui, sans-serif;
  font-size: 14px;
  line-height: 1.65;
}
.toolbox-v2 .page-heading { padding-bottom: 14px; }
.toolbox-v2 .page-heading h1 {
  margin: 0;
  color: var(--tb-heading);
  font-family: "Source Han Serif SC", "Noto Serif SC", "Songti SC", Georgia, serif;
  font-size: 32px;
  font-weight: 600;
  line-height: 1.2;
  letter-spacing: -0.01em;
}
.toolbox-v2 .lede {
  max-width: 62ch;
  margin: 8px 0 0;
  color: var(--tb-ink2);
  font-size: 14.5px;
  line-height: 1.65;
}
.toolbox-v2 .meta-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 36px;
  min-height: 48px;
  padding: 4px 2px;
  border-top: 1px solid var(--tb-line);
  border-bottom: 1px solid var(--tb-line);
}
.toolbox-v2 .meta-bar > div { display: flex; align-items: baseline; gap: 9px; }
.toolbox-v2 .meta-bar small { color: var(--tb-ink3); font-size: 13px; }
.toolbox-v2 .meta-bar b { font-size: 13.5px; font-weight: 600; font-variant-numeric: tabular-nums; }

/* 快捷入口（规范：Section 间距 24–32px，Card 间 12–16px） */
.toolbox-v2 .quick-tools {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  margin-top: 24px;
}
.toolbox-v2 .quick-tools > button {
  display: grid;
  grid-template-columns: 38px minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
  min-height: 84px;
  padding: 14px 16px;
  border: 1px solid var(--tb-line);
  border-radius: 12px;
  background: #fff;
  text-align: left;
  cursor: pointer;
  transition: transform 180ms cubic-bezier(0.16, 1, 0.3, 1), border-color 170ms ease-out, box-shadow 170ms ease-out;
}
.toolbox-v2 .quick-tools > button:hover {
  transform: translateY(-1px);
  border-color: #d7d1c7;
  box-shadow: 0 8px 24px rgba(35, 31, 25, 0.05);
}
.toolbox-v2 .quick-tools > button.active { border-color: var(--tb-brand-border); background: var(--tb-brand-container); }
.toolbox-v2 .quick-icon {
  display: grid;
  place-items: center;
  width: 38px;
  height: 38px;
  border-radius: 10px;
  background: var(--tb-muted);
  color: var(--tb-ink2);
}
.toolbox-v2 .quick-tools > button.active .quick-icon { background: #fff; color: var(--tb-brand-hover); }
.toolbox-v2 .quick-copy b { display: block; font-size: 14.5px; font-weight: 600; color: var(--tb-ink); }
.toolbox-v2 .quick-copy small { display: block; margin-top: 3px; color: var(--tb-ink3); font-size: 12.5px; }
.toolbox-v2 .quick-tools em {
  padding: 3px 9px;
  border-radius: 999px;
  background: var(--tb-muted);
  color: var(--tb-ink2);
  font-size: 11.5px;
  font-style: normal;
  font-weight: 600;
  white-space: nowrap;
}
.toolbox-v2 .quick-tools em.ai { background: var(--tb-ai-container); border: 1px solid var(--tb-ai-border); color: #5647c8; }

/* 工作区：目录 + 舞台 */
.toolbox-v2 .toolbox-workspace {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  gap: 16px;
  align-items: start;
  margin-top: 28px;
}
.toolbox-v2 .tool-catalog {
  position: sticky;
  top: 16px;
  display: grid;
  gap: 14px;
  padding: 14px;
  border: 1px solid var(--tb-line);
  border-radius: 12px;
  background: #fff;
}
.toolbox-v2 .catalog-search {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 38px;
  padding: 0 11px;
  border: 1px solid var(--tb-line);
  border-radius: 9px;
  background: var(--tb-subtle);
  color: var(--tb-ink3);
}
.toolbox-v2 .catalog-search input { flex: 1; min-width: 0; border: 0; outline: 0; background: transparent; color: var(--tb-ink); font-size: 13px; }
.toolbox-v2 .catalog-group { display: grid; gap: 2px; }
.toolbox-v2 .catalog-group > small {
  margin: 4px 2px;
  color: var(--tb-ink3);
  font-size: 11.5px;
  font-weight: 600;
  letter-spacing: 0.02em;
}
.toolbox-v2 .catalog-group > button {
  display: grid;
  grid-template-columns: 18px minmax(0, 1fr);
  align-items: center;
  gap: 10px;
  min-height: 52px;
  padding: 7px 10px;
  border: 0;
  border-left: 2px solid transparent;
  border-radius: 9px;
  background: transparent;
  color: var(--tb-ink2);
  text-align: left;
  cursor: pointer;
  transition: background 160ms ease-out, color 160ms ease-out;
}
.toolbox-v2 .catalog-group > button:hover { background: #f8f6f2; }
.toolbox-v2 .catalog-group > button.active {
  border-left-color: var(--tb-brand);
  background: var(--tb-brand-container);
  color: var(--tb-brand-hover);
}
.toolbox-v2 .catalog-group > button span b { display: block; font-size: 13px; font-weight: 600; color: var(--tb-ink); }
.toolbox-v2 .catalog-group > button.active span b { color: var(--tb-brand-hover); }
.toolbox-v2 .catalog-group > button span small { display: block; margin-top: 2px; color: var(--tb-ink3); font-size: 11.5px; }
.toolbox-v2 .catalog-empty { margin: 4px 2px; color: var(--tb-ink3); font-size: 12.5px; }

.toolbox-v2 .tool-stage {
  min-height: 480px;
  border: 1px solid var(--tb-line);
  border-radius: 14px;
  background: #fff;
}
.toolbox-v2 .stage-header {
  display: flex;
  align-items: flex-start;
  gap: 13px;
  padding: 20px 24px;
  border-bottom: 1px solid #ece8e1;
}
.toolbox-v2 .stage-icon {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  border-radius: 11px;
  background: var(--tb-brand-container);
  color: var(--tb-brand-hover);
}
.toolbox-v2 .stage-header h2 { margin: 0; color: var(--tb-heading); font-size: 17px; font-weight: 600; }
.toolbox-v2 .stage-header p { margin: 5px 0 0; color: var(--tb-ink2); font-size: 13px; line-height: 1.6; }
.toolbox-v2 .stage-body { padding: 20px 24px 24px; animation: stage-in 220ms ease-out; }
@keyframes stage-in {
  from { opacity: 0; transform: translateX(6px); }
  to { opacity: 1; transform: translateX(0); }
}

/* 更多入口 */
.toolbox-v2 .more-tools { margin-top: 32px; }
.toolbox-v2 .section-head { display: flex; align-items: baseline; gap: 14px; margin-bottom: 14px; }
.toolbox-v2 .section-head h2 { margin: 0; color: var(--tb-heading); font-size: 19px; font-weight: 600; }
.toolbox-v2 .section-head p { margin: 0; color: var(--tb-ink2); font-size: 13px; }

@media (max-width: 1100px) {
  .toolbox-v2 .toolbox-workspace { grid-template-columns: 1fr; }
  .toolbox-v2 .tool-catalog { position: static; }
  .toolbox-v2 .quick-tools { grid-template-columns: 1fr; }
}
@media (max-width: 720px) {
  .toolbox-v2 .page-heading h1 { font-size: 30px; }
  .toolbox-v2 .stage-body, .toolbox-v2 .stage-header { padding-inline: 16px; }
}
@media (prefers-reduced-motion: reduce) {
  .toolbox-v2 *, .toolbox-v2 *::before, .toolbox-v2 *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}

/* ============================================================
 * 学习工具箱 · 设计系统重排（2026-07-11）
 *
 * 规范来源：
 *  - Material Design 3：8dp 间距网格 / 字体角色（Display-Headline-
 *    Title-Body-Label）/ 海拔层级 / 标准缓动 cubic-bezier(.2,0,0,1)
 *  - ui-ux-pro-max 交付清单：可点击元素 cursor-pointer / 焦点态可见 /
 *    文本对比 ≥4.5:1 / 200-300ms 平滑过渡 / prefers-reduced-motion
 *  - 品牌延续：白色主画布 + 暖橙重点强调（--orange-500 #ea5a1a），
 *    对齐错题库的白卡片与暖色 Hero 层级
 * ============================================================ */

.toolbox-page {
  /* ---- Design Tokens ---- */
  --tb-ink: var(--neutral-900);
  --tb-ink-2: var(--neutral-700);
  --tb-muted: var(--neutral-500);
  --tb-faint: var(--neutral-400);
  --tb-line: var(--neutral-200);
  --tb-line-strong: var(--neutral-300);
  --tb-bg: var(--neutral-0);
  --tb-panel: var(--neutral-0);
  --tb-panel-2: var(--neutral-50);
  --tb-accent: var(--orange-500);
  --tb-accent-deep: var(--orange-600);
  --tb-accent-ink: var(--orange-700);
  --tb-accent-soft: var(--orange-50);
  --tb-accent-line: var(--orange-200);
  --tb-ok: #1f8a5b;
  --tb-ok-soft: #eefaf3;
  --tb-ok-line: #c6ecd8;
  --tb-warn: #b97a0a;
  --tb-warn-soft: #fdf7ea;
  --tb-warn-line: #f0dfb4;
  --tb-err: #c93a2e;
  --tb-err-soft: #fdf1ef;
  --tb-err-line: #f3cfc9;
  --tb-info: #0e7490;

  /* 海拔（Material elevation 的柔化版） */
  --tb-elev-1: 0 1px 2px rgba(103, 62, 22, 0.05), 0 8px 22px -18px rgba(103, 62, 22, 0.18);
  --tb-elev-2: 0 2px 4px rgba(103, 62, 22, 0.06), 0 16px 32px -20px rgba(103, 62, 22, 0.24);

  /* 动效 */
  --tb-ease: cubic-bezier(0.2, 0, 0, 1);
  --tb-dur: 220ms;

  /* 形状 */
  --tb-r-lg: 20px;   /* 页级容器 */
  --tb-r-md: 16px;   /* 卡片 */
  --tb-r-sm: 12px;   /* 卡内子面 / 输入框 */
  --tb-r-xs: 8px;

  max-width: 1320px;
  margin: 0 auto;
  padding: 24px 32px 56px;
  background: var(--tb-bg);
  color: var(--tb-ink);
}

/* ============================================================
 * Hero — 毛玻璃信息层 + 柔光晕装饰
 * ============================================================ */
.toolbox-hero {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(340px, 0.8fr);
  gap: 40px;
  align-items: center;
  padding: 36px 40px;
  border-radius: var(--tb-r-lg);
  border: 1px solid var(--tb-line);
  background:
    radial-gradient(640px 300px at 8% -20%, rgba(234, 90, 26, 0.10), transparent 62%),
    radial-gradient(520px 260px at 96% 130%, rgba(216, 146, 41, 0.08), transparent 60%),
    linear-gradient(120deg, var(--orange-50) 0%, #fef6ec 50%, #ffffff 100%);
  overflow: hidden;
  isolation: isolate;
}

/* 柔光晕：低饱和、重模糊，只做氛围不抢内容 */
.toolbox-hero-art {
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
}

.toolbox-hero-art .orb {
  position: absolute;
  display: block;
  border-radius: 50%;
  filter: blur(56px);
  opacity: 0.5;
}

.toolbox-hero-art .orb-a {
  width: 300px;
  height: 300px;
  left: -90px;
  top: -130px;
  background: radial-gradient(circle, rgba(249, 115, 22, 0.32), transparent 70%);
}

.toolbox-hero-art .orb-b {
  width: 260px;
  height: 260px;
  right: 16%;
  bottom: -150px;
  background: radial-gradient(circle, rgba(216, 146, 41, 0.18), transparent 70%);
}

.toolbox-hero-art .orb-c {
  width: 180px;
  height: 180px;
  right: -60px;
  top: -70px;
  background: radial-gradient(circle, rgba(234, 179, 8, 0.20), transparent 70%);
}

.toolbox-hero-copy {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 16px;
  min-width: 0;
}

/* Label 角色：眉标徽章 */
.tool-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 999px;
  border: 1px solid var(--tb-accent-line);
  background: rgba(255, 244, 234, 0.72);
  backdrop-filter: blur(10px) saturate(1.3);
  -webkit-backdrop-filter: blur(10px) saturate(1.3);
  color: var(--tb-accent-ink);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.02em;
}

/* Display 角色 */
.toolbox-hero h1 {
  margin: 0;
  font-size: clamp(28px, 3vw, 36px);
  line-height: 1.15;
  letter-spacing: -0.02em;
  font-weight: 700;
  color: var(--tb-ink);
}

.toolbox-hero p {
  max-width: 58ch;
  margin: 0;
  font-size: 15px;
  line-height: 1.8;
  color: var(--tb-muted);
  text-wrap: pretty;
}

/* 玻璃信息瓦片 */
.toolbox-hero-grid {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px;
}

.toolbox-hero-grid > div {
  display: grid;
  grid-template-columns: 36px minmax(0, 1fr);
  grid-template-areas: "icon title" "icon sub";
  align-items: center;
  gap: 2px 14px;
  padding: 16px 18px;
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.92);
  background: rgba(255, 255, 255, 0.82);
  backdrop-filter: blur(16px) saturate(1.4);
  -webkit-backdrop-filter: blur(16px) saturate(1.4);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.7), 0 8px 24px -18px rgba(20, 24, 28, 0.18);
  transition: transform var(--tb-dur) var(--tb-ease), box-shadow var(--tb-dur) var(--tb-ease);
}

.toolbox-hero-grid > div:hover {
  transform: translateY(-2px);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.7), 0 14px 30px -18px rgba(20, 24, 28, 0.22);
}

.toolbox-hero-grid svg {
  grid-area: icon;
  color: var(--tb-accent);
}

.toolbox-hero-grid b {
  grid-area: title;
  font-size: 14px;
  font-weight: 650;
  color: var(--tb-ink);
}

.toolbox-hero-grid span {
  grid-area: sub;
  font-size: 12px;
  line-height: 1.5;
  color: var(--tb-muted);
}

/* ============================================================
 * 分组标题 — Headline 角色 + 延伸细线制造呼吸段落
 * ============================================================ */
.toolbox-body {
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  gap: 20px;
  align-items: stretch;
  margin-top: 32px;
}

.tool-cluster-head {
  grid-column: 1 / -1;
  display: grid;
  grid-template-columns: auto minmax(120px, 1fr);
  grid-template-areas: "title line" "copy line";
  align-items: center;
  column-gap: 18px;
  row-gap: 3px;
  margin: 24px 0 0;
}

.toolbox-body > .tool-cluster-head:first-child {
  margin-top: 0;
}

.tool-cluster-head h2 {
  grid-area: title;
  margin: 0;
  font-family: var(--serif);
  font-size: 20px;
  font-weight: 700;
  line-height: 1.3;
  letter-spacing: -0.01em;
  color: var(--tb-ink);
}

.tool-cluster-head p {
  grid-area: copy;
  margin: 0;
  font-size: 12px;
  line-height: 1.5;
  color: var(--tb-muted);
}

/* 延伸细线：把分组标题变成有方向感的段落分隔 */
.tool-cluster-head::after {
  grid-area: line;
  content: "";
  width: 100%;
  height: 1px;
  background: linear-gradient(90deg, var(--tb-line-strong), transparent);
}

/* ============================================================
 * 工具卡 — Material 海拔 1 → hover 海拔 2
 * ============================================================ */
.tool-block {
  grid-column: span 6;
  min-width: 0;
  display: flex;
  flex-direction: column;
  padding: 24px;
  border-radius: var(--tb-r-md);
  border: 1px solid var(--tb-line);
  background: var(--tb-panel);
  box-shadow: var(--tb-elev-1);
  transition: box-shadow var(--tb-dur) var(--tb-ease), transform var(--tb-dur) var(--tb-ease), border-color var(--tb-dur) var(--tb-ease);
}

.tool-block:hover {
  box-shadow: var(--tb-elev-2);
  border-color: var(--tb-line-strong);
}

.tool-block-wide {
  grid-column: 1 / -1;
}

.tool-header {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  margin-bottom: 16px;
}

.tool-icon-wrap {
  flex-shrink: 0;
  width: 44px;
  height: 44px;
  border-radius: var(--tb-r-sm);
  display: grid;
  place-items: center;
  border: 1px solid var(--tb-accent-line);
  background: var(--tool-icon-bg, var(--tb-accent-soft));
  color: var(--tool-icon-color, var(--tb-accent));
}

.tool-header-body {
  min-width: 0;
  flex: 1;
}

/* Title 角色 */
.tool-title {
  margin: 0;
  font-size: 16px;
  font-weight: 650;
  line-height: 1.4;
  letter-spacing: -0.005em;
  color: var(--tb-ink);
}

.tool-sub {
  margin: 3px 0 0;
  font-size: 12.5px;
  line-height: 1.55;
  color: var(--tb-muted);
}

/* SectionTitle 组件在本页的对齐微调 */
.toolbox-body :deep(.section-head) {
  align-items: flex-start;
  margin-bottom: 14px;
}

/* 说明条：卡内轻量提示面 */
.tool-hint {
  margin: 0 0 16px;
  padding: 12px 16px;
  border: 1px solid var(--tb-line);
  border-radius: var(--tb-r-sm);
  background: var(--tb-panel-2);
  font-size: 12.5px;
  line-height: 1.7;
  color: var(--tb-muted);
}

/* ============================================================
 * 输入与按钮 — 焦点态可见（键盘可达）
 * ============================================================ */
.bloom-input,
.cov-input {
  display: flex;
  align-items: stretch;
  gap: 12px;
}

.bloom-input input,
.cov-input textarea {
  flex: 1;
  min-height: 44px;
  padding: 10px 16px;
  border-radius: var(--tb-r-sm);
  border: 1px solid var(--tb-line);
  background: var(--tb-panel-2);
  font-size: 13px;
  color: var(--tb-ink);
  transition: border-color var(--tb-dur) var(--tb-ease), box-shadow var(--tb-dur) var(--tb-ease), background var(--tb-dur) var(--tb-ease);
}

.cov-input textarea {
  min-height: 92px;
  resize: vertical;
  line-height: 1.6;
}

.bloom-input input::placeholder,
.cov-input textarea::placeholder {
  color: var(--tb-faint);
}

.bloom-input input:focus,
.cov-input textarea:focus {
  outline: none;
  background: #fff;
  border-color: var(--tb-accent);
  box-shadow: 0 0 0 3px rgba(234, 90, 26, 0.14);
}

.primary-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 0 22px;
  height: 44px;
  border-radius: var(--tb-r-sm);
  min-width: 112px;
  background: var(--tb-accent, #e85d16);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.01em;
  border: none;
  cursor: pointer;
  flex-shrink: 0;
  align-self: flex-start;
  transition: background var(--tb-dur) var(--tb-ease), transform var(--tb-dur) var(--tb-ease), box-shadow var(--tb-dur) var(--tb-ease);
}

.primary-btn:hover:not(:disabled) {
  background: var(--tb-accent-deep);
  transform: translateY(-1px);
  box-shadow: 0 10px 20px -10px rgba(234, 90, 26, 0.45);
}

.primary-btn:active:not(:disabled) {
  transform: translateY(0);
  box-shadow: none;
}

.primary-btn:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px rgba(234, 90, 26, 0.32);
}

.primary-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.primary-btn.sm {
  height: 34px;
  padding: 0 16px;
  font-size: 12px;
}

.spin {
  animation: tb-spin 1s linear infinite;
}

@keyframes tb-spin {
  to {
    transform: rotate(360deg);
  }
}

.tool-action-bar {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}

.empty-hint,
.review-stats {
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--tb-muted);
}

.empty-hint {
  margin-top: 12px;
  padding: 14px 16px;
  border-radius: var(--tb-r-sm);
  border: 1px dashed var(--tb-line-strong);
  background: var(--tb-panel-2);
}

/* ============================================================
 * 工具 1：Bloom 分析结果
 * ============================================================ */
.bloom-result {
  margin-top: 16px;
  padding: 18px;
  border-radius: var(--tb-r-sm);
  border: 1px solid var(--tb-accent-line);
  background: linear-gradient(165deg, var(--tb-accent-soft), #ffffff 62%);
}

.bloom-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.bloom-pill {
  padding: 5px 14px;
  border-radius: 999px;
  color: #fff;
  font-size: 12.5px;
  font-weight: 600;
  letter-spacing: 0.01em;
}

.bloom-pill.sm {
  padding: 3px 10px;
  font-size: 11px;
}

.bloom-pill.sub {
  background: var(--tb-ink-2);
}

.bloom-pill.dim {
  background: var(--tb-faint);
}

.bloom-def {
  margin: 0 0 10px;
  font-size: 13px;
  line-height: 1.7;
  color: var(--tb-ink-2);
}

.bloom-examples small {
  font-size: 11.5px;
  font-weight: 600;
  color: var(--tb-muted);
}

.bloom-examples ul {
  margin: 6px 0 0;
  padding-left: 18px;
}

.bloom-examples li {
  font-size: 12.5px;
  color: var(--tb-muted);
  line-height: 1.7;
}

/* ============================================================
 * 工具 2：CoV 验证
 * ============================================================ */
.demo-pills {
  margin-top: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.demo-pills button {
  padding: 5px 14px;
  border-radius: 999px;
  border: 1px solid var(--tb-line);
  background: var(--tb-panel);
  font-size: 11.5px;
  color: var(--tb-muted);
  cursor: pointer;
  transition: border-color var(--tb-dur) var(--tb-ease), color var(--tb-dur) var(--tb-ease), background var(--tb-dur) var(--tb-ease);
}

.demo-pills button:hover {
  border-color: var(--tb-accent-line);
  background: var(--tb-accent-soft);
  color: var(--tb-accent-ink);
}

.demo-pills button:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px rgba(234, 90, 26, 0.2);
}

.cov-result {
  margin-top: 16px;
}

.cov-summary {
  margin: 0 0 12px;
  padding: 12px 16px;
  border-radius: var(--tb-r-sm);
  background: var(--tb-panel-2);
  border: 1px solid var(--tb-line);
  font-size: 12.5px;
  color: var(--tb-ink-2);
  line-height: 1.7;
}

.axis-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 10px;
}

.axis-card {
  padding: 14px;
  border-radius: var(--tb-r-sm);
  border: 1px solid var(--tb-line);
  background: var(--tb-panel);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.axis-card.pass {
  border-color: var(--tb-ok-line);
  background: var(--tb-ok-soft);
  color: var(--tb-ok);
}

.axis-card.fail {
  border-color: var(--tb-err-line);
  background: var(--tb-err-soft);
  color: var(--tb-err);
}

.axis-card.uncertain {
  border-color: var(--tb-warn-line);
  background: var(--tb-warn-soft);
  color: var(--tb-warn);
}

.axis-card b {
  font-size: 12.5px;
  font-weight: 650;
  color: var(--tb-ink);
}

.axis-card small {
  font-size: 11.5px;
  color: var(--tb-muted);
  line-height: 1.55;
}

.axis-card .correction {
  color: var(--tb-info);
}

.cov-revised {
  margin: 12px 0 0;
  padding: 12px 16px;
  border-radius: var(--tb-r-sm);
  background: var(--tb-ok-soft);
  border: 1px solid var(--tb-ok-line);
  font-size: 12.5px;
  line-height: 1.7;
  color: var(--tb-ink-2);
}

/* ============================================================
 * 工具 3：质量保障面板
 * ============================================================ */
.quality-block .tool-header {
  margin-bottom: 18px;
}

.quality-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 14px;
}

.quality-card {
  display: flex;
  align-items: center;
  gap: 18px;
  padding: 18px 20px;
  border-radius: var(--tb-r-sm);
  border: 1px solid var(--tb-line);
  background: var(--tb-panel-2);
}

.quality-info strong {
  display: block;
  font-size: 14px;
  font-weight: 650;
  color: var(--tb-ink);
  margin-bottom: 3px;
}

.quality-info small {
  font-size: 11.5px;
  line-height: 1.5;
  color: var(--tb-muted);
}

.quality-action {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.quality-link-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 8px 16px;
  border-radius: var(--tb-r-xs);
  background: var(--tb-accent-soft);
  border: 1px solid var(--tb-accent-line);
  color: var(--tb-accent-ink);
  font-size: 12.5px;
  font-weight: 600;
  text-decoration: none;
  cursor: pointer;
  transition: background var(--tb-dur) var(--tb-ease), transform var(--tb-dur) var(--tb-ease);
}

.quality-link-btn:hover {
  background: #ffe9d5;
  transform: translateY(-1px);
}

/* ============================================================
 * 工具 4：智能辅导
 * ============================================================ */
.tutor-result {
  margin-top: 16px;
  padding: 18px;
  border-radius: var(--tb-r-sm);
  border: 1px solid var(--tb-accent-line);
  background: linear-gradient(165deg, var(--tb-accent-soft), #ffffff 62%);
}

.tutor-kp {
  margin-bottom: 10px;
}

.tutor-answer {
  margin: 0 0 8px;
  font-size: 13.5px;
  line-height: 1.75;
  color: var(--tb-ink-2);
}

.tutor-explanation {
  margin: 0 0 10px;
  font-size: 12.5px;
  line-height: 1.7;
  color: var(--tb-muted);
}

.tutor-examples small {
  font-size: 11.5px;
  font-weight: 600;
  color: var(--tb-muted);
}

.tutor-examples ul {
  margin: 4px 0 0;
  padding-left: 18px;
}

.tutor-examples li {
  font-size: 12.5px;
  color: var(--tb-muted);
  line-height: 1.7;
}

.tutor-agents {
  margin-top: 12px;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.tutor-agents small {
  font-size: 11.5px;
  color: var(--tb-muted);
}

.agent-tag {
  padding: 3px 10px;
  border-radius: 999px;
  background: var(--tb-panel);
  border: 1px solid var(--tb-line);
  font-size: 10.5px;
  color: var(--tb-info);
  font-family: var(--mono);
}

.tutor-history {
  margin-top: 16px;
}

.tutor-history > small {
  font-size: 11.5px;
  font-weight: 600;
  color: var(--tb-muted);
}

.tutor-record-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 2px;
  border-bottom: 1px dashed var(--tb-line);
  cursor: pointer;
  font-size: 12.5px;
  color: var(--tb-ink-2);
  transition: color var(--tb-dur) var(--tb-ease);
}

.tutor-record-row:hover {
  color: var(--tb-accent-deep);
}

.tutor-record-row em {
  font-style: normal;
  font-size: 10.5px;
  color: var(--tb-faint);
  margin-left: auto;
  font-family: var(--mono);
}

/* ============================================================
 * 工具 6：间隔复习
 * ============================================================ */
.review-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: 16px;
}

.review-item {
  padding: 16px;
  border-radius: var(--tb-r-sm);
  border: 1px solid var(--tb-line);
  background: var(--tb-panel-2);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.review-item-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.review-kp {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.review-kp strong {
  font-size: 14px;
  font-weight: 650;
  color: var(--tb-ink);
}

.review-kp small {
  font-size: 10.5px;
  color: var(--tb-faint);
  font-family: var(--mono);
}

.review-question {
  padding: 12px;
  border: 1px solid var(--tb-line);
  border-radius: var(--tb-r-xs);
  background: var(--tb-panel);
}

.review-question-label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 7px;
}

.review-question-label span {
  font-size: 11px;
  font-weight: 650;
  color: var(--tb-accent-ink);
}

.review-question-label small {
  overflow: hidden;
  color: var(--tb-faint);
  font-family: var(--mono);
  font-size: 9.5px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.review-question > p {
  margin: 0;
  color: var(--tb-ink);
  font-size: 12.5px;
  line-height: 1.65;
}

.review-options {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px;
  margin: 10px 0 0;
  padding: 0;
  list-style: none;
}

.review-options li {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  min-width: 0;
  color: var(--tb-muted);
  font-size: 11px;
  line-height: 1.45;
}

.review-options li > span {
  flex: 0 0 auto;
  color: var(--tb-accent-ink);
  font-family: var(--mono);
  font-weight: 650;
}

.review-objective {
  background: var(--tb-panel-2);
}

.review-priority {
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
}

.review-priority.high {
  background: var(--tb-err-soft);
  color: var(--tb-err);
}

.review-priority.normal {
  background: var(--tb-ok-soft);
  color: var(--tb-ok);
}

.review-reason {
  margin: 0;
  font-size: 12px;
  line-height: 1.6;
  color: var(--tb-muted);
}

.review-meta {
  display: flex;
  gap: 12px;
  font-size: 11px;
  color: var(--tb-faint);
}

.review-quality {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  padding-top: 8px;
  border-top: 1px dashed var(--tb-line);
}

.review-quality > small {
  font-size: 11.5px;
  color: var(--tb-muted);
}

.quality-btns {
  display: flex;
  gap: 6px;
}

.q-btn {
  padding: 5px 12px;
  border-radius: 999px;
  border: 1px solid var(--tb-line);
  background: var(--tb-panel);
  font-size: 11.5px;
  color: var(--tb-muted);
  cursor: pointer;
  transition: all var(--tb-dur) var(--tb-ease);
}

.q-btn:hover {
  border-color: var(--tb-accent-line);
  color: var(--tb-accent-ink);
}

.q-btn.active {
  border-color: var(--tb-accent);
  background: var(--tb-accent-soft);
  color: var(--tb-accent-ink);
  font-weight: 650;
}

/* ============================================================
 * 工具 7：下一题推荐
 * ============================================================ */
.nbq-list {
  display: grid;
  gap: 10px;
  margin-top: 16px;
}

.nbq-card {
  padding: 14px 16px;
  border-radius: var(--tb-r-sm);
  border: 1px solid var(--tb-line);
  background: var(--tb-panel-2);
}

.nbq-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 6px;
}

.nbq-idx {
  font-size: 12px;
  font-weight: 800;
  color: var(--tb-accent);
  font-variant-numeric: tabular-nums;
}

.nbq-uncertainty {
  margin-left: auto;
  font-size: 11px;
  color: var(--tb-faint);
}

.nbq-text {
  margin: 0;
  font-size: 12.5px;
  line-height: 1.65;
  color: var(--tb-ink-2);
}

.nbq-reason {
  margin: 6px 0 0;
  font-size: 11.5px;
  line-height: 1.55;
  color: var(--tb-muted);
}

/* ============================================================
 * 工具 8：反事实推演
 * ============================================================ */
.cf-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-top: 16px;
}

.cf-card {
  padding: 16px;
  border-radius: var(--tb-r-sm);
  border: 1px solid var(--tb-line);
  background: var(--tb-panel-2);
  text-align: center;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.cf-rate {
  font-size: 12px;
  font-weight: 600;
  color: var(--tb-muted);
}

.cf-final {
  font-size: 26px;
  font-weight: 750;
  letter-spacing: -0.02em;
  font-variant-numeric: tabular-nums;
}

.cf-card small {
  font-size: 11px;
  color: var(--tb-faint);
}

.cf-gain {
  margin: 12px 0 0;
  font-size: 12.5px;
  color: var(--tb-ink-2);
}

.cf-gain strong {
  color: var(--tb-accent-deep);
}

.cf-risk {
  margin: 8px 0 0;
  padding: 10px 14px;
  border-radius: var(--tb-r-xs);
  background: var(--tb-warn-soft);
  border: 1px solid var(--tb-warn-line);
  color: var(--tb-warn);
  font-size: 12px;
  line-height: 1.6;
}

/* ============================================================
 * 工具 9：反向学习规划
 * ============================================================ */
.rp-inputs {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.rp-inputs label {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
  padding: 14px 16px;
  border-radius: var(--tb-r-sm);
  border: 1px solid var(--tb-line);
  background: var(--tb-panel-2);
  font-size: 12.5px;
  color: var(--tb-ink-2);
}

.rp-inputs input[type="range"] {
  grid-column: 1 / -1;
  width: 100%;
  accent-color: var(--tb-accent);
  cursor: pointer;
}

.rp-inputs span {
  font-weight: 750;
  color: var(--tb-accent-deep);
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

.rp-result {
  margin-top: 16px;
  padding: 16px 18px;
  border-radius: var(--tb-r-sm);
  border: 1px solid var(--tb-line);
  background: var(--tb-panel-2);
}

.rp-status {
  display: inline-block;
  padding: 4px 14px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 650;
  margin-bottom: 12px;
}

.rp-status.ok {
  background: var(--tb-ok-soft);
  color: var(--tb-ok);
  border: 1px solid var(--tb-ok-line);
}

.rp-status.warn {
  background: var(--tb-warn-soft);
  color: var(--tb-warn);
  border: 1px solid var(--tb-warn-line);
}

.rp-metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.rp-metric {
  text-align: center;
  padding: 12px;
  border-radius: var(--tb-r-xs);
  background: var(--tb-panel);
  border: 1px solid var(--tb-line);
}

.rp-metric strong {
  display: block;
  font-size: 22px;
  font-weight: 750;
  letter-spacing: -0.02em;
  color: var(--tb-accent-deep);
  font-variant-numeric: tabular-nums;
}

.rp-metric small {
  font-size: 11px;
  color: var(--tb-muted);
}

.rp-narrative {
  margin: 10px 0 4px;
  font-size: 13px;
  color: var(--tb-fg);
  line-height: 1.55;
}

.rp-section-title {
  display: block;
  margin: 14px 0 8px;
  font-size: 11px;
  color: var(--tb-muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.rp-milestone-row {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.rp-milestone {
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid var(--tb-line);
  background: var(--tb-panel-2);
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 12px;
}

.rp-milestone strong {
  font-size: 13px;
  color: var(--tb-accent-deep);
}

.rp-milestone em {
  font-style: normal;
  font-weight: 700;
  color: var(--tb-fg);
  font-variant-numeric: tabular-nums;
}

.rp-milestone span {
  color: var(--tb-muted);
}

.rp-schedule {
  overflow-x: auto;
}

.rp-schedule table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.rp-schedule th,
.rp-schedule td {
  padding: 6px 10px;
  border-bottom: 1px solid var(--tb-line);
  text-align: left;
  font-variant-numeric: tabular-nums;
}

.rp-schedule th {
  color: var(--tb-muted);
  font-weight: 600;
  background: var(--tb-panel-2);
}

/* ============================================================
 * 工具 10：签到与成就
 * ============================================================ */
.gamify-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin: 4px 0 16px;
}

.gamify-card {
  min-height: 96px;
  padding: 16px 18px;
  border-radius: var(--tb-r-sm);
  border: 1px solid var(--tb-line);
  background: var(--tb-panel-2);
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 8px;
}

.gamify-level {
  font-size: 22px;
  font-weight: 750;
  letter-spacing: -0.02em;
  color: var(--tb-accent-deep);
}

.xp-bar {
  height: 8px;
  border-radius: 999px;
  background: var(--tb-line);
  overflow: hidden;
}

.xp-fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, var(--tb-accent), #f59e0b);
  transition: width 400ms var(--tb-ease);
}

.gamify-xp small {
  display: block;
  margin-top: 6px;
  font-size: 11.5px;
  color: var(--tb-muted);
}

.gamify-streak {
  display: flex;
  align-items: baseline;
  gap: 8px;
  color: var(--tb-accent);
}

.gamify-streak strong {
  font-size: 26px;
  font-weight: 750;
  letter-spacing: -0.02em;
  color: var(--tb-ink);
  font-variant-numeric: tabular-nums;
}

.gamify-streak small {
  font-size: 12px;
  color: var(--tb-muted);
}

.gamify-ach strong {
  font-size: 18px;
  font-weight: 700;
  color: var(--tb-ink);
  font-variant-numeric: tabular-nums;
}

.gamify-ach small {
  margin-left: 6px;
  font-size: 11.5px;
  color: var(--tb-muted);
}

.ach-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.ach-tag {
  padding: 3px 10px;
  border-radius: 999px;
  background: var(--tb-accent-soft);
  border: 1px solid var(--tb-accent-line);
  font-size: 10.5px;
  color: var(--tb-accent-ink);
}

.checkin-result {
  margin-top: 14px;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  padding: 12px 16px;
  border-radius: var(--tb-r-sm);
  background: var(--tb-ok-soft);
  border: 1px solid var(--tb-ok-line);
  color: var(--tb-ok);
  font-size: 12.5px;
  font-weight: 550;
}

/* ============================================================
 * 工具 11：学习同伴
 * ============================================================ */
.social-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  margin-top: 16px;
}

.social-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.social-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12.5px;
  font-weight: 650;
  color: var(--tb-ink-2);
}

.social-card {
  padding: 14px 16px;
  border-radius: var(--tb-r-sm);
  border: 1px solid var(--tb-line);
  background: var(--tb-panel-2);
}

.social-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 4px;
}

.social-id {
  font-size: 12.5px;
  font-weight: 650;
  color: var(--tb-ink);
  font-family: var(--mono);
}

.social-score {
  font-size: 11px;
  font-weight: 600;
  color: var(--tb-ok);
}

.social-reason {
  margin: 0;
  font-size: 12px;
  line-height: 1.6;
  color: var(--tb-muted);
}

.privacy-note {
  margin: 12px 0 0;
  font-size: 11.5px;
  color: var(--tb-faint);
}

/* ============================================================
 * 更多入口导航
 * ============================================================ */
.nav-grid {
  grid-column: 1 / -1;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 12px;
}

.nav-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px 18px;
  border-radius: var(--tb-r-sm);
  border: 1px solid var(--tb-line);
  background: var(--tb-panel);
  text-decoration: none;
  cursor: pointer;
  transition: transform var(--tb-dur) var(--tb-ease), box-shadow var(--tb-dur) var(--tb-ease), border-color var(--tb-dur) var(--tb-ease);
}

.nav-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--tb-elev-2);
  border-color: var(--nav-color);
}

.nav-card:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--nav-color) 35%, transparent);
}

.nav-icon {
  flex-shrink: 0;
  width: 42px;
  height: 42px;
  border-radius: var(--tb-r-sm);
  display: grid;
  place-items: center;
  background: color-mix(in srgb, var(--nav-color) 10%, transparent);
  color: var(--nav-color);
}

.nav-body {
  flex: 1;
  min-width: 0;
}

.nav-body strong {
  display: block;
  font-size: 13px;
  font-weight: 650;
  color: var(--tb-ink);
  margin-bottom: 2px;
}

.nav-body p {
  margin: 0;
  font-size: 11.5px;
  color: var(--tb-muted);
  line-height: 1.55;
}

.nav-arrow {
  flex-shrink: 0;
  color: var(--nav-color);
  opacity: 0;
  transform: translateX(-4px);
  transition: opacity var(--tb-dur) var(--tb-ease), transform var(--tb-dur) var(--tb-ease);
}

.nav-card:hover .nav-arrow {
  opacity: 1;
  transform: translateX(0);
}

/* ============================================================
 * 无障碍：动效偏好
 * ============================================================ */
@media (prefers-reduced-motion: reduce) {
  .toolbox-page *,
  .toolbox-page *::before,
  .toolbox-page *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}

/* ============================================================
 * 响应式：1440 / 1024 / 768 / 375
 * ============================================================ */
@media (max-width: 1024px) {
  .toolbox-hero {
    grid-template-columns: 1fr;
    gap: 24px;
    padding: 32px;
  }

  .toolbox-hero-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .tool-block,
  .tool-block-primary {
    grid-column: span 6;
  }

  .cf-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .rp-inputs,
  .gamify-grid,
  .rp-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .toolbox-page {
    /* AppShell 对直接子页面设置了 !important 全宽，移动端需按视口反向限宽。 */
    width: calc(100vw - 24px) !important;
    max-width: calc(100vw - 24px) !important;
    box-sizing: border-box;
    padding: 8px 16px 40px;
    overflow: hidden;
  }

  .toolbox-hero {
    padding: 26px 20px;
  }

  .toolbox-hero-grid {
    grid-template-columns: 1fr;
  }

  .toolbox-body {
    gap: 14px;
  }

  .tool-block,
  .tool-block-primary,
  .tool-block-wide {
    grid-column: 1 / -1;
    padding: 18px;
  }

  .review-list,
  .social-grid,
  .quality-grid {
    grid-template-columns: 1fr;
  }

  .review-options {
    grid-template-columns: 1fr;
  }

  .bloom-input,
  .cov-input {
    flex-direction: column;
  }

  .primary-btn {
    width: 100%;
    align-self: stretch;
  }

  .tool-cluster-head::after {
    display: none;
  }

  .tool-cluster-head {
    grid-template-columns: 1fr;
    grid-template-areas: "title" "copy";
    margin-top: 18px;
  }
}

@media (max-width: 375px) {
  .toolbox-hero h1 {
    font-size: 25px;
  }

  .cf-grid,
  .rp-inputs,
  .gamify-grid,
  .rp-metrics {
    grid-template-columns: 1fr;
  }
}
.image-tool-layout { display: grid; gap: 12px; }
.image-dropzone { display: grid; place-items: center; min-height: 220px; overflow: hidden; border: 1px dashed #cfc8bd; border-radius: 12px; background: #fbfaf7; color: #89857d; cursor: pointer; }
.image-dropzone:hover { border-color: #e85d16; background: #fffaf5; }
.image-dropzone input { position: absolute; width: 1px; height: 1px; opacity: 0; }
.image-dropzone img { width: 100%; max-height: 320px; object-fit: contain; }
.image-dropzone strong { margin-top: 10px; color: #1f1d1a; font-size: 14px; }
.image-dropzone span { margin-top: 4px; font-size: 12px; }
.tool-input-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 60px;
  padding: 8px 10px 8px 14px;
  border: 1px solid #e7e2da;
  border-radius: 11px;
  background: #fffaf6;
  color: #68635b;
  font-size: 12px;
}
.tool-input-actions > span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tool-error { padding: 10px 12px; border: 1px solid #edc9c5; border-radius: 8px; background: #fff1ee; color: #b5423a; font-size: 12px; }
.structured-result { margin-top: 15px; padding: 18px; border: 1px solid #e5e1f4; border-radius: 12px; background: #faf9ff; }
.structured-result > header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.structured-result h3 { margin: 4px 0 0; color: #171512; font-size: 17px; }
.structured-result small, .structured-result > header > span { color: #89857d; font-size: 11px; }
.structured-result > p, .structured-result section p { color: #625f58; font-size: 13px; line-height: 1.65; }
.structured-result section { margin-top: 14px; padding-top: 12px; border-top: 1px solid #e5e1f4; }
.structured-result code { display: block; margin-top: 6px; padding: 7px; border-radius: 6px; background: #fff; }
.result-tags { display: flex; flex-wrap: wrap; gap: 5px; }
.result-tags span { padding: 3px 7px; border-radius: 999px; background: #eeebff; color: #6557d9; font-size: 10px; }
.tag-result-list, .recommend-result-list { margin-top: 14px; border-top: 1px solid #e9e5de; }
.tag-result-list article { display: grid; grid-template-columns: 32px minmax(0,1fr) auto; align-items: center; gap: 10px; min-height: 66px; padding: 8px; border-bottom: 1px solid #e9e5de; }
.tag-result-list article > span { color: #b7b1a7; font-size: 11px; font-weight: 700; }
.tag-result-list strong { font-size: 13px; }
.tag-result-list p { margin: 4px 0 0; color: #89857d; font-size: 11px; }
.state-monitor { display: grid; gap: 16px; margin-top: 14px; }
.state-monitor dl { display: grid; grid-template-columns: repeat(4,1fr); margin: 0; border-top: 1px solid #e9e5de; border-bottom: 1px solid #e9e5de; }
.state-monitor dl div { padding: 18px; border-left: 1px solid #e9e5de; }
.state-monitor dl div:first-child { border-left: 0; }
.state-monitor dt { color: #89857d; font-size: 11px; }
.state-monitor dd { margin: 7px 0 0; color: #171512; font-size: 26px; font-weight: 750; }
.state-monitor > section { padding: 17px; border: 1px solid #e5e1f4; border-radius: 10px; background: #faf9ff; }
.state-monitor > section span { color: #6557d9; font-size: 11px; font-weight: 700; }
.state-monitor h3 { margin: 6px 0; font-size: 16px; }
.state-monitor p { margin: 0; color: #625f58; font-size: 12px; }
.recommend-result-list article { display: grid; grid-template-columns: 34px minmax(0,1fr) auto; align-items: center; gap: 12px; min-height: 82px; padding: 10px 7px; border-bottom: 1px solid #e9e5de; }
.recommend-rank { display: grid; place-items: center; width: 28px; height: 28px; border-radius: 50%; background: #fff3ea; color: #d75011; font-size: 11px; font-weight: 750; }
.recommend-result-list small { color: #6557d9; font-size: 10px; }
.recommend-result-list h3 { margin: 4px 0; color: #171512; font-size: 14px; }
.recommend-result-list p { margin: 0; color: #89857d; font-size: 11px; }
.recommend-result-list a { display: inline-flex; align-items: center; gap: 4px; color: #d75011; font-size: 11px; text-decoration: none; }
@media (max-width: 760px) {
  .state-monitor dl { grid-template-columns: 1fr 1fr; }
  .tag-result-list article, .recommend-result-list article { grid-template-columns: 30px minmax(0,1fr); }
  .tag-result-list .result-tags, .recommend-result-list a { grid-column: 2; }
}
</style>
