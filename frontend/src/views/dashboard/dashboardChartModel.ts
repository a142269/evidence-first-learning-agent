export const DASHBOARD_COLORS = {
  brand: "#2563EB",
  ink: "#16324F",
  success: "#14B8A6",
  warning: "#38BDF8",
  risk: "#F87171",
  profile: "#6366F1",
  info: "#0EA5E9",
  canvas: "#F4F8FF",
  surface: "#FFFFFF",
  grid: "#DCE8F5",
  muted: "#64748B",
} as const;

export const DASHBOARD_CHART_COLORS = {
  mastery: "#14B8A6",
  masteryWarning: "#38BDF8",
  masteryRisk: "#F87171",
  forecast: "#4F46E5",
  forecastBand: "#E0E7FF",
  milestone: "#06B6D4",
  profile: ["#2563EB", "#0EA5E9", "#06B6D4", "#14B8A6", "#6366F1", "#64748B"],
  errors: ["#FDBA74", "#FB923C", "#F97316", "#EF4444", "#B91C1C"],
  score: ["#C4B5FD", "#A78BFA", "#818CF8", "#6366F1", "#4F46E5"],
  weight: "#6366F1",
  weightSecondary: "#38BDF8",
  trend: "#6366F1",
  trendPass: "#14B8A6",
  trendFail: "#F87171",
  trendAverage: "#64748B",
  rhythm: ["#60A5FA", "#38BDF8", "#22D3EE", "#2DD4BF", "#14B8A6", "#0D9488", "#2563EB"],
  matrix: ["#EFF6FF", "#BFDBFE", "#60A5FA", "#2563EB", "#1E3A8A"],
  heatmap: ["#ECFDF5", "#A7F3D0", "#5EEAD4", "#14B8A6", "#0F766E"],
  activity: {
    profile_snapshot: "#6366F1",
    path_adjustment: "#2563EB",
    mistake_recorded: "#F87171",
    assessment: "#14B8A6",
    resource_generated: "#06B6D4",
  },
} as const;

export type SemanticTone = "risk" | "warning" | "success";
export type ProfileTone = "profile" | "neutral";

const RESOURCE_LABELS: Record<string, string> = {
  document: "文档",
  quiz: "题库",
  mindmap: "思维导图",
  video: "视频",
  code: "代码练习",
};

const DASHBOARD_LABELS: Record<string, string> = {
  conceptual_misunderstanding: "概念理解偏差",
  calculation_error: "计算错误",
  application_transfer: "迁移应用困难",
  careless_error: "审题疏忽",
  reading_comprehension: "题意理解偏差",
  memory_gap: "知识记忆缺口",
  strategy_error: "解题策略不当",
  incomplete_answer: "作答不完整",
  concept_confusion: "概念混淆",
  careless: "粗心失误",
  ambiguous_question: "题意模糊",
  input_error: "输入错误",
  boundary_unclear: "边界不清",
  prerequisite_missing: "先修知识缺失",
  procedural_slip: "步骤失误",
  unknown: "待归因",
  improving: "上升",
  declining: "下降",
  stable: "平稳",
  document: "文档",
  doc: "文档",
  quiz: "测验",
  mindmap: "思维导图",
  video: "视频",
  code: "代码练习",
  article: "文章",
  audio: "音频",
  presentation: "演示文稿",
  ppt: "演示文稿",
  pptx: "演示文稿",
  practice: "练习",
  project: "项目实践",
  assessment: "测评",
  path_adjustment: "路径调整",
  resource_generated: "资源生成",
};

