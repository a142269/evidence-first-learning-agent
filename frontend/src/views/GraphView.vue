<script setup lang="ts">
import * as echarts from "echarts";
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import {
  ArrowLeft,
  ArrowRight,
  BarChart3,
  BookOpen,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
  Download,
  Filter,
  Focus,
  Fullscreen,
  GitBranch,
  Keyboard,
  Layers3,
  ListTree,
  Loader2,
  Map as MapIcon,
  MessageCircle,
  Minus,
  MoreHorizontal,
  Network,
  PanelBottomClose,
  PanelLeftClose,
  PanelLeftOpen,
  PlayCircle,
  Plus,
  RefreshCcw,
  Route as RouteIcon,
  RotateCcw,
  Search,
  SlidersHorizontal,
  Sparkles,
  Sprout,
  Target,
  Trophy,
  X,
  ZoomIn,
  ZoomOut,
} from "lucide-vue-next";

import { useSession } from "@/composables/useSession";
import { useRoute, useRouter } from "vue-router";
import {
  getGraph3d,
  getKnowledgePoint,
  lookupKnowledgePoint,
  getGraphStats,
  searchKnowledgeGraph,
  getLearningPath,
  getMasteryHistory,
  planDualGraph,
  getMasteryForecast,
  type Graph3dEdge,
  type Graph3dNode,
} from "@/api/knowledgeGraph";
import { listCourses } from "@/api/knowledge";
import { seedKnowledgeGraph } from "@/api/insights";

const { userId } = useSession();
const router = useRouter();

const loading = ref(true);
const error = ref("");
const course = ref("artificial_intelligence");
const courses = ref<string[]>(["artificial_intelligence", "python_programming"]);
const nodes = ref<Graph3dNode[]>([]);
const edges = ref<Graph3dEdge[]>([]);
const stats = ref<Record<string, any>>({});
const globalStats = ref<Record<string, any>>({});

type DockTab = "graphrag" | "path" | "search" | "recommend" | "achievement" | "stats";
type DrawerTab = "overview" | "analysis" | "evaluation";
type GraphLevel = "clusters" | "nodes";

interface GraphCluster {
  id: string;
  label: string;
  hub: Graph3dNode;
  members: Graph3dNode[];
  averageMastery: number;
  weakCount: number;
  relationCount: number;
  color: string;
  softColor: string;
}

const dockTabs: Array<{ key: DockTab; label: string; icon: typeof Network }> = [
  { key: "graphrag", label: "GraphRAG", icon: Sparkles },
  { key: "path", label: "学习路径", icon: RouteIcon },
  { key: "search", label: "知识检索", icon: Search },
  { key: "recommend", label: "智能推荐", icon: Target },
  { key: "achievement", label: "学习成就", icon: Trophy },
  { key: "stats", label: "图谱统计", icon: BarChart3 },
];

const activeDock = ref<DockTab | null>(null);
const graphLevel = ref<GraphLevel>("clusters");
const activeClusterId = ref<string | null>(null);
const selectedCluster = ref<GraphCluster | null>(null);
const coursePanelOpen = ref(false);
const filterOpen = ref(false);
const legendOpen = ref(true);
const shortcutsOpen = ref(false);
const drawerTab = ref<DrawerTab>("overview");
const topSearchEl = ref<HTMLInputElement | null>(null);
const courseTreeQuery = ref("");
const workspaceNotice = ref("");
let workspaceNoticeTimer: ReturnType<typeof setTimeout> | null = null;

const graphRagQuestion = ref("");
const graphRagLoading = ref(false);
const graphRagAnswer = ref("");
const graphRagNodeIds = ref<Set<string>>(new Set());

const nodeRating = ref(0);
const difficultyRating = ref(0);
const resourceRating = ref(0);
const personalNote = ref("");
const markNeedsReview = ref(false);
const markEasilyConfused = ref(false);
const contextMenu = ref<{ x: number; y: number; node: Graph3dNode } | null>(null);

function showWorkspaceNotice(message: string) {
  workspaceNotice.value = message;
  if (workspaceNoticeTimer) clearTimeout(workspaceNoticeTimer);
  workspaceNoticeTimer = setTimeout(() => (workspaceNotice.value = ""), 2400);
}

function toggleDock(tab: DockTab) {
  activeDock.value = activeDock.value === tab ? null : tab;
  filterOpen.value = false;
  requestAnimationFrame(() => chart?.resize());
}

function closeOverlays() {
  if (contextMenu.value) contextMenu.value = null;
  else if (shortcutsOpen.value) shortcutsOpen.value = false;
  else if (filterOpen.value) filterOpen.value = false;
  else if (selectedCluster.value) selectedCluster.value = null;
  else if (selected.value) {
    selected.value = null;
    selectedDetail.value = null;
    selectedNeighbors.value = [];
    chart?.dispatchAction({ type: "downplay" });
  } else if (activeDock.value) activeDock.value = null;
  else if (coursePanelOpen.value) coursePanelOpen.value = false;
  requestAnimationFrame(() => chart?.resize());
}

function zoomGraph(factor: number) {
  chart?.dispatchAction({ type: "graphRoam", zoom: factor });
}

function fitGraph() {
  savedZoom.value = 0.9;
  savedCenter.value = null;
  zoomTier.value = zoomToTier(savedZoom.value);
  chart?.resize();
  chart?.setOption({ series: [{ zoom: savedZoom.value, center: undefined }] });
  showWorkspaceNotice("已适应当前图谱范围");
}

function resetGraphView() {
  chart?.dispatchAction({ type: "restore" });
  renderChart();
  showWorkspaceNotice("图谱视图已重置");
}

async function toggleFullscreen() {
  try {
    if (!document.fullscreenElement) await document.documentElement.requestFullscreen();
    else await document.exitFullscreen();
  } catch {
    showWorkspaceNotice("当前浏览器未允许全屏操作");
  }
}

const expandedNodes = ref<Set<string>>(new Set());

const CLUSTER_PALETTE = [
  { color: "#d98525", soft: "#fff1de" },
  { color: "#3473ad", soft: "#e8f0f7" },
  { color: "#2f8b69", soft: "#e5f2ed" },
  { color: "#7659b6", soft: "#eee9f8" },
  { color: "#c45d68", soft: "#f8e8ea" },
  { color: "#2f8f91", soft: "#e4f2f2" },
  { color: "#9a6a35", soft: "#f4ece2" },
];

const graphClusters = computed<GraphCluster[]>(() => {
  if (!nodes.value.length) return [];

  const adjacency = new Map<string, Set<string>>();
  const degree = new Map<string, number>();
  for (const node of nodes.value) adjacency.set(node.id, new Set());
  for (const edge of edges.value) {
    if (!adjacency.has(edge.source) || !adjacency.has(edge.target)) continue;
    adjacency.get(edge.source)!.add(edge.target);
    adjacency.get(edge.target)!.add(edge.source);
  }
  for (const node of nodes.value) degree.set(node.id, adjacency.get(node.id)?.size || 0);

  const distanceFrom = (source: string) => {
    const distances = new Map<string, number>([[source, 0]]);
    const queue = [source];
    while (queue.length) {
      const current = queue.shift()!;
      const nextDistance = (distances.get(current) || 0) + 1;
      for (const next of adjacency.get(current) || []) {
        if (distances.has(next)) continue;
        distances.set(next, nextDistance);
        queue.push(next);
      }
    }
    return distances;
  };

  const clusterCount = Math.min(7, Math.max(3, Math.round(Math.sqrt(nodes.value.length / 2))));
  const candidates = [...nodes.value].sort(
    (a, b) => (degree.get(b.id) || 0) - (degree.get(a.id) || 0),
  );
  const hubs: Graph3dNode[] = candidates.length ? [candidates[0]] : [];
  const hubDistances = new Map<string, Map<string, number>>();
  if (hubs[0]) hubDistances.set(hubs[0].id, distanceFrom(hubs[0].id));

  while (hubs.length < clusterCount && hubs.length < nodes.value.length) {
    let best: Graph3dNode | null = null;
    let bestScore = -1;
    for (const node of candidates) {
      if (hubs.some((hub) => hub.id === node.id)) continue;
      const minDistance = Math.min(
        ...hubs.map((hub) => hubDistances.get(hub.id)?.get(node.id) ?? nodes.value.length),
      );
      const score = minDistance * 100 + (degree.get(node.id) || 0);
      if (score > bestScore) {
        best = node;
        bestScore = score;
      }
    }
    if (!best) break;
    hubs.push(best);
    hubDistances.set(best.id, distanceFrom(best.id));
  }

  const buckets = new Map<string, Graph3dNode[]>(hubs.map((hub) => [hub.id, [hub]]));
  const hubIds = new Set(hubs.map((hub) => hub.id));
  const targetSize = Math.ceil(nodes.value.length / Math.max(hubs.length, 1));
  const softCapacity = Math.max(targetSize + 1, Math.ceil(targetSize * 1.35));
  const assignable = nodes.value
    .filter((node) => !hubIds.has(node.id))
    .sort((a, b) => (degree.get(b.id) || 0) - (degree.get(a.id) || 0));
  assignable.forEach((node, index) => {
    let owner = hubs[index % hubs.length];
    let bestScore = Number.POSITIVE_INFINITY;
    for (const hub of hubs) {
      const bucketSize = buckets.get(hub.id)!.length;
      const distance = hubDistances.get(hub.id)?.get(node.id) ?? nodes.value.length;
      const balancePenalty = (bucketSize / Math.max(targetSize, 1)) * 1.35;
      const capacityPenalty = bucketSize >= softCapacity ? nodes.value.length : 0;
      const score = distance + balancePenalty + capacityPenalty;
      if (score < bestScore) {
        owner = hub;
        bestScore = score;
      }
    }
    buckets.get(owner.id)!.push(node);
  });

  return hubs
    .map((hub, index) => {
      const members = buckets.get(hub.id) || [hub];
      const memberIds = new Set(members.map((node) => node.id));
      const relations = edges.value.filter(
        (edge) => memberIds.has(edge.source) && memberIds.has(edge.target),
      ).length;
      const palette = CLUSTER_PALETTE[index % CLUSTER_PALETTE.length];
      return {
        id: `cluster-${hub.id}`,
        label: hub.name,
        hub,
        members,
        averageMastery: members.length
          ? members.reduce((sum, node) => sum + node.mastery, 0) / members.length
          : 0,
        weakCount: members.filter((node) => node.mastery < 0.6).length,
        relationCount: relations,
        color: palette.color,
        softColor: palette.soft,
      };
    })
    .sort((a, b) => b.members.length - a.members.length);
});

const clusterMembership = computed(() => {
  const mapping = new Map<string, string>();
  for (const cluster of graphClusters.value) {
    for (const node of cluster.members) mapping.set(node.id, cluster.id);
  }
  return mapping;
});

const clusterRelations = computed(() => {
  const aggregated = new Map<string, { source: string; target: string; count: number }>();
  for (const edge of edges.value) {
    const source = clusterMembership.value.get(edge.source);
    const target = clusterMembership.value.get(edge.target);
    if (!source || !target || source === target) continue;
    const key = source < target ? `${source}|${target}` : `${target}|${source}`;
    const current = aggregated.get(key);
    if (current) current.count += 1;
    else aggregated.set(key, { source, target, count: 1 });
  }
  return [...aggregated.values()];
});

const activeCluster = computed(
  () => graphClusters.value.find((cluster) => cluster.id === activeClusterId.value) || null,
);

function showClusterOverview() {
  graphLevel.value = "clusters";
  activeClusterId.value = null;
  selectedCluster.value = null;
  selected.value = null;
  renderChart();
}

function showAllCourseNodes() {
  graphLevel.value = "nodes";
  activeClusterId.value = null;
  selectedCluster.value = null;
  selected.value = null;
  renderChart();
  showWorkspaceNotice("已展开当前课程的全部知识点");
}

function selectCluster(cluster: GraphCluster) {
  selected.value = null;
  selectedCluster.value = cluster;
}

function openCluster(cluster: GraphCluster) {
  graphLevel.value = "nodes";
  activeClusterId.value = cluster.id;
  selectedCluster.value = null;
  selected.value = null;
  // 聚类钻取的语义是查看该组的全部成员，不能继承课程级的缩小筛选。
  nodeFilter.value = "all";
  chapterFocus.value = null;
  viewMode.value = "explore";
  if (perspective.value === "weakness" || perspective.value === "path") {
    perspective.value = "cluster";
    layoutMode.value = "cluster";
  }
  expandedNodes.value = new Set(cluster.members.map((node) => node.id));
  renderChart();
  showWorkspaceNotice(`已展开「${cluster.label}」的 ${cluster.members.length} 个知识点`);
}

// ===== 学习路径高亮 =====
const learningPath = ref<Array<{ kp_id: string; name: string; order: number }>>([]);
const currentPathIndex = ref(0);
const showPathHighlight = ref(true);

// ===== 知识点状态筛选 =====
type FilterType = 'all' | 'mastered' | 'learning' | 'not_started' | 'at_risk' | 'recommended';
const nodeFilter = ref<FilterType>('all');

const FILTER_OPTIONS = [
  { key: 'all', label: '全部', icon: 'ALL' },
  { key: 'mastered', label: '已掌握', icon: 'OK' },
  { key: 'learning', label: '学习中', icon: 'RUN' },
  { key: 'not_started', label: '未开始', icon: 'NEW' },
  { key: 'at_risk', label: '有风险', icon: 'RISK' },
  { key: 'recommended', label: '推荐', icon: 'NEXT' },
] as const;

// ===== 掌握度趋势图 =====
const showTrendChart = ref(false);
const trendData = ref<Array<{ date: string; mastery: number; attempts: number; correct: number }>>([]);
const trendChartEl = ref<HTMLElement | null>(null);
let trendChart: echarts.ECharts | null = null;
const trendRange = ref(30); // 默认30天

// ===== 知识对比功能 =====
const compareMode = ref(false);
const compareNodes = ref<Graph3dNode[]>([]);
const compareChartEl = ref<HTMLElement | null>(null);
let compareChart: echarts.ECharts | null = null;

// ===== 智能推荐 =====
const showRecommendations = ref(false);
const recommendedNodes = computed(() => {
  // 推荐逻辑：学习路径上未掌握的知识点
  if (!learningPath.value.length) return [];
  return learningPath.value
    .slice(currentPathIndex.value, currentPathIndex.value + 3)
    .map(p => nodes.value.find(n => n.id === p.kp_id))
    .filter((n): n is Graph3dNode => !!n && n.mastery < 0.8);
});

// ===== 学习模式 =====
type ViewMode = 'explore' | 'focus';
const viewMode = ref<ViewMode>('explore');

// ===== 学习里程碑 =====
const milestones = computed(() => {
  const ms = [];
  const masteredCount = nodes.value.filter(n => n.mastery >= 0.8).length;
  const totalCount = nodes.value.length;
  
  if (masteredCount >= 1) ms.push({ icon: '01', title: '初次掌握', desc: '掌握第一个知识点' });
  if (masteredCount >= 5) ms.push({ icon: '05', title: '渐入佳境', desc: '掌握5个知识点' });
  if (masteredCount >= totalCount * 0.5) ms.push({ icon: '50', title: '半程达成', desc: '掌握一半知识点' });
  if (masteredCount >= totalCount) ms.push({ icon: '100', title: '完全掌握', desc: '掌握全部知识点' });
  
  return ms;
});

// ===== 双图路径规划（后端 /learning-path/dual-graph） =====
const dualGraphLoading = ref(false);
const dualGraphResult = ref<{
  focus_kp_name: string;
  main_path: Array<{ kp_id: string; title: string; source: string; reason: string; mastery: number | null; bloom: string }>;
  detour_path: Array<{ kp_id: string; title: string; source: string; reason: string; mastery: number | null; bloom: string }>;
  remediation_path: Array<{ kp_id: string; title: string; source: string; reason: string; mastery: number | null; bloom: string }>;
  explanations: Array<{ kind: string; note: string; weakness_handling: string }>;
  stats: { kp_count: number; edge_count: number; similar_count: number; weak_kp_count: number };
} | null>(null);
const dualGraphActivePath = ref<'main' | 'detour' | 'remediation'>('main');
const dualGraphHighlightNodes = ref<Set<string>>(new Set());

async function runDualGraph(node: Graph3dNode) {
  dualGraphLoading.value = true;
  try {
    const res = await planDualGraph(userId.value, node.id);
    dualGraphResult.value = res;
    dualGraphActivePath.value = 'main';
    updateDualGraphHighlight();
  } catch (e) {
    console.error('双图路径规划失败:', e);
    dualGraphResult.value = null;
  }
  dualGraphLoading.value = false;
}

function updateDualGraphHighlight() {
  const path = dualGraphActivePath.value;
  const result = dualGraphResult.value;
  if (!result) { dualGraphHighlightNodes.value = new Set(); return; }
  const pathKey = `${path}_path` as keyof typeof result;
  dualGraphHighlightNodes.value = new Set(
    (result[pathKey] as any[]).map((s: any) => s.kp_id)
  );
  renderChart();
}

function switchDualGraphPath(path: 'main' | 'detour' | 'remediation') {
  dualGraphActivePath.value = path;
  updateDualGraphHighlight();
}

function clearDualGraph() {
  dualGraphResult.value = null;
  dualGraphHighlightNodes.value = new Set();
  renderChart();
}

// 双图路径规划增强数据
const dualGraphStats = computed(() => {
  const r = dualGraphResult.value;
  if (!r) return null;
  return r.stats;
});

// 当前路径难度评估
const dualGraphPathMeta = computed(() => {
  const r = dualGraphResult.value;
  if (!r) return null;
  const pathKey = `${dualGraphActivePath.value}_path` as keyof typeof r;
  const steps = (r[pathKey] as any[]) ?? [];
  const totalSteps = steps.length;
  // 难度 = 未掌握节点占比
  const weakSteps = steps.filter(s => s.mastery != null && s.mastery < 0.5).length;
  const difficulty = totalSteps > 0 ? Math.round((weakSteps / totalSteps) * 100) : 0;
  // 预估学习时间（每个节点约 25 分钟）
  const estMinutes = totalSteps * 25;
  const estHours = Math.floor(estMinutes / 60);
  const estMins = estMinutes % 60;
  const estTime = estHours > 0 ? `${estHours}h${estMins > 0 ? estMins + 'm' : ''}` : `${estMins}m`;
  // Bloom 层级分布
  const bloomDist: Record<string, number> = {};
  steps.forEach(s => { bloomDist[s.bloom] = (bloomDist[s.bloom] ?? 0) + 1; });
  // 平均掌握度
  const masteredSteps = steps.filter(s => s.mastery != null);
  const avgMastery = masteredSteps.length > 0
    ? Math.round((masteredSteps.reduce((sum, s) => sum + (s.mastery ?? 0), 0) / masteredSteps.length) * 100)
    : 0;
  return { totalSteps, weakSteps, difficulty, estTime, bloomDist, avgMastery };
});

// 路径对比摘要
const dualGraphComparison = computed(() => {
  const r = dualGraphResult.value;
  if (!r) return null;
  const paths = [
    { key: 'main', label: '主路径', steps: r.main_path.length, icon: '主' },
    { key: 'detour', label: '绕行路径', steps: r.detour_path.length, icon: '绕' },
    { key: 'remediation', label: '卡点补救', steps: r.remediation_path.length, icon: '补' },
  ];
  return paths;
});

// ===== 掌握度时光机预测（后端 /cognitive/forecast） =====
const forecastLoading = ref(false);
const forecastData = ref<{
  current_mastery: number;
  forecast: Array<{ day: number; p_learned: number; ci_low: number; ci_high: number }>;
  milestones: Array<{ day: number; target: number; label: string; p_at_day: number }>;
  summary_text: string;
} | null>(null);
const forecastEl = ref<HTMLElement | null>(null);
let forecastChart: echarts.ECharts | null = null;

async function loadForecast(node: Graph3dNode) {
  forecastLoading.value = true;
  try {
    const res = await getMasteryForecast(userId.value, node.id, 30);
    forecastData.value = res;
    await nextTick();
    renderForecastChart();
  } catch (e) {
    console.error('时光机预测失败:', e);
    forecastData.value = null;
  }
  forecastLoading.value = false;
}

function renderForecastChart() {
  if (!forecastEl.value) return;
  if (!forecastChart) {
    forecastChart = echarts.init(forecastEl.value);
  }
  if (!forecastData.value || forecastData.value.forecast.length === 0) {
    forecastChart.clear();
    return;
  }

  const f = forecastData.value;
  const days = f.forecast.map(p => `D+${p.day}`);
  const masteryVals = f.forecast.map(p => Math.round(p.p_learned * 100));
  const ciLow = f.forecast.map(p => Math.round(p.ci_low * 100));
  const ciHigh = f.forecast.map(p => Math.round(p.ci_high * 100));

  const milestoneMarks = f.milestones.map(m => ({
    xAxis: `D+${m.day}`,
    label: { formatter: m.label, color: '#2f9f6b', fontSize: 10 },
  }));

  const option: echarts.EChartsOption = {
    tooltip: { trigger: 'axis' },
    grid: { left: 10, right: 10, top: 30, bottom: 20, containLabel: true },
    xAxis: {
      type: 'category', data: days,
      axisLine: { lineStyle: { color: '#e5e7eb' } },
      axisLabel: { color: '#6b7280', fontSize: 10, interval: 4 },
    },
    yAxis: {
      type: 'value', min: 0, max: 100,
      axisLabel: { formatter: '{value}%', color: '#6b7280', fontSize: 10 },
      splitLine: { lineStyle: { color: '#f3f4f6' } },
    },
    series: [
      {
        name: '置信下界', type: 'line', data: ciLow,
        lineStyle: { opacity: 0 }, stack: 'ci', symbol: 'none',
      },
      {
        name: '置信区间', type: 'line', data: ciHigh.map((v, i) => v - ciLow[i]),
        lineStyle: { opacity: 0 }, areaStyle: { color: 'rgba(234,90,26,0.15)' },
        stack: 'ci', symbol: 'none',
      },
      {
        name: '预测掌握度', type: 'line', data: masteryVals,
        smooth: true, symbol: 'circle', symbolSize: 4,
        lineStyle: { color: '#ea5a1a', width: 2 },
        itemStyle: { color: '#ea5a1a' },
        markLine: milestoneMarks.length > 0 ? {
          symbol: 'none', silent: true,
          data: milestoneMarks,
          lineStyle: { color: '#2f9f6b', type: 'dashed' },
        } : undefined,
      },
    ],
  };
  forecastChart.setOption(option, true);
}

// ===== 知识解锁链路分析 =====
const unlockAnalysis = ref(false);
const unlockDirectNodes = ref<Set<string>>(new Set());
const unlockChainNodes = ref<Set<string>>(new Set());
const unlockStats = computed(() => ({
  direct: unlockDirectNodes.value.size,
  total: unlockChainNodes.value.size,
}));

function analyzeUnlock(node: Graph3dNode) {
  unlockAnalysis.value = true;
  unlockDirectNodes.value = new Set();
  unlockChainNodes.value = new Set();
  weaknessTrace.value = false; // 互斥

  // BFS 找到所有下游节点
  const visited = new Set<string>([node.id]);
  const queue: string[] = [node.id];

  // 第一层：直接后续
  edges.value.forEach(e => {
    if (e.source === node.id && !visited.has(e.target)) {
      unlockDirectNodes.value.add(e.target);
    }
  });

  while (queue.length) {
    const current = queue.shift()!;
    edges.value.forEach(e => {
      if (e.source === current && !visited.has(e.target)) {
        visited.add(e.target);
        unlockChainNodes.value.add(e.target);
        queue.push(e.target);
      }
    });
  }
  renderChart();
}

function clearUnlockAnalysis() {
  unlockAnalysis.value = false;
  unlockDirectNodes.value = new Set();
  unlockChainNodes.value = new Set();
  renderChart();
}

// ===== 薄弱根因追溯 =====
const weaknessTrace = ref(false);
const weaknessChain = ref<string[]>([]);
const weaknessRoot = computed(() => {
  if (weaknessChain.value.length === 0) return null;
  return nodes.value.find(n => n.id === weaknessChain.value[0]) ?? null;
});

function traceWeakness(node: Graph3dNode) {
  weaknessTrace.value = true;
  weaknessChain.value = [];
  unlockAnalysis.value = false; // 互斥

  const visited = new Set<string>();
  let current: Graph3dNode | undefined = node;

  while (current && !visited.has(current.id)) {
    visited.add(current.id);
    weaknessChain.value.unshift(current.id);

    // 找到掌握度最低的先修节点
    let weakestPrereq: Graph3dNode | undefined;
    let weakestMastery = 1;

    edges.value.forEach(e => {
      if (e.target === current!.id) {
        const prereq = nodes.value.find(n => n.id === e.source);
        if (prereq && prereq.mastery < weakestMastery && !visited.has(prereq.id)) {
          weakestMastery = prereq.mastery;
          weakestPrereq = prereq;
        }
      }
    });

    // 如果先修节点掌握度也低，继续追溯
    if (weakestPrereq && weakestMastery < 0.5) {
      current = weakestPrereq;
    } else {
      current = undefined;
    }
  }
  renderChart();
}

function clearWeaknessTrace() {
  weaknessTrace.value = false;
  weaknessChain.value = [];
  renderChart();
}

// 薄弱根因链增强数据
const weaknessChainDetails = computed(() => {
  if (!weaknessTrace.value || weaknessChain.value.length === 0) return [];
  return weaknessChain.value.map((id, idx) => {
    const node = nodes.value.find(n => n.id === id);
    if (!node) return null;
    // 找到从上一个节点到当前节点的边
    const prevId = idx > 0 ? weaknessChain.value[idx - 1] : null;
    const relation = prevId
      ? edges.value.find(e => e.source === id && e.target === prevId)?.relation ?? '先修'
      : '起点';
    return {
      id,
      name: node.name,
      mastery: node.mastery,
      bloom: node.bloom_level,
      bloomColor: node.bloom_color,
      relation,
      isRoot: idx === 0,
      isCurrent: idx === weaknessChain.value.length - 1,
      gap: Math.round((0.8 - node.mastery) * 100), // 与掌握目标的差距
    };
  }).filter(Boolean) as Array<{
    id: string; name: string; mastery: number; bloom: string; bloomColor: string;
    relation: string; isRoot: boolean; isCurrent: boolean; gap: number;
  }>;
});

// 薄弱根因推荐动作
const weaknessRecommendations = computed(() => {
  if (weaknessChainDetails.value.length === 0) return [];
  const recs: string[] = [];
  const root = weaknessChainDetails.value[0];
  if (root.mastery < 0.3) {
    recs.push(`根源知识点「${root.name}」掌握度仅 ${Math.round(root.mastery * 100)}%，建议从基础概念重新学习`);
  } else if (root.mastery < 0.5) {
    recs.push(`根源知识点「${root.name}」掌握度 ${Math.round(root.mastery * 100)}%，建议复习核心概念后做针对性练习`);
  }
  const midNodes = weaknessChainDetails.value.slice(1, -1);
  if (midNodes.length > 0) {
    const weakestMid = midNodes.reduce((min, n) => n.mastery < min.mastery ? n : min, midNodes[0]);
    recs.push(`中间链路「${weakestMid.name}」是关键瓶颈，掌握度 ${Math.round(weakestMid.mastery * 100)}%`);
  }
  recs.push(`建议按根因链从底层向上逐个突破，每个节点达到 60% 以上再进入下一个`);
  return recs;
});

// 解锁链路增强数据
const unlockDirectList = computed(() => {
  if (!unlockAnalysis.value) return [];
  return Array.from(unlockDirectNodes.value)
    .map(id => nodes.value.find(n => n.id === id))
    .filter(Boolean) as Graph3dNode[];
});

const unlockChainList = computed(() => {
  if (!unlockAnalysis.value) return [];
  return Array.from(unlockChainNodes.value)
    .filter(id => !unlockDirectNodes.value.has(id))
    .map(id => nodes.value.find(n => n.id === id))
    .filter(Boolean) as Graph3dNode[];
});

// 解锁链路 Bloom 分布
const unlockBloomDist = computed(() => {
  const all = [...unlockDirectList.value, ...unlockChainList.value];
  const dist: Record<string, number> = {};
  all.forEach(n => { dist[n.bloom_level] = (dist[n.bloom_level] ?? 0) + 1; });
  return dist;
});

// 时光机增强数据
const forecastInsights = computed(() => {
  if (!forecastData.value || forecastData.value.forecast.length === 0) return null;
  const f = forecastData.value;
  const current = f.current_mastery;
  const last = f.forecast[f.forecast.length - 1];
  const futureMastery = last.p_learned;
  const delta = futureMastery - current;
  // 趋势
  const trend = delta > 0.05 ? 'up' : delta < -0.05 ? 'down' : 'stable';
  // 风险评估
  const ciWidth = last.ci_high - last.ci_low;
  const risk = ciWidth > 0.3 ? 'high' : ciWidth > 0.15 ? 'medium' : 'low';
  // 达成 80% 的里程碑
  const reachMastery = f.milestones.find(m => m.label.includes('掌握') || m.target >= 0.8);
  // 推荐动作
  const actions: string[] = [];
  if (current < 0.3) {
    actions.push('当前掌握度较低，建议先通过智灵讲解夯实基础概念');
  } else if (current < 0.6) {
    actions.push('掌握度处于上升期，建议结合错题练习加速突破');
  } else {
    actions.push('掌握度较好，建议通过变式题和高阶应用巩固');
  }
  if (trend === 'down') {
    actions.push('预测趋势下滑，可能存在遗忘，建议及时复习');
  }
  if (risk === 'high') {
    actions.push('预测置信区间较宽，建议增加练习频率以稳定掌握度');
  }
  if (reachMastery) {
    actions.push(`预计 D+${reachMastery.day} 可达成「${reachMastery.label}」（${Math.round(reachMastery.p_at_day * 100)}%）`);
  }
  return { current, futureMastery, delta, trend, risk, reachMastery, actions };
});

// ===== 图谱快照导出 =====
function exportSnapshot() {
  if (!chart) return;
  const url = chart.getDataURL({
    type: 'png',
    pixelRatio: 2,
    backgroundColor: '#fff',
  });
  const a = document.createElement('a');
  a.href = url;
  a.download = `knowledge-graph-${course.value}-${Date.now()}.png`;
  a.click();
}

// ===== 键盘快捷键 =====
function handleKeydown(e: KeyboardEvent) {
  if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
  switch (e.key) {
    case 'f': case 'F':
      fitGraph();
      break;
    case 'r': case 'R':
      resetGraphView();
      break;
    case '/':
      e.preventDefault();
      topSearchEl.value?.focus();
      break;
    case 'g': case 'G':
      toggleDock('graphrag');
      break;
    case 'p': case 'P':
      toggleDock('path');
      break;
    case 'l': case 'L':
      legendOpen.value = !legendOpen.value;
      break;
    case 'Enter':
      if (selected.value) {
        const idx = visibleNodesList.value.findIndex((node) => node.id === selected.value?.id);
        if (idx >= 0) chart?.dispatchAction({ type: 'focusNodeAdjacency', seriesIndex: 0, dataIndex: idx });
      }
      break;
    case 'Escape':
      closeOverlays();
      break;
    case 'Delete':
      showWorkspaceNotice('当前为只读学习视图，不会删除真实知识节点');
      break;
  }
}

// ===== 学习成就时间线（增强版里程碑） =====
const timelineEvents = computed(() => {
  const events: Array<{ icon: string; title: string; desc: string; unlocked: boolean; progress: number }> = [];
  const masteredCount = nodes.value.filter(n => n.mastery >= 0.8).length;
  const totalCount = nodes.value.length;
  const progressPct = totalCount > 0 ? Math.round((masteredCount / totalCount) * 100) : 0;

  const stages = [
    { icon: '01', title: '初次掌握', desc: '掌握第一个知识点', threshold: 1, count: masteredCount },
    { icon: '05', title: '渐入佳境', desc: '掌握 5 个知识点', threshold: 5, count: masteredCount },
    { icon: '50', title: '半程达成', desc: '掌握一半知识点', threshold: Math.ceil(totalCount * 0.5), count: masteredCount },
    { icon: '100', title: '完全掌握', desc: '掌握全部知识点', threshold: totalCount, count: masteredCount },
  ];

  for (const s of stages) {
    events.push({
      icon: s.icon,
      title: s.title,
      desc: s.desc,
      unlocked: s.count >= s.threshold,
      progress: s.threshold > 0 ? Math.min(Math.round((s.count / s.threshold) * 100), 100) : 0,
    });
  }
  return events;
});

const overallProgress = computed(() => {
  const mastered = nodes.value.filter(n => n.mastery >= 0.8).length;
  const total = nodes.value.length;
  return total > 0 ? Math.round((mastered / total) * 100) : 0;
});

// 根据筛选条件过滤节点
const filteredNodes = computed(() => {
  const clusterIds = activeCluster.value
    ? new Set(activeCluster.value.members.map((node) => node.id))
    : null;
  let pool = clusterIds ? nodes.value.filter((node) => clusterIds.has(node.id)) : nodes.value;
  // 章节聚焦：课程结构侧栏点击后只看该章节
  if (chapterFocus.value) {
    pool = pool.filter((n) => (n.bloom_level || "其他") === chapterFocus.value);
  }
  // 薄弱知识视角：只保留薄弱节点及其直接前置，隐藏健康节点
  if (perspective.value === "weakness") {
    const weakIds = new Set(
      pool
        .filter((n) => ((n.bkt_attempts && n.bkt_attempts > 0) || n.mastery > 0) && n.mastery < 0.6)
        .map((n) => n.id),
    );
    edges.value.forEach((e) => {
      if (weakIds.has(e.target) && e.relation === "prerequisite") weakIds.add(e.source);
    });
    pool = pool.filter((n) => weakIds.has(n.id));
  }
  // 学习路径视角：路径节点 + 必要前置
  if (perspective.value === "path" && pathNodeIds.value.size > 0) {
    const keep = new Set(pathNodeIds.value);
    edges.value.forEach((e) => {
      if (keep.has(e.target) && e.relation === "prerequisite") keep.add(e.source);
    });
    pool = pool.filter((n) => keep.has(n.id));
  }
  // 专注模式：只显示学习路径上的节点
  if (viewMode.value === 'focus' && pathNodeIds.value.size > 0) {
    pool = pool.filter(n => pathNodeIds.value.has(n.id));
  }

  if (nodeFilter.value === 'all') return pool;
  
  return pool.filter(n => {
    const hasDone = (n.bkt_attempts && n.bkt_attempts > 0) || n.mastery > 0;
    const isMastered = n.mastery >= 0.8;
    const isAtRisk = n.bkt_trend === 'declining';
    const isRecommended = isNodeOnPath(n.id) && !isMastered;
    
    switch (nodeFilter.value) {
      case 'mastered':
        return isMastered;
      case 'learning':
        return hasDone && !isMastered;
      case 'not_started':
        return !hasDone;
      case 'at_risk':
        return isAtRisk;
      case 'recommended':
        return isRecommended;
      default:
        return true;
    }
  });
});

const visibleNodesList = computed(() => {
  const visible = new Set<string>();
  const sourceNodes = filteredNodes.value;
  if (!sourceNodes.length) return [];

  // 聚类成员不一定构成单根有向树。聚类钻取时若继续从根节点沿边展开，
  // 无法从首个根到达的成员会被误删，导致“7 个知识点”实际只显示 1 个。
  if (activeCluster.value) return sourceNodes;
  
  // Find roots (in-degree == 0)
  const inDegree = new Map<string, number>();
  sourceNodes.forEach(n => inDegree.set(n.id, 0));
  edges.value.forEach(e => {
    if (sourceNodes.find(n => n.id === e.source) && sourceNodes.find(n => n.id === e.target)) {
      inDegree.set(e.target, (inDegree.get(e.target) || 0) + 1);
    }
  });
  
  let roots = sourceNodes.filter(n => inDegree.get(n.id) === 0);
  if (roots.length === 0) {
    roots = [sourceNodes[0]];
  }
  
  roots.forEach(r => visible.add(r.id));
  
  // Iteratively expand
  let added = true;
  while(added) {
    added = false;
    for (const e of edges.value) {
      if (visible.has(e.source) && expandedNodes.value.has(e.source) && !visible.has(e.target)) {
        const targetInFiltered = sourceNodes.find(n => n.id === e.target);
        if (targetInFiltered) {
          visible.add(e.target);
          added = true;
        }
      }
    }
  }
  return sourceNodes.filter(n => visible.has(n.id));
});

const visibleEdgesList = computed(() => {
  const vIds = new Set(visibleNodesList.value.map(n => n.id));
  return edges.value.filter(
    (e) => vIds.has(e.source) && vIds.has(e.target) && !hiddenRelations.value.has(e.relation),
  );
});

// 学习路径节点集合
const pathNodeIds = computed(() => new Set(learningPath.value.map(p => p.kp_id)));

// 判断节点是否在学习路径上
function isNodeOnPath(nodeId: string): boolean {
  return showPathHighlight.value && pathNodeIds.value.has(nodeId);
}

// 获取节点在学习路径中的位置
function getNodePathIndex(nodeId: string): number {
  return learningPath.value.findIndex(p => p.kp_id === nodeId);
}

// 判断节点是否是当前学习位置
function isCurrentLearningNode(nodeId: string): boolean {
  if (!showPathHighlight.value || learningPath.value.length === 0) return false;
  const currentKp = learningPath.value[currentPathIndex.value];
  return currentKp?.kp_id === nodeId;
}

const RELATION_LABELS: Record<string, string> = {
  prerequisite: "先修",
  related: "相关",
  part_of: "从属",
  contains: "包含",
  extends: "延伸",
  applies_to: "应用",
  similar_to: "相似",
  confusable: "易混",
  easily_confused: "易混",
  error_propagation: "错误传播",
  semantic: "语义关联",
};

// Plan D · 3.4 — BKT mastery hover 用的趋势标签 / 箭头 / 颜色
const TREND_LABELS: Record<string, string> = {
  improving: "上升",
  declining: "下滑",
  stable: "平稳",
  insufficient_data: "数据不足",
};
const TREND_ARROWS: Record<string, string> = {
  improving: "↗",
  declining: "↘",
  stable: "→",
  insufficient_data: "?",
};
const TREND_COLORS: Record<string, string> = {
  improving: "#2f9f6b",
  declining: "#c86a5a",
  stable: "#94a3b8",
  insufficient_data: "#cbd5e1",
};

// 课程显示名由 /knowledge/courses 的 course.yaml 清单动态填充（平台化改造）
const COURSE_LABELS: Record<string, string> = {};

// ============================================================
// 图谱工作区 v2：布局模式 / Zoom 分层标签 / 章节聚焦 / 关系语义
// ============================================================
type LayoutMode = "cluster" | "force" | "path" | "network";
const layoutMode = ref<LayoutMode>("cluster");
const LAYOUT_LABELS: Record<LayoutMode, string> = {
  cluster: "章节分层",
  force: "力导向",
  path: "学习路径",
  network: "关系网络",
};
const layoutOptions = Object.entries(LAYOUT_LABELS) as Array<[LayoutMode, string]>;

// —— 图谱视角：一张图六种读法（决定节点范围/关系权重/布局/标签策略） ——
type Perspective = "structure" | "cluster" | "path" | "mastery" | "weakness" | "network";
const perspective = ref<Perspective>("structure");
const PERSPECTIVE_LABELS: Record<Perspective, string> = {
  structure: "课程结构",
  cluster: "章节聚类",
  path: "学习路径",
  mastery: "掌握状态",
  weakness: "薄弱知识",
  network: "关系网络",
};
const perspectiveOptions = Object.entries(PERSPECTIVE_LABELS) as Array<[Perspective, string]>;
/** 结构性关系：课程结构视角下唯一保持完整视觉权重的边 */
const STRUCT_RELATIONS = new Set(["prerequisite", "part_of", "contains"]);

function setPerspective(next: Perspective) {
  if (perspective.value === next) return;
  perspective.value = next;
  layoutMode.value = next === "path" ? "path" : next === "network" ? "network" : "cluster";
  if (next === "path") showPathHighlight.value = true;
  savedZoom.value = 0.9;
  savedCenter.value = null;
  zoomTier.value = zoomToTier(savedZoom.value);
  renderChart();
  showWorkspaceNotice(`已切换到「${PERSPECTIVE_LABELS[next]}」视角`);
}
const perspectiveModel = computed({
  get: () => perspective.value,
  set: (value: Perspective) => setPerspective(value),
});

const nodeGroupMap = computed(() => {
  const map = new Map<string, string>();
  nodes.value.forEach((n) => map.set(n.id, n.bloom_level || "其他"));
  return map;
});

/** 每个章节的“头节点”（分区中心）：远距离缩放时只保留它的标签 */
const clusterHeadByGroup = computed(() => {
  const heads = new Map<string, string>();
  for (const [label, items] of chapterGroups.value) {
    const sorted = [...items].sort((a, b) => TIER_SIZE[nodeTier(b)] - TIER_SIZE[nodeTier(a)]);
    if (sorted[0]) heads.set(label, sorted[0].id);
  }
  return heads;
});
const clusterHeadIds = computed(() => new Set(clusterHeadByGroup.value.values()));

// —— 章节折叠：默认每章聚合为一个章节节点，点击展开查看全部知识点 ——
const expandedChapters = ref<Set<string>>(new Set());
const CHAPTER_NODE_PREFIX = "chapter::";

/** 折叠只在章节类布局下生效；薄弱视角本身就是小子集，不折叠 */
function chapterCollapseActive() {
  return graphLevel.value === "nodes" && !activeCluster.value && layoutMode.value === "cluster" && perspective.value !== "weakness";
}

function isChapterExpanded(label: string) {
  return expandedChapters.value.has(label) || chapterFocus.value === label;
}

function expandChapter(label: string) {
  const next = new Set(expandedChapters.value);
  next.add(label);
  expandedChapters.value = next;
  renderChart();
  showWorkspaceNotice(`已展开「${label}」章节，点击工具栏图层按钮可整体收起`);
}

const allChaptersExpanded = computed(() =>
  [...chapterGroups.value.keys()].every((label) => isChapterExpanded(label)),
);

function toggleAllChapters() {
  expandedChapters.value = allChaptersExpanded.value
    ? new Set()
    : new Set(chapterGroups.value.keys());
  savedCenter.value = null;
  renderChart();
  showWorkspaceNotice(allChaptersExpanded.value ? "已展开全部章节" : "已收起为章节总览");
}
const chapterFocus = ref<string | null>(null);
const hiddenRelations = ref<Set<string>>(new Set());
const recentNodes = ref<Graph3dNode[]>([]);
const savedZoom = ref(0.9);
const savedCenter = ref<[number, number] | null>(null);
const zoomTier = ref<0 | 1 | 2>(1);
/** 每门课程各自记住缩放、布局、视角与筛选，切课往返不丢状态 */
const viewStateByCourse = new Map<
  string,
  {
    zoom: number;
    center: [number, number] | null;
    layout: LayoutMode;
    filter: FilterType;
    chapter: string | null;
    view: string;
  }
>();

function zoomToTier(zoom: number): 0 | 1 | 2 {
  if (zoom < 0.78) return 0;
  if (zoom < 1.55) return 1;
  return 2;
}

// —— 节点分级：根 / 章节 / 核心 / 普通 / 叶子（按出入度） ——
const degreeMaps = computed(() => {
  const outDeg = new Map<string, number>();
  const inDeg = new Map<string, number>();
  for (const e of edges.value) {
    outDeg.set(e.source, (outDeg.get(e.source) || 0) + 1);
    inDeg.set(e.target, (inDeg.get(e.target) || 0) + 1);
  }
  return { outDeg, inDeg };
});

type NodeTier = "root" | "chapter" | "core" | "normal" | "leaf";
const TIER_SIZE: Record<NodeTier, number> = { root: 58, chapter: 46, core: 38, normal: 30, leaf: 24 };

function nodeTier(n: Graph3dNode): NodeTier {
  const { outDeg, inDeg } = degreeMaps.value;
  const out = outDeg.get(n.id) || 0;
  const inn = inDeg.get(n.id) || 0;
  if (inn === 0 && out >= 2) return "root";
  if (out >= 4) return "chapter";
  if (out + inn >= 4) return "core";
  if (out === 0 && inn <= 1) return "leaf";
  return "normal";
}

// —— 章节分组（bloom_level 作为课程结构维度） ——
const chapterGroups = computed(() => {
  const grouped = new Map<string, Graph3dNode[]>();
  for (const node of nodes.value) {
    const key = node.bloom_level || "其他";
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key)!.push(node);
  }
  return grouped;
});

// —— 章节聚类布局：每章一个分区中心，节点按黄金角螺旋展开，铺满画布 ——
const clusterPositions = computed(() => {
  const positions = new Map<string, { x: number; y: number }>();
  const groups = [...chapterGroups.value.entries()];
  if (!groups.length) return positions;
  const cols = Math.max(2, Math.ceil(Math.sqrt(groups.length)));
  // 分区间距按组内最大节点数自适应：章节之间保持明显空隙，组内相对紧凑
  const maxCount = Math.max(...groups.map(([, items]) => items.length));
  const spread = 130 + Math.sqrt(maxCount) * 96;
  const cellW = spread * 2 + 320;
  const cellH = spread * 1.7 + 260;
  groups.forEach(([, items], gi) => {
    const cx = (gi % cols) * cellW;
    const cy = Math.floor(gi / cols) * cellH;
    const sorted = [...items].sort((a, b) => TIER_SIZE[nodeTier(b)] - TIER_SIZE[nodeTier(a)]);
    sorted.forEach((node, i) => {
      if (i === 0) {
        positions.set(node.id, { x: cx, y: cy });
        return;
      }
      const radius = 130 + Math.sqrt(i) * 96;
      const angle = i * 2.399963; // 黄金角：避免节点排成直线或重叠
      positions.set(node.id, { x: cx + Math.cos(angle) * radius, y: cy + Math.sin(angle) * radius * 0.85 });
    });
  });
  return positions;
});

// —— 学习路径布局：路径蛇形主轴 + 其余节点退到下方网格 ——
const pathPositions = computed(() => {
  const positions = new Map<string, { x: number; y: number }>();
  const stepX = 220;
  const perRow = 6;
  learningPath.value.forEach((step, i) => {
    const row = Math.floor(i / perRow);
    const col = i % perRow;
    const x = (row % 2 === 0 ? col : perRow - 1 - col) * stepX;
    positions.set(step.kp_id, { x, y: row * 250 });
  });
  const rest = nodes.value.filter((n) => !positions.has(n.id));
  const baseY = Math.ceil(Math.max(1, learningPath.value.length) / perRow) * 250 + 340;
  rest.forEach((n, i) => {
    positions.set(n.id, { x: (i % 8) * 180, y: baseY + Math.floor(i / 8) * 156 });
  });
  return positions;
});

function setLayoutMode(mode: LayoutMode) {
  if (layoutMode.value === mode) return;
  layoutMode.value = mode;
  savedZoom.value = 0.9;
  savedCenter.value = null;
  renderChart();
  showWorkspaceNotice(`布局已切换为「${LAYOUT_LABELS[mode]}」`);
}

// —— 章节聚焦：课程结构 → 图谱双向联动 ——
function toggleChapterFocus(label: string) {
  chapterFocus.value = chapterFocus.value === label ? null : label;
  savedCenter.value = null;
  savedZoom.value = chapterFocus.value ? 1.1 : 0.9;
  renderChart();
  showWorkspaceNotice(chapterFocus.value ? `已聚焦章节「${label}」` : "已恢复全部章节");
}

// —— 关系类型显隐（图例 / 统计面板联动） ——
function toggleRelation(relation: string) {
  const next = new Set(hiddenRelations.value);
  if (next.has(relation)) next.delete(relation);
  else next.add(relation);
  hiddenRelations.value = next;
  renderChart();
}

/** 统计面板「只看某类关系」：再次点击恢复全部 */
function soloRelation(relation: string) {
  const others = relationTypes.value.map((item) => item.key).filter((key) => key !== relation);
  const isSolo = !hiddenRelations.value.has(relation) && others.every((key) => hiddenRelations.value.has(key));
  hiddenRelations.value = isSolo ? new Set() : new Set(others);
  renderChart();
  showWorkspaceNotice(isSolo ? "已恢复全部关系类型" : `只显示「${RELATION_LABELS[relation] ?? relation}」关系`);
}

function clearGraphFilters() {
  nodeFilter.value = "all";
  chapterFocus.value = null;
  hiddenRelations.value = new Set();
  viewMode.value = "explore";
  renderChart();
  showWorkspaceNotice("已清除全部图谱筛选");
}

/** 成就 / 统计 / 图例 → 图谱状态筛选联动 */
function filterFromPanel(filter: FilterType, label: string) {
  nodeFilter.value = nodeFilter.value === filter ? "all" : filter;
  showWorkspaceNotice(nodeFilter.value === "all" ? "已恢复全部节点" : `图谱已筛选：${label}`);
}

// —— 关系线语义样式（按类型区分实线/虚线/点划线与低饱和色） ——
const RELATION_STYLE: Record<string, { color: string; type: "solid" | "dashed" | "dotted" | number[]; width: number }> = {
  prerequisite: { color: "#c8c1b4", type: "solid", width: 1.6 },
  part_of: { color: "#d9d4cc", type: "solid", width: 1.1 },
  contains: { color: "#d9d4cc", type: "solid", width: 1.1 },
  related: { color: "#b9c8d6", type: [4, 4], width: 1.2 },
  similar_to: { color: "#b9c8d6", type: [4, 4], width: 1.2 },
  extends: { color: "#c9bfa5", type: [8, 4], width: 1.3 },
  applies_to: { color: "#c9bfa5", type: [8, 4], width: 1.2 },
  confusable: { color: "#dfa96e", type: [8, 3, 2, 3], width: 1.5 },
  easily_confused: { color: "#dfa96e", type: [8, 3, 2, 3], width: 1.5 },
  error_propagation: { color: "#d8a09a", type: "solid", width: 1.5 },
  semantic: { color: "#c9c2ef", type: [3, 4], width: 1.2 },
};

function relationStyle(relation: string) {
  return RELATION_STYLE[relation] || { color: "#d9d4cc", type: "solid" as const, width: 1.2 };
}

const relationTypes = computed(() => {
  const counts = new Map<string, number>();
  edges.value.forEach((e) => counts.set(e.relation, (counts.get(e.relation) || 0) + 1));
  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .map(([key, count]) => ({ key, count, label: RELATION_LABELS[key] ?? key, style: relationStyle(key) }));
});

// —— 面板分析数据（全部由真实 nodes/edges 计算） ——
const nodeStateCounts = computed(() => {
  let mastered = 0;
  let learning = 0;
  let weak = 0;
  let pending = 0;
  for (const n of nodes.value) {
    const hasDone = (n.bkt_attempts && n.bkt_attempts > 0) || n.mastery > 0;
    if (n.mastery >= 0.8) mastered += 1;
    else if (hasDone && n.mastery < 0.3) weak += 1;
    else if (hasDone) learning += 1;
    else pending += 1;
  }
  return { mastered, learning, weak, pending };
});

const chapterStats = computed(() =>
  [...chapterGroups.value.entries()].map(([label, items]) => ({
    label,
    count: items.length,
    mastery: items.length
      ? Math.round((items.reduce((sum, n) => sum + n.mastery, 0) / items.length) * 100)
      : 0,
    weak: items.filter((n) => n.mastery < 0.6).length,
  })),
);
const completedChapterCount = computed(() => chapterStats.value.filter((c) => c.mastery >= 80).length);

const dependencyInsights = computed(() => {
  const { outDeg, inDeg } = degreeMaps.value;
  let topOut: Graph3dNode | null = null;
  let topIn: Graph3dNode | null = null;
  for (const n of nodes.value) {
    if (!topOut || (outDeg.get(n.id) || 0) > (outDeg.get(topOut.id) || 0)) topOut = n;
    if (!topIn || (inDeg.get(n.id) || 0) > (inDeg.get(topIn.id) || 0)) topIn = n;
  }
  const isolatedCount = nodes.value.filter(
    (n) => !(outDeg.get(n.id) || 0) && !(inDeg.get(n.id) || 0),
  ).length;
  return {
    topOut,
    topOutCount: topOut ? outDeg.get(topOut.id) || 0 : 0,
    topIn,
    topInCount: topIn ? inDeg.get(topIn.id) || 0 : 0,
    isolatedCount,
  };
});

const nextAchievement = computed(() => timelineEvents.value.find((event) => !event.unlocked) || null);

// —— 节点详情：前置 / 后续关系（本地边数据即可计算，点击定位） ——
const selectedPrereqs = computed(() => {
  if (!selected.value) return [];
  return edges.value
    .filter((e) => e.target === selected.value!.id && e.relation === "prerequisite")
    .map((e) => nodes.value.find((n) => n.id === e.source))
    .filter((n): n is Graph3dNode => Boolean(n));
});
const selectedNextNodes = computed(() => {
  if (!selected.value) return [];
  return edges.value
    .filter((e) => e.source === selected.value!.id)
    .map((e) => ({ node: nodes.value.find((n) => n.id === e.target), relation: e.relation }))
    .filter((item): item is { node: Graph3dNode; relation: string } => Boolean(item.node))
    .slice(0, 8);
});

function rememberRecent(node: Graph3dNode) {
  recentNodes.value = [node, ...recentNodes.value.filter((item) => item.id !== node.id)].slice(0, 6);
}

const courseTreeGroups = computed(() => {
  const query = courseTreeQuery.value.trim().toLowerCase();
  const source = query
    ? nodes.value.filter((node) => `${node.name} ${node.id} ${node.bloom_level}`.toLowerCase().includes(query))
    : nodes.value;
  const grouped = new Map<string, Graph3dNode[]>();
  for (const node of source) {
    const key = node.bloom_level || "其他知识点";
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key)!.push(node);
  }
  return [...grouped.entries()].map(([label, items]) => ({
    label,
    items: items.sort((a, b) => a.mastery - b.mastery),
    mastery: items.length
      ? Math.round((items.reduce((sum, node) => sum + node.mastery, 0) / items.length) * 100)
      : 0,
    weakCount: items.filter((node) => node.mastery < 0.6).length,
  }));
});

const relationTypeCount = computed(() => new Set(edges.value.map((edge) => edge.relation)).size);
const learningCount = computed(() =>
  nodes.value.filter((node) => node.mastery > 0 && node.mastery < 0.8).length,
);

function chooseCourse(nextCourse: string) {
  course.value = nextCourse;
  coursePanelOpen.value = false;
}

async function locateNode(node: Graph3dNode) {
  // 目标节点所在章节处于折叠态时先展开
  const group = nodeGroupMap.value.get(node.id);
  if (chapterCollapseActive() && group && !isChapterExpanded(group)) {
    expandChapter(group);
  }
  await selectNode(node);
  const idx = displayedNodeIds.indexOf(node.id);
  if (idx >= 0) {
    chart?.dispatchAction({ type: "focusNodeAdjacency", seriesIndex: 0, dataIndex: idx });
    chart?.dispatchAction({ type: "highlight", seriesIndex: 0, dataIndex: idx });
  }
}

// ---- 选中节点详情 ----
const selected = ref<Graph3dNode | null>(null);
const selectedDetail = ref<Record<string, any> | null>(null);
const selectedNeighbors = ref<Array<Record<string, any>>>([]);

// ---- 搜索 ----
const searchQuery = ref("");
const searching = ref(false);
const searchResults = ref<Array<Record<string, any>>>([]);

const chartEl = ref<HTMLDivElement | null>(null);
let chart: echarts.ECharts | null = null;
/** 最近一次渲染的节点顺序（含聚合章节节点），供 highlight/locate 用 */
let displayedNodeIds: string[] = [];

async function load(autoFallback = true) {
  loading.value = true;
  error.value = "";
  const results = await Promise.allSettled([
    getGraph3d(userId.value, course.value, 120),
    getGraphStats(),
    listCourses(),
    getLearningPath(userId.value, course.value),
  ]);
  if (results[1].status === "fulfilled") globalStats.value = results[1].value;
  if (results[2].status === "fulfilled") {
    const list: string[] = [];
    for (const c of results[2].value.courses ?? []) {
      if (typeof c === "string") {
        list.push(c);
        continue;
      }
      const id = String((c as any).id ?? (c as any).name ?? "");
      if (!id) continue;
      list.push(id);
      const label = String((c as any).display_name ?? "");
      if (label) COURSE_LABELS[id] = label;
    }
    if (list.length) courses.value = list;
  }
  // 加载学习路径
  if (results[3].status === "fulfilled") {
    learningPath.value = results[3].value.path ?? [];
    currentPathIndex.value = results[3].value.current_index ?? 0;
  }
  if (results[0].status === "fulfilled") {
    nodes.value = results[0].value.nodes ?? [];
    edges.value = results[0].value.edges ?? [];
    stats.value = results[0].value.stats ?? {};
    expandedNodes.value = new Set(nodes.value.map((node) => node.id));
    selected.value = null;
    selectedDetail.value = null;
    graphRagNodeIds.value = new Set();
    if (!nodes.value.length) {
      // 当前课程没有图谱节点时，自动切到第一个有节点的课程
      if (autoFallback) {
        for (const c of courses.value.filter((c) => c !== course.value)) {
          try {
            const probe = await getGraph3d(userId.value, c, 120);
            if (probe.nodes?.length) {
              course.value = c;
              nodes.value = probe.nodes;
              edges.value = probe.edges ?? [];
              stats.value = probe.stats ?? {};
              break;
            }
          } catch {
            /* 尝试下一个课程 */
          }
        }
      }
      if (!nodes.value.length) error.value = "该课程暂无知识图谱节点。";
    }
  } else {
    error.value = "知识图谱服务未连接，请先启动后端。";
  }
  loading.value = false;
  renderChart();
}

function masteryColor(mastery: number): string {
  if (mastery >= 0.8) return "#2f9f6b";
  if (mastery >= 0.3) return "#d89229";
  return "#c86a5a";
}
/** 按知识点 id 稳定分配色相（0-360），保证每个球颜色不同且刷新不变 */
function nodeHue(id: string): number {
  let hash = 0;
  for (let i = 0; i < id.length; i++) {
    hash = (hash * 31 + id.charCodeAt(i)) >>> 0;
  }
  return hash % 360;
}

function graphSphereFill(color: any) {
  if (typeof color !== "string") return color; // 已是每球独立色相的渐变对象，直接用
  const rim = color === "#9aa3af" ? "#6b7280" : color;
  const glow = color === "#9aa3af" ? "#f8fafc" : "#fffaf4";
  return {
    type: "radial",
    x: 0.34,
    y: 0.26,
    r: 0.92,
    colorStops: [
      { offset: 0, color: "#ffffff" },
      { offset: 0.18, color: glow },
      { offset: 0.58, color },
      { offset: 1, color: rim },
    ],
  } as any;
}

// ===== 学习动作入口 =====
function askZhiling(node: Graph3dNode) {
  // 跳转到聊天页面，携带知识点信息，自动触发提问
  router.push({
    path: '/chat',
    query: {
      kp_id: node.id,
      kp_name: node.name,
      ask: '1', // 标记需要自动提问
    },
  });
}

function startPractice(node: Graph3dNode) {
  // 跳转到错题本页面，筛选当前知识点相关练习题
  router.push({
    path: '/mistakes',
    query: {
      kp_id: node.id,
      kp_name: node.name,
      course: node.course,
      mode: 'practice', // 标记为练习模式
    },
  });
}

function viewResources(node: Graph3dNode) {
  // 跳转到资源页面，筛选当前知识点相关资源
  router.push({
    path: '/resources',
    query: {
      kp_id: node.id,
      kp_name: node.name,
      filter: 'related',
    },
  });
}

// ===== 掌握度趋势图 =====
async function loadTrendData(kpId: string) {
  try {
    const res = await getMasteryHistory(userId.value, kpId, trendRange.value);
    trendData.value = res.history ?? [];
    renderTrendChart();
  } catch (e) {
    console.error('加载趋势数据失败:', e);
    trendData.value = [];
  }
}

function renderTrendChart() {
  if (!trendChartEl.value) return;
  if (!trendChart) {
    trendChart = echarts.init(trendChartEl.value);
  }
  
  if (trendData.value.length === 0) {
    trendChart.clear();
    return;
  }

  const dates = trendData.value.map(d => d.date.slice(5)); // MM-DD
  const masteryValues = trendData.value.map(d => Math.round(d.mastery * 100));
  const attemptsValues = trendData.value.map(d => d.attempts);

  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        const idx = params[0].dataIndex;
        const d = trendData.value[idx];
        return `<div style="font-size:12px">
          <div>${d.date}</div>
          <div>掌握度: <b>${Math.round(d.mastery * 100)}%</b></div>
          <div>答题: ${d.correct}/${d.attempts} 正确</div>
        </div>`;
      },
    },
    grid: {
      left: 10,
      right: 10,
      top: 30,
      bottom: 20,
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: dates,
      axisLine: { lineStyle: { color: '#e5e7eb' } },
      axisLabel: { color: '#6b7280', fontSize: 10 },
    },
    yAxis: [
      {
        type: 'value',
        min: 0,
        max: 100,
        axisLabel: { formatter: '{value}%', color: '#6b7280', fontSize: 10 },
        splitLine: { lineStyle: { color: '#f3f4f6' } },
      },
      {
        type: 'value',
        min: 0,
        show: false,
      },
    ],
    series: [
      {
        name: '掌握度',
        type: 'line',
        data: masteryValues,
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { color: '#ea5a1a', width: 2 },
        itemStyle: { color: '#ea5a1a' },
        areaStyle: {
          color: new (echarts as any).graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(234, 90, 26, 0.3)' },
            { offset: 1, color: 'rgba(234, 90, 26, 0.05)' },
          ]),
        },
      },
      {
        name: '答题数',
        type: 'bar',
        yAxisIndex: 1,
        data: attemptsValues,
        barWidth: 8,
        itemStyle: { color: '#94a3b8', borderRadius: 2 },
      },
    ],
  };

  trendChart.setOption(option);
}

function toggleTrendChart() {
  showTrendChart.value = !showTrendChart.value;
  if (showTrendChart.value && selected.value) {
    void loadTrendData(selected.value.id);
  }
}