const KNOWLEDGE_POINT_LABELS: Record<string, string> = {
  AI_001: "人工智能概述",
  AI_002: "搜索算法",
  AI_003: "知识表示与推理",
  AI_004: "机器学习基础",
  AI_005: "监督学习算法",
  AI_005_01: "线性回归与逻辑回归",
  AI_005_02: "决策树与集成学习",
  AI_005_03: "支持向量机（SVM）",
  AI_006: "神经网络与深度学习",
  AI_006_01: "卷积神经网络（CNN）",
  AI_006_02: "循环神经网络（RNN）",
  AI_006_03: "Transformer 与注意力机制",
  AI_007: "自然语言处理（NLP）",
  AI_008: "计算机视觉（CV）",
  AI_009: "强化学习",
  AI_010: "AI 伦理与前沿趋势",
  CODE_001: "Python 编程基础",
  CODE_002: "深度学习框架（PyTorch）",
  MATH_001: "线性代数基础",
  MATH_002: "概率论与数理统计",
  MATH_003: "微积分与最优化",
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
  "transformer/layer_norm": "层归一化",
  "cnn/convolution": "CNN 卷积计算",
  "cnn/pooling": "CNN 池化",
  "cnn/receptive_field": "CNN 感受野",
  "cnn/batch_norm": "批归一化（BatchNorm）",
  "linear_algebra/eigenvalue": "特征值与特征向量",
  "linear_algebra/matrix_multiply": "矩阵乘法",
  "linear_algebra/svd": "奇异值分解（SVD）",
  "rag/retrieval": "RAG 检索与重排",
  "rag/chunking": "RAG 文本分块",
  "rag/embedding": "RAG 语义向量检索",
  "rag/hybrid_search": "RAG 混合检索",
  "rag/eval": "RAG 忠实度评估",
};

export function localizeDashboardLabel(value: unknown): string {
  const label = String(value ?? "").trim();
  if (!label) return "—";
  return DASHBOARD_LABELS[label.toLowerCase()] ?? label;
}

export function localizeKnowledgePointLabel(kpId: unknown, apiName?: unknown): string {
  const id = String(kpId ?? "").trim();
  const name = String(apiName ?? "").trim();
  if (name && name !== id) return name;
  return KNOWLEDGE_POINT_LABELS[id] || id || "未命名知识点";
}

export function localizeLearningMaterialTitle(value: unknown): string {
  const title = String(value ?? "").trim();
  if (!title) return "未命名学习资料";
  if (/Dropout:\s*A Simple Way to Prevent Neural Networks from Overfitting/i.test(title)) {
    return "Dropout：一种防止神经网络过拟合的简单方法";
  }
  if (/Understanding the Bias[- ]Variance Tradeoff/i.test(title)) {
    return "理解偏差与方差权衡";
  }
  return title;
}

export function masteryTone(value: number): SemanticTone {
  if (value < 0.5) return "risk";
  if (value < 0.8) return "warning";
  return "success";
}

export function rankErrorCategories(categories: Record<string, number>) {
  const entries = Object.entries(categories)
    .map(([name, value], sourceIndex) => ({ name, value: Number(value) || 0, sourceIndex }))
    .filter((item) => item.value >= 0)
    .sort((a, b) => b.value - a.value || a.sourceIndex - b.sourceIndex);
  const total = entries.reduce((sum, item) => sum + item.value, 0);
  return entries.map(({ name, value }, rank) => ({
    name,
    value,
    percent: total ? Math.round((value / total) * 1000) / 10 : 0,
    rank,
  }));
}

export function buildOrganicBubbleLayout<T>(items: readonly T[]) {
  const goldenAngle = Math.PI * (3 - Math.sqrt(5));
  return items.map((item, index) => {
    if (index === 0) return { ...item, x: 1.5, y: 1 };
    const radius = 0.82 + Math.sqrt(index - 1) * 0.5;
    const angle = index * goldenAngle - 0.8;
    return {
      ...item,
      x: Math.round((1.5 + Math.cos(angle) * radius) * 1_000) / 1_000,
      y: Math.round((1 + Math.sin(angle) * radius * 0.48) * 1_000) / 1_000,
    };
  });
}