// ===== 知识对比功能 =====
function toggleCompareMode() {
  compareMode.value = !compareMode.value;
  if (!compareMode.value) {
    compareNodes.value = [];
  }
}

function addToCompare(node: Graph3dNode) {
  if (compareNodes.value.length >= 2) {
    compareNodes.value = [compareNodes.value[1], node];
  } else if (!compareNodes.value.find(n => n.id === node.id)) {
    compareNodes.value.push(node);
  }
  renderCompareChart();
}

function removeFromCompare(nodeId: string) {
  compareNodes.value = compareNodes.value.filter(n => n.id !== nodeId);
  renderCompareChart();
}

function renderCompareChart() {
  if (!compareChartEl.value) return;
  if (!compareChart) {
    compareChart = echarts.init(compareChartEl.value);
  }
  
  if (compareNodes.value.length === 0) {
    compareChart.clear();
    return;
  }

  const categories = ['掌握度', '练习量', 'Bloom层级'];
  const series = compareNodes.value.map((node, idx) => {
    const color = idx === 0 ? '#ea5a1a' : '#3b82f6';
    const bloomLevelMap: Record<string, number> = {
      'remember': 1, 'understand': 2, 'apply': 3,
      'analyze': 4, 'evaluate': 5, 'create': 6
    };
    const bloomLevel = bloomLevelMap[node.bloom_level?.toLowerCase()] || 3;
    
    return {
      name: node.name,
      type: 'radar' as const,
      symbol: 'none',
      lineStyle: { color, width: 2 },
      areaStyle: { color, opacity: 0.2 },
      itemStyle: { color },
      data: [{
        value: [
          Math.round(node.mastery * 100),
          Math.min((node.bkt_attempts || 0) * 10, 100),
          (bloomLevel / 6) * 100,
        ],
        name: node.name,
      }],
    };
  });

  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'item',
      formatter: (params: any) => {
        const node = compareNodes.value.find(n => n.name === params.name);
        if (!node) return params.name;
        return `<div style="font-size:12px">
          <b>${node.name}</b><br/>
          掌握度: ${Math.round(node.mastery * 100)}%<br/>
          答题数: ${node.bkt_attempts || 0}<br/>
          Bloom: ${node.bloom_level}
        </div>`;
      },
    },
    legend: {
      data: compareNodes.value.map(n => n.name),
      bottom: 0,
      textStyle: { fontSize: 11 },
    },
    radar: {
      indicator: categories.map(c => ({ name: c, max: 100 })),
      radius: '60%',
      axisName: { fontSize: 11, color: '#6b7280' },
      splitArea: { areaStyle: { color: ['#f9fafb', '#f3f4f6'] } },
    },
    series,
  };

  compareChart.setOption(option, true);
}

function renderChart() {
  if (!chartEl.value) return;
  if (!chart) {
    chart = echarts.init(chartEl.value);
    chart.on("click", (params: any) => {
      if (params.dataType === "node" && params.data?.clusterMeta) {
        selectCluster(params.data.clusterMeta as GraphCluster);
        return;
      }
      if (params.dataType === "node" && params.data?.courseRoot) {
        showAllCourseNodes();
        return;
      }
      // 聚合章节节点：点击展开本章全部知识点
      if (params.dataType === "node" && params.data?.chapterKey) {
        expandChapter(params.data.chapterKey as string);
        return;
      }
      if (params.dataType === "node" && params.data?.meta) {
        void selectNode(params.data.meta as Graph3dNode);
      }
    });
    chart.on("dblclick", (params: any) => {
      if (params.dataType !== "node" || !params.data?.meta) return;
      const node = params.data.meta as Graph3dNode;
      expandedNodes.value.add(node.id);
      void locateNode(node);
      renderChart();
    });
    chart.on("contextmenu", (params: any) => {
      if (params.dataType !== "node" || !params.data?.meta) return;
      params.event?.event?.preventDefault?.();
      const dom = chartEl.value?.getBoundingClientRect();
      contextMenu.value = {
        x: Math.min((params.event?.offsetX || 0) + (dom?.left || 0), window.innerWidth - 220),
        y: Math.min((params.event?.offsetY || 0) + (dom?.top || 0), window.innerHeight - 320),
        node: params.data.meta as Graph3dNode,
      };
    });
    chart.getZr().on('click', (event: any) => {
      contextMenu.value = null;
      if (!event.target) chart?.dispatchAction({ type: 'downplay' });
    });
    // Zoom 追踪：保存缩放/中心（供重绘与切课恢复），跨档位时切换标签显示策略
    chart.on("graphroam", () => {
      const series: any = (chart?.getOption() as any)?.series?.[0];
      if (!series) return;
      if (typeof series.zoom === "number") savedZoom.value = series.zoom;
      if (Array.isArray(series.center)) savedCenter.value = series.center as [number, number];
      const tier = zoomToTier(savedZoom.value);
      if (tier !== zoomTier.value) {
        zoomTier.value = tier;
        renderChart();
      }
    });
  }
  if (!nodes.value.length) {
    chart.clear();
  }

  if (graphLevel.value === "clusters" && nodes.value.length) {
    const clusterNodes = graphClusters.value;
    const canvasWidth = chartEl.value.clientWidth || 1000;
    const canvasHeight = chartEl.value.clientHeight || 720;
    const compactClusterView = canvasWidth < 680;
    const radiusX = compactClusterView
      ? Math.max(120, Math.min(155, canvasWidth * 0.34))
      : Math.max(330, Math.min(520, canvasWidth * 0.32));
    const radiusY = compactClusterView
      ? Math.max(185, Math.min(250, canvasHeight * 0.3))
      : Math.max(220, Math.min(350, canvasHeight * 0.33));
    const rootId = "course::root";
    const courseName = COURSE_LABELS[course.value] ?? course.value;
    const clusterData = clusterNodes.map((cluster, index) => {
      const angle = -Math.PI / 2 + (index / Math.max(clusterNodes.length, 1)) * Math.PI * 2;
      return {
        id: cluster.id,
        name: cluster.label,
        x: Math.cos(angle) * radiusX,
        y: Math.sin(angle) * radiusY,
        symbol: "circle",
        symbolSize: Math.min(78, 48 + cluster.members.length * 2.2),
        clusterMeta: cluster,
        label: {
          show: true,
          position: compactClusterView ? "bottom" : Math.cos(angle) > 0.2 ? "left" : "right",
          distance: compactClusterView ? 5 : 10,
          color: "#292620",
          fontSize: compactClusterView ? 10.5 : 13,
          fontWeight: 700,
          backgroundColor: "rgba(255,255,255,.92)",
          borderColor: "rgba(35,31,25,.1)",
          borderWidth: 1,
          borderRadius: 7,
          padding: compactClusterView ? [3, 5] : [5, 8],
          width: compactClusterView ? 86 : undefined,
          overflow: compactClusterView ? "truncate" : undefined,
          formatter: compactClusterView
            ? cluster.label
            : `${cluster.label}\n{meta|${cluster.members.length} 个知识点 · 掌握 ${Math.round(cluster.averageMastery * 100)}%${cluster.weakCount ? ` · ${cluster.weakCount} 个薄弱` : ""}}`,
          rich: { meta: { color: "#777169", fontSize: 10.5, lineHeight: 17, fontWeight: 500 } },
        },
        itemStyle: {
          color: cluster.softColor,
          borderColor: cluster.color,
          borderWidth: 3,
          shadowBlur: 18,
          shadowColor: `${cluster.color}33`,
        },
      };
    });
    const rootLinks = clusterNodes.map((cluster) => ({
      source: rootId,
      target: cluster.id,
      lineStyle: { color: cluster.color, opacity: 0.34, width: 1.6, curveness: 0.08 },
    }));
    const relationLinks = clusterRelations.value.map((relation) => ({
      source: relation.source,
      target: relation.target,
      relationCount: relation.count,
      lineStyle: {
        color: "#bcb6ad",
        opacity: Math.min(0.38, 0.12 + relation.count * 0.035),
        width: Math.min(2.4, 0.8 + Math.log2(relation.count + 1) * 0.45),
        type: "dashed",
        curveness: 0.16,
      },
    }));
    displayedNodeIds = [rootId, ...clusterNodes.map((cluster) => cluster.id)];
    chart.setOption({
      tooltip: {
        formatter: (params: any) => {
          if (params.data?.courseRoot) return `<b>${courseName}</b><br/>${nodes.value.length} 个知识点 · ${clusterNodes.length} 个聚类`;
          const cluster = params.data?.clusterMeta as GraphCluster | undefined;
          if (cluster) return `<b>${cluster.label}</b><br/>${cluster.members.length} 个知识点<br/>平均掌握 ${Math.round(cluster.averageMastery * 100)}%<br/>点击查看聚类摘要`;
          if (params.data?.relationCount) return `${params.data.relationCount} 条跨聚类关系`;
          return "";
        },
      },
      series: [{
        type: "graph",
        layout: "none",
        roam: true,
        zoom: savedZoom.value,
        center: savedCenter.value ?? undefined,
        scaleLimit: { min: 0.3, max: 5 },
        edgeSymbol: ["none", "arrow"],
        edgeSymbolSize: 6,
        emphasis: { focus: "adjacency", lineStyle: { opacity: 0.9, width: 2.5 } },
        data: [{
          id: rootId,
          name: courseName,
          x: 0,
          y: 0,
          symbol: "circle",
          symbolSize: 82,
          courseRoot: true,
          label: {
            show: true,
            position: compactClusterView ? "bottom" : "right",
            distance: compactClusterView ? 8 : 14,
            color: "#1d1a16",
            fontSize: compactClusterView ? 12 : 15,
            fontWeight: 800,
            formatter: compactClusterView ? courseName : `${courseName}\n{meta|${nodes.value.length} 个知识点 · 点击查看全部}`,
            rich: { meta: { color: "#8b5c3c", fontSize: 11, lineHeight: 18, fontWeight: 600 } },
          },
          itemStyle: { color: "#ee8b2f", borderColor: "#fff", borderWidth: 6, shadowBlur: 28, shadowColor: "rgba(238,139,47,.34)" },
        }, ...clusterData],
        links: [...rootLinks, ...relationLinks],
      }],
    }, true);
    return;
  }

  const nodeById = new Map(nodes.value.map((n) => [n.id, n]));

  // —— 章节折叠：折叠章节的成员替换为一个聚合章节节点，相关边重定向并去重 ——
  const collapseOn = chapterCollapseActive();
  const groupOfCollapsed = (id: string): string | null => {
    if (!collapseOn) return null;
    const group = nodeGroupMap.value.get(id);
    return group && !isChapterExpanded(group) ? group : null;
  };
  const displayNodes = visibleNodesList.value.filter((n) => !groupOfCollapsed(n.id));
  const chapterAgg = new Map<string, { count: number; mastery: number; weak: number }>();
  if (collapseOn) {
    for (const n of visibleNodesList.value) {
      const group = groupOfCollapsed(n.id);
      if (!group) continue;
      const agg = chapterAgg.get(group) || { count: 0, mastery: 0, weak: 0 };
      agg.count += 1;
      agg.mastery += n.mastery;
      if (n.mastery < 0.6) agg.weak += 1;
      chapterAgg.set(group, agg);
    }
  }
  const chapterNodeData = [...chapterAgg.entries()].map(([label, agg]) => {
    const headId = clusterHeadByGroup.value.get(label);
    const pos = headId ? clusterPositions.value.get(headId) : undefined;
    const masteryPct = agg.count ? Math.round((agg.mastery / agg.count) * 100) : 0;
    return {
      id: `${CHAPTER_NODE_PREFIX}${label}`,
      name: label,
      symbolSize: Math.min(96, 56 + agg.count * 2.4),
      symbol: "circle",
      x: pos?.x,
      y: pos?.y,
      chapterKey: label,
      label: {
        show: true,
        color: "#171512",
        fontSize: 13,
        fontWeight: 700,
        backgroundColor: "rgba(255,255,255,0.92)",
        borderColor: "rgba(35,31,25,0.1)",
        borderWidth: 1,
        borderRadius: 6,
        padding: [3, 7],
        distance: 10,
        formatter: `${label}\n{grp|${agg.count} 个知识点 · 掌握 ${masteryPct}%${agg.weak ? ` · ${agg.weak} 薄弱` : ""}}\n{tip|点击展开本章}`,
        rich: {
          grp: { color: "#625f58", fontSize: 10.5, lineHeight: 16 },
          tip: { color: "#d75011", fontSize: 10, lineHeight: 14, fontWeight: 600 },
        },
      },
      itemStyle: {
        color: masteryPct >= 80 ? "#e3f1e9" : agg.weak ? "#fdf0ec" : "#fff3ea",
        borderColor: masteryPct >= 80 ? "#247553" : agg.weak ? "#c98680" : "#e8a34d",
        borderWidth: 3,
        shadowBlur: 6,
        shadowColor: "rgba(35, 31, 25, 0.12)",
      },
    };
  });
  const aggEdges = new Map<string, { source: string; target: string; relation: string; agg: number }>();
  const displayEdges: Array<Graph3dEdge & { agg?: number }> = [];
  for (const e of visibleEdgesList.value) {
    const gs = groupOfCollapsed(e.source);
    const gt = groupOfCollapsed(e.target);
    if (!gs && !gt) {
      displayEdges.push(e);
      continue;
    }
    const s = gs ? `${CHAPTER_NODE_PREFIX}${gs}` : e.source;
    const t = gt ? `${CHAPTER_NODE_PREFIX}${gt}` : e.target;
    if (s === t) continue;
    const key = `${s}→${t}`;
    const existing = aggEdges.get(key);
    if (existing) existing.agg! += 1;
    else aggEdges.set(key, { source: s, target: t, relation: e.relation, agg: 1 });
  }
  displayEdges.push(...(aggEdges.values() as any));
  displayedNodeIds = [...displayNodes.map((n) => n.id), ...chapterNodeData.map((c) => c.id)];

  chart.setOption(
    {
      tooltip: {
        formatter: (params: any) => {
          if (params.dataType === "node" && params.data?.chapterKey) {
            return `<b>${params.data.chapterKey}</b><br/>点击展开本章知识点`;
          }
          if (params.dataType === "edge" && params.data?.aggCount) {
            return `${params.data.aggCount} 条章节间关联`;
          }
          if (params.dataType === "node" && params.data?.meta) {
            const n = params.data.meta as Graph3dNode;
            const trendArrow = TREND_ARROWS[n.bkt_trend ?? "stable"] ?? "→";
            const attempts = n.bkt_attempts ?? 0;
            const trendLabel = TREND_LABELS[n.bkt_trend ?? "stable"] ?? "平稳";
            return `<b>${n.name}</b><br/>` +
                   `掌握度：${Math.round(n.mastery * 100)}%<br/>` +
                   `Bloom：${n.bloom_level}<br/>` +
                   `趋势：${trendArrow} ${trendLabel}<br/>` +
                   `答题数：${attempts}`;
          }
          if (params.dataType === "edge") {
            return RELATION_LABELS[params.data?.relation] ?? params.data?.relation ?? "";
          }
          return "";
        },
      },
      series: [
        {
          type: "graph",
          // 章节分层/学习路径用预计算坐标（保证画布利用率与章节分区）；力导向/关系网络交给引擎
          layout: layoutMode.value === "force" || layoutMode.value === "network" ? "force" : "none",
          roam: true,
          zoom: savedZoom.value,
          center: savedCenter.value ?? undefined,
          scaleLimit: { min: 0.3, max: 5 },
          top: 10,
          bottom: 10,
          left: 10,
          right: 10,
          force:
            layoutMode.value === "network"
              ? { repulsion: [420, 780], edgeLength: [70, 130], gravity: 0.14, friction: 0.18 }
              : { repulsion: [900, 1600], edgeLength: [110, 190], gravity: 0.08, friction: 0.2 },
          label: {
            show: true,
            fontSize: 12,
            color: "#33312c",
            fontWeight: 600,
            position: "bottom",
            distance: 6,
          },
          // 标签碰撞避让：重叠时自动隐藏低优先级标签
          labelLayout: { hideOverlap: true },
          edgeSymbol: ["none", "arrow"],
          edgeSymbolSize: 7,
          lineStyle: { color: "#d9d4cc", curveness: 0.14, width: 1.2, opacity: 0.85 },
          emphasis: {
            focus: "adjacency",
            lineStyle: { width: 2.6, color: "#e88d4f", opacity: 1 },
            itemStyle: { shadowBlur: 16, shadowColor: "rgba(232, 93, 22, .35)", borderColor: "#e85d16", borderWidth: 3 },
          },
          data: [...displayNodes.map((n) => {
            const hasDone = (n.bkt_attempts && n.bkt_attempts > 0) || n.mastery > 0;
            const onPath = isNodeOnPath(n.id);
            const isCurrent = isCurrentLearningNode(n.id);
            const pathIndex = getNodePathIndex(n.id);
            const isWeak = hasDone && n.mastery < 0.3;
            const isMastered = n.mastery >= 0.8;
            const isLearning = hasDone && !isMastered && !isWeak;
            const isAiRecommended = recommendedNodes.value.some((item) => item.id === n.id);
            const isGraphRag = graphRagNodeIds.value.has(n.id);
            const stateColor = isMastered
              ? "#247553"
              : isWeak
                ? "#b5423a"
                : isLearning
                  ? "#3e6d9c"
                  : "#89857d";

            // 每个节点独立色相（按 id 稳定哈希）：已掌握=点亮的饱和色，其余=低饱和粉彩
            const hue = nodeHue(n.id);
            let sphere = isMastered
              ? `hsl(${hue}, 50%, 72%)`
              : hasDone
                ? `hsl(${hue}, 40%, 86%)`
                : `hsl(${hue}, 24%, 92%)`;
            // 掌握状态视角：填充改为语义容器色，状态一眼可读
            if (perspective.value === "mastery") {
              sphere = isMastered ? "#e3f1e9" : isWeak ? "#f9e6e3" : isLearning ? "#e4edf6" : "#efece6";
            }

            // 学习路径上的节点使用品牌橙系
            let pathColor: any = isCurrent ? "#ffe4d2" : (onPath ? "#fff0e2" : sphere);
            let pathBorderColor = isCurrent ? "#e85d16" : (onPath ? "#e08a4a" : stateColor);
            let pathBorderWidth = isCurrent ? 4 : (onPath ? 3 : 2);
            let pathShadowBlur = isCurrent ? 12 : (onPath ? 8 : 0);
            let pathOpacity = onPath ? 1 : (hasDone ? 1 : 0.62);

            // 节点分级：根（双环圆）/ 章节（圆角矩形）/ 核心 / 普通 / 叶子
            const tier = nodeTier(n);
            let symbolShape = "circle";
            let symbolSize = TIER_SIZE[tier] + Math.min(6, Math.round(n.size_hint || 0));
            if (onPath) symbolSize += 4;
            if (tier === "root") {
              pathBorderWidth = Math.max(pathBorderWidth, 5);
              pathShadowBlur = Math.max(pathShadowBlur, 6);
            }
            // AI 推荐节点用菱形 + 紫色，形状与颜色双重表达
            // AI 推荐节点保持圆形，用颜色表达区别

            // 解锁链路分析高亮
            const isUnlockDirect = unlockAnalysis.value && unlockDirectNodes.value.has(n.id);
            const isUnlockChain = unlockAnalysis.value && unlockChainNodes.value.has(n.id);
            if (isUnlockDirect) {
              pathColor = "#2f9f6b";
              pathBorderColor = "#2f9f6b";
              pathBorderWidth = 4;
              pathShadowBlur = 30;
              pathOpacity = 1;
              symbolSize = Math.max(symbolSize, 34);
            } else if (isUnlockChain) {
              pathColor = "#6bcf9f";
              pathBorderColor = "#2f9f6b";
              pathBorderWidth = 3;
              pathShadowBlur = 20;
              pathOpacity = 1;
            }

            // 薄弱根因追溯高亮
            const weakIdx = weaknessTrace.value ? weaknessChain.value.indexOf(n.id) : -1;
            if (weakIdx === 0) {
              // 根源节点
              pathColor = "#b3413a";
              pathBorderColor = "#b3413a";
              pathBorderWidth = 5;
              pathShadowBlur = 35;
              pathOpacity = 1;
              symbolShape = "circle";
              symbolSize = 42;
            } else if (weakIdx > 0) {
              // 链路中间节点
              pathColor = "#c86a5a";
              pathBorderColor = "#b3413a";
              pathBorderWidth = 3;
              pathShadowBlur = 22;
              pathOpacity = 1;
            }

            // 双图路径规划高亮
            const isDualPath = dualGraphHighlightNodes.value.has(n.id);
            if (isDualPath) {
              pathShadowBlur = Math.max(pathShadowBlur, 12);
              pathBorderWidth = Math.max(pathBorderWidth, 4);
              pathBorderColor = '#6366f1';
            }

            if (isAiRecommended || isGraphRag) {
              pathBorderColor = '#6557d9';
              pathBorderWidth = Math.max(pathBorderWidth, 3.5);
              pathShadowBlur = Math.max(pathShadowBlur, 10);
              pathOpacity = 1;
            }

            // —— Zoom 分层标签：远=只看课程/章节头，中=加核心与路径，近=全部+掌握度 ——
            const tierRank: Record<NodeTier, number> = { root: 0, chapter: 0, core: 1, normal: 2, leaf: 3 };
            const isHead = clusterHeadIds.value.has(n.id) && layoutMode.value === "cluster";
            const labelVisible =
              zoomTier.value === 0
                ? tierRank[tier] === 0 || isHead
                : zoomTier.value === 1
                  ? tierRank[tier] <= 1 || isHead || onPath
                  : true;
            const stateBadge = isMastered ? "✓ " : isWeak ? "⚠ " : "";
            const masterySuffix =
              zoomTier.value === 2 && hasDone ? `  ${Math.round(n.mastery * 100)}%` : "";
            // 章节头节点附带章节信息行，远距离即可读懂课程结构
            const groupLabel = n.bloom_level || "其他";
            const headSuffix = isHead
              ? `\n{grp|${groupLabel} · ${chapterGroups.value.get(groupLabel)?.length ?? 0} 个知识点}`
              : "";
            const baseText = `${stateBadge}${n.name}${masterySuffix}${headSuffix}`;

            // 预计算坐标（章节分层 / 学习路径布局）
            const pos =
              layoutMode.value === "cluster"
                ? clusterPositions.value.get(n.id)
                : layoutMode.value === "path"
                  ? pathPositions.value.get(n.id)
                  : undefined;

            return {
              id: n.id,
              name: n.name,
              symbolSize,
              symbol: symbolShape,
              x: pos?.x,
              y: pos?.y,
              draggable: true,
              label: {
                show: labelVisible,
                color: "#33312c",
                fontSize: tier === "root" ? 14 : tier === "chapter" ? 13 : zoomTier.value === 2 ? 12.5 : 11.5,
                fontWeight: tier === "root" || tier === "chapter" ? 700 : 600,
                backgroundColor: "rgba(255, 255, 255, 0.9)",
                borderColor: "rgba(35, 31, 25, 0.1)",
                borderWidth: 1,
                borderRadius: 5,
                padding: [2, 5],
                distance: 8,
                width: zoomTier.value <= 1 && tierRank[tier] >= 2 && !isHead ? 92 : undefined,
                overflow:
                  zoomTier.value <= 1 && tierRank[tier] >= 2 && !isHead
                    ? ("truncate" as const)
                    : undefined,
                formatter: onPath ? `{path|${pathIndex + 1}}  ${baseText}` : baseText,
                rich: {
                  path: {
                    backgroundColor: isCurrent ? "#e85d16" : "#e8a34d",
                    color: "#fff",
                    padding: [2, 6],
                    borderRadius: 4,
                    fontWeight: "bold",
                  },
                  grp: { color: "#89857d", fontSize: 10, lineHeight: 15, fontWeight: 500 },
                },
              },
              itemStyle: {
                color: pathColor,
                borderColor: pathBorderColor,
                borderWidth: pathBorderWidth,
                // 待学习节点用虚线描边，不只靠颜色表达状态
                borderType: !hasDone && !onPath ? ("dashed" as const) : ("solid" as const),
                shadowBlur: pathOpacity < 1 ? 4 : pathShadowBlur,
                shadowColor:
                  pathOpacity < 1
                    ? "rgba(137, 133, 125, 0.2)"
                    : typeof pathColor === "string"
                      ? pathColor
                      : stateColor,
                opacity: pathOpacity,
              },
              meta: n,
            };
          }), ...chapterNodeData],
          links: displayEdges.map((e) => {
            // 聚合边（章节间汇总）：中性色，粗细随关联数量
            if (e.agg) {
              return {
                source: e.source,
                target: e.target,
                relation: e.relation,
                aggCount: e.agg,
                lineStyle: {
                  color: "#cbc4b6",
                  width: Math.min(3, 1 + Math.log2(e.agg + 1)),
                  type: "solid",
                  opacity: 0.5,
                  curveness: 0.12,
                },
              };
            }
            // 关系类型语义：先修实线 / 相似短虚线 / 易混点划线 / 错误传播浅红 / 语义关联浅紫
            const baseStyle = relationStyle(e.relation);
            let lineColor = baseStyle.color;
            let lineWidth = baseStyle.width;
            let lineType: any = baseStyle.type;
            let lineOpacity = 0.85;

            // —— 视角决定默认关系权重：非结构关系降为背景层，减少视觉噪音 ——
            const structural = STRUCT_RELATIONS.has(e.relation);
            if (perspective.value === "structure" && !structural) {
              lineOpacity = 0.45;
              lineWidth = Math.min(lineWidth, 1);
            } else if (perspective.value === "mastery") {
              lineOpacity = structural ? 0.5 : 0.3;
            } else if (perspective.value === "path") {
              lineOpacity = 0.3;
            } else if (perspective.value === "weakness") {
              const target = nodeById.get(e.target);
              const intoWeak =
                !!target &&
                ((target.bkt_attempts && target.bkt_attempts > 0) || target.mastery > 0) &&
                target.mastery < 0.6;
              if (intoWeak) {
                lineColor = "#c98680";
                lineWidth = 1.8;
                lineOpacity = 0.9;
              } else {
                lineOpacity = 0.3;
              }
            }
            // 跨章节关系整体弱化，让章节集群边界更清晰
            if (layoutMode.value === "cluster") {
              const gs = nodeGroupMap.value.get(e.source);
              const gt = nodeGroupMap.value.get(e.target);
              if (gs && gt && gs !== gt) lineOpacity *= 0.75;
            }

            const sourcePathIndex = learningPath.value.findIndex((item) => item.kp_id === e.source);
            const targetPathIndex = learningPath.value.findIndex((item) => item.kp_id === e.target);
            if (
              showPathHighlight.value &&
              sourcePathIndex >= 0 &&
              targetPathIndex >= 0 &&
              Math.abs(sourcePathIndex - targetPathIndex) === 1
            ) {
              lineColor = "#e85d16";
              lineWidth = 2.8;
              lineOpacity = 1;
            }

            if (graphRagNodeIds.value.has(e.source) && graphRagNodeIds.value.has(e.target)) {
              lineColor = "#6557d9";
              lineWidth = 3;
              lineOpacity = 1;
            }

            if (dualGraphHighlightNodes.value.has(e.source) && dualGraphHighlightNodes.value.has(e.target)) {
              lineColor = "#6557d9";
              lineWidth = 3;
              lineOpacity = 1;
            }

            // 解锁链路边高亮
            if (unlockAnalysis.value) {
              const sInChain = unlockChainNodes.value.has(e.source) || unlockDirectNodes.value.has(e.source) || e.source === selected.value?.id;
              const tInChain = unlockChainNodes.value.has(e.target) || unlockDirectNodes.value.has(e.target);
              if (sInChain && tInChain) {
                lineColor = "#2f9f6b";
                lineWidth = 3;
                lineOpacity = 1;
              }
            }

            // 薄弱根因追溯边高亮
            if (weaknessTrace.value) {
              const sIdx = weaknessChain.value.indexOf(e.source);
              const tIdx = weaknessChain.value.indexOf(e.target);
              if (sIdx >= 0 && tIdx >= 0 && Math.abs(sIdx - tIdx) === 1) {
                lineColor = "#b3413a";
                lineWidth = 3.5;
                lineOpacity = 1;
              }
            }

            // 任一联动高亮（路径/RAG/双图/解锁/根因）生效时统一改为实线
            if (lineWidth >= 2.6) lineType = "solid";

            return {
              source: e.source,
              target: e.target,
              relation: e.relation,
              lineStyle: { color: lineColor, width: lineWidth, type: lineType, opacity: lineOpacity, curveness: 0.14 },
            };
          }),
        },
      ],
    },
    true,
  );
}

async function selectNode(n: Graph3dNode) {
  // 对比模式下，点击节点添加到对比列表
  if (compareMode.value) {
    addToCompare(n);
    return;
  }

  selected.value = n;
  selectedDetail.value = null;
  selectedNeighbors.value = [];
  drawerTab.value = "overview";
  rememberRecent(n);
  loadNodeEvaluation(n.id);
  
  // Highlight visually
  const idx = displayedNodeIds.indexOf(n.id);
  if (idx >= 0 && chart) {
    chart.dispatchAction({ type: 'downplay' });
    chart.dispatchAction({ type: 'highlight', seriesIndex: 0, dataIndex: idx });
  }

  try {
    const detail = await getKnowledgePoint(n.id);
    selectedDetail.value = detail.kp ?? detail;
    const nb = detail.neighbors;
    let neighbors: Array<Record<string, any>> = (
      Array.isArray(nb) ? nb : (nb?.neighbors ?? [])
    ) as Array<Record<string, any>>;
    // 后端未返回 neighbors 时，从已有图谱边中补充关联节点
    if (neighbors.length === 0) {
      const nodeById = new Map(nodes.value.map((nd) => [nd.id, nd]));
      const fromEdges = edges.value
        .filter((e) => e.source === n.id || e.target === n.id)
        .map((e) => {
          const otherId = e.source === n.id ? e.target : e.source;
          const other = nodeById.get(otherId);
          return other
            ? { ...other, relation: e.relation, direction: e.source === n.id ? "post" : "pre" }
            : null;
        })
        .filter((item): item is Graph3dNode & { relation: string; direction: string } => item !== null);
      neighbors = fromEdges;
    }
    selectedNeighbors.value = neighbors;
  } catch {
    /* 保留基础信息；从已有图谱边中补充关联节点 */
    const nodeById = new Map(nodes.value.map((nd) => [nd.id, nd]));
    selectedNeighbors.value = edges.value
      .filter((e) => e.source === n.id || e.target === n.id)
      .map((e) => {
        const otherId = e.source === n.id ? e.target : e.source;
        const other = nodeById.get(otherId);
        return other
          ? { ...other, relation: e.relation, direction: e.source === n.id ? "post" : "pre" }
          : null;
      })
      .filter((item): item is Graph3dNode & { relation: string; direction: string } => item !== null);
  }
}

async function runSearch() {
  const q = searchQuery.value.trim();
  if (!q || searching.value) return;
  searching.value = true;
  try {
    const r = await searchKnowledgeGraph(q, 6);
    searchResults.value = r.results ?? [];
  } catch (e: any) {
    error.value = `检索失败：${e?.detail ?? e?.message ?? e}`;
  }
  searching.value = false;
}

function focusSearchResult(r: Record<string, any>) {
  const id = String(r.id ?? r.kp_id ?? "");
  const node = nodes.value.find((n) => n.id === id || n.name === String(r.name ?? ""));
  if (node) void locateNode(node);
}

async function runGraphRag() {
  const question = graphRagQuestion.value.trim();
  if (!question || graphRagLoading.value) return;
  graphRagLoading.value = true;
  graphRagAnswer.value = "";
  searchQuery.value = question;
  await runSearch();
  const matched = searchResults.value
    .map((result) => {
      const id = String(result.id ?? result.kp_id ?? "");
      return nodes.value.find((node) => node.id === id || node.name === String(result.name ?? ""));
    })
    .filter((node): node is Graph3dNode => Boolean(node))
    .slice(0, 5);
  graphRagNodeIds.value = new Set(matched.map((node) => node.id));
  const relatedEdges = edges.value.filter(
    (edge) => graphRagNodeIds.value.has(edge.source) && graphRagNodeIds.value.has(edge.target),
  );
  graphRagAnswer.value = matched.length
    ? `已在「${COURSE_LABELS[course.value] ?? course.value}」中定位 ${matched.length} 个相关知识点，并找到 ${relatedEdges.length} 条直接关系。建议从「${matched[0].name}」开始，沿高亮关系核对先修与后续知识。`
    : "当前课程图谱中没有找到直接匹配节点，可以换一种表述或使用知识点 ID 精确查找。";
  renderChart();
  if (matched[0]) await locateNode(matched[0]);
  graphRagLoading.value = false;
}

function saveGraphRagNote() {
  if (!graphRagAnswer.value) return;
  const key = "tripleu.graph.notes";
  const existing = JSON.parse(localStorage.getItem(key) || "[]") as Array<Record<string, unknown>>;
  existing.unshift({
    course: course.value,
    question: graphRagQuestion.value,
    answer: graphRagAnswer.value,
    node_ids: [...graphRagNodeIds.value],
    created_at: Date.now(),
  });
  localStorage.setItem(key, JSON.stringify(existing.slice(0, 50)));
  showWorkspaceNotice("GraphRAG 结果已保存为学习笔记");
}

function loadNodeEvaluation(nodeId: string) {
  const all = JSON.parse(localStorage.getItem("tripleu.graph.node-evaluations") || "{}") as Record<string, any>;
  const value = all[nodeId] || {};
  nodeRating.value = Number(value.understanding || 0);
  difficultyRating.value = Number(value.difficulty || 0);
  resourceRating.value = Number(value.resource || 0);
  personalNote.value = String(value.note || "");
  markNeedsReview.value = Boolean(value.needs_review);
  markEasilyConfused.value = Boolean(value.easily_confused);
}

function saveNodeEvaluation() {
  if (!selected.value) return;
  const key = "tripleu.graph.node-evaluations";
  const all = JSON.parse(localStorage.getItem(key) || "{}") as Record<string, any>;
  all[selected.value.id] = {
    understanding: nodeRating.value,
    difficulty: difficultyRating.value,
    resource: resourceRating.value,
    note: personalNote.value.trim(),
    needs_review: markNeedsReview.value,
    easily_confused: markEasilyConfused.value,
    updated_at: Date.now(),
  };
  localStorage.setItem(key, JSON.stringify(all));
  showWorkspaceNotice("知识点评价已保存到本地学习记录");
}

function toggleNodeBranch(node: Graph3dNode) {
  if (expandedNodes.value.has(node.id)) expandedNodes.value.delete(node.id);
  else expandedNodes.value.add(node.id);
  renderChart();
}

function runContextAction(action: "detail" | "expand" | "study" | "practice" | "resource" | "ask" | "pin") {
  const node = contextMenu.value?.node;
  if (!node) return;
  contextMenu.value = null;
  if (action === "detail") void locateNode(node);
  else if (action === "expand") toggleNodeBranch(node);
  else if (action === "study" || action === "ask") askZhiling(node);
  else if (action === "practice") startPractice(node);
  else if (action === "resource") viewResources(node);
  else if (action === "pin") {
    expandedNodes.value.add(node.id);
    showWorkspaceNotice(`已固定「${node.name}」的展开状态`);
  }
}

function miniMapPosition(node: Graph3dNode, index: number) {
  const hue = nodeHue(node.id);
  return {
    left: `${8 + ((hue * 17 + index * 23) % 84)}%`,
    top: `${10 + ((hue * 11 + index * 19) % 76)}%`,
    background: masteryColor(node.mastery),
  };
}

// ---- 精确查找知识点（按 kp_id） ----
const lookupId = ref("");
const lookingUp = ref(false);
const lookupResult = ref<Record<string, any> | null>(null);

async function runLookup() {
  const id = lookupId.value.trim();
  if (!id || lookingUp.value) return;
  lookingUp.value = true;
  lookupResult.value = null;
  try {
    lookupResult.value = await lookupKnowledgePoint(id);
  } catch (e: any) {
    error.value = `查找失败：${e?.detail ?? e?.message ?? e}`;
  }
  lookingUp.value = false;
}

function focusLookupResult() {
  if (!lookupResult.value) return;
  const id = String(lookupResult.value.id ?? lookupResult.value.kp_id ?? "");
  const node = nodes.value.find((n) => n.id === id || n.name === String(lookupResult.value?.name ?? ""));
  if (node) void selectNode(node);
}

const masteredPct = computed(() => {
  const total = stats.value.total_kps ?? nodes.value.length;
  if (!total) return 0;
  return Math.round(((stats.value.mastered_kps ?? 0) / total) * 100);
});

// 一键初始化：knowledge_map.yaml（32 节点 AI 课程）灌入图谱库
const seeding = ref(false);

async function handleSeed() {
  if (seeding.value) return;
  seeding.value = true;
  try {
    const r = await seedKnowledgeGraph("artificial_intelligence");
    error.value = "";
    await load(false);
    void r;
  } catch (e: any) {
    error.value = `初始化失败：${e?.detail ?? e?.message ?? e}`;
  }
  seeding.value = false;
}

function handleResize() {
  chart?.resize();
}

// 加载中的自动课程切换不触发重复加载；每门课各自记住视图状态
watch(course, (next, prev) => {
  if (prev) {
    viewStateByCourse.set(prev, {
      zoom: savedZoom.value,
      center: savedCenter.value,
      layout: layoutMode.value,
      filter: nodeFilter.value,
      chapter: chapterFocus.value,
      view: perspective.value,
    });
  }
  const restored = viewStateByCourse.get(next);
  savedZoom.value = restored?.zoom ?? 0.9;
  savedCenter.value = restored?.center ?? null;
  layoutMode.value = restored?.layout ?? "cluster";
  nodeFilter.value = restored?.filter ?? "all";
  chapterFocus.value = restored?.chapter ?? null;
  perspective.value = (restored?.view as Perspective) ?? "structure";
  graphLevel.value = "clusters";
  activeClusterId.value = null;
  selectedCluster.value = null;
  selected.value = null;
  zoomTier.value = zoomToTier(savedZoom.value);
  if (!loading.value) void load(false);
});

watch([nodeFilter, viewMode, graphLevel, activeClusterId], () => renderChart());
watch([course, nodeFilter, viewMode], () => {
  localStorage.setItem(
    "tripleu.graph.workspace-state",
    JSON.stringify({ course: course.value, filter: nodeFilter.value, mode: viewMode.value }),
  );
});

// ---- 外部跳转聚焦：/graph?kp=xxx（学习路径「今日推荐资源」、AI 建议等入口） ----
const route = useRoute();

async function focusFromQuery() {
  const raw = route.query.kp;
  const target = (typeof raw === "string" ? raw : "").trim();
  if (!target || !nodes.value.length) return;
  // 先按 id 精确匹配，再按名称精确/包含匹配
  const node =
    nodes.value.find((n) => n.id === target) ||
    nodes.value.find((n) => n.name === target) ||
    nodes.value.find((n) => target.includes(n.name) || n.name.includes(target));
  if (node) {
    await selectNode(node);
    return;
  }
  // 图谱里没有同名节点时，退化为语义搜索，让用户可从结果中选
  searchQuery.value = target;
  void runSearch();
}

onMounted(async () => {
  try {
    const saved = JSON.parse(localStorage.getItem("tripleu.graph.workspace-state") || "{}") as Record<string, string>;
    if (saved.course) course.value = saved.course;
    if (FILTER_OPTIONS.some((option) => option.key === saved.filter)) nodeFilter.value = saved.filter as FilterType;
    if (saved.mode === "explore" || saved.mode === "focus") viewMode.value = saved.mode;
  } catch {
    /* 使用默认视图 */
  }
  if (window.innerWidth <= 600) legendOpen.value = false;
  await load();
  void focusFromQuery();
  window.addEventListener("resize", handleResize);
  window.addEventListener("keydown", handleKeydown);
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", handleResize);
  window.removeEventListener("keydown", handleKeydown);
  chart?.dispose();
  chart = null;
  forecastChart?.dispose();
  forecastChart = null;
  if (workspaceNoticeTimer) clearTimeout(workspaceNoticeTimer);
});
</script>