export function rankResourceWeights(weights: Record<string, number>) {
  return Object.entries(weights)
    .map(([key, value], sourceIndex) => ({
      key,
      label: RESOURCE_LABELS[key] ?? key,
      value: Number(value) || 0,
      sourceIndex,
    }))
    .sort((a, b) => b.value - a.value || a.sourceIndex - b.sourceIndex)
    .map(({ key, label, value }, rank) => ({ key, label, value, isTop: rank === 0 }));
}

export function sortAssessmentRecords<T extends { timestamp?: unknown }>(records: readonly T[]): T[] {
  const toTime = (value: unknown) => {
    if (typeof value === "number" && Number.isFinite(value)) return value;
    if (typeof value === "string") {
      const parsed = Date.parse(value);
      return Number.isFinite(parsed) ? parsed : 0;
    }
    return 0;
  };
  return [...records].sort((a, b) => toTime(a.timestamp) - toTime(b.timestamp));
}

export function deriveForecastMilestones(
  forecast: readonly { day: number; p_learned?: number; mastery?: number }[],
  targets = [0.8, 0.9, 0.95],
) {
  return targets.flatMap((target) => {
    const point = forecast.find((item) => Number(item.p_learned ?? item.mastery ?? 0) >= target);
    return point ? [{ day: point.day, target, label: `${Math.round(target * 100)}%` }] : [];
  });
}

type ForecastMasteryPoint = { p_learned?: number; mastery?: number };

const clampMastery = (value: number) => Math.min(1, Math.max(0, value));

export function buildRisingForecastCurve(forecast: readonly ForecastMasteryPoint[]) {
  if (!forecast.length) return [];
  const raw = forecast.map((item) => clampMastery(Number(item.mastery ?? item.p_learned ?? 0)));
  const start = raw[0];
  const end = Math.max(start, ...raw);
  if (raw.length === 1 || end <= start) return raw;

  const easingStrength = 2.2;
  const easingScale = 1 - Math.exp(-easingStrength);
  return raw.map((_, index) => {
    const progress = index / (raw.length - 1);
    const easedProgress = (1 - Math.exp(-easingStrength * progress)) / easingScale;
    return Math.round((start + (end - start) * easedProgress) * 10_000) / 10_000;
  });
}

export function buildForecastAxis(values: readonly number[]) {
  if (!values.length) return { min: 0, max: 1 };
  const lowest = Math.min(...values);
  const highest = Math.max(...values);
  const padding = Math.max(0.015, (highest - lowest) * 0.25);
  let min = Math.max(0, Math.floor((lowest - padding) * 100) / 100);
  let max = Math.min(1, Math.ceil((highest + padding) * 100) / 100);
  if (max - min < 0.04) {
    min = Math.max(0, Math.floor((lowest - 0.02) * 100) / 100);
    max = Math.min(1, Math.ceil((highest + 0.02) * 100) / 100);
  }
  return { min, max };
}

export function buildForecastBand(
  forecast: readonly { ci_low?: number; ci_high?: number }[],
  centers?: readonly number[],
) {
  const lower = forecast.map((item, index) => {
    const rawLow = Number(item.ci_low ?? 0);
    const rawHigh = Number(item.ci_high ?? rawLow);
    const width = Math.min(1, Math.max(0, rawHigh - rawLow));
    const center = centers?.[index];
    if (center == null) return rawLow;
    return Math.min(1 - width, Math.max(0, center - width / 2));
  });
  const range = forecast.map((item, index) => {
    const rawLow = Number(item.ci_low ?? 0);
    const rawHigh = Number(item.ci_high ?? rawLow);
    return Math.round(Math.max(0, rawHigh - rawLow) * 1_000_000) / 1_000_000;
  });
  return { lower, range };
}

export function buildProfileRows<T extends { name: string; value: number; status?: string }>(rows: readonly T[]) {
  return rows.map((row) => ({
    ...row,
    tone: (row.status === "unknown" ? "neutral" : "profile") as ProfileTone,
  }));
}