<template>
  <div
    class="kg-workspace"
    :class="{ 'has-dock': activeDock, 'has-drawer': selected || selectedCluster, 'course-panel-open': coursePanelOpen }"
    @contextmenu.prevent
  >
    <div class="kg-canvas-layer" aria-label="课程知识图谱画布">
      <div ref="chartEl" class="graph-canvas" />
      <div v-if="loading" class="canvas-state loading-state" role="status">
        <Loader2 :size="22" class="spin" />
        <div>
          <strong>正在加载「{{ COURSE_LABELS[course] ?? course }}」知识图谱</strong>
          <span>正在同步节点、关系与学习状态</span>
        </div>
      </div>
      <div v-else-if="error && !nodes.length" class="canvas-state empty-state" role="status">
        <Network :size="28" />
        <div>
          <strong>当前课程暂无知识图谱</strong>
          <span>{{ error }}</span>
        </div>
        <button type="button" :disabled="seeding" @click="handleSeed">
          <Loader2 v-if="seeding" :size="16" class="spin" />
          <Sprout v-else :size="16" />同步知识点
        </button>
      </div>
    </div>

    <header class="floating-topbar">
      <div class="topbar-identity">
        <button type="button" class="icon-button back-button" aria-label="返回学习工作台" title="返回学习工作台" @click="router.push('/home')">
          <ArrowLeft :size="18" />
        </button>
        <span class="mini-logo"><img src="/logo.png" alt="triple U" /></span>
        <div class="workspace-name">
          <strong>知识图谱</strong>
          <span>{{ COURSE_LABELS[course] ?? course }}</span>
        </div>
      </div>

      <div class="graph-level-switch" aria-label="图谱层级">
        <button type="button" :class="{ active: graphLevel === 'clusters' }" @click="showClusterOverview">
          <Layers3 :size="15" /><span>聚类概览</span>
        </button>
        <button type="button" :class="{ active: graphLevel === 'nodes' && !activeCluster }" @click="showAllCourseNodes">
          <Network :size="15" /><span>全部节点</span>
        </button>
      </div>

      <label class="topbar-search">
        <Search :size="17" />
        <input
          ref="topSearchEl"
          v-model="searchQuery"
          aria-label="搜索知识点、章节或关系"
          placeholder="搜索知识点、章节或关系"
          @keydown.enter="activeDock = 'search'; runSearch()"
        />
        <kbd>/</kbd>
      </label>

      <div class="topbar-controls">
        <label class="select-control perspective-control">
          <span>视角</span>
          <select v-model="perspectiveModel" aria-label="切换图谱视角">
            <option v-for="[key, label] in perspectiveOptions" :key="key" :value="key">{{ label }}</option>
          </select>
          <ChevronDown :size="14" />
        </label>
        <label class="select-control course-control">
          <span>课程</span>
          <select v-model="course" aria-label="切换课程">
            <option v-for="item in courses" :key="item" :value="item">{{ COURSE_LABELS[item] ?? item }}</option>
          </select>
          <ChevronDown :size="14" />
        </label>
        <label class="select-control scope-control">
          <span>范围</span>
          <select v-model="nodeFilter" aria-label="切换图谱范围">
            <option v-for="option in FILTER_OPTIONS" :key="option.key" :value="option.key">{{ option.label }}</option>
          </select>
          <ChevronDown :size="14" />
        </label>
        <button type="button" class="icon-button" :class="{ active: filterOpen }" aria-label="筛选图谱" title="筛选图谱" @click="filterOpen = !filterOpen">
          <Filter :size="17" />
          <i v-if="nodeFilter !== 'all'" />
        </button>
        <button type="button" class="icon-button desktop-action" aria-label="适应画布" title="适应画布（F）" @click="fitGraph"><Focus :size="17" /></button>
        <button type="button" class="icon-button desktop-action" aria-label="全屏" title="进入全屏" @click="toggleFullscreen"><Fullscreen :size="17" /></button>
        <details class="more-menu">
          <summary class="icon-button" aria-label="更多图谱操作" title="更多操作"><MoreHorizontal :size="18" /></summary>
          <div class="more-menu-popover">
            <button type="button" :disabled="loading" @click="load()"><RefreshCcw :size="16" />刷新当前图谱</button>
            <button type="button" :disabled="seeding" @click="handleSeed"><Sprout :size="16" />更新知识图谱</button>
            <button type="button" @click="exportSnapshot"><Download :size="16" />导出 PNG</button>
            <button type="button" @click="shortcutsOpen = true"><Keyboard :size="16" />键盘快捷键</button>
          </div>
        </details>
      </div>
    </header>

    <div v-if="filterOpen" class="filter-popover" role="dialog" aria-label="图谱筛选">
      <header><div><strong>筛选图谱</strong><span>当前显示 {{ visibleNodesList.length }} / {{ nodes.length }} 个节点</span></div><button type="button" aria-label="关闭筛选" @click="filterOpen = false"><X :size="17" /></button></header>
      <div class="filter-section">
        <span>掌握状态</span>
        <div class="filter-options">
          <button v-for="option in FILTER_OPTIONS" :key="option.key" type="button" :class="{ active: nodeFilter === option.key }" @click="nodeFilter = option.key as FilterType">
            <i :class="`state-${option.key}`" />{{ option.label }}<Check v-if="nodeFilter === option.key" :size="14" />
          </button>
        </div>
      </div>
      <div class="filter-section">
        <span>视图模式</span>
        <div class="segmented-control">
          <button type="button" :class="{ active: viewMode === 'explore' }" @click="viewMode = 'explore'">全课程</button>
          <button type="button" :class="{ active: viewMode === 'focus' }" @click="viewMode = 'focus'">我的学习路径</button>
        </div>
      </div>
      <div class="filter-section">
        <span>布局方式</span>
        <div class="segmented-control layout-control">
          <button
            v-for="[key, label] in layoutOptions"
            :key="key"
            type="button"
            :class="{ active: layoutMode === key }"
            @click="setLayoutMode(key)"
          >{{ label }}</button>
        </div>
      </div>
      <footer><button type="button" @click="clearGraphFilters">清除全部</button><button type="button" @click="filterOpen = false">应用筛选</button></footer>
    </div>

    <button
      v-if="!coursePanelOpen"
      type="button"
      class="course-panel-trigger"
      aria-label="展开课程结构"
      title="课程结构"
      @click="coursePanelOpen = true"
    ><PanelLeftOpen :size="18" /><span>课程结构</span></button>

    <aside class="course-tree-panel" aria-label="课程结构">
      <header>
        <div><span>课程结构</span><strong>{{ COURSE_LABELS[course] ?? course }}</strong></div>
        <button type="button" aria-label="收起课程结构" @click="coursePanelOpen = false"><PanelLeftClose :size="18" /></button>
      </header>
      <label class="tree-search"><Search :size="15" /><input v-model="courseTreeQuery" placeholder="搜索本课程节点" /></label>
      <div class="course-switch-list">
        <button v-for="item in courses" :key="item" type="button" :class="{ active: course === item }" @click="chooseCourse(item)">
          <BookOpen :size="15" /><span>{{ COURSE_LABELS[item] ?? item }}</span><Check v-if="course === item" :size="14" />
        </button>
      </div>
      <div class="tree-groups">
        <section v-if="graphLevel === 'clusters'" class="cluster-tree-list" aria-label="课程知识聚类">
          <header><span>知识聚类</span><em>{{ graphClusters.length }} 组</em></header>
          <button
            v-for="cluster in graphClusters"
            :key="cluster.id"
            type="button"
            :class="{ active: selectedCluster?.id === cluster.id }"
            @click="selectCluster(cluster)"
          >
            <i :style="{ background: cluster.softColor, borderColor: cluster.color }" />
            <span><b>{{ cluster.label }}</b><small>{{ cluster.members.length }} 个知识点 · 掌握 {{ Math.round(cluster.averageMastery * 100) }}%</small></span>
            <ChevronRight :size="14" />
          </button>
        </section>
        <template v-if="graphLevel === 'nodes'">
        <details v-for="group in courseTreeGroups" :key="group.label" open>
          <summary>
            <span><Layers3 :size="15" />{{ group.label }}</span>
            <em>{{ group.mastery }}% · {{ group.weakCount }} 薄弱</em>
            <button
              type="button"
              class="chapter-focus-btn"
              :class="{ active: chapterFocus === group.label }"
              :title="chapterFocus === group.label ? '恢复全部章节' : '在图谱中只看本章'"
              :aria-label="chapterFocus === group.label ? '恢复全部章节' : `聚焦章节 ${group.label}`"
              @click.prevent.stop="toggleChapterFocus(group.label)"
            ><Focus :size="13" /></button>
          </summary>
          <button v-for="node in group.items" :key="node.id" type="button" :class="{ active: selected?.id === node.id }" @click="locateNode(node)">
            <i :style="{ borderColor: masteryColor(node.mastery) }" />
            <span>{{ node.name }}</span>
            <small>{{ Math.round(node.mastery * 100) }}%</small>
          </button>
        </details>
        </template>
      </div>
    </aside>

    <button
      v-if="activeCluster"
      type="button"
      class="cluster-breadcrumb"
      title="返回聚类概览"
      @click="showClusterOverview"
    ><ChevronLeft :size="15" /><span>聚类概览</span><i />{{ activeCluster.label }} · {{ activeCluster.members.length }} 个知识点</button>

    <nav class="canvas-toolbar" aria-label="图谱画布工具">
      <button type="button" aria-label="放大图谱" title="放大" @click="zoomGraph(1.2)"><ZoomIn :size="18" /></button>
      <button type="button" aria-label="缩小图谱" title="缩小" @click="zoomGraph(0.82)"><ZoomOut :size="18" /></button>
      <span />
      <button
        type="button"
        :class="{ active: allChaptersExpanded }"
        :aria-label="allChaptersExpanded ? '收起为章节总览' : '展开全部章节'"
        :title="allChaptersExpanded ? '收起为章节总览' : '展开全部章节'"
        @click="toggleAllChapters"
      ><Layers3 :size="18" /></button>
      <button type="button" aria-label="适应画布" title="适应画布（F）" @click="fitGraph"><Focus :size="18" /></button>
      <button type="button" aria-label="重置图谱" title="重置视图（R）" @click="resetGraphView"><RotateCcw :size="18" /></button>
      <button
        v-if="learningPath.length"
        type="button"
        :class="{ active: showPathHighlight }"
        aria-label="显示或隐藏学习路径"
        title="学习路径"
        @click="showPathHighlight = !showPathHighlight; renderChart()"
      ><RouteIcon :size="18" /></button>
      <button type="button" :class="{ active: legendOpen }" aria-label="显示或隐藏图例" title="图例（L）" @click="legendOpen = !legendOpen"><MapIcon :size="18" /></button>
    </nav>

    <section v-if="legendOpen" class="graph-legend" aria-label="图谱图例">
      <header><strong>图例</strong><button type="button" aria-label="收起图例" @click="legendOpen = false"><Minus :size="14" /></button></header>
      <details class="legend-group" open>
      <summary>节点状态<em>点击筛选</em></summary>
      <div class="legend-nodes">
        <button type="button" :class="{ active: nodeFilter === 'mastered' }" @click="filterFromPanel('mastered', '已掌握')"><i class="mastered" />已掌握</button>
        <button type="button" :class="{ active: nodeFilter === 'learning' }" @click="filterFromPanel('learning', '学习中')"><i class="learning" />学习中</button>
        <button type="button" :class="{ active: nodeFilter === 'at_risk' }" @click="filterFromPanel('at_risk', '薄弱')"><i class="weak" />薄弱</button>
        <button type="button" :class="{ active: nodeFilter === 'not_started' }" @click="filterFromPanel('not_started', '待学习')"><i class="pending" />待学习</button>
        <button type="button" :class="{ active: nodeFilter === 'recommended' }" @click="filterFromPanel('recommended', 'AI 推荐')"><i class="ai" />AI 推荐</button>
        <button type="button" :class="{ active: showPathHighlight }" @click="showPathHighlight = !showPathHighlight; renderChart()"><i class="path" />学习路径</button>
      </div>
      </details>
      <details class="legend-group">
      <summary>关系类型<em>点击隐藏</em></summary>
      <div class="legend-relations">
        <button
          v-for="item in relationTypes"
          :key="item.key"
          type="button"
          :class="{ muted: hiddenRelations.has(item.key) }"
          :title="hiddenRelations.has(item.key) ? '点击恢复该类关系' : '点击隐藏该类关系'"
          @click="toggleRelation(item.key)"
        >
          <i
            :style="{
              background: 'transparent',
              borderTop: `2px ${Array.isArray(item.style.type) ? 'dashed' : item.style.type} ${item.style.color}`,
            }"
          />{{ item.label }}<em>{{ item.count }}</em>
        </button>
      </div>
      </details>
    </section>

    <section class="graph-minimap" aria-label="图谱小地图">
      <header><span>图谱概览</span><MapIcon :size="14" /></header>
      <div class="minimap-canvas">
        <i v-for="(node, index) in nodes.slice(0, 36)" :key="node.id" :class="{ selected: selected?.id === node.id }" :style="miniMapPosition(node, index)" />
        <span class="viewport-indicator" />
      </div>
    </section>

    <section v-if="compareMode" class="compare-floating" aria-label="知识点对比">
      <header><div><strong>知识对比</strong><span>选择两个节点 · {{ compareNodes.length }}/2</span></div><button type="button" aria-label="退出对比" @click="toggleCompareMode"><X :size="17" /></button></header>
      <div class="compare-selected">
        <button v-for="node in compareNodes" :key="node.id" type="button" @click="removeFromCompare(node.id)">{{ node.name }}<X :size="13" /></button>
      </div>
      <div v-if="compareNodes.length === 2" ref="compareChartEl" class="compare-chart" />
      <p v-else>请在图谱中再选择 {{ 2 - compareNodes.length }} 个节点。</p>
    </section>

    <aside v-if="selectedCluster && !selected" class="node-drawer cluster-drawer" aria-labelledby="cluster-drawer-title">
      <header class="drawer-header">
        <div>
          <span>{{ COURSE_LABELS[course] ?? course }} · 知识聚类</span>
          <h2 id="cluster-drawer-title">{{ selectedCluster.label }}</h2>
        </div>
        <button type="button" aria-label="关闭聚类详情" @click="selectedCluster = null"><X :size="19" /></button>
      </header>
      <div class="drawer-body">
        <section class="cluster-overview-card" :style="{ '--cluster-color': selectedCluster.color, '--cluster-soft': selectedCluster.softColor }">
          <div class="cluster-orbit"><Network :size="24" /></div>
          <p>该聚类以「{{ selectedCluster.hub.name }}」为中心，汇集结构关系最接近的一组知识点。</p>
          <dl>
            <div><dt>知识点</dt><dd>{{ selectedCluster.members.length }}</dd></div>
            <div><dt>平均掌握</dt><dd>{{ Math.round(selectedCluster.averageMastery * 100) }}%</dd></div>
            <div><dt>薄弱点</dt><dd>{{ selectedCluster.weakCount }}</dd></div>
            <div><dt>内部关系</dt><dd>{{ selectedCluster.relationCount }}</dd></div>
          </dl>
        </section>
        <section class="drawer-section">
          <header><strong>聚类内知识点</strong><span>{{ selectedCluster.members.length }}</span></header>
          <div class="cluster-member-list">
            <button
              v-for="node in [...selectedCluster.members].sort((a, b) => b.mastery - a.mastery).slice(0, 8)"
              :key="node.id"
              type="button"
              @click="openCluster(selectedCluster); locateNode(node)"
            >
              <i :style="{ borderColor: masteryColor(node.mastery) }" />
              <span>{{ node.name }}</span><em>{{ Math.round(node.mastery * 100) }}%</em>
            </button>
          </div>
          <p v-if="selectedCluster.members.length > 8" class="cluster-more">还有 {{ selectedCluster.members.length - 8 }} 个知识点，展开后可查看全部。</p>
        </section>
        <button type="button" class="cluster-open-button" @click="openCluster(selectedCluster)">
          查看全部节点 <ArrowRight :size="17" />
        </button>
      </div>
    </aside>

    <aside v-if="selected" class="node-drawer" aria-labelledby="node-drawer-title">
      <header class="drawer-header">
        <div>
          <span>{{ COURSE_LABELS[selected.course] ?? selected.course }} · {{ selected.bloom_level }}</span>
          <h2 id="node-drawer-title">{{ selected.name }}</h2>
        </div>
        <button type="button" aria-label="关闭节点详情" @click="selected = null"><X :size="19" /></button>
      </header>
      <nav class="drawer-tabs" aria-label="节点详情标签">
        <button type="button" :class="{ active: drawerTab === 'overview' }" @click="drawerTab = 'overview'">概览</button>
        <button type="button" :class="{ active: drawerTab === 'analysis' }" @click="drawerTab = 'analysis'">智能分析</button>
        <button type="button" :class="{ active: drawerTab === 'evaluation' }" @click="drawerTab = 'evaluation'">我的评价</button>
      </nav>
      <div class="drawer-body">
        <template v-if="drawerTab === 'overview'">
          <section class="mastery-summary">
            <div><span>当前掌握度</span><strong :style="{ color: masteryColor(selected.mastery) }">{{ Math.round(selected.mastery * 100) }}%</strong></div>
            <div class="mastery-track"><i :style="{ transform: `scaleX(${Math.max(0, Math.min(1, selected.mastery))})`, background: masteryColor(selected.mastery) }" /></div>
            <dl>
              <div><dt>学习趋势</dt><dd>{{ TREND_ARROWS[selected.bkt_trend ?? 'stable'] }} {{ TREND_LABELS[selected.bkt_trend ?? 'stable'] }}</dd></div>
              <div><dt>练习次数</dt><dd>{{ selected.bkt_attempts ?? 0 }} 次</dd></div>
              <div><dt>关联知识</dt><dd>{{ selectedNeighbors.length }} 个</dd></div>
              <div><dt>节点 ID</dt><dd>{{ selected.id }}</dd></div>
            </dl>
          </section>
          <p v-if="selectedDetail?.description" class="node-description">{{ selectedDetail.description }}</p>
          <section class="drawer-section">
            <header><strong>前置知识</strong><span>{{ selectedPrereqs.length }}</span></header>
            <div v-if="selectedPrereqs.length" class="relation-rows">
              <button v-for="node in selectedPrereqs" :key="node.id" type="button" @click="locateNode(node)">
                <i :style="{ background: masteryColor(node.mastery) }" />
                <span>{{ node.name }}</span>
                <em>{{ Math.round(node.mastery * 100) }}%</em>
                <ChevronRight :size="13" />
              </button>
            </div>
            <p v-else class="inline-empty">没有前置依赖，可直接学习。</p>
          </section>
          <section class="drawer-section">
            <header><strong>后续知识</strong><span>{{ selectedNextNodes.length }}</span></header>
            <div v-if="selectedNextNodes.length" class="relation-rows">
              <button v-for="item in selectedNextNodes" :key="item.node.id" type="button" @click="locateNode(item.node)">
                <i :style="{ background: masteryColor(item.node.mastery) }" />
                <span>{{ item.node.name }}</span>
                <small>{{ RELATION_LABELS[item.relation] ?? item.relation }}</small>
                <ChevronRight :size="13" />
              </button>
            </div>
            <p v-else class="inline-empty">掌握本节点后暂无直接后续。</p>
          </section>
          <section class="drawer-section">
            <header><strong>直接关系</strong><span>{{ selectedNeighbors.length }}</span></header>
            <div v-if="selectedNeighbors.length" class="neighbor-chips">
              <button v-for="(neighbor, index) in selectedNeighbors.slice(0, 10)" :key="index" type="button">
                {{ (neighbor as any).name ?? (neighbor as any).kp_id ?? (neighbor as any).target_id ?? neighbor }}
              </button>
            </div>
            <p v-else class="inline-empty">暂无可展示的直接关系。</p>
          </section>
          <div class="drawer-primary-actions">
            <button type="button" class="primary-action" @click="askZhiling(selected)"><PlayCircle :size="17" />开始学习</button>
            <button type="button" @click="startPractice(selected)">开始练习</button>
            <button type="button" @click="viewResources(selected)">查看资源</button>
          </div>
          <div class="drawer-text-actions">
            <button type="button" @click="toggleCompareMode"><GitBranch :size="15" />{{ compareMode ? '退出知识对比' : '加入知识对比' }}</button>
            <button type="button" @click="toggleNodeBranch(selected)"><Layers3 :size="15" />{{ expandedNodes.has(selected.id) ? '收起分支' : '展开一层' }}</button>
          </div>
          <section v-if="recentNodes.length > 1" class="drawer-section recent-section">
            <header><strong>最近查看</strong></header>
            <div class="neighbor-chips">
              <button
                v-for="node in recentNodes.filter((item) => item.id !== selected?.id).slice(0, 5)"
                :key="node.id"
                type="button"
                @click="locateNode(node)"
              >{{ node.name }}</button>
            </div>
          </section>
        </template>

        <template v-else-if="drawerTab === 'analysis'">
          <div class="analysis-action-list">
            <button type="button" :class="{ active: dualGraphResult }" :disabled="dualGraphLoading" @click="dualGraphResult ? clearDualGraph() : runDualGraph(selected)">
              <span><RouteIcon :size="18" /><b>双图路径规划</b><small>先修图 + 语义相似图</small></span><Loader2 v-if="dualGraphLoading" :size="16" class="spin" /><ChevronRight v-else :size="16" />
            </button>
            <button type="button" :class="{ active: forecastData }" :disabled="forecastLoading" @click="forecastData ? forecastData = null : loadForecast(selected)">
              <span><BarChart3 :size="18" /><b>掌握度时光机</b><small>BKT + Kalman 预测未来 30 天</small></span><Loader2 v-if="forecastLoading" :size="16" class="spin" /><ChevronRight v-else :size="16" />
            </button>
            <button type="button" :class="{ active: unlockAnalysis }" @click="unlockAnalysis ? clearUnlockAnalysis() : analyzeUnlock(selected)">
              <span><Network :size="18" /><b>解锁链路分析</b><small>查看掌握后可解锁的知识</small></span><ChevronRight :size="16" />
            </button>
            <button type="button" :class="{ active: weaknessTrace }" @click="weaknessTrace ? clearWeaknessTrace() : traceWeakness(selected)">
              <span><Target :size="18" /><b>薄弱根因追溯</b><small>追溯先修知识缺口</small></span><ChevronRight :size="16" />
            </button>
          </div>

          <section v-if="dualGraphResult" class="analysis-result">
            <header><div><strong>双图路径 · {{ dualGraphResult.focus_kp_name }}</strong><span>{{ dualGraphPathMeta?.estTime }} · 平均掌握 {{ dualGraphPathMeta?.avgMastery }}%</span></div><button type="button" @click="clearDualGraph"><X :size="15" /></button></header>
            <div class="path-switch">
              <button type="button" :class="{ active: dualGraphActivePath === 'main' }" @click="switchDualGraphPath('main')">主路径 {{ dualGraphResult.main_path.length }}</button>
              <button type="button" :class="{ active: dualGraphActivePath === 'detour' }" @click="switchDualGraphPath('detour')">绕行 {{ dualGraphResult.detour_path.length }}</button>
              <button type="button" :class="{ active: dualGraphActivePath === 'remediation' }" @click="switchDualGraphPath('remediation')">补救 {{ dualGraphResult.remediation_path.length }}</button>
            </div>
            <button v-for="(step, index) in (dualGraphResult as any)[`${dualGraphActivePath}_path`]" :key="step.kp_id" type="button" class="analysis-path-row" @click="locateNode(nodes.find(node => node.id === step.kp_id)! as Graph3dNode)">
              <span>{{ index + 1 }}</span><div><b>{{ step.title }}</b><small>{{ step.reason }}</small></div><em>{{ step.mastery == null ? '—' : `${Math.round(step.mastery * 100)}%` }}</em>
            </button>
          </section>

          <section v-if="unlockAnalysis" class="analysis-result compact-result">
            <header><div><strong>解锁链路</strong><span>直接 {{ unlockDirectList.length }} · 间接 {{ unlockChainList.length }}</span></div><button type="button" @click="clearUnlockAnalysis"><X :size="15" /></button></header>
            <button v-for="node in [...unlockDirectList, ...unlockChainList].slice(0, 10)" :key="node.id" type="button" class="result-node-row" @click="locateNode(node)"><span>{{ node.name }}</span><em>{{ Math.round(node.mastery * 100) }}%</em></button>
          </section>

          <section v-if="weaknessTrace" class="analysis-result compact-result">
            <header><div><strong>薄弱根因链</strong><span>{{ weaknessChainDetails.length }} 个节点</span></div><button type="button" @click="clearWeaknessTrace"><X :size="15" /></button></header>
            <button v-for="item in weaknessChainDetails" :key="item.id" type="button" class="result-node-row" @click="locateNode(nodes.find(node => node.id === item.id)! as Graph3dNode)"><span>{{ item.isRoot ? '根源 · ' : '' }}{{ item.name }}</span><em>{{ Math.round(item.mastery * 100) }}%</em></button>
          </section>

          <section v-if="forecastData" class="analysis-result forecast-result">
            <header><div><strong>30 天掌握度预测</strong><span>{{ forecastData.summary_text }}</span></div><button type="button" @click="forecastData = null"><X :size="15" /></button></header>
            <div v-if="forecastInsights" class="forecast-summary-grid">
              <div><span>当前</span><strong>{{ Math.round(forecastInsights.current * 100) }}%</strong></div><div><span>30 天后</span><strong>{{ Math.round(forecastInsights.futureMastery * 100) }}%</strong></div><div><span>变化</span><strong>{{ Math.round(forecastInsights.delta * 100) }}%</strong></div>
            </div>
            <div ref="forecastEl" class="forecast-chart" />
          </section>

          <button type="button" class="trend-button" :class="{ active: showTrendChart }" @click="toggleTrendChart"><BarChart3 :size="16" />{{ showTrendChart ? '隐藏历史趋势' : '查看历史趋势' }}</button>
          <div v-if="showTrendChart" ref="trendChartEl" class="trend-chart" />
        </template>

        <template v-else>
          <section class="evaluation-form">
            <div class="rating-field"><span>理解程度</span><div><button v-for="value in 5" :key="`understanding-${value}`" type="button" :class="{ active: nodeRating >= value }" :aria-label="`理解程度 ${value} 分`" @click="nodeRating = value">★</button></div></div>
            <div class="rating-field"><span>学习难度</span><div><button v-for="value in 5" :key="`difficulty-${value}`" type="button" :class="{ active: difficultyRating >= value }" :aria-label="`学习难度 ${value} 分`" @click="difficultyRating = value">★</button></div></div>
            <div class="rating-field"><span>资源质量</span><div><button v-for="value in 5" :key="`resource-${value}`" type="button" :class="{ active: resourceRating >= value }" :aria-label="`资源质量 ${value} 分`" @click="resourceRating = value">★</button></div></div>
            <label class="evaluation-check"><input v-model="markNeedsReview" type="checkbox" />标记为需要复习</label>
            <label class="evaluation-check"><input v-model="markEasilyConfused" type="checkbox" />标记为易混知识</label>
            <label class="note-field"><span>个人备注</span><textarea v-model="personalNote" rows="5" placeholder="记录理解、疑问或易错点…" /></label>
            <button type="button" class="save-evaluation" @click="saveNodeEvaluation">保存评价</button>
            <p>评价保存在当前设备的学习记录中，不会修改课程原始图谱。</p>
          </section>
        </template>
      </div>
    </aside>

    <div
      v-if="contextMenu"
      class="node-context-menu"
      :style="{ left: `${contextMenu.x}px`, top: `${contextMenu.y}px` }"
      role="menu"
      @click.stop
    >
      <strong>{{ contextMenu.node.name }}</strong>
      <button type="button" role="menuitem" @click="runContextAction('detail')">查看详情</button>
      <button type="button" role="menuitem" @click="runContextAction('expand')">{{ expandedNodes.has(contextMenu.node.id) ? '收起分支' : '展开一层' }}</button>
      <button type="button" role="menuitem" @click="runContextAction('study')">开始学习</button>
      <button type="button" role="menuitem" @click="runContextAction('practice')">开始练习</button>
      <button type="button" role="menuitem" @click="runContextAction('resource')">查看资源</button>
      <button type="button" role="menuitem" @click="runContextAction('ask')">向 AI 提问</button>
      <button type="button" role="menuitem" @click="runContextAction('pin')">固定展开状态</button>
    </div>

    <footer class="bottom-workspace-dock" aria-label="知识图谱功能工作台">
      <nav class="dock-tabs">
        <button v-for="tab in dockTabs" :key="tab.key" type="button" :class="{ active: activeDock === tab.key }" @click="toggleDock(tab.key)">
          <component :is="tab.icon" :size="17" /><span>{{ tab.label }}</span><ChevronDown :size="14" />
        </button>
        <button v-if="activeDock" type="button" class="dock-close" aria-label="收起底部工作台" @click="activeDock = null"><PanelBottomClose :size="18" /></button>
      </nav>
      <div v-if="activeDock" class="dock-panel">
        <section v-if="activeDock === 'graphrag'" class="dock-content graphrag-panel">
          <div class="dock-heading"><div><span class="ai-label"><Sparkles :size="14" />GraphRAG</span><h2>沿知识关系查找答案</h2></div><p>混合检索课程节点与直接关系，并将引用路径同步高亮在图谱中。</p></div>
          <div class="graphrag-layout">
            <div class="rag-conversation">
              <label><textarea v-model="graphRagQuestion" rows="3" placeholder="例如：多智能体系统和任务分解之间是什么关系？" @keydown.ctrl.enter="runGraphRag" /></label>
              <div class="rag-actions"><button type="button" :disabled="graphRagLoading || !graphRagQuestion.trim()" @click="runGraphRag"><Loader2 v-if="graphRagLoading" :size="16" class="spin" /><MessageCircle v-else :size="16" />检索关系</button><span>Ctrl + Enter</span></div>
              <article v-if="graphRagAnswer" class="rag-answer"><strong>关系结论</strong><p>{{ graphRagAnswer }}</p><button type="button" @click="saveGraphRagNote">保存为学习笔记</button></article>
            </div>
            <div class="rag-citations"><header><strong>引用节点与关系</strong><span>{{ graphRagNodeIds.size }} 个节点</span></header><button v-for="result in searchResults" :key="String(result.id ?? result.kp_id)" type="button" @click="focusSearchResult(result)"><Network :size="15" /><span><b>{{ result.name ?? result.kp_id ?? result.id }}</b><small>{{ String(result.description ?? result.snippet ?? '').slice(0, 72) }}</small></span><em v-if="result.score != null">{{ Number(result.score).toFixed(2) }}</em></button></div>
          </div>
        </section>

        <section v-else-if="activeDock === 'path'" class="dock-content path-panel">
          <div class="dock-heading"><div><span>学习路径</span><h2>我的课程路径</h2></div><p>橙色路径会直接叠加到图谱，点击步骤即可定位节点。</p></div>
          <div v-if="learningPath.length" class="learning-path-strip">
            <button v-for="(step, index) in learningPath" :key="step.kp_id" type="button" :class="{ completed: index < currentPathIndex, current: index === currentPathIndex }" @click="locateNode(nodes.find(node => node.id === step.kp_id)! as Graph3dNode)">
              <span>{{ index < currentPathIndex ? '✓' : index + 1 }}</span><div><b>{{ step.name }}</b><small>{{ index < currentPathIndex ? '已完成' : index === currentPathIndex ? '当前节点' : '待学习' }}</small></div><ChevronRight :size="15" />
            </button>
          </div>
          <div v-else class="dock-empty"><RouteIcon :size="22" /><strong>当前课程还没有个人学习路径</strong><span>选择图谱节点后，可使用“双图路径规划”生成路径建议。</span></div>
        </section>

        <section v-else-if="activeDock === 'search'" class="dock-content search-panel">
          <div class="dock-heading"><div><span>知识检索</span><h2>统一搜索课程知识</h2></div><p>支持名称、语义与知识点 ID 检索，结果可直接定位图谱。</p></div>
          <div class="search-workspace">
            <div><label><Search :size="16" /><input v-model="searchQuery" placeholder="输入名称、问题或关系" @keydown.enter="runSearch" /><button type="button" :disabled="searching" @click="runSearch"><Loader2 v-if="searching" :size="15" class="spin" /><Search v-else :size="15" /></button></label><button v-for="result in searchResults" :key="String(result.id ?? result.kp_id)" type="button" class="search-result-row" @click="focusSearchResult(result)"><Network :size="15" /><span><b>{{ result.name ?? result.kp_id ?? result.id }}</b><small>{{ String(result.description ?? result.snippet ?? '').slice(0, 80) }}</small></span><em v-if="result.score != null">{{ Number(result.score).toFixed(2) }}</em></button></div>
            <div><label><Target :size="16" /><input v-model="lookupId" placeholder="精确输入 kp_id" @keydown.enter="runLookup" /><button type="button" :disabled="lookingUp" @click="runLookup"><Loader2 v-if="lookingUp" :size="15" class="spin" /><Target v-else :size="15" /></button></label><button v-if="lookupResult" type="button" class="search-result-row" @click="focusLookupResult"><Target :size="15" /><span><b>{{ lookupResult.name ?? lookupResult.kp_id ?? lookupResult.id }}</b><small>{{ String(lookupResult.description ?? lookupResult.summary ?? '').slice(0, 80) }}</small></span></button></div>
          </div>
        </section>

        <section v-else-if="activeDock === 'recommend'" class="dock-content recommendation-panel">
          <div class="dock-heading"><div><span class="ai-label"><Sparkles :size="14" />智能推荐</span><h2>下一步学习建议</h2></div><p>根据当前路径与掌握状态选择优先节点。</p></div>
          <div v-if="recommendedNodes.length" class="recommendation-list"><button v-for="node in recommendedNodes" :key="node.id" type="button" @click="locateNode(node)"><span class="recommend-icon"><Sparkles :size="16" /></span><div><b>建议学习「{{ node.name }}」</b><p>当前掌握度 {{ Math.round(node.mastery * 100) }}%，位于你的学习路径中。</p><small>智狐规划 + 团团评估 · 预计 20 分钟</small></div><span>定位节点<ChevronRight :size="15" /></span></button></div>
          <div v-else class="dock-empty"><Check :size="22" /><strong>当前路径节点状态良好</strong><span>完成新的练习后，推荐会随掌握度变化更新。</span></div>
        </section>

        <section v-else-if="activeDock === 'achievement'" class="dock-content achievement-panel">
          <div class="achievement-grid">
            <div class="achievement-main">
              <div class="achievement-progress-head">
                <div><span>图谱节点进度</span><strong>{{ nodeStateCounts.mastered }}<i> / {{ nodes.length }}</i></strong></div>
                <em>{{ overallProgress }}%</em>
              </div>
              <div class="stage-track">
                <i class="stage-fill" :style="{ transform: `scaleX(${overallProgress / 100})` }" />
              </div>
              <div class="stage-marks">
                <button
                  v-for="event in timelineEvents"
                  :key="event.title"
                  type="button"
                  :class="{ unlocked: event.unlocked }"
                  :title="event.desc"
                  @click="filterFromPanel('mastered', '已掌握')"
                >
                  <b>{{ event.title }}</b>
                  <small>{{ event.unlocked ? '已解锁' : `${event.progress}%` }}</small>
                </button>
              </div>
              <div class="achievement-kpis">
                <button type="button" :class="{ active: nodeFilter === 'mastered' }" @click="filterFromPanel('mastered', '已掌握')"><span>已掌握</span><strong>{{ nodeStateCounts.mastered }}</strong></button>
                <button type="button" :class="{ active: nodeFilter === 'learning' }" @click="filterFromPanel('learning', '学习中')"><span>学习中</span><strong>{{ nodeStateCounts.learning }}</strong></button>
                <button type="button" :class="{ active: nodeFilter === 'at_risk' }" @click="filterFromPanel('at_risk', '薄弱')"><span>薄弱</span><strong>{{ nodeStateCounts.weak }}</strong></button>
                <button type="button" :class="{ active: nodeFilter === 'not_started' }" @click="filterFromPanel('not_started', '待学习')"><span>待学习</span><strong>{{ nodeStateCounts.pending }}</strong></button>
                <button type="button" @click="coursePanelOpen = true"><span>已完成章节</span><strong>{{ completedChapterCount }}<i> / {{ chapterStats.length }}</i></strong></button>
              </div>
            </div>
            <div class="achievement-side">
              <div v-if="nextAchievement" class="next-achievement">
                <span>下一成就目标</span>
                <b>{{ nextAchievement.title }}</b>
                <small>{{ nextAchievement.desc }} · 当前 {{ nextAchievement.progress }}%</small>
                <i><em :style="{ transform: `scaleX(${nextAchievement.progress / 100})` }" /></i>
              </div>
              <div v-else class="next-achievement done">
                <span>全部成就已解锁</span>
                <b>你已点亮整张知识图谱</b>
              </div>
              <div class="recommend-action">
                <span>推荐行动</span>
                <button v-if="recommendedNodes.length" type="button" @click="locateNode(recommendedNodes[0])">
                  <Sparkles :size="14" />学习「{{ recommendedNodes[0].name }}」<ChevronRight :size="14" />
                </button>
                <button v-else type="button" @click="activeDock = 'path'">
                  <RouteIcon :size="14" />查看学习路径<ChevronRight :size="14" />
                </button>
              </div>
            </div>
          </div>
        </section>

        <section v-else class="dock-content statistics-panel">
          <div class="statistics-strip">
            <div><span>知识节点</span><strong>{{ nodes.length }}</strong></div>
            <div><span>关系边</span><strong>{{ edges.length }}</strong></div>
            <div><span>关系类型</span><strong>{{ relationTypeCount }}</strong></div>
            <button type="button" :class="{ active: nodeFilter === 'learning' }" @click="filterFromPanel('learning', '学习中')"><span>学习中</span><strong>{{ nodeStateCounts.learning }}</strong></button>
            <button type="button" :class="{ active: nodeFilter === 'mastered' }" @click="filterFromPanel('mastered', '已掌握')"><span>已掌握</span><strong>{{ nodeStateCounts.mastered }}</strong></button>
            <div><span>章节数</span><strong>{{ chapterStats.length }}</strong></div>
          </div>
          <div class="statistics-grid">
            <div class="stat-block">
              <header><strong>节点状态分布</strong><span>点击筛选图谱</span></header>
              <button type="button" class="dist-row" :class="{ active: nodeFilter === 'mastered' }" @click="filterFromPanel('mastered', '已掌握')">
                <span>已掌握</span><i><em :style="{ width: `${nodes.length ? (nodeStateCounts.mastered / nodes.length) * 100 : 0}%`, background: '#247553' }" /></i><b>{{ nodeStateCounts.mastered }}</b>
              </button>
              <button type="button" class="dist-row" :class="{ active: nodeFilter === 'learning' }" @click="filterFromPanel('learning', '学习中')">
                <span>学习中</span><i><em :style="{ width: `${nodes.length ? (nodeStateCounts.learning / nodes.length) * 100 : 0}%`, background: '#3e6d9c' }" /></i><b>{{ nodeStateCounts.learning }}</b>
              </button>
              <button type="button" class="dist-row" :class="{ active: nodeFilter === 'at_risk' }" @click="filterFromPanel('at_risk', '薄弱')">
                <span>薄弱</span><i><em :style="{ width: `${nodes.length ? (nodeStateCounts.weak / nodes.length) * 100 : 0}%`, background: '#b5423a' }" /></i><b>{{ nodeStateCounts.weak }}</b>
              </button>
              <button type="button" class="dist-row" :class="{ active: nodeFilter === 'not_started' }" @click="filterFromPanel('not_started', '待学习')">
                <span>待学习</span><i><em :style="{ width: `${nodes.length ? (nodeStateCounts.pending / nodes.length) * 100 : 0}%`, background: '#89857d' }" /></i><b>{{ nodeStateCounts.pending }}</b>
              </button>
            </div>
            <div class="stat-block">
              <header><strong>章节分布</strong><span>点击只看本章</span></header>
              <button
                v-for="chapter in chapterStats"
                :key="chapter.label"
                type="button"
                class="dist-row"
                :class="{ active: chapterFocus === chapter.label }"
                @click="toggleChapterFocus(chapter.label)"
              >
                <span>{{ chapter.label }}</span><i><em :style="{ width: `${chapter.mastery}%`, background: chapter.mastery >= 80 ? '#247553' : chapter.mastery >= 50 ? '#d0a84a' : '#be5a50' }" /></i><b>{{ chapter.count }} 节点</b>
              </button>
            </div>
            <div class="stat-block">
              <header><strong>关系类型分布</strong><span>点击只看该类</span></header>
              <button
                v-for="item in relationTypes.slice(0, 6)"
                :key="item.key"
                type="button"
                class="dist-row"
                @click="soloRelation(item.key)"
              >
                <span>{{ item.label }}</span><i><em :style="{ width: `${edges.length ? (item.count / edges.length) * 100 : 0}%`, background: item.style.color }" /></i><b>{{ item.count }}</b>
              </button>
            </div>
            <div class="stat-block">
              <header><strong>依赖分析</strong><span>点击定位节点</span></header>
              <button v-if="dependencyInsights.topIn" type="button" class="dist-row" @click="dependencyInsights.topIn && locateNode(dependencyInsights.topIn)">
                <span>前置依赖最多</span><b>{{ dependencyInsights.topIn.name }} · {{ dependencyInsights.topInCount }}</b>
              </button>
              <button v-if="dependencyInsights.topOut" type="button" class="dist-row" @click="dependencyInsights.topOut && locateNode(dependencyInsights.topOut)">
                <span>后续影响最大</span><b>{{ dependencyInsights.topOut.name }} · {{ dependencyInsights.topOutCount }}</b>
              </button>
              <div class="dist-row static"><span>孤立节点</span><b>{{ dependencyInsights.isolatedCount }}</b></div>
              <button type="button" class="clear-filters-btn" @click="clearGraphFilters">清除全部筛选</button>
            </div>
          </div>
        </section>
      </div>
    </footer>

    <div class="graph-status-bar" role="status">
      <span><i :class="loading ? 'loading' : 'ready'" />{{ loading ? '正在同步' : '图谱已就绪' }}</span>
      <button type="button" class="status-link" title="打开图谱统计" @click="toggleDock('stats')">
        {{ graphLevel === 'clusters' ? `${graphClusters.length} 聚类 · ${nodes.length} 知识点` : `${visibleNodesList.length} 节点 · ${visibleEdgesList.length} 关系` }}
      </button>
      <span>{{ graphLevel === 'clusters' ? '聚类概览' : activeCluster ? `聚类 · ${activeCluster.label}` : `${PERSPECTIVE_LABELS[perspective]} · ${LAYOUT_LABELS[layoutMode]}` }}</span>
      <span>Zoom {{ Math.round(savedZoom * 100) }}%</span>
      <button
        v-if="nodeFilter !== 'all' || chapterFocus || hiddenRelations.size"
        type="button"
        class="status-filter"
        title="清除全部筛选"
        @click="clearGraphFilters"
      >筛选中{{ chapterFocus ? ` · ${chapterFocus}` : '' }}<X :size="12" /></button>
      <button type="button" @click="shortcutsOpen = true"><Keyboard :size="14" />快捷键</button>
    </div>

    <div v-if="shortcutsOpen" class="shortcuts-backdrop" role="dialog" aria-modal="true" aria-labelledby="shortcuts-title" @click.self="shortcutsOpen = false">
      <section class="shortcuts-dialog">
        <header><div><span>操作帮助</span><h2 id="shortcuts-title">知识图谱快捷键</h2></div><button type="button" aria-label="关闭快捷键说明" @click="shortcutsOpen = false"><X :size="18" /></button></header>
        <dl><div><dt>F</dt><dd>适应画布</dd></div><div><dt>R</dt><dd>重置视图</dd></div><div><dt>/</dt><dd>搜索节点</dd></div><div><dt>G</dt><dd>打开 GraphRAG</dd></div><div><dt>P</dt><dd>打开学习路径</dd></div><div><dt>L</dt><dd>显示或隐藏图例</dd></div><div><dt>Enter</dt><dd>聚焦当前节点</dd></div><div><dt>Esc</dt><dd>关闭当前面板</dd></div></dl>
      </section>
    </div>

    <transition name="notice-fade"><div v-if="workspaceNotice" class="workspace-notice" role="status">{{ workspaceNotice }}</div></transition>
  </div>

</template>

<style scoped>
.spin {
  animation: gr-spin 1s linear infinite;
}

@keyframes gr-spin {
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
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.seed-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.empty-hint {
  padding: 12px;
  border-radius: 10px;
  background: var(--paper-2);
  color: var(--muted);
  font-size: 12.5px;
  line-height: 1.6;
}

.course-select {
  height: 32px;
  padding: 0 10px;
  border-radius: 9px;
  border: var(--border-soft);
  background: var(--paper);
  font-size: 12.5px;
  color: var(--ink);
}

.graph-kpis {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 10px;
  margin-bottom: 12px;
}

.graph-kpis > div {
  padding: 10px;
  border-radius: var(--radius-md);
  border: var(--border-soft);
  background: var(--paper);
  text-align: center;
}

.graph-kpis b {
  display: block;
  font-size: 20px;
  color: var(--orange-600);
  font-family: var(--serif);
}

.graph-kpis small {
  font-size: 11px;
  color: var(--muted);
}

.graph-main {
  padding: 24px;
  display: flex;
  flex-direction: column;
}

.graph-canvas {
  /* 大屏跟随视口高度，小屏保底 480px，避免图谱被压扁或超出排版 */
  height: clamp(480px, 62vh, 680px);
  border-radius: var(--radius-md);
  border: var(--border-soft);
  background:
    radial-gradient(circle at 30% 20%, rgba(255, 230, 207, 0.35), transparent 55%),
    var(--paper);
}

.graph-legend {
  margin-top: 10px;
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  font-size: 12px;
  color: var(--neutral-600);
}

.graph-legend span {
  display: flex;
  align-items: center;
  gap: 6px;
}

.graph-legend i {
  width: 10px;
  height: 10px;
  border-radius: 999px;
}

.graph-legend small {
  margin-left: auto;
  color: var(--subtle);
}

.path-legend {
  font-weight: 500;
}

/* 学习路径开关按钮 */
.path-toggle {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.path-toggle.active {
  background: #fef3c7;
  border-color: #f59e0b;
  color: #b45309;
}

.path-icon {
  font-size: 14px;
}

/* ---------- 检索 ---------- */
.search-row {
  display: flex;
  gap: 8px;
}

.search-row input {
  flex: 1;
  height: 34px;
  padding: 0 12px;
  border-radius: 9px;
  border: var(--border-soft);
  background: var(--paper);
  font-size: 13px;
}

.search-result {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 8px 6px;
  border-radius: 9px;
  cursor: pointer;
  transition: background 0.12s ease;
}

.search-result:hover {
  background: var(--paper-2);
}

.search-result > div {
  flex: 1;
  min-width: 0;
}

.search-result b {
  display: block;
  font-size: 12.5px;
  color: var(--ink);
}

.search-result small {
  font-size: 11px;
  color: var(--muted);
}

.search-result em {
  font-style: normal;
  font-size: 11px;
  color: var(--status-info);
  font-family: var(--mono);
}

/* ---------- 详情 ---------- */
.kp-detail {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.kp-meta {
  margin: 0;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.kp-desc {
  margin: 0;
  font-size: 12.5px;
  line-height: 1.65;
  color: var(--neutral-600);
}

.neighbor-list b {
  display: block;
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 6px;
}

.neighbor-list span {
  display: inline-block;
  margin: 0 6px 6px 0;
  padding: 3px 10px;
  border-radius: 999px;
  background: var(--paper-2);
  border: var(--border-soft);
  font-size: 11.5px;
  color: var(--neutral-600);
}

.kp-action {
  justify-content: center;
  text-align: center;
  text-decoration: none;
}

/* Plan D · 3.4 — BKT mastery hover 详情卡 */
.bkt-trend-card {
  border: 1px solid var(--neutral-300, #cbd5e1);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.72);
  border-radius: 8px;
  padding: 8px 10px;
  background: var(--paper-2);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.bkt-trend-head {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12.5px;
}

.bkt-trend-arrow {
  font-size: 16px;
  font-weight: 700;
  line-height: 1;
}

.bkt-trend-meta {
  font-size: 11.5px;
  color: var(--muted);
}

.bkt-trend-meta b {
  color: var(--ink);
  font-family: var(--mono);
}

.bkt-trend-tip {
  margin: 2px 0 0;
  font-size: 11.5px;
  color: var(--muted);
  line-height: 1.55;
}

/* ---------- 节点筛选器 ---------- */
.filter-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 8px 0;
}

.filter-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  border-radius: 999px;
  border: var(--border-soft);
  background: var(--paper);
  font-size: 12px;
  color: var(--neutral-600);
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease, background 0.2s ease, color 0.2s ease, opacity 0.2s ease;
}

.filter-chip:hover {
  background: var(--paper-2);
  border-color: var(--neutral-300);
}

.filter-chip.active {
  background: var(--orange-50);
  border-color: var(--orange-400);
  color: var(--orange-700);
  font-weight: 500;
}

.chip-icon {
  font-size: 13px;
}

.filter-stats {
  padding-top: 8px;
  border-top: var(--border-soft);
  font-size: 11px;
  color: var(--muted);
  text-align: right;
}

/* ---------- 学习动作入口 ---------- */
.action-buttons {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 12px;
}

.action-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 10px 16px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease, background 0.2s ease, color 0.2s ease, opacity 0.2s ease;
  text-decoration: none;
  border: none;
}

.action-btn.primary {
  background: linear-gradient(135deg, var(--orange-500), var(--orange-600));
  color: white;
  box-shadow: 0 2px 8px rgba(234, 90, 26, 0.3);
}

.action-btn.primary:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(234, 90, 26, 0.4);
}

.action-btn.secondary {
  background: var(--paper-2);
  color: var(--neutral-700);
  border: var(--border-soft);
}

.action-btn.secondary:hover {
  background: var(--neutral-100);
  border-color: var(--neutral-300);
}

.btn-icon {
  font-size: 14px;
}

/* ---------- 掌握度趋势图 ---------- */
.trend-toggle {
  width: 100%;
  margin-top: 12px;
  padding: 10px 12px;
  border-radius: 10px;
  border: var(--border-soft);
  background: var(--paper-2);
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease, background 0.2s ease, color 0.2s ease, opacity 0.2s ease;
}

.trend-toggle:hover {
  background: var(--neutral-100);
}

.trend-toggle.active {
  background: #fef3c7;
  border-color: #f59e0b;
}

.trend-toggle span {
  font-size: 13px;
  font-weight: 500;
  color: var(--neutral-700);
}

.trend-toggle small {
  font-size: 11px;
  color: var(--muted);
}

.trend-chart-container {
  margin-top: 12px;
  padding: 12px;
  border-radius: 10px;
  background: var(--paper);
  border: var(--border-soft);
  position: relative;
}

.trend-chart {
  height: 160px;
  width: 100%;
}

.trend-empty {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-size: 12px;
  color: var(--muted);
}

/* ---------- 知识对比 ---------- */
.compare-hint {
  padding: 8px 0;
  font-size: 12px;
  color: var(--muted);
}

.compare-hint p {
  margin: 0;
}

.compare-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 12px;
}

.compare-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: var(--paper-2);
  border-radius: 8px;
  border: var(--border-soft);
}

.compare-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--neutral-700);
}