export function buildHeatmapWeeks<T extends { date: string }>(days: readonly T[]): (T | null)[][] {
  if (!days.length) return [];
  const firstDate = new Date(`${days[0].date}T00:00:00`);
  const frontPadding = Number.isFinite(firstDate.getTime()) ? firstDate.getDay() : 0;
  const padded: (T | null)[] = [...Array(frontPadding).fill(null), ...days];
  const backPadding = (7 - (padded.length % 7)) % 7;
  padded.push(...Array(backPadding).fill(null));
  const weeks: (T | null)[][] = [];
  for (let index = 0; index < padded.length; index += 7) {
    weeks.push(padded.slice(index, index + 7));
  }
  return weeks;
}

export function groupRecommendationsByKnowledgePoint<
  T extends { kp_id: string; topic?: string },
  W extends { kp_id: string; mastery: number; name?: string },
>(items: readonly T[], weakestKnowledgePoints: readonly W[]) {
  const masteryByKnowledgePoint = new Map(
    weakestKnowledgePoints.map((item) => [item.kp_id, item]),
  );
  const grouped = new Map<string, {
    key: string;
    kpId: string;
    name: string;
    mastery: number;
    resources: T[];
  }>();

  for (const item of items) {
    const key = item.topic || item.kp_id || "未命名知识点";
    const weakPoint = masteryByKnowledgePoint.get(item.kp_id);
    const existing = grouped.get(key);
    if (existing) {
      existing.resources.push(item);
      continue;
    }
    grouped.set(key, {
      key,
      kpId: item.kp_id,
      name: item.topic || weakPoint?.name || item.kp_id || "未命名知识点",
      mastery: Number(weakPoint?.mastery ?? 0),
      resources: [item],
    });
  }

  return Array.from(grouped.values());
}

const WEEKDAY_LABELS = [
  { key: 1, label: "周一" },
  { key: 2, label: "周二" },
  { key: 3, label: "周三" },
  { key: 4, label: "周四" },
  { key: 5, label: "周五" },
  { key: 6, label: "周六" },
  { key: 0, label: "周日" },
] as const;

export function aggregateWeekdayRhythm(
  days: readonly { date: string; count?: number; minutes?: number }[],
) {
  const totals = new Map<number, { count: number; minutes: number }>(
    WEEKDAY_LABELS.map(({ key }) => [key, { count: 0, minutes: 0 }]),
  );

  for (const day of days) {
    const date = new Date(`${day.date}T00:00:00`);
    if (!Number.isFinite(date.getTime())) continue;
    const slot = totals.get(date.getDay());
    if (!slot) continue;
    slot.count += Math.max(0, Number(day.count) || 0);
    slot.minutes += Math.max(0, Number(day.minutes) || 0);
  }

  return WEEKDAY_LABELS.map(({ key, label }) => ({
    key,
    label,
    count: Math.round((totals.get(key)?.count ?? 0) * 100) / 100,
    minutes: Math.round((totals.get(key)?.minutes ?? 0) * 100) / 100,
  }));
}

export function deriveWeekdayPeak<T extends { minutes: number }>(items: readonly T[]): T | null {
  return items.reduce<T | null>((peak, item) => (
    !peak || Number(item.minutes) > Number(peak.minutes) ? item : peak
  ), null);
}

export function formatCompactMinutes(value: number): string {
  const minutes = Math.max(0, Math.round(Number(value) || 0));
  if (minutes < 1000) return `${minutes} 分钟`;
  return `${(minutes / 1000).toFixed(1)}k 分钟`;
}