.compare-remove {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  border: none;
  background: var(--neutral-200);
  color: var(--neutral-600);
  cursor: pointer;
  font-size: 14px;
  line-height: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.compare-remove:hover {
  background: var(--status-error);
  color: white;
}

.compare-chart-container {
  padding: 12px;
  background: var(--paper);
  border-radius: 10px;
  border: var(--border-soft);
}

.compare-chart {
  height: 200px;
  width: 100%;
}

.compare-waiting {
  padding: 20px;
  text-align: center;
  font-size: 12px;
  color: var(--muted);
  background: var(--paper-2);
  border-radius: 8px;
  border: var(--border-soft);
}

/* ---------- 学习模式切换 ---------- */
.mode-switch {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.mode-btn {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px;
  border-radius: 10px;
  border: var(--border-soft);
  background: var(--paper);
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease, background 0.2s ease, color 0.2s ease, opacity 0.2s ease;
}

.mode-btn:hover {
  background: var(--paper-2);
}

.mode-btn.active {
  background: #fef3c7;
  border-color: #f59e0b;
}

.mode-icon {
  font-size: 20px;
}

.mode-info {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
}

.mode-info b {
  font-size: 13px;
  color: var(--neutral-700);
}

.mode-info small {
  font-size: 11px;
  color: var(--muted);
}

/* ---------- 智能推荐 ---------- */
.recommend-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.recommend-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: var(--paper-2);
  border-radius: 10px;
  border: var(--border-soft);
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease, background 0.2s ease, color 0.2s ease, opacity 0.2s ease;
}

.recommend-item:hover {
  background: #fef3c7;
  border-color: #f59e0b;
}

.rec-icon {
  font-size: 16px;
}

.rec-info {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.rec-info b {
  font-size: 13px;
  color: var(--neutral-700);
}

.rec-info small {
  font-size: 11px;
  color: var(--muted);
}

.rec-arrow {
  font-size: 14px;
  color: var(--orange-500);
}

.rec-empty {
  padding: 16px;
  text-align: center;
  font-size: 12px;
  color: var(--muted);
  background: var(--paper-2);
  border-radius: 8px;
}

.rec-summary {
  padding: 12px;
  text-align: center;
  font-size: 12px;
  color: var(--muted);
}

.rec-summary p {
  margin: 0;
}

/* ---------- 学习里程碑 ---------- */
.milestones {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.milestone-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: var(--paper-2);
  border-radius: 10px;
  border: var(--border-soft);
}

.ms-icon {
  font-size: 20px;
}

.ms-info {
  display: flex;
  flex-direction: column;
}

.ms-info b {
  font-size: 13px;
  color: var(--neutral-700);
}

.ms-info small {
  font-size: 11px;
  color: var(--muted);
}

.ms-empty {
  padding: 16px;
  text-align: center;
  font-size: 12px;
  color: var(--muted);
}

/* =====================================================
   新增功能样式
   ===================================================== */

/* ---------- 双图路径规划 ---------- */
.dual-graph-bar {
  margin-top: 10px;
  padding: 14px 16px;
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, #eef2ff, #f5f3ff);
  border: 1px solid #6366f1;
  box-shadow: var(--shadow-2);
  animation: tour-slide-in 0.3s ease;
}

.dual-graph-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.dual-graph-badge {
  padding: 3px 10px;
  border-radius: 999px;
  background: #6366f1;
  color: white;
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
}

.dual-graph-title {
  font-size: 13px;
  color: #3730a3;
  font-weight: 500;
}

.dual-graph-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.dual-tab {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 10px;
  border: 1px solid #c7d2fe;
  background: white;
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease, background 0.2s ease, color 0.2s ease, opacity 0.2s ease;
  text-align: left;
}

.dual-tab:hover {
  background: #eef2ff;
}

.dual-tab.active {
  background: #6366f1;
  border-color: #6366f1;
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.3);
}

.dual-tab.active .tab-info b,
.dual-tab.active .tab-info small {
  color: white;
}

.dual-tab.active .tab-icon {
  filter: brightness(1.3);
}

.tab-icon {
  font-size: 18px;
  flex-shrink: 0;
}

.tab-info {
  display: flex;
  flex-direction: column;
}

.tab-info b {
  font-size: 12.5px;
  color: #3730a3;
}

.tab-info small {
  font-size: 10px;
  color: #6366f1;
}

.dual-graph-steps {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 240px;
  overflow-y: auto;
}

.dual-step {
  display: flex;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.7);
  border: 1px solid #e0e7ff;
  cursor: pointer;
  transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease, background 0.15s ease, color 0.15s ease, opacity 0.15s ease;
}

.dual-step:hover {
  background: white;
  border-color: #a5b4fc;
}

.dual-step.current {
  background: #6366f1;
  border-color: #6366f1;
}

.dual-step.current .step-content b,
.dual-step.current .step-content small,
.dual-step.current .step-num {
  color: white;
}

.step-num {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #eef2ff;
  color: #4f46e5;
  font-size: 11px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.step-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.step-content b {
  font-size: 12.5px;
  color: var(--neutral-700);
}

.step-content small {
  font-size: 11px;
  color: var(--muted);
  line-height: 1.4;
}

.step-tags {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  margin-top: 2px;
}

.tag {
  padding: 1px 6px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 500;
  background: var(--paper-2);
  color: var(--neutral-600);
}

.tag-prereq { background: #dbeafe; color: #1e40af; }
.tag-similarity { background: #fef3c7; color: #92400e; }
.tag-mastery { background: #fee2e2; color: #991b1b; }

.dual-graph-explanation {
  margin-top: 10px;
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.5);
}

.dual-graph-explanation p {
  margin: 0;
  font-size: 11.5px;
  color: #3730a3;
  font-weight: 500;
}

.dual-graph-explanation small {
  font-size: 10.5px;
  color: #6366f1;
}

/* ---------- 时光机预测 ---------- */
.forecast-container {
  margin-top: 12px;
  padding: 12px;
  border-radius: 10px;
  background: linear-gradient(135deg, #fff7ed, #fffbf0);
  border: 1px solid #f59e0b;
}

.forecast-summary {
  font-size: 12px;
  color: #92400e;
  line-height: 1.5;
  margin-bottom: 8px;
}

.forecast-chart {
  height: 180px;
  width: 100%;
}

.forecast-milestones {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: 8px;
}

.forecast-milestone {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.6);
}

.ms-day {
  font-size: 10px;
  font-weight: 700;
  color: #2f9f6b;
  font-family: var(--mono);
  white-space: nowrap;
}

.ms-label {
  flex: 1;
  font-size: 11.5px;
  color: var(--neutral-600);
}

.ms-pred {
  font-size: 12px;
  font-weight: 600;
  color: #ea5a1a;
  font-family: var(--mono);
}

/* ---------- 双图路径规划增强 ---------- */
.dual-graph-meta {
  display: flex;
  gap: 8px;
  margin-top: 8px;
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(99, 102, 241, 0.06);
  flex-wrap: wrap;
}
.dual-graph-meta .meta-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.7);
}
.dual-graph-meta .meta-icon { font-size: 14px; }
.dual-graph-meta .meta-info { display: flex; flex-direction: column; }
.dual-graph-meta .meta-info b { font-size: 13px; font-weight: 700; color: #3730a3; }
.dual-graph-meta .meta-info small { font-size: 9.5px; color: #6366f1; }

.dual-graph-bloom {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 6px;
  padding: 4px 10px;
  flex-wrap: wrap;
}
.dual-graph-bloom .bloom-label { font-size: 10.5px; color: #6b7280; font-weight: 600; }
.dual-graph-bloom .bloom-chip {
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 10px;
  background: rgba(234, 90, 26, 0.1);
  color: #ea5a1a;
  font-weight: 500;
}

.dual-graph-stats {
  display: flex;
  gap: 12px;
  margin-top: 6px;
  padding: 6px 10px;
  border-radius: 6px;
  background: rgba(47, 159, 107, 0.06);
  flex-wrap: wrap;
}
.dual-graph-stats span {
  font-size: 10.5px;
  color: #2f9f6b;
  font-weight: 500;
}

/* ---------- 时光机预测洞察 ---------- */
.forecast-insights {
  margin-bottom: 10px;
}
.forecast-insights .insight-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 6px;
  margin-bottom: 8px;
}
.forecast-insights .insight-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 6px 4px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.7);
  border: 1px solid rgba(234, 90, 26, 0.12);
}
.forecast-insights .insight-label {
  font-size: 9.5px;
  color: #92400e;
  margin-bottom: 2px;
}
.forecast-insights .insight-value {
  font-size: 14px;
  font-weight: 700;
  font-family: var(--mono);
}
.forecast-insights .trend-up { color: #2f9f6b; }
.forecast-insights .trend-down { color: #c86a5a; }
.forecast-insights .trend-stable { color: #d89229; }
.forecast-insights .risk-high { color: #c86a5a; }
.forecast-insights .risk-medium { color: #d89229; }
.forecast-insights .risk-low { color: #2f9f6b; }

.forecast-actions {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 6px 8px;
  border-radius: 6px;
  background: rgba(234, 90, 26, 0.06);
}
.forecast-action {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  font-size: 11px;
  color: #92400e;
  line-height: 1.4;
}
.forecast-action .action-icon { flex-shrink: 0; font-size: 12px; }

/* ---------- 解锁链路详情面板 ---------- */
.unlock-detail-panel {
  margin-top: 12px;
  padding: 12px;
  border-radius: 10px;
  background: linear-gradient(135deg, rgba(47, 159, 107, 0.06), rgba(47, 159, 107, 0.02));
  border: 1px solid rgba(47, 159, 107, 0.2);
}
.detail-panel-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.detail-badge {
  font-size: 12px;
  font-weight: 700;
  color: #2f9f6b;
  padding: 3px 10px;
  border-radius: 6px;
  background: rgba(47, 159, 107, 0.12);
}
.detail-badge.weak {
  color: #b3413a;
  background: rgba(179, 65, 58, 0.12);
}
.detail-subtitle {
  font-size: 11px;
  color: #6b7280;
}
.unlock-summary-bar {
  display: flex;
  gap: 6px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}
.unlock-summary-bar .summary-chip {
  font-size: 10.5px;
  padding: 3px 8px;
  border-radius: 10px;
  background: rgba(47, 159, 107, 0.1);
  color: #2f9f6b;
  font-weight: 600;
}
.unlock-summary-bar .summary-chip.bloom {
  background: rgba(234, 90, 26, 0.1);
  color: #ea5a1a;
}
.unlock-section {
  margin-bottom: 8px;
}
.unlock-section-title {
  font-size: 11px;
  font-weight: 600;
  color: #374151;
  margin-bottom: 4px;
  padding-left: 2px;
}
.unlock-node-list {
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.unlock-node-list.compact {
  max-height: 200px;
  overflow-y: auto;
}
.unlock-node-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 8px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.6);
  cursor: pointer;
  transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease, background 0.15s ease, opacity 0.15s ease;
}
.unlock-node-item:hover {
  background: rgba(47, 159, 107, 0.1);
  transform: translateX(2px);
}
.unlock-node-item.direct { border-color: rgba(47, 159, 107, 0.26); box-shadow: inset 0 0 0 1px rgba(47, 159, 107, 0.08); }
.unlock-node-item.indirect { border-color: rgba(216, 146, 41, 0.26); opacity: 0.9; box-shadow: inset 0 0 0 1px rgba(216, 146, 41, 0.08); }
.unlock-node-icon { font-size: 14px; flex-shrink: 0; }
.unlock-node-info { flex: 1; min-width: 0; }
.unlock-node-info b { font-size: 12px; color: #374151; display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.unlock-node-info small { font-size: 10px; color: #9ca3af; }
.unlock-node-mastery { font-size: 12px; font-weight: 700; font-family: var(--mono); flex-shrink: 0; }

/* ---------- 薄弱根因链详情面板 ---------- */
.weakness-detail-panel {
  margin-top: 12px;
  padding: 12px;
  border-radius: 10px;
  background: linear-gradient(135deg, rgba(179, 65, 58, 0.06), rgba(179, 65, 58, 0.02));
  border: 1px solid rgba(179, 65, 58, 0.2);
}
.weakness-chain-visual {
  display: flex;
  flex-direction: column;
  gap: 0;
  margin-bottom: 10px;
}
.weakness-chain-item {
  display: flex;
  flex-direction: column;
  align-items: stretch;
}
.chain-connector {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 2px 0;
  position: relative;
}
.chain-connector .connector-line {
  width: 2px;
  height: 12px;
  background: #d1d5db;
}
.chain-connector .connector-label {
  font-size: 9.5px;
  color: #9ca3af;
  position: absolute;
  left: 50%;
  transform: translateX(8px);
  top: 2px;
  white-space: nowrap;
}
.chain-node-card {
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.7);
  border: 1px solid rgba(229, 231, 235, 0.8);
  cursor: pointer;
  transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease, background 0.15s ease, opacity 0.15s ease;
}
.chain-node-card:hover {
  border-color: #b3413a;
  box-shadow: 0 2px 8px rgba(179, 65, 58, 0.1);
}
.weakness-chain-item.root .chain-node-card {
  border-color: #b3413a;
  border-width: 2px;
  background: rgba(179, 65, 58, 0.06);
}
.weakness-chain-item.current .chain-node-card {
  border-color: #ea5a1a;
  border-style: dashed;
}
.chain-node-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}
.chain-node-icon { font-size: 14px; }
.chain-node-icon.root { font-size: 16px; }
.chain-node-header b { font-size: 12.5px; color: #1f2937; flex: 1; }
.chain-tag {
  font-size: 9px;
  padding: 1px 6px;
  border-radius: 8px;
  font-weight: 600;
}
.chain-tag.root-tag { background: #b3413a; color: #fff; }
.chain-tag.current-tag { background: #ea5a1a; color: #fff; }
.chain-node-meta {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 4px;
}
.chain-node-meta .meta-chip {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.8);
  font-weight: 500;
}
.chain-node-meta .gap-chip { color: #c86a5a; background: rgba(200, 106, 90, 0.1); }
.chain-mastery-bar {
  position: relative;
  height: 5px;
  border-radius: 3px;
  background: #f3f4f6;
  overflow: visible;
}
.chain-mastery-fill {
  height: 100%;
  border-radius: 3px;
  transition: transform 0.3s ease;
}
.chain-mastery-target {
  position: absolute;
  left: 80%;
  top: -2px;
  width: 2px;
  height: 9px;
  background: #2f9f6b;
  border-radius: 1px;
}
.weakness-recommendations {
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(234, 90, 26, 0.06);
}
.weakness-recommendations .rec-title {
  font-size: 11.5px;
  font-weight: 600;
  color: #ea5a1a;
  margin-bottom: 4px;
}
.weakness-recommendations .rec-item {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  font-size: 11px;
  color: #6b7280;
  line-height: 1.4;
  margin-bottom: 2px;
}
.weakness-recommendations .rec-num {
  flex-shrink: 0;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #ea5a1a;
  color: #fff;
  font-size: 9px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* ---------- 智能分析按钮 ---------- */
@keyframes tour-slide-in {
  from { opacity: 0; transform: translateY(-8px); }
  to { opacity: 1; transform: translateY(0); }
}

.analysis-buttons {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 10px;
}

.analysis-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease, background 0.2s ease, color 0.2s ease, opacity 0.2s ease;
  border: 1px solid;
  text-align: left;
  flex-direction: row;
}

.analysis-btn .btn-icon {
  font-size: 16px;
  flex-shrink: 0;
}

.analysis-btn small {
  display: block;
  font-size: 11px;
  font-weight: 400;
  opacity: 0.8;
  margin-top: 1px;
}

.unlock-btn {
  background: #ecfdf5;
  border-color: #6ee7b7;
  color: #065f46;
}

.dualgraph-btn {
  background: #eef2ff;
  border-color: #a5b4fc;
  color: #3730a3;
}

.dualgraph-btn:hover {
  background: #e0e7ff;
  border-color: #818cf8;
}

.dualgraph-btn.active {
  background: #6366f1;
  border-color: #6366f1;
  color: white;
}

.forecast-btn {
  background: #fffbeb;
  border-color: #fcd34d;
  color: #78350f;
}

.forecast-btn:hover {
  background: #fef3c7;
  border-color: #fbbf24;
}

.forecast-btn.active {
  background: #f59e0b;
  border-color: #f59e0b;
  color: white;
}

.unlock-btn:hover {
  background: #d1fae5;
  border-color: #34d399;
}

.unlock-btn.active {
  background: #2f9f6b;
  border-color: #2f9f6b;
  color: white;
}

.weak-btn {
  background: #fef2f2;
  border-color: #fca5a5;
  color: #991b1b;
}

.weak-btn:hover {
  background: #fee2e2;
  border-color: #f87171;
}

.weak-btn.active {
  background: #b3413a;
  border-color: #b3413a;
  color: white;
}

/* ---------- 学习成就时间线 ---------- */
.timeline-overall {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 12px;
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, #fff7ed, #fef3c7);
  border: 1px solid #f59e0b;
  margin-bottom: 14px;
}

.timeline-overall-ring {
  position: relative;
  width: 56px;
  height: 56px;
  flex-shrink: 0;
}

.ring-svg {
  width: 100%;
  height: 100%;
}

.ring-progress {
  transition: stroke-dasharray 0.6s ease;
}

.ring-text {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-size: 13px;
  font-weight: 700;
  color: var(--orange-600);
  font-family: var(--mono);
}

.timeline-overall-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.timeline-overall-info b {
  font-size: 14px;
  color: var(--neutral-800);
}

.timeline-overall-info small {
  font-size: 11.5px;
  color: var(--neutral-600);
}

.timeline {
  display: flex;
  flex-direction: column;
  gap: 0;
  position: relative;
}

.timeline::before {
  content: '';
  position: absolute;
  left: 16px;
  top: 8px;
  bottom: 8px;
  width: 2px;
  background: var(--neutral-200);
}

.timeline-item {
  display: flex;
  gap: 12px;
  padding: 8px 0;
  position: relative;
  opacity: 0.5;
  transition: opacity 0.3s ease;
}

.timeline-item.unlocked {
  opacity: 1;
}

.timeline-item.in-progress {
  opacity: 0.85;
}

.timeline-dot {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: var(--paper);
  border: 2px solid var(--neutral-200);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  z-index: 1;
  transition: transform 0.3s ease, box-shadow 0.3s ease, border-color 0.3s ease, background 0.3s ease, opacity 0.3s ease;
}

.timeline-item.unlocked .timeline-dot {
  border-color: var(--orange-500);
  background: #fff7ed;
  box-shadow: 0 0 12px rgba(234, 90, 26, 0.25);
  animation: timeline-pop 0.4s ease;
}

.timeline-item.in-progress .timeline-dot {
  border-color: #f59e0b;
  background: #fef3c7;
}

@keyframes timeline-pop {
  0% { transform: scale(0.6); }
  60% { transform: scale(1.15); }
  100% { transform: scale(1); }
}

.timeline-icon {
  font-size: 16px;
}

.timeline-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding-top: 2px;
}

.timeline-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.timeline-head b {
  font-size: 13px;
  color: var(--neutral-700);
}

.timeline-badge-done {
  padding: 2px 8px;
  border-radius: 999px;
  background: #d1fae5;
  color: #065f46;
  font-size: 10px;
  font-weight: 600;
  white-space: nowrap;
}

.timeline-badge-progress {
  padding: 2px 8px;
  border-radius: 999px;
  background: #fef3c7;
  color: #92400e;
  font-size: 10px;
  font-weight: 600;
  font-family: var(--mono);
  white-space: nowrap;
}

.timeline-content small {
  font-size: 11.5px;
  color: var(--muted);
}

.timeline-mini-bar {
  margin-top: 4px;
  height: 4px;
  border-radius: 2px;
  background: var(--neutral-200);
  overflow: hidden;
}

.timeline-mini-fill {
  height: 100%;
  border-radius: 2px;
  background: linear-gradient(90deg, #f59e0b, #ea5a1a);
  transition: transform 0.5s ease;
}

/* ===== Impeccable graph polish: refined student-facing visual language ===== */
.graph-page {
  --graph-ease: cubic-bezier(0.22, 1, 0.36, 1);
}

.graph-page .graph-main,
.graph-page .side-card {
  border: 1px solid rgba(229, 212, 190, 0.86);
  background: linear-gradient(180deg, rgba(255, 253, 248, 0.98), rgba(255, 248, 241, 0.92));
  box-shadow: 0 16px 34px rgba(78, 55, 34, 0.07);
}

.graph-page .side-card {
  transition: transform 0.22s var(--graph-ease), box-shadow 0.22s var(--graph-ease), border-color 0.22s var(--graph-ease);
}

.graph-page .side-card:hover {
  transform: translateY(-2px);
  border-color: rgba(234, 90, 26, 0.24);
  box-shadow: 0 20px 40px rgba(78, 55, 34, 0.09);
}

.graph-canvas {
  border-radius: 18px;
  border-color: rgba(229, 212, 190, 0.9);
  background:
    linear-gradient(180deg, rgba(255, 253, 248, 0.95), rgba(255, 247, 237, 0.74)),
    radial-gradient(circle at 24% 18%, rgba(234, 90, 26, 0.12), transparent 34%),
    radial-gradient(circle at 82% 70%, rgba(47, 159, 107, 0.1), transparent 32%);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.86), 0 12px 30px rgba(78, 55, 34, 0.06);
}

.graph-kpis > div {
  background: linear-gradient(180deg, #fffdf8, #fff8f1);
  border-color: rgba(229, 212, 190, 0.88);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.82);
  transition: transform 0.18s var(--graph-ease), box-shadow 0.18s var(--graph-ease), border-color 0.18s var(--graph-ease);
}

.graph-kpis > div:hover {
  transform: translateY(-2px);
  border-color: rgba(234, 90, 26, 0.2);
  box-shadow: 0 10px 22px rgba(78, 55, 34, 0.07);
}

.graph-page .chip-icon,
.graph-page .mode-icon,
.graph-page .rec-icon,
.graph-page .btn-icon,
.graph-page .tab-icon,
.graph-page .meta-icon,
.graph-page .unlock-node-icon,
.graph-page .chain-node-icon,
.graph-page .action-icon {
  width: 24px;
  height: 24px;
  border-radius: 8px;
  display: inline-grid;
  place-items: center;
  flex: 0 0 auto;
  background: rgba(255, 247, 237, 0.92);
  border: 1px solid rgba(254, 215, 170, 0.9);
  color: #c2410c;
  font-size: 10px;
  font-weight: 800;
  line-height: 1;
  letter-spacing: 0;
}

.graph-page .chip-icon {
  width: 28px;
  font-size: 9px;
  border-radius: 999px;
}

.path-icon {
  width: 24px;
  height: 24px;
  border-radius: 8px;
  display: inline-grid;
  place-items: center;
  flex: 0 0 auto;
  background: rgba(255, 247, 237, 0.92);
  border: 1px solid rgba(254, 215, 170, 0.9);
  color: #c2410c;
}

.path-icon::before {
  content: "";
  width: 8px;
  height: 8px;
  border-radius: 999px;
  border: 2px solid currentColor;
  box-shadow: 0 0 0 3px rgba(234, 90, 26, 0.09);
}

.filter-chip,
.mode-btn,
.recommend-item,
.action-btn,
.analysis-btn,
.dual-tab,
.dual-step,
.chain-node-card,
.unlock-node-item,
.trend-toggle {
  transition-timing-function: var(--graph-ease);
}

.graph-page .small-progress .bar {
  position: relative;
  height: 6px;
  overflow: hidden;
  border-radius: 999px;
  background: var(--neutral-200);
}

.graph-page .small-progress .bar i,
.chain-mastery-fill,
.timeline-mini-fill {
  display: block;
  width: 100%;
  transform-origin: left center;
}

.chain-mastery-bar,
.timeline-mini-bar {
  overflow: hidden;
}

.timeline-icon {
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0;
}

.detail-badge,
.dual-graph-badge,
.summary-chip,
.bloom-chip {
  letter-spacing: 0;
}

@media (prefers-reduced-motion: reduce) {
  .graph-page .side-card,
  .graph-kpis > div,
  .filter-chip,
  .mode-btn,
  .recommend-item,
  .action-btn,
  .analysis-btn,
  .dual-tab,
  .dual-step,
  .chain-node-card,
  .unlock-node-item,
  .trend-toggle,
  .chain-mastery-fill,
  .timeline-mini-fill {
    transition: none;
  }
}

/* ===== Flagship graph workspace refresh ===== */
.graph-page {
  --graph-ink: #161a1d;
  --graph-muted: #5d6670;
  --graph-line: #dfe5ea;
  --graph-panel: #ffffff;
  gap: 22px;
  padding: 6px 24px 42px;
}

.graph-page .graph-main {
  padding: 0;
  border: 0;
  border-radius: 18px;
  background: #f7f8fa;
  box-shadow: 0 16px 30px rgba(21, 24, 28, 0.11);
  overflow: hidden;
}

.graph-main > .section-head {
  margin: 0;
  padding: 24px 28px 16px;
  background: #ffffff;
  border-bottom: 1px solid var(--graph-line);
}

.graph-main .section-copy h2 {
  color: var(--graph-ink);
  font-family: var(--sans);
  font-size: 24px;
  letter-spacing: 0;
}

.graph-main .section-copy p {
  color: var(--graph-muted);
}

.graph-main .section-action .primary-btn,
.graph-main .section-action .ghost-btn,
.graph-main .section-action .course-select {
  min-height: 38px;
  border-radius: 10px;
}

.graph-stage-strip {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(420px, 0.8fr);
  gap: 18px;
  align-items: stretch;
  margin: 18px 28px 16px;
  padding: 18px;
  border-radius: 14px;
  background: linear-gradient(132deg, #181512 0%, #27201a 58%, #4a2818 100%);
  color: #fff7ed;
  box-shadow: 0 10px 18px rgba(24, 21, 18, 0.18);
}

.graph-stage-copy {
  display: flex;
  flex-direction: column;
  gap: 5px;
  justify-content: center;
}

.graph-stage-copy span {
  width: fit-content;
  padding: 3px 9px;
  border-radius: 999px;
  background: rgba(249, 115, 22, 0.18);
  color: #fed7aa;
  font-size: 11px;
  font-weight: 800;
}

.graph-stage-copy strong {
  font-size: 24px;
  line-height: 1.2;
}

.graph-stage-copy small {
  max-width: 58ch;
  color: rgba(255, 247, 237, 0.7);
  font-size: 13px;
  line-height: 1.6;
}

.graph-stage-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.graph-stage-metrics > div {
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-height: 82px;
  padding: 12px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.1);
}

.graph-stage-metrics b {
  font-size: 22px;
  color: #ffffff;
}

.graph-stage-metrics small {
  margin-top: 4px;
  color: rgba(255, 247, 237, 0.66);
  font-size: 11px;
}

.graph-kpis {
  margin: 0 28px 16px;
  gap: 12px;
}

.graph-kpis > div {
  padding: 14px 12px;
  border: 1px solid var(--graph-line);
  border-radius: 12px;
  background: var(--graph-panel);
  box-shadow: none;
}

.graph-kpis b {
  color: #d94f16;
  font-family: var(--sans);
  font-size: 22px;
}

.graph-canvas {
  margin: 0 28px;
  height: clamp(540px, 66vh, 760px);
  border: 0;
  border-radius: 14px;
  background:
    linear-gradient(180deg, #101418, #171b1f 64%, #1d1713),
    #101418;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.08);
}

.graph-legend {
  margin: 14px 28px 24px;
  padding: 10px 12px;
  border-radius: 12px;
  background: #ffffff;
  border: 1px solid var(--graph-line);
  color: var(--graph-muted);
}

.graph-page .right-column {
  grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
  gap: 16px;
}

.graph-page .side-card {
  border: 1px solid var(--graph-line);
  border-radius: 14px;
  background: #ffffff;
  box-shadow: none;
}

.graph-page .side-card:hover {
  border-color: #f2b384;
  box-shadow: 0 8px 14px rgba(21, 24, 28, 0.07);
}

.graph-page .chip-icon,
.graph-page .mode-icon,
.graph-page .rec-icon,
.graph-page .btn-icon,
.graph-page .tab-icon,
.graph-page .meta-icon,
.graph-page .unlock-node-icon,
.graph-page .chain-node-icon,
.graph-page .action-icon,
.path-icon {
  border-color: #ffd7b5;
  background: #fff5ec;
  color: #c2410c;
}

.filter-chip,
.mode-btn,
.recommend-item,
.action-btn,
.analysis-btn,
.dual-tab,
.dual-step,
.trend-toggle {
  border-radius: 10px;
}

@media (max-width: 980px) {
  .graph-stage-strip { grid-template-columns: 1fr; }
  .graph-stage-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

@media (max-width: 720px) {
  .graph-page { padding: 0 14px 28px; }
  .graph-main > .section-head,
  .graph-stage-strip,
  .graph-kpis,
  .graph-canvas,
  .graph-legend { margin-left: 14px; margin-right: 14px; }
  .graph-kpis { grid-template-columns: repeat(2, 1fr); }
  .graph-canvas { height: 520px; }
}

/* ===== Graph workspace correction: light graph canvas and stable right rail ===== */
.graph-page.layout-two {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(340px, 380px);
  gap: 18px;
  align-items: start;
  padding: 6px 24px 42px;
}

.graph-page .graph-main {
  border: 1px solid var(--graph-line);
  background: #ffffff;
  box-shadow: none;
}

.graph-stage-strip {
  border: 1px solid var(--graph-line);
  background: linear-gradient(180deg, #ffffff 0%, #f7fafc 100%);
  color: var(--graph-ink);
  box-shadow: none;
}

.graph-stage-copy span {
  background: #fff4e8;
  color: #c8480f;
}

.graph-stage-copy strong {
  color: var(--graph-ink);
}

.graph-stage-copy small {
  color: var(--graph-muted);
}

.graph-stage-metrics > div {
  border: 1px solid #e6ebef;
  background: #ffffff;
}

.graph-stage-metrics b {
  color: #c8480f;
}

.graph-stage-metrics small {
  color: var(--graph-muted);
}

.graph-canvas {
  border: 1px solid #dfe6ec;
  background: linear-gradient(180deg, #fbfdff 0%, #f5f8fb 64%, #fffaf4 100%);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.84);
}

.graph-legend {
  align-items: center;
  justify-content: flex-start;
}

.graph-page .right-column {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-width: 0;
  position: sticky;
  top: 12px;
  max-height: calc(100vh - 110px);
  overflow: auto;
  padding-right: 2px;
}

.graph-page .side-card {
  border: 1px solid var(--graph-line);
  background: #ffffff;
  box-shadow: none;
}

@media (max-width: 1180px) {
  .graph-page.layout-two {
    grid-template-columns: 1fr;
  }

  .graph-page .right-column {
    position: static;
    max-height: none;
    overflow: visible;
    padding-right: 0;
  }
}

/* ===== Web workspace layout: graph canvas + utility rail ===== */
.graph-page.layout-two {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 380px;
  align-items: start;
  gap: 18px;
  width: 100%;
  min-width: 960px;
  padding: 4px 0 38px;
}

.graph-page .graph-main {
  min-width: 0;
  overflow: hidden;
  border: 1px solid #e5d4be;
  border-radius: 8px;
  background: #fffdf8;
}

.graph-main > .section-head {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 14px;
  padding: 22px 24px 18px;
  border-bottom: 1px solid #e5d4be;
  background: #fdf6e3;
}

.graph-main > .section-head .section-action {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-start;
  gap: 8px;
}

.graph-main > .section-head .section-action .seed-btn {
  margin-right: 0 !important;
}

.graph-stage-strip {
  grid-template-columns: minmax(190px, 0.75fr) minmax(320px, 1.25fr);
  gap: 14px;
  margin: 18px 20px 14px;
  padding: 16px;
  border-color: #e5d4be;
  border-radius: 8px;
  background: #fff8ef;
}

.graph-stage-metrics {
  gap: 8px;
}

.graph-stage-metrics > div {
  min-height: 70px;
  padding: 9px;
  border-color: #eadbc8;
  border-radius: 8px;
  background: #fffdf8;
}

.graph-kpis {
  margin: 0 20px 14px;
  gap: 8px;
}

.graph-kpis > div {
  min-width: 0;
  padding: 11px 8px;
  border-color: #e5d4be;
  border-radius: 8px;
  background: #ffffff;
}

.graph-canvas {
  height: 680px;
  margin: 0 20px;
  border-color: #e1d4c4;
  border-radius: 8px;
  background: #fffaf2;
}

.graph-legend {
  margin: 12px 20px 20px;
  padding: 11px 12px;
  border-color: #e5d4be;
  border-radius: 8px;
  background: #ffffff;
}

.graph-legend > small:last-child {
  flex-basis: 100%;
  margin-left: 0;
  padding-top: 4px;
  border-top: 1px solid #eee3d5;
}

.graph-page .right-column {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  align-items: start;
  gap: 12px;
  min-width: 0;
  max-height: none;
  overflow: visible;
  position: static;
  padding: 0;
}

.graph-page .side-card {
  min-width: 0;
  border: 1px solid #e5d4be;
  border-radius: 8px;
  background: #fffdf8;
  box-shadow: none;
}

.graph-page .side-card:hover {
  transform: none;
  border-color: #d8b28d;
  box-shadow: 0 7px 16px rgba(78, 55, 34, 0.07);
}

.graph-page .search-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 42px;
  gap: 8px;
}

.graph-page .filter-chips {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.graph-page .mode-switch,
.graph-page .action-buttons,
.graph-page .analysis-buttons {
  gap: 8px;
}

.graph-page .mode-btn,
.graph-page .action-btn,
.graph-page .analysis-btn,
.graph-page .filter-chip,
.graph-page .recommend-item,
.graph-page .trend-toggle {
  border-radius: 8px;
}

/* ===== Knowledge graph page layout: full-width workspace ===== */
/* 仅重排页面模块；图谱节点、连线、内容和配色保持原样。 */
.graph-page.layout-two {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 18px;
  width: 100%;
  min-width: 0;
  padding: 4px 0 38px;
}

.graph-page .graph-main {
  width: 100%;
  min-width: 0;
}

.graph-main > .section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
}

.graph-main > .section-head .section-copy {
  min-width: 0;
}

.graph-main > .section-head .section-action {
  flex: 0 1 auto;
  justify-content: flex-end;
  max-width: 720px;
}

.graph-main > .agent-crew {
  margin: 16px 20px 0 !important;
}

.graph-stage-strip {
  margin-top: 14px;
}

.graph-canvas {
  height: clamp(600px, 70vh, 780px);
}

.graph-page .right-column {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  grid-auto-flow: row;
  align-items: start;
  gap: 14px;
  width: 100%;
  min-width: 0;
  max-height: none;
  overflow: visible;
  position: static;
  padding: 0;
}

.graph-page .right-column > .side-card {
  width: 100%;
  min-width: 0;
}

@media (max-width: 1280px) {
  .graph-main > .section-head {
    flex-direction: column;
  }

  .graph-main > .section-head .section-action {
    justify-content: flex-start;
    max-width: none;
  }

  .graph-page .right-column {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .graph-page.layout-two {
    gap: 14px;
    padding: 0 12px 28px;
  }

  .graph-main > .section-head {
    padding: 18px 16px 14px;
  }

  .graph-main > .agent-crew {
    margin: 12px 12px 0 !important;
  }

  .graph-stage-strip {
    grid-template-columns: 1fr;
    margin: 12px;
  }

  .graph-stage-metrics,
  .graph-kpis {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .graph-kpis,
  .graph-canvas,
  .graph-legend {
    margin-left: 12px;
    margin-right: 12px;
  }

  .graph-canvas {
    height: 540px;
  }

  .graph-page .right-column {
    grid-template-columns: 1fr;
  }
}

/* =========================================================
   Student Knowledge Graph · Immersive Workspace
   ========================================================= */
.kg-workspace {
  --graph-bg: #fbfaf7;
  --graph-surface: rgba(255, 255, 255, .96);
  --graph-border: #e5e1d9;
  --graph-divider: #ece8e1;
  --text-primary: #1f1d1a;
  --text-secondary: #625f58;
  --text-tertiary: #89857d;
  --primary: #e85d16;
  --primary-hover: #d75011;
  --primary-container: #fff3ea;
  --ai-primary: #6557d9;
  --ai-container: #faf9ff;
  --success: #247553;
  --warning: #a46916;
  --error: #b5423a;
  --info: #3e6d9c;
  position: fixed;
  inset: 0;
  z-index: 160;
  width: 100vw;
  height: 100dvh;
  overflow: hidden;
  background: var(--graph-bg);
  color: var(--text-primary);
  font-family: "Inter", "PingFang SC", "Noto Sans SC", "Microsoft YaHei", system-ui, sans-serif;
  font-variant-numeric: tabular-nums;
}

.kg-workspace *,
.kg-workspace *::before,
.kg-workspace *::after { box-sizing: border-box; }

.kg-workspace button,
.kg-workspace input,
.kg-workspace select,
.kg-workspace textarea { font: inherit; }

.kg-workspace button { color: inherit; }

.kg-workspace :is(button, input, select, textarea, summary):focus-visible {
  outline: 3px solid rgba(232, 93, 22, .28);
  outline-offset: 2px;
}

.kg-workspace button svg { transition: transform 180ms cubic-bezier(.16, 1, .3, 1); }
.kg-workspace button:hover svg { transform: translateY(-1px) scale(1.06); }
.kg-workspace button:active svg { transform: scale(.94); }

.kg-canvas-layer {
  position: absolute;
  inset: 0;
  overflow: hidden;
  background-color: var(--graph-bg);
  background-image: radial-gradient(circle, rgba(90, 84, 74, .09) 1px, transparent 1px);
  background-size: 22px 22px;
}

.kg-workspace .graph-canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  min-height: 0;
  margin: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
}

.canvas-state {
  position: absolute;
  top: 50%;
  left: 50%;
  display: flex;
  align-items: center;
  gap: 13px;
  min-width: 300px;
  padding: 18px 20px;
  border: 1px solid var(--graph-border);
  border-radius: 12px;
  background: var(--graph-surface);
  box-shadow: 0 8px 24px rgba(35, 31, 25, .05);
  transform: translate(-50%, -50%);
}

.canvas-state > div { display: flex; flex: 1; flex-direction: column; gap: 4px; }
.canvas-state strong { font-size: 14px; }
.canvas-state span { color: var(--text-secondary); font-size: 12px; }
.canvas-state svg { color: var(--primary); }
.canvas-state button { display: inline-flex; align-items: center; gap: 7px; min-height: 40px; padding: 0 13px; border: 1px solid var(--graph-border); border-radius: 8px; background: #fff; cursor: pointer; }

.floating-topbar {
  position: absolute;
  top: 14px;
  right: 14px;
  left: 14px;
  z-index: 50;
  display: grid;
  grid-template-columns: minmax(220px, auto) auto minmax(240px, 560px) minmax(410px, auto);
  align-items: center;
  gap: 14px;
  min-height: 54px;
  padding: 6px 8px;
  border: 1px solid var(--graph-border);
  border-radius: 12px;
  background: var(--graph-surface);
  box-shadow: 0 8px 24px rgba(35, 31, 25, .05);
  backdrop-filter: blur(12px);
}

.topbar-identity,
.topbar-controls,
.workspace-name,
.select-control,
.topbar-search { display: flex; align-items: center; }

.topbar-identity { min-width: 0; gap: 9px; }
.icon-button {
  position: relative;
  display: grid;
  flex: 0 0 auto;
  place-items: center;
  width: 40px;
  height: 40px;
  padding: 0;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  transition: transform 180ms cubic-bezier(.16, 1, .3, 1), background-color 170ms ease-out, border-color 170ms ease-out, color 170ms ease-out;
}
.icon-button:hover,
.icon-button.active { border-color: #f0d5c3; background: var(--primary-container); color: var(--primary-hover); transform: translateY(-1px); }
.icon-button > i { position: absolute; top: 7px; right: 7px; width: 6px; height: 6px; border-radius: 50%; background: var(--primary); }
.back-button { border-color: var(--graph-border); background: #fff; }
.mini-logo { display: grid; flex: 0 0 auto; place-items: center; width: 32px; height: 32px; overflow: hidden; border-radius: 8px; }
.mini-logo img { width: 100%; height: 100%; object-fit: cover; }
.workspace-name { min-width: 0; flex-direction: column; align-items: flex-start; line-height: 1.2; }
.workspace-name strong { color: var(--text-primary); font-size: 14px; font-weight: 750; }
.workspace-name span { max-width: 180px; overflow: hidden; color: var(--text-tertiary); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }

.graph-level-switch { display: flex; align-items: center; gap: 3px; padding: 3px; border: 1px solid var(--graph-border); border-radius: 9px; background: #f6f3ee; }
.graph-level-switch button { display: inline-flex; align-items: center; gap: 6px; min-height: 32px; padding: 0 9px; border: 0; border-radius: 6px; background: transparent; color: var(--text-tertiary); font-size: 11px; font-weight: 650; white-space: nowrap; cursor: pointer; transition: transform 160ms ease-out, background-color 160ms ease-out, color 160ms ease-out; }
.graph-level-switch button:hover { color: var(--text-primary); transform: translateY(-1px); }
.graph-level-switch button.active { background: #fff; color: var(--primary-hover); box-shadow: 0 2px 7px rgba(35, 31, 25, .07); }

.topbar-search {
  min-width: 0;
  height: 40px;
  gap: 9px;
  padding: 0 11px;
  border: 1px solid var(--graph-border);
  border-radius: 9px;
  background: #fff;
  color: var(--text-tertiary);
  transition: border-color 170ms ease-out, box-shadow 170ms ease-out;
}
.topbar-search:focus-within { border-color: var(--primary); box-shadow: 0 0 0 3px rgba(232, 93, 22, .10); }
.topbar-search input { min-width: 0; flex: 1; border: 0; outline: 0; background: transparent; color: var(--text-primary); font-size: 13px; }
.topbar-search input::placeholder { color: #716d66; }
.topbar-search kbd { padding: 2px 6px; border: 1px solid var(--graph-border); border-radius: 5px; background: #f7f5f1; color: var(--text-tertiary); font-size: 11px; }

.topbar-controls { justify-content: flex-end; gap: 5px; min-width: 0; }
.select-control { position: relative; height: 40px; gap: 5px; padding: 0 8px 0 10px; border: 1px solid var(--graph-border); border-radius: 8px; background: #fff; }
.select-control > span { color: var(--text-tertiary); font-size: 11px; }
.select-control select { max-width: 132px; padding: 0 18px 0 0; border: 0; outline: 0; appearance: none; background: transparent; color: var(--text-primary); font-size: 12px; font-weight: 650; cursor: pointer; }
.select-control svg { position: absolute; right: 6px; pointer-events: none; color: var(--text-tertiary); }
.scope-control select { max-width: 90px; }

.more-menu { position: relative; }
.more-menu > summary { list-style: none; }
.more-menu > summary::-webkit-details-marker { display: none; }
.more-menu-popover {
  position: absolute;
  top: calc(100% + 9px);
  right: 0;
  z-index: 80;
  width: 196px;
  padding: 6px;
  border: 1px solid var(--graph-border);
  border-radius: 10px;
  background: #fff;
  box-shadow: 0 8px 24px rgba(35, 31, 25, .08);
}
.more-menu-popover button { display: flex; align-items: center; gap: 9px; width: 100%; min-height: 38px; padding: 0 10px; border: 0; border-radius: 7px; background: transparent; color: var(--text-secondary); font-size: 12px; text-align: left; cursor: pointer; }
.more-menu-popover button:hover { background: var(--primary-container); color: var(--primary-hover); }

.filter-popover {
  position: absolute;
  top: 76px;
  right: 138px;
  z-index: 70;
  width: 320px;
  padding: 15px;
  border: 1px solid var(--graph-border);
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 8px 24px rgba(35, 31, 25, .08);
}
.filter-popover > header { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding-bottom: 12px; border-bottom: 1px solid var(--graph-divider); }
.filter-popover > header div { display: flex; flex-direction: column; gap: 2px; }
.filter-popover > header strong { font-size: 14px; }
.filter-popover > header span { color: var(--text-tertiary); font-size: 11px; }
.filter-popover > header button,
.course-tree-panel > header button,
.drawer-header > button,
.analysis-result > header button,
.compare-floating header button,
.shortcuts-dialog header button { display: grid; place-items: center; width: 36px; height: 36px; padding: 0; border: 1px solid var(--graph-border); border-radius: 8px; background: #fff; cursor: pointer; }
.filter-section { padding: 13px 0 0; }
.filter-section > span { display: block; margin-bottom: 8px; color: var(--text-tertiary); font-size: 11px; }
.filter-options { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 6px; }
.filter-options button { display: grid; grid-template-columns: 8px minmax(0, 1fr) 14px; align-items: center; gap: 7px; min-height: 36px; padding: 0 9px; border: 1px solid var(--graph-border); border-radius: 8px; background: #fff; color: var(--text-secondary); font-size: 12px; text-align: left; cursor: pointer; }
.filter-options button.active { border-color: #efc2a6; background: var(--primary-container); color: var(--primary-hover); }
.filter-options i { width: 7px; height: 7px; border-radius: 50%; background: #aaa59b; }
.filter-options i.state-mastered { background: var(--success); }
.filter-options i.state-learning { background: var(--info); }
.filter-options i.state-at_risk { background: var(--error); }
.filter-options i.state-recommended { background: var(--ai-primary); }
.segmented-control { display: grid; grid-template-columns: 1fr 1fr; padding: 3px; border-radius: 8px; background: #f3f1ed; }
.segmented-control button { min-height: 34px; border: 0; border-radius: 6px; background: transparent; color: var(--text-secondary); font-size: 12px; cursor: pointer; }
.segmented-control button.active { background: #fff; color: var(--text-primary); box-shadow: 0 2px 5px rgba(35, 31, 25, .06); }
.filter-popover > footer { display: flex; justify-content: space-between; gap: 8px; margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--graph-divider); }
.filter-popover > footer button { min-height: 36px; padding: 0 12px; border: 1px solid var(--graph-border); border-radius: 8px; background: #fff; font-size: 12px; cursor: pointer; }
.filter-popover > footer button:last-child { border-color: var(--primary); background: var(--primary); color: #fff; }

.course-panel-trigger {
  position: absolute;
  top: 86px;
  left: 14px;
  z-index: 42;
  display: flex;
  align-items: center;
  gap: 7px;
  min-height: 40px;
  padding: 0 12px;
  border: 1px solid var(--graph-border);
  border-radius: 9px;
  background: var(--graph-surface);
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 650;
  box-shadow: 0 6px 16px rgba(35, 31, 25, .05);
  cursor: pointer;
}
.course-panel-trigger:hover { border-color: #efc2a6; color: var(--primary-hover); transform: translateY(-1px); }
.course-tree-panel {
  position: absolute;
  top: 82px;
  bottom: 66px;
  left: 14px;
  z-index: 48;
  display: flex;
  width: 286px;
  overflow: hidden;
  flex-direction: column;
  border: 1px solid var(--graph-border);
  border-radius: 12px;
  background: var(--graph-surface);
  box-shadow: 0 8px 24px rgba(35, 31, 25, .06);
  transform: translateX(calc(-100% - 24px));
  transition: transform 240ms cubic-bezier(.16, 1, .3, 1);
}
.course-panel-open .course-tree-panel { transform: translateX(0); }
.course-tree-panel > header { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 14px; border-bottom: 1px solid var(--graph-divider); }
.course-tree-panel > header div { display: flex; min-width: 0; flex-direction: column; gap: 3px; }
.course-tree-panel > header span { color: var(--text-tertiary); font-size: 11px; }
.course-tree-panel > header strong { overflow: hidden; font-size: 14px; text-overflow: ellipsis; white-space: nowrap; }
.tree-search { display: flex; align-items: center; gap: 8px; height: 38px; margin: 12px; padding: 0 10px; border: 1px solid var(--graph-border); border-radius: 8px; background: #fff; color: var(--text-tertiary); }
.tree-search input { min-width: 0; flex: 1; border: 0; outline: 0; background: transparent; color: var(--text-primary); font-size: 12px; }
.course-switch-list { display: flex; gap: 5px; padding: 0 12px 11px; overflow-x: auto; border-bottom: 1px solid var(--graph-divider); }
.course-switch-list button { display: flex; flex: 0 0 auto; align-items: center; gap: 6px; min-height: 34px; padding: 0 9px; border: 1px solid var(--graph-border); border-radius: 7px; background: #fff; color: var(--text-secondary); font-size: 11px; cursor: pointer; }
.course-switch-list button.active { border-color: #efc2a6; background: var(--primary-container); color: var(--primary-hover); }
.tree-groups { flex: 1; min-height: 0; overflow-y: auto; padding: 6px 12px 14px; }
.tree-groups details { border-bottom: 1px solid var(--graph-divider); }
.tree-groups summary { display: flex; align-items: center; justify-content: space-between; gap: 8px; min-height: 42px; color: var(--text-primary); font-size: 12px; cursor: pointer; }
.tree-groups summary > span { display: flex; align-items: center; gap: 7px; font-weight: 650; }
.tree-groups summary em { color: var(--text-tertiary); font-size: 10px; font-style: normal; }
.tree-groups details > button { display: grid; grid-template-columns: 10px minmax(0, 1fr) auto; align-items: center; gap: 8px; width: 100%; min-height: 36px; padding: 0 7px; border: 0; border-radius: 7px; background: transparent; color: var(--text-secondary); font-size: 11px; text-align: left; cursor: pointer; }
.tree-groups details > button:hover,
.tree-groups details > button.active { background: var(--primary-container); color: var(--primary-hover); }
.tree-groups details > button i { width: 9px; height: 9px; border: 2px solid; border-radius: 50%; background: #fff; }
.tree-groups details > button span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tree-groups details > button small { color: var(--text-tertiary); }
.cluster-tree-list { display: flex; flex-direction: column; gap: 5px; padding: 6px 0 10px; }
.cluster-tree-list > header { display: flex; align-items: center; justify-content: space-between; padding: 5px 5px 7px; color: var(--text-tertiary); font-size: 10.5px; }
.cluster-tree-list > header em { font-style: normal; }
.cluster-tree-list > button { display: grid; grid-template-columns: 12px minmax(0, 1fr) 14px; align-items: center; gap: 9px; width: 100%; min-height: 48px; padding: 7px 8px; border: 1px solid transparent; border-radius: 8px; background: transparent; color: var(--text-secondary); text-align: left; cursor: pointer; transition: transform 160ms ease-out, background-color 160ms ease-out, border-color 160ms ease-out; }
.cluster-tree-list > button:hover { border-color: var(--graph-border); background: #fff; transform: translateX(2px); }
.cluster-tree-list > button.active { border-color: #efc2a6; background: var(--primary-container); }
.cluster-tree-list > button > i { width: 12px; height: 12px; border: 2px solid; border-radius: 50%; }
.cluster-tree-list > button > span { display: flex; min-width: 0; flex-direction: column; gap: 3px; }
.cluster-tree-list b { overflow: hidden; color: var(--text-primary); font-size: 11.5px; text-overflow: ellipsis; white-space: nowrap; }
.cluster-tree-list small { color: var(--text-tertiary); font-size: 9.5px; }
.cluster-tree-list svg { color: var(--text-tertiary); }

.cluster-breadcrumb { position: absolute; top: 84px; left: 50%; z-index: 43; display: inline-flex; align-items: center; gap: 7px; min-height: 34px; padding: 0 11px; border: 1px solid var(--graph-border); border-radius: 999px; background: rgba(255,255,255,.92); color: var(--text-secondary); font-size: 11px; font-weight: 650; box-shadow: 0 5px 16px rgba(35,31,25,.06); transform: translateX(-50%); cursor: pointer; backdrop-filter: blur(10px); }
.cluster-breadcrumb:hover { color: var(--primary-hover); transform: translate(-50%, -1px); }
.cluster-breadcrumb i { width: 1px; height: 13px; background: var(--graph-divider); }

.canvas-toolbar {
  position: absolute;
  top: 142px;
  left: 14px;
  z-index: 41;
  display: flex;
  flex-direction: column;
  padding: 5px;
  border: 1px solid var(--graph-border);
  border-radius: 10px;
  background: var(--graph-surface);
  box-shadow: 0 6px 16px rgba(35, 31, 25, .05);
}
.course-panel-open .canvas-toolbar { left: 314px; }
.canvas-toolbar button { display: grid; place-items: center; width: 38px; height: 38px; padding: 0; border: 0; border-radius: 7px; background: transparent; color: var(--text-secondary); cursor: pointer; }
.canvas-toolbar button:hover,
.canvas-toolbar button.active { background: var(--primary-container); color: var(--primary-hover); }
.canvas-toolbar > span { height: 1px; margin: 4px 5px; background: var(--graph-divider); }

.graph-legend {
  position: absolute;
  bottom: 66px;
  left: 14px;
  z-index: 40;
  width: 206px;
  padding: 11px 12px;
  border: 1px solid var(--graph-border);
  border-radius: 10px;
  background: var(--graph-surface);
  box-shadow: 0 6px 16px rgba(35, 31, 25, .04);
}
.course-panel-open .graph-legend { left: 314px; }
.graph-legend header { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 8px; }
.graph-legend header strong { font-size: 12px; }
.graph-legend header button { display: grid; place-items: center; width: 26px; height: 26px; padding: 0; border: 0; border-radius: 6px; background: transparent; cursor: pointer; }
.graph-legend > div { display: grid; grid-template-columns: 1fr 1fr; gap: 7px 10px; }
.graph-legend > div span { display: flex; align-items: center; gap: 6px; color: var(--text-secondary); font-size: 10px; }
.graph-legend > div i { width: 10px; height: 10px; border: 2px solid #9b978f; border-radius: 50%; background: #eeece7; }
.graph-legend i.mastered { border-color: var(--success); background: #dfeee6; }
.graph-legend i.learning { border-color: var(--info); background: #e5edf5; }
.graph-legend i.weak { border-color: var(--error); background: #f6e4e1; }
.graph-legend i.ai { border-color: var(--ai-primary); }
.graph-legend i.path { border-color: var(--primary); box-shadow: 0 0 0 2px #f7d8c5; }

.graph-minimap {
  position: absolute;
  right: 14px;
  bottom: 66px;
  z-index: 39;
  width: 164px;
  padding: 8px;
  border: 1px solid var(--graph-border);
  border-radius: 10px;
  background: var(--graph-surface);
  box-shadow: 0 6px 16px rgba(35, 31, 25, .04);
}
.has-drawer .graph-minimap { right: 390px; }
.graph-minimap header { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 5px; color: var(--text-tertiary); font-size: 10px; }
.minimap-canvas { position: relative; height: 94px; overflow: hidden; border-radius: 6px; background: #f4f2ed; }
.minimap-canvas > i { position: absolute; width: 4px; height: 4px; border-radius: 50%; opacity: .75; }
.minimap-canvas > i.selected { width: 7px; height: 7px; margin: -2px 0 0 -2px; outline: 2px solid #fff; }
.viewport-indicator { position: absolute; inset: 20% 18%; border: 1px solid rgba(232, 93, 22, .65); border-radius: 3px; }

.node-drawer {
  position: absolute;
  top: 82px;
  right: 14px;
  bottom: 66px;
  z-index: 60;
  display: flex;
  width: 362px;
  overflow: hidden;
  flex-direction: column;
  border: 1px solid var(--graph-border);
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 8px 24px rgba(35, 31, 25, .08);
  animation: drawer-slide-in 240ms cubic-bezier(.16, 1, .3, 1);
}
@keyframes drawer-slide-in { from { transform: translateX(18px); } to { transform: translateX(0); } }
.drawer-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 14px; padding: 17px 17px 14px; border-bottom: 1px solid var(--graph-divider); }
.drawer-header > div { min-width: 0; }
.drawer-header span { display: block; margin-bottom: 4px; color: var(--text-tertiary); font-size: 11px; }
.drawer-header h2 { overflow: hidden; margin: 0; color: var(--text-primary); font-family: "Source Han Serif SC", "Noto Serif SC", "Songti SC", serif; font-size: 22px; font-weight: 600; line-height: 1.3; text-overflow: ellipsis; white-space: nowrap; }
.drawer-tabs { display: grid; grid-template-columns: repeat(3, 1fr); padding: 0 12px; border-bottom: 1px solid var(--graph-divider); }
.drawer-tabs button { position: relative; min-height: 42px; border: 0; background: transparent; color: var(--text-secondary); font-size: 12px; cursor: pointer; }
.drawer-tabs button::after { content: ""; position: absolute; right: 14px; bottom: -1px; left: 14px; height: 2px; border-radius: 2px 2px 0 0; background: var(--primary); transform: scaleX(0); transition: transform 180ms ease-out; }
.drawer-tabs button.active { color: var(--primary-hover); font-weight: 700; }
.drawer-tabs button.active::after { transform: scaleX(1); }
.drawer-body { flex: 1; min-height: 0; overflow-y: auto; padding: 16px; }
.cluster-overview-card { padding: 18px; border: 1px solid color-mix(in srgb, var(--cluster-color) 30%, white); border-radius: 12px; background: linear-gradient(145deg, var(--cluster-soft), #fff 72%); }
.cluster-orbit { display: grid; place-items: center; width: 48px; height: 48px; margin-bottom: 13px; border: 2px solid var(--cluster-color); border-radius: 50%; background: #fff; color: var(--cluster-color); box-shadow: 0 0 0 8px color-mix(in srgb, var(--cluster-color) 10%, transparent); }
.cluster-overview-card > p { margin: 0 0 16px; color: var(--text-secondary); font-size: 12px; line-height: 1.65; }
.cluster-overview-card dl { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin: 0; }
.cluster-overview-card dl div { padding-top: 10px; border-top: 1px solid color-mix(in srgb, var(--cluster-color) 18%, white); }
.cluster-overview-card dt { color: var(--text-tertiary); font-size: 10px; }
.cluster-overview-card dd { margin: 4px 0 0; color: var(--text-primary); font-size: 19px; font-weight: 750; }
.cluster-member-list { display: grid; gap: 4px; }
.cluster-member-list button { display: grid; grid-template-columns: 10px minmax(0, 1fr) auto; align-items: center; gap: 8px; width: 100%; min-height: 37px; padding: 0 7px; border: 0; border-radius: 7px; background: transparent; color: var(--text-secondary); font-size: 11px; text-align: left; cursor: pointer; }
.cluster-member-list button:hover { background: var(--primary-container); color: var(--primary-hover); transform: translateX(2px); }
.cluster-member-list i { width: 9px; height: 9px; border: 2px solid; border-radius: 50%; background: #fff; }
.cluster-member-list span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cluster-member-list em { color: var(--text-tertiary); font-size: 10px; font-style: normal; }
.cluster-more { margin: 9px 0 0; color: var(--text-tertiary); font-size: 10.5px; }
.cluster-open-button { display: flex; align-items: center; justify-content: center; gap: 8px; width: 100%; min-height: 43px; margin-top: 18px; border: 1px solid var(--primary); border-radius: 9px; background: var(--primary); color: #fff; font-size: 12px; font-weight: 700; cursor: pointer; transition: transform 170ms ease-out, background-color 170ms ease-out; }
.cluster-open-button:hover { background: var(--primary-hover); transform: translateY(-1px); }

.mastery-summary { padding-bottom: 15px; border-bottom: 1px solid var(--graph-divider); }
.mastery-summary > div:first-child { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
.mastery-summary > div:first-child span { color: var(--text-secondary); font-size: 12px; }
.mastery-summary > div:first-child strong { font-size: 29px; font-weight: 700; }
.mastery-track { height: 7px; margin: 9px 0 15px; overflow: hidden; border-radius: 999px; background: #efede8; }
.mastery-track i { display: block; width: 100%; height: 100%; border-radius: inherit; transform-origin: left; }
.mastery-summary dl { display: grid; grid-template-columns: 1fr 1fr; gap: 10px 16px; margin: 0; }
.mastery-summary dl div { min-width: 0; }
.mastery-summary dt { margin-bottom: 3px; color: var(--text-tertiary); font-size: 10px; }
.mastery-summary dd { overflow: hidden; margin: 0; color: var(--text-primary); font-size: 12px; font-weight: 650; text-overflow: ellipsis; white-space: nowrap; }
.node-description { margin: 15px 0 0; color: var(--text-secondary); font-size: 12px; line-height: 1.7; }
.drawer-section { margin-top: 17px; padding-top: 15px; border-top: 1px solid var(--graph-divider); }
.drawer-section > header { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 9px; }
.drawer-section > header strong { font-size: 13px; }
.drawer-section > header span { color: var(--text-tertiary); font-size: 11px; }
.neighbor-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.neighbor-chips button { min-height: 30px; padding: 0 9px; border: 1px solid var(--graph-border); border-radius: 999px; background: #fff; color: var(--text-secondary); font-size: 10px; cursor: pointer; }
.inline-empty { margin: 0; color: var(--text-tertiary); font-size: 11px; }
.drawer-primary-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 7px; margin-top: 18px; }
.drawer-primary-actions button { min-height: 40px; border: 1px solid var(--graph-border); border-radius: 8px; background: #fff; color: var(--text-secondary); font-size: 12px; font-weight: 650; cursor: pointer; }
.drawer-primary-actions .primary-action { grid-column: 1 / -1; display: flex; align-items: center; justify-content: center; gap: 7px; border-color: var(--primary); background: var(--primary); color: #fff; }
.drawer-primary-actions .primary-action:hover { background: var(--primary-hover); }
.drawer-text-actions { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 7px; }
.drawer-text-actions button { display: flex; align-items: center; gap: 6px; min-height: 34px; padding: 0 7px; border: 0; background: transparent; color: var(--text-secondary); font-size: 11px; cursor: pointer; }
.drawer-text-actions button:hover { color: var(--primary-hover); }

.analysis-action-list { display: grid; gap: 7px; }
.analysis-action-list > button { display: flex; align-items: center; justify-content: space-between; gap: 9px; width: 100%; min-height: 58px; padding: 8px 10px; border: 1px solid var(--graph-border); border-radius: 9px; background: #fff; text-align: left; cursor: pointer; }
.analysis-action-list > button:hover,
.analysis-action-list > button.active { border-color: #d8d2eb; background: var(--ai-container); color: var(--ai-primary); }
.analysis-action-list > button > span { display: grid; grid-template-columns: 22px minmax(0, 1fr); flex: 1; align-items: center; gap: 1px 7px; }
.analysis-action-list > button b { grid-column: 2; font-size: 12px; }
.analysis-action-list > button small { grid-column: 2; color: var(--text-tertiary); font-size: 10px; }
.analysis-action-list > button svg { grid-row: 1 / 3; }
.analysis-result { margin-top: 12px; overflow: hidden; border: 1px solid #ded9ec; border-radius: 9px; background: var(--ai-container); }
.analysis-result > header { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 11px; border-bottom: 1px solid #e8e4f3; }
.analysis-result > header > div { display: flex; min-width: 0; flex-direction: column; gap: 3px; }
.analysis-result > header strong { font-size: 12px; }
.analysis-result > header span { overflow: hidden; color: var(--text-tertiary); font-size: 10px; text-overflow: ellipsis; white-space: nowrap; }
.analysis-result > header button { width: 30px; height: 30px; }
.path-switch { display: grid; grid-template-columns: repeat(3, 1fr); gap: 4px; padding: 8px; }
.path-switch button { min-height: 32px; border: 0; border-radius: 6px; background: #eeebf8; color: var(--text-secondary); font-size: 10px; cursor: pointer; }
.path-switch button.active { background: var(--ai-primary); color: #fff; }
.analysis-path-row { display: grid; grid-template-columns: 24px minmax(0, 1fr) auto; align-items: center; gap: 8px; width: calc(100% - 16px); min-height: 48px; margin: 0 8px; padding: 7px 0; border: 0; border-top: 1px solid #e8e4f3; background: transparent; text-align: left; cursor: pointer; }
.analysis-path-row > span { display: grid; place-items: center; width: 22px; height: 22px; border-radius: 50%; background: #ece9f6; color: var(--ai-primary); font-size: 10px; font-weight: 700; }
.analysis-path-row div { display: flex; min-width: 0; flex-direction: column; gap: 2px; }
.analysis-path-row b { font-size: 11px; }
.analysis-path-row small { overflow: hidden; color: var(--text-tertiary); font-size: 9px; text-overflow: ellipsis; white-space: nowrap; }
.analysis-path-row em { color: var(--ai-primary); font-size: 10px; font-style: normal; }
.compact-result { padding-bottom: 7px; }
.result-node-row { display: flex; align-items: center; justify-content: space-between; gap: 10px; width: calc(100% - 16px); min-height: 34px; margin: 0 8px; padding: 0 3px; border: 0; border-bottom: 1px solid #e8e4f3; background: transparent; font-size: 10px; cursor: pointer; }
.result-node-row em { color: var(--ai-primary); font-style: normal; }
.forecast-summary-grid { display: grid; grid-template-columns: repeat(3, 1fr); padding: 8px; }
.forecast-summary-grid div { display: flex; flex-direction: column; gap: 3px; padding: 8px; border-left: 1px solid #e8e4f3; }
.forecast-summary-grid div:first-child { border-left: 0; }
.forecast-summary-grid span { color: var(--text-tertiary); font-size: 9px; }
.forecast-summary-grid strong { font-size: 14px; }
.kg-workspace .forecast-chart,
.kg-workspace .trend-chart { width: 100%; height: 170px; }
.trend-button { display: flex; align-items: center; justify-content: center; gap: 7px; width: 100%; min-height: 38px; margin-top: 10px; border: 1px solid var(--graph-border); border-radius: 8px; background: #fff; color: var(--text-secondary); font-size: 11px; cursor: pointer; }
.trend-button.active { border-color: #d8d2eb; background: var(--ai-container); color: var(--ai-primary); }

.evaluation-form { display: grid; gap: 15px; }
.rating-field { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding-bottom: 12px; border-bottom: 1px solid var(--graph-divider); }
.rating-field > span { color: var(--text-secondary); font-size: 12px; }
.rating-field > div { display: flex; gap: 2px; }
.rating-field button { padding: 0 2px; border: 0; background: transparent; color: #c9c5bd; font-size: 19px; cursor: pointer; }
.rating-field button.active { color: #d9853b; }
.evaluation-check { display: flex; align-items: center; gap: 8px; color: var(--text-secondary); font-size: 12px; }
.evaluation-check input { accent-color: var(--primary); }
.note-field { display: flex; flex-direction: column; gap: 7px; color: var(--text-secondary); font-size: 12px; }
.note-field textarea { resize: vertical; min-height: 96px; padding: 9px 10px; border: 1px solid var(--graph-border); border-radius: 8px; outline: 0; color: var(--text-primary); line-height: 1.55; }
.note-field textarea:focus { border-color: var(--primary); }
.save-evaluation { min-height: 40px; border: 1px solid var(--primary); border-radius: 8px; background: var(--primary); color: #fff !important; font-size: 12px; font-weight: 700; cursor: pointer; }
.evaluation-form > p { margin: 0; color: var(--text-tertiary); font-size: 10px; line-height: 1.6; }

.node-context-menu {
  position: fixed;
  z-index: 90;
  width: 208px;
  padding: 6px;
  border: 1px solid var(--graph-border);
  border-radius: 10px;
  background: #fff;
  box-shadow: 0 8px 24px rgba(35, 31, 25, .12);
}
.node-context-menu strong { display: block; overflow: hidden; padding: 8px 9px; border-bottom: 1px solid var(--graph-divider); font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.node-context-menu button { width: 100%; min-height: 34px; padding: 0 9px; border: 0; border-radius: 6px; background: transparent; color: var(--text-secondary); font-size: 11px; text-align: left; cursor: pointer; }
.node-context-menu button:hover { background: var(--primary-container); color: var(--primary-hover); }

.compare-floating {
  position: absolute;
  top: 82px;
  right: 14px;
  z-index: 58;
  width: 330px;
  padding: 13px;
  border: 1px solid var(--graph-border);
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 8px 24px rgba(35, 31, 25, .08);
}
.has-drawer .compare-floating { right: 390px; }
.compare-floating header { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.compare-floating header > div { display: flex; flex-direction: column; gap: 2px; }
.compare-floating header strong { font-size: 13px; }
.compare-floating header span,
.compare-floating > p { color: var(--text-tertiary); font-size: 10px; }
.compare-selected { display: flex; gap: 5px; margin-top: 9px; }
.compare-selected button { display: flex; align-items: center; gap: 5px; min-height: 30px; padding: 0 8px; border: 1px solid var(--graph-border); border-radius: 7px; background: #fff; font-size: 10px; cursor: pointer; }
.kg-workspace .compare-chart { width: 100%; height: 210px; margin-top: 7px; }

.bottom-workspace-dock {
  position: absolute;
  right: 14px;
  bottom: 12px;
  left: 14px;
  z-index: 55;
  overflow: hidden;
  border: 1px solid var(--graph-border);
  border-radius: 12px;
  background: var(--graph-surface);
  box-shadow: 0 8px 24px rgba(35, 31, 25, .07);
  backdrop-filter: blur(12px);
}
.dock-tabs { display: flex; align-items: center; min-height: 46px; padding: 4px 6px; overflow-x: auto; }
.dock-tabs > button { display: flex; flex: 0 0 auto; align-items: center; gap: 7px; min-height: 38px; padding: 0 11px; border: 0; border-radius: 8px; background: transparent; color: var(--text-secondary); font-size: 11px; font-weight: 650; cursor: pointer; }
.dock-tabs > button > svg:last-child { opacity: .45; transition: transform 180ms ease-out; }
.dock-tabs > button.active { background: var(--primary-container); color: var(--primary-hover); }
.dock-tabs > button.active > svg:last-child { transform: rotate(180deg); }
.dock-tabs > .dock-close { margin-left: auto; }
.dock-panel { height: min(350px, 43vh); overflow: hidden; border-top: 1px solid var(--graph-divider); animation: dock-slide-in 260ms cubic-bezier(.16, 1, .3, 1); }
@keyframes dock-slide-in { from { transform: translateY(12px); } to { transform: translateY(0); } }
.dock-content { height: 100%; overflow-y: auto; padding: 17px 20px 20px; }
.dock-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 24px; margin-bottom: 14px; }
.dock-heading > div { min-width: 0; }
.dock-heading span { display: inline-flex; align-items: center; gap: 5px; color: var(--primary); font-size: 10px; font-weight: 700; }
.dock-heading span.ai-label { color: var(--ai-primary); }
.dock-heading h2 { margin: 3px 0 0; color: var(--text-primary); font-family: "Source Han Serif SC", "Noto Serif SC", "Songti SC", serif; font-size: 19px; font-weight: 600; }
.dock-heading > p { max-width: 520px; margin: 0; color: var(--text-secondary); font-size: 11px; line-height: 1.6; }

.graphrag-layout { display: grid; grid-template-columns: minmax(0, 1.1fr) minmax(320px, .9fr); gap: 18px; }
.rag-conversation > label textarea { width: 100%; min-height: 76px; resize: none; padding: 10px 12px; border: 1px solid #ded9ec; border-radius: 9px; outline: 0; background: var(--ai-container); color: var(--text-primary); font-size: 12px; line-height: 1.6; }
.rag-conversation > label textarea:focus { border-color: var(--ai-primary); }
.rag-actions { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-top: 7px; }
.rag-actions button { display: flex; align-items: center; gap: 7px; min-height: 38px; padding: 0 13px; border: 1px solid var(--ai-primary); border-radius: 8px; background: var(--ai-primary); color: #fff; font-size: 11px; font-weight: 700; cursor: pointer; }
.rag-actions span { color: var(--text-tertiary); font-size: 9px; }
.rag-answer { margin-top: 10px; padding: 11px; border: 1px solid #ded9ec; border-radius: 9px; background: var(--ai-container); }
.rag-answer strong { font-size: 11px; }
.rag-answer p { margin: 5px 0; color: var(--text-secondary); font-size: 11px; line-height: 1.65; }
.rag-answer button { padding: 0; border: 0; background: transparent; color: var(--ai-primary); font-size: 10px; font-weight: 700; cursor: pointer; }
.rag-citations { overflow: hidden; border: 1px solid var(--graph-border); border-radius: 9px; background: #fff; }
.rag-citations > header { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 10px; border-bottom: 1px solid var(--graph-divider); }
.rag-citations > header strong { font-size: 11px; }
.rag-citations > header span { color: var(--text-tertiary); font-size: 9px; }
.rag-citations > button,
.search-result-row { display: grid; grid-template-columns: 22px minmax(0, 1fr) auto; align-items: center; gap: 8px; width: 100%; min-height: 49px; padding: 7px 9px; border: 0; border-top: 1px solid var(--graph-divider); background: transparent; color: var(--text-secondary); text-align: left; cursor: pointer; }
.rag-citations > button:first-of-type { border-top: 0; }
.rag-citations > button:hover,
.search-result-row:hover { background: var(--primary-container); }
.rag-citations > button > span,
.search-result-row > span { display: flex; min-width: 0; flex-direction: column; gap: 2px; }
.rag-citations b,
.search-result-row b { color: var(--text-primary); font-size: 10px; }
.rag-citations small,
.search-result-row small { overflow: hidden; color: var(--text-tertiary); font-size: 9px; text-overflow: ellipsis; white-space: nowrap; }
.rag-citations em,
.search-result-row em { color: var(--ai-primary); font-size: 9px; font-style: normal; }

.learning-path-strip { display: flex; gap: 7px; overflow-x: auto; padding-bottom: 5px; }
.learning-path-strip > button { display: grid; grid-template-columns: 27px minmax(120px, 1fr) 16px; flex: 0 0 210px; align-items: center; gap: 8px; min-height: 62px; padding: 7px 9px; border: 1px solid var(--graph-border); border-radius: 9px; background: #fff; text-align: left; cursor: pointer; }
.learning-path-strip > button:hover,
.learning-path-strip > button.current { border-color: #efc2a6; background: var(--primary-container); }
.learning-path-strip > button > span { display: grid; place-items: center; width: 25px; height: 25px; border-radius: 50%; background: #f0ede8; color: var(--text-secondary); font-size: 10px; font-weight: 700; }
.learning-path-strip > button.current > span { background: var(--primary); color: #fff; }
.learning-path-strip > button.completed > span { background: var(--success); color: #fff; }
.learning-path-strip > button div { display: flex; min-width: 0; flex-direction: column; gap: 3px; }
.learning-path-strip b { overflow: hidden; font-size: 10px; text-overflow: ellipsis; white-space: nowrap; }
.learning-path-strip small { color: var(--text-tertiary); font-size: 9px; }

.search-workspace { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
.search-workspace > div { overflow: hidden; border: 1px solid var(--graph-border); border-radius: 9px; background: #fff; }
.search-workspace label { display: grid; grid-template-columns: 22px minmax(0, 1fr) 38px; align-items: center; gap: 6px; height: 44px; padding-left: 9px; border-bottom: 1px solid var(--graph-divider); color: var(--text-tertiary); }
.search-workspace input { min-width: 0; border: 0; outline: 0; color: var(--text-primary); font-size: 11px; }
.search-workspace label > button { display: grid; place-items: center; width: 34px; height: 34px; padding: 0; border: 0; border-radius: 7px; background: var(--primary-container); color: var(--primary-hover); cursor: pointer; }

.recommendation-list { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 9px; }
.recommendation-list > button { display: grid; grid-template-columns: 34px minmax(0, 1fr); gap: 9px; min-height: 100px; padding: 12px; border: 1px solid #ded9ec; border-radius: 9px; background: var(--ai-container); text-align: left; cursor: pointer; }
.recommend-icon { display: grid; place-items: center; width: 34px; height: 34px; border-radius: 8px; background: #ece9ff; color: var(--ai-primary); }
.recommendation-list > button > div { min-width: 0; }
.recommendation-list b { color: var(--text-primary); font-size: 11px; }
.recommendation-list p { margin: 5px 0; color: var(--text-secondary); font-size: 10px; line-height: 1.5; }
.recommendation-list small { color: var(--text-tertiary); font-size: 9px; }
.recommendation-list > button > span:last-child { grid-column: 2; display: flex; align-items: center; gap: 4px; color: var(--ai-primary); font-size: 9px; font-weight: 700; }

.achievement-list { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }
.achievement-list article { display: grid; grid-template-columns: 34px minmax(0, 1fr) auto; align-items: center; gap: 8px; min-height: 74px; padding: 9px; border: 1px solid var(--graph-border); border-radius: 9px; background: #fff; opacity: .65; }
.achievement-list article.unlocked { border-color: #d4e6db; background: #f4faf6; opacity: 1; }
.achievement-list article > span { display: grid; place-items: center; width: 32px; height: 32px; border-radius: 50%; background: #f0ede8; color: var(--text-secondary); font-size: 10px; font-weight: 750; }
.achievement-list article.unlocked > span { background: var(--success); color: #fff; }
.achievement-list article > div { display: flex; min-width: 0; flex-direction: column; gap: 3px; }
.achievement-list b { font-size: 10px; }
.achievement-list small { color: var(--text-tertiary); font-size: 9px; }
.achievement-list i { height: 4px; overflow: hidden; border-radius: 999px; background: #eceae5; }
.achievement-list i em { display: block; width: 100%; height: 100%; background: var(--success); transform-origin: left; }
.achievement-list article > strong { color: var(--success); font-size: 9px; }

.statistics-strip { display: grid; grid-template-columns: repeat(6, 1fr); border-block: 1px solid var(--graph-divider); }
.statistics-strip > div,
.statistics-strip > button { display: flex; flex-direction: column; gap: 5px; padding: 15px; border-left: 1px solid var(--graph-divider); }
.statistics-strip > :first-child { border-left: 0; }
.statistics-strip span { color: var(--text-tertiary); font-size: 11px; }
.statistics-strip strong { color: var(--text-primary); font-size: 24px; font-weight: 680; }
.dock-empty { display: flex; align-items: center; justify-content: center; gap: 10px; min-height: 120px; color: var(--text-tertiary); }
.dock-empty > div { display: flex; flex-direction: column; }
.dock-empty strong { color: var(--text-primary); font-size: 12px; }
.dock-empty span { font-size: 10px; }

.graph-status-bar {
  position: absolute;
  right: 20px;
  bottom: 66px;
  z-index: 38;
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 30px;
  padding: 0 9px;
  border: 1px solid var(--graph-border);
  border-radius: 8px;
  background: var(--graph-surface);
  color: var(--text-tertiary);
  font-size: 9px;
}
.has-drawer .graph-status-bar { right: 390px; }
.graph-status-bar span { display: flex; align-items: center; gap: 5px; }
.graph-status-bar i { width: 6px; height: 6px; border-radius: 50%; background: var(--success); }
.graph-status-bar i.loading { background: var(--warning); }
.graph-status-bar button { display: flex; align-items: center; gap: 5px; padding: 0; border: 0; background: transparent; color: var(--text-tertiary); font-size: 9px; cursor: pointer; }
.graph-status-bar button:hover { color: var(--primary-hover); }

.shortcuts-backdrop { position: fixed; inset: 0; z-index: 100; display: grid; place-items: center; padding: 20px; background: rgba(31, 29, 26, .28); }
.shortcuts-dialog { width: min(440px, 100%); padding: 0 18px 18px; border: 1px solid var(--graph-border); border-radius: 12px; background: #fff; box-shadow: 0 8px 24px rgba(35, 31, 25, .12); }
.shortcuts-dialog > header { display: flex; align-items: center; justify-content: space-between; gap: 18px; padding: 17px 0 14px; border-bottom: 1px solid var(--graph-divider); }
.shortcuts-dialog > header span { color: var(--primary); font-size: 10px; font-weight: 700; }
.shortcuts-dialog > header h2 { margin: 3px 0 0; font-size: 18px; }
.shortcuts-dialog dl { display: grid; grid-template-columns: 1fr 1fr; gap: 0 18px; margin: 12px 0 0; }
.shortcuts-dialog dl div { display: grid; grid-template-columns: 32px 1fr; align-items: center; gap: 9px; min-height: 42px; border-bottom: 1px solid var(--graph-divider); }
.shortcuts-dialog dt { display: grid; place-items: center; width: 28px; height: 28px; border: 1px solid var(--graph-border); border-radius: 6px; background: #f6f4f0; font-size: 10px; font-weight: 700; }
.shortcuts-dialog dd { margin: 0; color: var(--text-secondary); font-size: 11px; }

.workspace-notice { position: fixed; bottom: 72px; left: 50%; z-index: 120; padding: 9px 14px; border-radius: 8px; background: rgba(31, 29, 26, .9); color: #fff; font-size: 11px; transform: translateX(-50%); box-shadow: 0 8px 24px rgba(35, 31, 25, .12); }
/* ============================================================
 * 图谱工作区 v2：章节聚焦 / 图例联动 / 关系列表 / 面板密度
 * ============================================================ */
.chapter-focus-btn {
  display: grid;
  place-items: center;
  width: 24px;
  height: 24px;
  margin-left: 6px;
  border: 1px solid #e5e1d9;
  border-radius: 6px;
  background: #fff;
  color: #89857d;
  cursor: pointer;
  transition: color 160ms ease-out, border-color 160ms ease-out, background 160ms ease-out;
}
.chapter-focus-btn:hover { color: #e85d16; border-color: #f1c9ae; }
.chapter-focus-btn.active { background: #fff3ea; border-color: #f1c9ae; color: #d75011; }

.graph-legend {
  width: 232px;
  /* 顶端始终低于左侧画布工具柱底部（约 430px），避免相互遮挡 */
  max-height: max(180px, calc(100dvh - 520px));
  overflow: auto;
}
.graph-legend .legend-group summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-height: 28px;
  color: #625f58;
  font-size: 11.5px;
  font-weight: 600;
  cursor: pointer;
  list-style: none;
}
.graph-legend .legend-group summary::-webkit-details-marker { display: none; }
.graph-legend .legend-group summary em {
  color: #aaa69e;
  font-size: 10.5px;
  font-style: normal;
  font-weight: 500;
}
.graph-legend .legend-group + .legend-group {
  margin-top: 6px;
  padding-top: 4px;
  border-top: 1px solid #ece8e1;
}
.graph-legend .legend-nodes,
.graph-legend .legend-relations {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 6px;
  padding: 2px 0 4px;
}
.graph-legend .legend-relations {
  max-height: 150px;
  overflow: auto;
}
.legend-nodes button,
.legend-relations button {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 8px;
  border: 1px solid transparent;
  border-radius: 999px;
  background: transparent;
  color: #625f58;
  font-size: 12px;
  cursor: pointer;
  transition: background 160ms ease-out, border-color 160ms ease-out, color 160ms ease-out, opacity 160ms ease-out;
}
.legend-nodes button:hover,
.legend-relations button:hover { background: #f8f6f2; }
.legend-nodes button.active { border-color: #f1c9ae; background: #fff3ea; color: #d75011; }
.legend-relations button.muted { opacity: 0.4; text-decoration: line-through; }
.legend-relations button i { width: 18px; height: 0; border: 0; border-radius: 0; background: transparent; }
.legend-relations button em { color: #89857d; font-size: 11px; font-style: normal; font-variant-numeric: tabular-nums; }

.relation-rows { display: grid; gap: 2px; }
.relation-rows button {
  display: grid;
  grid-template-columns: 8px minmax(0, 1fr) auto 14px;
  align-items: center;
  gap: 9px;
  width: 100%;
  min-height: 36px;
  padding: 4px 8px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: #1f1d1a;
  font-size: 12.5px;
  text-align: left;
  cursor: pointer;
  transition: background 160ms ease-out;
}
.relation-rows button:hover { background: #f8f6f2; }
.relation-rows button i { width: 8px; height: 8px; border-radius: 3px; }
.relation-rows button span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.relation-rows button em,
.relation-rows button small { color: #89857d; font-size: 11.5px; font-style: normal; font-variant-numeric: tabular-nums; }
.recent-section { margin-top: 14px; }

/* —— 成就面板：进度轴 + KPI Strip + 下一目标 —— */
.achievement-grid { display: grid; grid-template-columns: minmax(0, 1.5fr) minmax(260px, 0.7fr); gap: 24px; align-items: start; }
.achievement-progress-head { display: flex; align-items: baseline; justify-content: space-between; gap: 16px; }
.achievement-progress-head span { display: block; color: #89857d; font-size: 12.5px; }
.achievement-progress-head strong { font-size: 26px; font-weight: 650; font-variant-numeric: tabular-nums; }
.achievement-progress-head strong i { color: #89857d; font-size: 14px; font-style: normal; font-weight: 500; }
.achievement-progress-head em { color: #d75011; font-size: 18px; font-style: normal; font-weight: 700; font-variant-numeric: tabular-nums; }
.stage-track { height: 8px; margin-top: 10px; border-radius: 999px; overflow: hidden; background: #f1ede6; }
.stage-track .stage-fill { display: block; width: 100%; height: 100%; border-radius: inherit; background: linear-gradient(90deg, #e8a34d, #e85d16); transform-origin: left center; transition: transform 300ms ease-out; }
.stage-marks { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; margin-top: 8px; }
.stage-marks button { display: grid; gap: 2px; padding: 6px 8px; border: 1px solid transparent; border-radius: 8px; background: transparent; text-align: left; cursor: pointer; transition: background 160ms ease-out, border-color 160ms ease-out; }
.stage-marks button:hover { background: #f8f6f2; }
.stage-marks button b { color: #89857d; font-size: 12px; font-weight: 600; }
.stage-marks button small { color: #aaa69e; font-size: 11.5px; }
.stage-marks button.unlocked b { color: #247553; }
.stage-marks button.unlocked small { color: #247553; }
.achievement-kpis { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); margin-top: 16px; border-top: 1px solid #e9e5de; border-bottom: 1px solid #e9e5de; }
.achievement-kpis button { display: grid; gap: 4px; padding: 12px 14px; border: 0; border-left: 1px solid #e9e5de; background: transparent; text-align: left; cursor: pointer; transition: background 160ms ease-out; }
.achievement-kpis button:first-child { border-left: 0; }
.achievement-kpis button:hover { background: #f8f6f2; }
.achievement-kpis button.active { background: #fff3ea; }
.achievement-kpis span { color: #89857d; font-size: 12px; }
.achievement-kpis strong { font-size: 20px; font-weight: 650; font-variant-numeric: tabular-nums; }
.achievement-kpis strong i { color: #89857d; font-size: 12px; font-style: normal; font-weight: 500; }
.achievement-side { display: grid; gap: 12px; }
.next-achievement { padding: 14px 16px; border: 1px solid #f1c9ae; border-radius: 12px; background: #fff3ea; }
.next-achievement span { display: block; color: #d75011; font-size: 11.5px; font-weight: 700; }
.next-achievement b { display: block; margin-top: 5px; font-size: 15px; }
.next-achievement small { display: block; margin-top: 4px; color: #625f58; font-size: 12px; }
.next-achievement i { display: block; height: 5px; margin-top: 10px; border-radius: 999px; overflow: hidden; background: rgba(232, 93, 22, 0.14); }
.next-achievement i em { display: block; width: 100%; height: 100%; border-radius: inherit; background: #e85d16; transform-origin: left center; }
.next-achievement.done { border-color: #cfe4d8; background: #eef8f2; }
.next-achievement.done span { color: #247553; }
.recommend-action { display: grid; gap: 6px; }
.recommend-action > span { color: #89857d; font-size: 11.5px; font-weight: 600; }
.recommend-action button { display: inline-flex; align-items: center; gap: 6px; min-height: 38px; padding: 0 12px; border: 1px solid #e5e1d9; border-radius: 9px; background: #fff; color: #1f1d1a; font-size: 12.5px; font-weight: 600; cursor: pointer; transition: border-color 160ms ease-out, transform 160ms ease-out; }
.recommend-action button:hover { border-color: #f1c9ae; transform: translateY(-1px); }

/* —— 统计面板：KPI Strip + 四块分布分析 —— */
.statistics-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 20px; margin-top: 16px; }
.stat-block header { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; margin-bottom: 6px; }
.stat-block header strong { font-size: 13px; font-weight: 650; }
.stat-block header span { color: #aaa69e; font-size: 11px; }
.dist-row { display: grid; grid-template-columns: minmax(0, auto) minmax(0, 1fr) auto; align-items: center; gap: 10px; width: 100%; min-height: 32px; padding: 3px 8px; border: 0; border-radius: 7px; background: transparent; color: #1f1d1a; font-size: 12.5px; text-align: left; cursor: pointer; transition: background 160ms ease-out; }
.dist-row:hover { background: #f8f6f2; }
.dist-row.active { background: #fff3ea; }
.dist-row.static { cursor: default; }
.dist-row.static:hover { background: transparent; }
.dist-row span { overflow: hidden; color: #625f58; text-overflow: ellipsis; white-space: nowrap; }
.dist-row i { display: block; height: 6px; border-radius: 999px; overflow: hidden; background: #f1ede6; }
.dist-row i em { display: block; height: 100%; border-radius: inherit; transition: width 250ms ease-out; }
.dist-row b { font-weight: 600; font-variant-numeric: tabular-nums; white-space: nowrap; }
.statistics-strip button { border: 0; background: transparent; text-align: left; cursor: pointer; transition: background 160ms ease-out; }
.statistics-strip button:hover { background: #f8f6f2; }
.statistics-strip button.active { background: #fff3ea; }
.clear-filters-btn { width: 100%; min-height: 34px; margin-top: 8px; border: 1px solid #e5e1d9; border-radius: 8px; background: #fff; color: #625f58; font-size: 12.5px; font-weight: 600; cursor: pointer; transition: color 160ms ease-out, border-color 160ms ease-out; }
.clear-filters-btn:hover { color: #d75011; border-color: #f1c9ae; }

/* —— 状态栏扩展 —— */
.graph-status-bar .status-link { border: 0; background: transparent; color: inherit; font: inherit; cursor: pointer; }
.graph-status-bar .status-link:hover { color: #d75011; }
.graph-status-bar .status-filter { display: inline-flex; align-items: center; gap: 4px; padding: 2px 8px; border: 1px solid #f1c9ae; border-radius: 999px; background: #fff3ea; color: #d75011; font-size: 11.5px; font-weight: 600; cursor: pointer; }
.layout-control { flex-wrap: wrap; }

@media (max-width: 900px) {
  .achievement-grid { grid-template-columns: 1fr; }
  .statistics-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .achievement-kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .achievement-kpis button:nth-child(odd) { border-left: 0; }
  .achievement-kpis button:nth-child(n + 3) { border-top: 1px solid #e9e5de; }
}

.notice-fade-enter-active,
.notice-fade-leave-active { transition: opacity 180ms ease-out, transform 180ms ease-out; }
.notice-fade-enter-from,
.notice-fade-leave-to { opacity: 0; transform: translate(-50%, 5px); }

@media (max-width: 1180px) {
  .floating-topbar { grid-template-columns: minmax(190px, auto) auto minmax(210px, 1fr) auto; }
  .workspace-name span,
  .select-control > span,
  .desktop-action { display: none; }
  .course-control select { max-width: 110px; }
  .scope-control { display: none; }
  .node-drawer { width: 322px; }
  .has-drawer .graph-minimap,
  .has-drawer .graph-status-bar { right: 350px; }
  .graphrag-layout { grid-template-columns: 1fr 1fr; }
  .recommendation-list { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

@media (max-width: 860px) {
  .floating-topbar { grid-template-columns: 1fr auto auto; gap: 6px; }
  .topbar-search { grid-column: 1 / -1; grid-row: 2; }
  .graph-level-switch button { padding: 0 8px; }
  .graph-level-switch button span { display: none; }
  .floating-topbar { min-height: 98px; }
  .course-panel-trigger { top: 130px; }
  .course-tree-panel { top: 126px; }
  .canvas-toolbar { top: 184px; }
  .graph-minimap { display: none; }
  .filter-popover { top: 130px; right: 14px; }
  .node-drawer { top: 126px; bottom: 64px; width: min(360px, calc(100vw - 28px)); }
  .compare-floating { top: 126px; }
  .dock-heading { flex-direction: column; gap: 6px; }
  .graphrag-layout,
  .search-workspace { grid-template-columns: 1fr; }
  .achievement-list { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .statistics-strip { grid-template-columns: repeat(3, 1fr); }
  .statistics-strip > div:nth-child(4) { border-left: 0; border-top: 1px solid var(--graph-divider); }
  .statistics-strip > div:nth-child(n + 4) { border-top: 1px solid var(--graph-divider); }
}

@media (max-width: 600px) {
  .floating-topbar { top: 8px; right: 8px; left: 8px; }
  .topbar-identity { gap: 5px; }
  .mini-logo,
  .workspace-name span { display: none; }
  .workspace-name { display: none; }
  .graph-level-switch { display: none; }
  .topbar-controls { gap: 2px; }
  .course-control { max-width: 116px; }
  .course-control select { max-width: 92px; font-size: 10px; }
  .course-panel-trigger { top: 124px; left: 8px; }
  .course-panel-trigger span { display: none; }
  .course-tree-panel { top: 120px; bottom: 60px; left: 8px; width: calc(100vw - 16px); }
  .canvas-toolbar { top: 174px; left: 8px; }
  .course-panel-open .canvas-toolbar { display: none; }
  .graph-legend { bottom: 60px; left: 8px; }
  .course-panel-open .graph-legend { display: none; }
  .filter-popover { top: 124px; right: 8px; width: calc(100vw - 16px); }
  .node-drawer { inset: 0; width: 100%; border: 0; border-radius: 0; }
  .drawer-header { padding-top: max(17px, env(safe-area-inset-top)); }
  .compare-floating { top: 120px; right: 8px; left: 8px; width: auto; }
  .has-drawer .compare-floating { display: none; }
  .bottom-workspace-dock { right: 8px; bottom: 8px; left: 8px; }
  .dock-tabs > button { padding: 0 9px; }
  .dock-tabs > button span { display: none; }
  .dock-tabs > button > svg:last-child { display: none; }
  .dock-panel { height: min(420px, 52vh); }
  .dock-content { padding: 14px; }
  .dock-heading h2 { font-size: 17px; }
  .recommendation-list,
  .achievement-list { grid-template-columns: 1fr; }
  .statistics-strip { grid-template-columns: repeat(2, 1fr); }
  .statistics-strip > div:nth-child(odd) { border-left: 0; }
  .statistics-strip > div:nth-child(n + 3) { border-top: 1px solid var(--graph-divider); }
  .graph-status-bar { right: 12px; bottom: 60px; }
  .graph-status-bar span:nth-of-type(n + 4),
  .graph-status-bar button { display: none; }
  .shortcuts-dialog dl { grid-template-columns: 1fr; }
}

@media (prefers-reduced-motion: reduce) {
  .kg-workspace *,
  .kg-workspace *::before,
  .kg-workspace *::after { animation-duration: .01ms !important; transition-duration: .01ms !important; scroll-behavior: auto !important; }
}
</style>