export function buildMistakeMatrix(
  response: {
    categories?: readonly string[];
    matrix?: readonly ({ kp_id: string; total?: number } & Record<string, unknown>)[];
    total_mistakes?: number;
  } | null | undefined,
  limit = 8,
) {
  const categories = [...(response?.categories ?? [])];
  const rows = [...(response?.matrix ?? [])]
    .map((row, sourceIndex) => ({
      row,
      sourceIndex,
      total: Math.max(0, Number(row.total) || 0),
    }))
    .filter(({ row }) => Boolean(row.kp_id))
    .sort((a, b) => b.total - a.total || a.sourceIndex - b.sourceIndex)
    .slice(0, Math.max(0, limit));

  let max = 0;
  const data: number[][] = [];
  rows.forEach(({ row }, knowledgePointIndex) => {
    categories.forEach((category, categoryIndex) => {
      const value = Math.max(0, Number(row[category]) || 0);
      max = Math.max(max, value);
      data.push([categoryIndex, knowledgePointIndex, value]);
    });
  });

  return {
    categories,
    knowledgePoints: rows.map(({ row }) => row.kp_id),
    data,
    max,
    total: Math.max(0, Number(response?.total_mistakes) || 0),
  };
}

export function buildMasteryComparison(
  items: readonly {
    kp_id: string;
    bkt_p_learned: number | null;
    dina_mastery: number | null;
  }[],
) {
  return items
    .flatMap((item, sourceIndex) => {
      if (
        typeof item.bkt_p_learned !== "number"
        || !Number.isFinite(item.bkt_p_learned)
        || typeof item.dina_mastery !== "number"
        || !Number.isFinite(item.dina_mastery)
      ) return [];
      const bkt = Math.min(1, Math.max(0, item.bkt_p_learned));
      const dina = Math.min(1, Math.max(0, item.dina_mastery));
      return [{
        kpId: item.kp_id,
        bkt,
        dina,
        gap: Math.round(Math.abs(bkt - dina) * 1_000_000) / 1_000_000,
        sourceIndex,
      }];
    })
    .sort((a, b) => b.gap - a.gap || a.sourceIndex - b.sourceIndex)
    .map(({ sourceIndex: _sourceIndex, ...item }) => item);
}

export function buildScoreDistribution(records: readonly { score?: unknown }[]) {
  const bands = [
    { label: "0–59", min: 0, max: 59, count: 0 },
    { label: "60–69", min: 60, max: 69, count: 0 },
    { label: "70–79", min: 70, max: 79, count: 0 },
    { label: "80–89", min: 80, max: 89, count: 0 },
    { label: "90–100", min: 90, max: 100, count: 0 },
  ];
  for (const record of records) {
    if (typeof record.score !== "number" || !Number.isFinite(record.score)) continue;
    const score = Math.min(100, Math.max(0, record.score));
    const band = bands.find((item) => score >= item.min && score <= item.max);
    if (band) band.count += 1;
  }
  return bands;
}

export function buildResourceTreemap(types: Record<string, number>) {
  return Object.entries(types)
    .map(([key, value], sourceIndex) => ({
      key,
      name: RESOURCE_LABELS[key] ?? key,
      value: Math.max(0, Number(value) || 0),
      sourceIndex,
    }))
    .filter((item) => item.value > 0)
    .sort((a, b) => b.value - a.value || a.sourceIndex - b.sourceIndex)
    .map(({ sourceIndex: _sourceIndex, ...item }) => item);
}

export const DASHBOARD_CHART_THEME = {
  textStyle: { color: DASHBOARD_COLORS.ink, fontFamily: "inherit" },
  axisLabel: { color: DASHBOARD_COLORS.muted, fontSize: 11 },
  axisLine: { lineStyle: { color: DASHBOARD_COLORS.grid } },
  splitLine: { lineStyle: { color: DASHBOARD_COLORS.grid, opacity: 0.75 } },
  tooltip: {
    backgroundColor: "rgba(255,255,255,0.98)",
    borderColor: DASHBOARD_COLORS.grid,
    textStyle: { color: DASHBOARD_COLORS.ink, fontSize: 13 },
    extraCssText: "box-shadow: 0 8px 24px rgba(37,99,235,0.10); border-radius: 10px;",
  },
} as const;
