<script setup lang="ts">
/**
 * ResourcesView.vue — 资源库
 *
 * 双栏布局：
 *   - 主区：搜索条 / 类型 Tab / 排序与视图切换 / 精选专题 Hero / 资源卡片网格 / 分页
 *   - 侧栏：资源概览 / 资源分类 / 最近访问 / 上传入口 / AI 推荐 / 本周推荐
 *
 * 配色沿用 tokens.scss 的暖橙系（--orange-* / --paper-* / --ink-*），
 * 不引入新的色板，仅在保持视觉一致的前提下用语义化变量表达。
 */
import { computed, onMounted, onBeforeUnmount, ref, watch, type Component } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  Bookmark, BookOpen, ChevronDown, ChevronLeft, ChevronRight, ChevronsLeft,
  ChevronsRight, ClipboardCheck, ClipboardList, Cloud, CloudUpload, Code2,
  Eye, FileText, Files, Filter, Folder, FolderPlus, Grid3x3, Headphones,
  Image as ImageIcon, LayoutGrid, List, Loader2, MessageSquareText,
  MessagesSquare, MoreHorizontal, Network, Presentation, RefreshCw, Search,
  Share2, SlidersHorizontal, Sparkles, Star, TrendingUp, Users, Video, X,
} from "lucide-vue-next";
import { renderMarkdown } from "@/utils/markdown";

import { downloadResourceAttachment, listResources, saveResource, type Resource } from "@/api/resources";
import { getRecommendations, type RecommendationItem } from "@/api/insights";
import { listCourses } from "@/api/knowledge";
import {
  listArtifacts,
  getArtifactDownloadFullUrl,
  artifactDataUriUrl,
  artifactDownloadUrl,
  getArtifactInfo,
  type ArtifactInfo,
} from "@/api/artifacts";
import { getChatArchive, type ChatArchiveRecord } from "@/api/chat";
import { useSession } from "@/composables/useSession";
import {
  localizeResourceTags,
  localizeResourceText,
  resourceAgentLabel,
  resourceTypeLabel,
} from "@/utils/resourceDisplay";

const { userId, course, setCourse } = useSession();
const router = useRouter();

interface CourseOption {
  value: string;
  label: string;
}

// 课程显示名由 /knowledge/courses 的 course.yaml 清单动态下发（平台化改造）
const FALLBACK_COURSES: CourseOption[] = [
  { value: "artificial_intelligence", label: "人工智能导论" },
];
const courseOptions = ref<CourseOption[]>([...FALLBACK_COURSES]);

function courseLabel(value: string): string {
  return courseOptions.value.find((item) => item.value === value)?.label
    || value.replace(/_/g, " ");
}

function asRecord(value: unknown): Record<string, any> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, any>
    : null;
}

/**
 * 接口和旧版 localStorage 可能返回半结构化记录。先在边界处补齐默认值，
 * 避免某一条坏记录在 computed/template 中抛异常，把整个资源库渲染成白屏。
 */
function normalizeResourceRows(value: unknown): Resource[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item) => {
    const row = asRecord(item);
    if (!row || !row.id) return [];
    const metadata = asRecord(row.metadata) || {};
    const tags = Array.isArray(row.tags)
      ? row.tags.map((tag) => String(tag || "")).filter(Boolean)
      : [];
    return [{
      ...row,
      id: String(row.id),
      user_id: String(row.user_id || ""),
      type: String(row.type || row.resource_type || "document"),
      title: String(row.title || "未命名资源"),
      content: typeof row.content === "string" ? row.content : String(row.content || ""),
      content_type: String(row.content_type || "text/markdown"),
      agent_name: String(row.agent_name || ""),
      metadata,
      created_at: Number.isFinite(Number(row.created_at)) ? Number(row.created_at) : 0,
      tags,
    } as Resource];
  });
}

function normalizeArtifactRows(value: unknown): ArtifactInfo[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item) => {
    const row = asRecord(item);
    const id = row?.id || row?.resource_id;
    if (!row || !id) return [];
    return [{
      ...row,
      id: String(row.id || id),
      resource_id: row.resource_id ? String(row.resource_id) : undefined,
      type: String(row.type || "file"),
      metadata: asRecord(row.metadata) || {},
      created_at: Number.isFinite(Number(row.created_at)) ? Number(row.created_at) : undefined,
    } as ArtifactInfo];
  });
}

async function loadCourseOptions() {
  try {
    const response = await listCourses();
    const options = response.courses
      .map((item) => {
        if (typeof item === "string") {
          return { value: item, label: item.replace(/_/g, " ") };
        }
        const value = String(item.id || item.name || "");
        return {
          value,
          label: String(item.display_name || "") || value.replace(/_/g, " "),
        };
      })
      .filter((item) => Boolean(item.value));
    if (options.length) {
      courseOptions.value = options;
    }
  } catch {
    courseOptions.value = [...FALLBACK_COURSES];
  }
  if (!courseOptions.value.some((item) => item.value === course.value)) {
    setCourse(courseOptions.value[0]?.value || FALLBACK_COURSES[0].value);
  }
}

function handleCourseChange(event: Event) {
  setCourse((event.target as HTMLSelectElement).value);
}

/* -------------------- 来源筛选（学习资源 / 聊天存档） -------------------- */
const sourceFilter = ref<"learning" | "chat">("learning");

/* -------------------- 聊天存档数据 -------------------- */
const chatArchiveRecords = ref<ChatArchiveRecord[]>([]);
const chatArchiveLoading = ref(false);

async function loadChatArchive() {
  if (!userId.value) return;
  chatArchiveLoading.value = true;
  try {
    const r = await getChatArchive(userId.value, 100);
    chatArchiveRecords.value = Array.isArray(r?.records)
      ? r.records.filter((record): record is ChatArchiveRecord => {
        const row = asRecord(record);
        return Boolean(row && typeof row.role === "string" && typeof row.content === "string");
      })
      : [];
  } catch {
    chatArchiveRecords.value = [];
  } finally {
    chatArchiveLoading.value = false;
    // 数据加载完成后更新 tab 计数
    updateTypeTabCounts();
  }
}

/** 把聊天记录转成卡片格式，供 filteredCards 使用 */
const chatArchiveCards = computed<CardItem[]>(() => {
  // 1. 群聊对话中生成的资源文件（从学习资源分流过来）
  const chatFiles: CardItem[] = cards.value.filter((c) => c.fromChat).map((c) => ({
    ...c,
    tags: ["聊天生成", ...(c.tags || [])].slice(0, 4),
  }));

  // 2. 把 user + assistant 配对成问答对
  const pairs: CardItem[] = [];
  let i = 0;
  while (i < chatArchiveRecords.value.length) {
    const rec = chatArchiveRecords.value[i];
    if (rec.role === "user") {
      const answer = chatArchiveRecords.value[i + 1];
      const agentName = resourceAgentLabel(answer?.agent_name || "");
      const question = localizeResourceText(rec.content, "问题待补充");
      const answerText = answer ? localizeResourceText(answer.content, "暂无回答") : "（等待回复）";
      const categoryKeys = inferArchiveCategoryKeys(question, answerText, agentName);
      pairs.push({
        id: `chat-${rec.id || i}`,
        rid: `chat-${rec.id || i}`,
        kind: "note",
        badgeText: "💬",
        title: question.slice(0, 60) + (question.length > 60 ? "..." : ""),
        desc: answerText.slice(0, 120) + (answerText.length > 120 ? "..." : ""),
        author: agentName || "AI",
        date: formatTime(rec.created_at),
        views: "—",
        tags: ["聊天记录", agentName].filter(Boolean),
        artifactType: "chat",
        categoryKeys,
      });
      i += 2;
    } else {
      i += 1;
    }
  }
  return [...chatFiles, ...pairs.reverse()]; // 文件在前，问答按最新在前
});

function formatTime(ts?: number): string {
  if (!ts) return "";
  const d = new Date(ts * 1000);
  return `${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/* -------------------- 类型 Tab -------------------- */
interface TypeTab {
  key: string;
  label: string;
  count: number;
}
const typeTabs = ref<TypeTab[]>([
  { key: "all",     label: "全部资源", count: 286 },
  { key: "doc",     label: "文档",     count: 102 },
  { key: "video",   label: "视频",     count: 58  },
  { key: "quiz",    label: "题库",     count: 47  },
  { key: "ppt",     label: "课件",     count: 38  },
  { key: "kg",      label: "知识图谱", count: 21  },
]);
const activeTab = ref<string>("all");

const TYPE_CATEGORY_MAP: Record<string, string[]> = {
  doc: ["document", "prompt", "markdown", "md", "reading", "txt", "code"],
  video: ["manim", "video", "mp4", "mp3", "tts", "audio"],
  quiz: ["quiz", "question_bank"],
  ppt: ["ppt", "pptx"],
  kg: ["mermaid", "mindmap", "mind", "graph", "knowledge_graph"],
};

const RESOURCE_ICON_MAP: Record<string, Component> = {
  all: Files,
  doc: FileText,
  document: FileText,
  txt: FileText,
  markdown: FileText,
  md: FileText,
  reading: BookOpen,
  prompt: MessageSquareText,
  video: Video,
  mp4: Video,
  manim: Video,
  audio: Headphones,
  mp3: Headphones,
  tts: Headphones,
  quiz: ClipboardCheck,
  question_bank: ClipboardCheck,
  ppt: Presentation,
  pptx: Presentation,
  kg: Network,
  mind: Network,
  mindmap: Network,
  mermaid: Network,
  mermaid_png: Network,
  graph: Network,
  knowledge_graph: Network,
  image: ImageIcon,
  png: ImageIcon,
  svg: ImageIcon,
  code: Code2,
  tutoring: MessagesSquare,
  evaluation_report: ClipboardList,
  report: ClipboardList,
  folder: Folder,
  file: Files,
};

function resourceIconForType(type: unknown): Component {
  const key = String(type ?? "")
    .trim()
    .toLowerCase()
    .replace(/[\s-]+/g, "_");
  if (RESOURCE_ICON_MAP[key]) return RESOURCE_ICON_MAP[key];
  if (key.includes("ppt")) return Presentation;
  if (key.includes("audio") || key.includes("mp3") || key.includes("tts")) return Headphones;
  if (key.includes("video") || key.includes("mp4") || key.includes("manim")) return Video;
  if (key.includes("mermaid") || key.includes("mind") || key.includes("graph")) return Network;
  if (key.includes("image") || key.includes("png") || key.includes("svg")) return ImageIcon;
  if (key.includes("quiz") || key.includes("question")) return ClipboardCheck;
  if (key.includes("code")) return Code2;
  if (key.includes("tutor")) return MessagesSquare;
  if (key.includes("evaluat") || key.includes("report")) return ClipboardList;
  if (key.includes("prompt")) return MessageSquareText;
  if (key.includes("doc") || key.includes("reading") || key.includes("text")) return FileText;
  return Files;
}

/* -------------------- 排序 / 视图 -------------------- */
const sortKey = ref<string>("latest");
const sortOptions = [
  { key: "latest",   label: "最新上传" },
  { key: "popular",  label: "最多浏览" },
  { key: "rating",   label: "评分最高" },
  { key: "favor",    label: "收藏最多" },
];
const sortOpen = ref(false);
const viewMode = ref<"grid" | "list">("grid");
// filteredCards 会在 watch(totalPages) 建立依赖时立即求值，必须先初始化。
const favOnlyFilter = ref(false);

/* -------------------- Hero 精选专题（内置两课有定制文案，新课程走通用模板） -------------------- */
const hero = computed(() => {
  if (course.value === "python_programming") {
    return {
      tag: "精选课程",
      title: "Python 程序设计课程资源",
      desc: "汇集 Python 语法、程序设计、数据结构、算法与项目实践等真实课程资料，支持讲义、题库、演示文稿、音视频和代码案例统一学习。",
      cta: "查看全部资源",
      formula: "Python",
    };
  }
  if (course.value === "artificial_intelligence") {
    return {
      tag: "精选课程",
      title: "人工智能课程资源",
      desc: "汇集机器学习、深度学习、RAG、AI Agent 与多模态学习等真实课程资料，支持讲义、题库、演示文稿、音视频和知识图谱统一学习。",
      cta: "查看全部资源",
      formula: "AI",
    };
  }
  const label = courseLabel(course.value);
  return {
    tag: "精选课程",
    title: `${label}课程资源`,
    desc: `汇集「${label}」课程的讲义、题库、演示文稿、音视频等教学资料，由教师在课程知识库中持续维护更新。`,
    cta: "查看全部资源",
    formula: label.slice(0, 6),
  };
});

/* -------------------- 资源卡片 -------------------- */
type ResKind = "pdf" | "video" | "quiz" | "mind" | "note" | "ppt" | "mp3" | "manim";
interface CardItem {
  id: string;
  kind: ResKind;
  badgeText: string;
  title: string;
  desc: string;
  author: string;
  date: string;       // MM-DD
  views: string;      // 1.2k / 876
  tags: string[];
  rid?: string;       // artifact registry id（用于下载/预览）
  artifactType?: string;
  filepath?: string;
  session_id?: string;
  resourceId?: string;  // resource id（来自 /resources/list，content 可直接预览）
  resourceType?: string;
  attachment?: { filename: string; size_bytes?: number; media_type?: string };
  fromChat?: boolean;   // 群聊对话生成的资源 → 归入「聊天存档」
  /** 个性化标记：本资源生成时注入了学生画像；hint = 注入的画像摘要（可能为空字符串） */
  personalized?: boolean;
  personalizedHint?: string;
  /** 一条综合协作记录可能同时包含 PPT、题库、视频等多类资源。 */
  categoryKeys?: string[];
}

function inferArchiveCategoryKeys(...parts: string[]): string[] {
  const text = parts.join(" ").toLowerCase();
  const categories = new Set<string>();
  const includesAny = (tokens: string[]) => tokens.some((token) => text.includes(token));

  if (includesAny(["ppt", "pptx", "课件", "幻灯片", "演示文稿"])) categories.add("ppt");
  if (includesAny(["视频", "动画", "配音", "音频", "语音", "tts", "播客", "mp4"])) categories.add("video");
  if (includesAny(["练习题", "习题", "题库", "测验", "试卷", "单选", "多选", "判断题", "debug"])) categories.add("quiz");
  if (includesAny(["思维导图", "脑图", "知识图谱", "mermaid", "导图", "关系图"])) categories.add("kg");
  if (includesAny(["文档", "资料", "讲义", "笔记", "知识点", "学习路径", "代码", "示例", "总结"])) categories.add("doc");

  return [...categories];
}

function cardMatchesCategory(card: CardItem, category: string): boolean {
  if (category === "all") return true;
  if (card.categoryKeys?.includes(category)) return true;
  const acceptedTypes = TYPE_CATEGORY_MAP[category] || [];
  const rawTypes = [card.artifactType, card.resourceType]
    .filter(Boolean)
    .map((value) => String(value).toLowerCase());
  return acceptedTypes.some((type) => rawTypes.some((raw) => raw.includes(type)));
}

/* 硬编码的演示卡片（当后端无 artifact 时作为 fallback） */
const fallbackCards: CardItem[] = [
  { id: "c1", kind: "pdf",   badgeText: "MD", title: "特征值与特征向量核心讲义",
    desc: "系统梳理定义、性质与计算方法，配合典型例题与证明思路解析。",
    author: "系统协调员", date: "05-10", views: "2.1k",
    tags: ["文档", "线性代数", "重点"],
    resourceId: "demo-c1", resourceType: "document" },
  { id: "c2", kind: "video", badgeText: "▶",   title: "线性代数例题精讲视频",
    desc: "精选高频考点例题，逐题讲解思路与解题技巧。",
    author: "课程讲解员", date: "05-09", views: "1.8k",
    tags: ["视频", "45min", "讲解"],
    resourceId: "demo-c2", resourceType: "video" },
  { id: "c3", kind: "quiz",  badgeText: "✓",   title: "精选习题集（含解析）",
    desc: "分章节习题与详细解析，附难度分级与考点标注。",
    author: "习题教练", date: "05-08", views: "3.4k",
    tags: ["题库", "练习", "含解析"],
    resourceId: "demo-c3", resourceType: "quiz" },
  { id: "c4", kind: "mind",  badgeText: "◉",   title: "知识图谱：矩阵与对角化",
    desc: "可视化展示知识点关联，支持节点展开与路径学习。",
    author: "知识图谱助手", date: "05-07", views: "1.2k",
    tags: ["图谱", "矩阵", "对角化"],
    resourceId: "demo-c4", resourceType: "mindmap" },
  { id: "c5", kind: "note",  badgeText: "≡",   title: "期末复习速记卡",
    desc: "核心公式与结论整理，便于快速记忆与复习。",
    author: "学习分析员", date: "05-06", views: "876",
    tags: ["笔记", "速记卡", "复习"],
    resourceId: "demo-c5", resourceType: "document" },
  { id: "c6", kind: "ppt",   badgeText: "PPT", title: "课堂PPT：线性变换基础",
    desc: "课堂讲解PPT，包含定义、性质、例题与板书总结。",
    author: "课程讲解员", date: "05-05", views: "1.6k",
    tags: ["课件", "线性变换", "课堂"],
    resourceId: "demo-c6", resourceType: "ppt" },
];

/* 演示卡片的示例 Markdown 内容 */
const demoContents: Record<string, { content: string; content_type: string; type: string }> = {
  "demo-c1": {
    type: "document",
    content_type: "markdown",
    content: `# 特征值与特征向量核心讲义

## 1. 基本定义

设 $A$ 是 $n$ 阶方阵，如果存在非零向量 $x$ 和标量 $\lambda$，使得

$$Ax = \lambda x$$

则称 $\lambda$ 为矩阵 $A$ 的**特征值**，$x$ 为对应的**特征向量**。

## 2. 重要性质

1. **特征值之和**等于矩阵的迹：$\sum \lambda_i = \text{tr}(A)$
2. **特征值之积**等于矩阵的行列式：$\prod \lambda_i = \det(A)$
3. 若 $\lambda$ 是 $A$ 的特征值，则 $\lambda^k$ 是 $A^k$ 的特征值

## 3. 计算方法

### 步骤
1. 构造特征方程 $\det(A - \lambda I) = 0$
2. 求解多项式方程得到所有特征值
3. 对每个特征值 $\lambda_i$，解齐次方程组 $(A - \lambda_i I)x = 0$ 得到特征向量

### 例题
> 求矩阵 $A = \begin{pmatrix} 2 & 1 \\ 1 & 2 \end{pmatrix}$ 的特征值和特征向量。

**解**：

特征方程为 $\det(A - \lambda I) = (2-\lambda)^2 - 1 = 0$

解得 $\lambda_1 = 3, \lambda_2 = 1$

- 对 $\lambda_1 = 3$：$(A-3I)x = 0$，得特征向量 $x_1 = (1, 1)^T$
- 对 $\lambda_2 = 1$：$(A-I)x = 0$，得特征向量 $x_2 = (1, -1)^T$`,
  },
  "demo-c2": {
    type: "video",
    content_type: "markdown",
    content: `# 线性代数例题精讲视频

## 视频信息
- **时长**：45 分钟
- **难度**：中等
- **适用**：理工科本科生

## 内容概要

本视频精选线性代数高频考点例题，逐题讲解解题思路与技巧。

### 涵盖知识点
1. 矩阵运算与性质
2. 行列式计算
3. 特征值与特征向量
4. 线性方程组求解
5. 向量空间与线性变换

## 观看建议

> 建议先复习相关理论，再观看视频讲解效果更佳。`,
  },
  "demo-c3": {
    type: "quiz",
    content_type: "markdown",
    content: `# 精选习题集（含解析）

## 第一章 矩阵与行列式

### 第1题
设 $A$ 为 3 阶方阵，$\det(A) = 2$，求 $\det(2A)$。

**答案**：$16$

**解析**：$\det(kA) = k^n \det(A)$，其中 $n$ 为矩阵阶数。故 $\det(2A) = 2^3 \times 2 = 16$。

### 第2题
设 $A = \begin{pmatrix} 1 & 2 \\ 3 & 4 \end{pmatrix}$，求 $A^{-1}$。

**答案**：$A^{-1} = \begin{pmatrix} -2 & 1 \\ 1.5 & -0.5 \end{pmatrix}$

**解析**：$\det(A) = 4 - 6 = -2$，$A^{-1} = \frac{1}{\det(A)} \begin{pmatrix} 4 & -2 \\ -3 & 1 \end{pmatrix}$

## 第二章 特征值理论

### 第3题
证明：若 $\lambda$ 是 $A$ 的特征值，则 $\lambda^2$ 是 $A^2$ 的特征值。

**证明**：设 $x$ 为 $\lambda$ 对应的特征向量，则 $Ax = \lambda x$。于是 $A^2 x = A(Ax) = A(\lambda x) = \lambda(Ax) = \lambda^2 x$。`,
  },
  "demo-c4": {
    type: "mindmap",
    content_type: "markdown",
    content: `# 知识图谱：矩阵与对角化

## 核心概念

- **矩阵对角化**
  - 定义：$A = P\Lambda P^{-1}$
  - 条件：$A$ 有 $n$ 个线性无关的特征向量
  - 方法：求特征值和特征向量

- **特征值**
  - 计算方法：$\det(A - \lambda I) = 0$
  - 性质
    - 和 = 迹
    - 积 = 行列式
    - $A^k$ 的特征值 = $\lambda^k$

- **特征向量**
  - 求法：$(A - \lambda I)x = 0$
  - 线性无关性
  - 正交性（对称矩阵）

- **应用**
  - 矩阵幂运算
  - 微分方程求解
  - 主成分分析（PCA）`,
  },
  "demo-c5": {
    type: "document",
    content_type: "markdown",
    content: `# 期末复习速记卡

## 线性代数核心公式

| 公式 | 说明 |
|------|------|
| $Ax = \lambda x$ | 特征值定义 |
| $\det(A - \lambda I) = 0$ | 特征方程 |
| $A = P\Lambda P^{-1}$ | 对角化 |
| $\sum \lambda_i = \text{tr}(A)$ | 特征值之和 |
| $\prod \lambda_i = \det(A)$ | 特征值之积 |

## 重要结论

1. **可对角化条件**：$n$ 阶方阵有 $n$ 个线性无关的特征向量
2. **对称矩阵**：特征值均为实数，不同特征值对应的特征向量正交
3. **正交矩阵**：$Q^T Q = I$，特征值的模为 1`,
  },
  "demo-c6": {
    type: "ppt",
    content_type: "markdown",
    content: `# 课堂PPT：线性变换基础

## 第一页：线性变换定义

设 $T: V \to W$ 是向量空间之间的映射，若满足：
1. $T(u + v) = T(u) + T(v)$
2. $T(cu) = cT(u)$

则称 $T$ 为**线性变换**。

## 第二页：矩阵表示

线性变换 $T$ 可以用矩阵表示：$T(x) = Ax$

其中 $A$ 称为变换的**标准矩阵**。

## 第三页：重要性质

- 线性变换保持加法和数乘
- 核空间 $\ker(T)$ 是 $V$ 的子空间
- 像空间 $\text{im}(T)$ 是 $W$ 的子空间
- 维数定理：$\dim(V) = \dim(\ker(T)) + \dim(\text{im}(T))$`,
  },
};

/* 真实 artifact 列表 */
const realArtifacts = ref<ArtifactInfo[]>([]);

/** 判断资源记录是否为群聊对话过程中生成（应归入「聊天存档」而非「学习资源」）。
 * 新数据看 metadata.source === "chat"；旧数据用启发式：
 * Agent 生成 + 无正文 + 非教师建设的资源，即聊天回合落库的产物元数据。 */
function isChatGeneratedResource(r: Resource): boolean {
  const meta = (r.metadata || {}) as Record<string, any>;
  if (meta.source === "chat") return true;
  if (meta.created_by) return false; // 教师建设的课程资源
  return !r.content && !!r.agent_name && r.agent_name !== "teacher" && r.agent_name !== "系统";
}

/* 合并后的卡片列表：resources + artifacts + fallback */
const cards = computed<CardItem[]>(() => {
  // 1. Resources from /resources/list（文档/题库等，content 可直接预览）
  const filteredResources = apiResources.value.filter((resource) => {
    const resourceCourse = String(resource.metadata?.course || "").trim();
    // 历史资源没有写入 course 元数据时也应可见；只有明确标记了课程的
    // 资源才做课程隔离。否则接口明明返回了数据，页面却会被前端筛成空白。
    return !resourceCourse || resourceCourse === course.value;
  });
  const resCards: CardItem[] = filteredResources.map((r, i) => {
    const type = String(r.type || "document");
    const kind = resourceTypeToKind(type);
    const ts = r.created_at ? new Date(r.created_at * 1000) : new Date();
    const dateStr = `${String(ts.getMonth() + 1).padStart(2, "0")}-${String(ts.getDate()).padStart(2, "0")}`;
    const meta = (r.metadata || {}) as Record<string, any>;
    // 只有后端明确写入画像证据时才标记“个性化”。Agent 名称本身不能证明
    // 读取过用户画像，否则离线模板或无 user_id 的生成会被误标为个性化。
    const personalized = meta.personalized === true
      || meta.personalization_applied === true
      || Boolean(meta.profile_hint);
    return {
      id: `res-${i}`,
      rid: generatedArtifactId(r.metadata),
      resourceId: r.id,
      resourceType: type,
      kind,
      badgeText: resourceBadge(type),
      title: localizeResourceText(r.title, "未命名资源"),
      desc: localizeResourceText((r.content || "").slice(0, 100) || (meta.attachment
        ? `教师上传文件：${String(meta.attachment.filename || r.title)}`
        : String(meta.summary || `资源类型：${resourceTypeLabel(type)}`)), "暂无资源说明"),
      author: meta.created_by ? "课程教师" : resourceAgentLabel(r.agent_name),
      date: dateStr,
      views: "—",
      tags: localizeResourceTags(meta.attachment
        ? ["教师发布", ...((r.tags && r.tags.length) ? r.tags : [type])]
        : ((r.tags && r.tags.length) ? r.tags : [type])),
      attachment: meta.attachment,
      fromChat: isChatGeneratedResource(r),
      personalized,
      personalizedHint: String(meta.profile_hint || ""),
    };
  });

  // 2. Artifacts from /artifacts/list（PPT/图片/音频/视频等）
  const filteredArtifacts = realArtifacts.value.filter((artifact) => {
    const artifactCourse = String(artifact.metadata?.course || "").trim();
    // 历史生成资源没有 course 元数据时仍应可见；有明确课程时才做隔离。
    const courseMatches = !artifactCourse || artifactCourse === course.value;
    // 已失效的临时文件不进入卡片区。后端仍保留元数据供诊断，但一个坏记录
    // 不应让学生点到 404，更不能影响其它资源渲染。
    return courseMatches && artifact.exists !== false && artifact.download_ready !== false;
  });
  const real: CardItem[] = filteredArtifacts.map((a, i) => {
    const type = String(a.type || "file");
    const kind = artifactTypeToKind(type);
    const rid = String(a.id || a.resource_id || "");
    const artifactMeta = (a.metadata || {}) as Record<string, any>;
    const contentSource = String(artifactMeta.content_source || "").toLowerCase();
    const outlineSource = String(artifactMeta.outline_source || "").toLowerCase();
    const providerTag = contentSource === "kimi"
      ? (outlineSource === "deepseek" ? "DeepSeek 大纲 + Kimi K2.6" : "Kimi K2.6")
      : contentSource === "template_fallback" ? "本地模板兜底" : "";
    const templateName = String(artifactMeta.template_name || "");
    const templateTag = templateName && templateName !== "built-in-editorial"
      ? `模板：${templateName}` : "";
    const providerDesc = providerTag ? `由 ${providerTag} 生成 · ` : "";
    const personalized = artifactMeta.personalized === true
      || artifactMeta.personalization_applied === true
      || Boolean(artifactMeta.profile_hint);
    const ts = a.created_at ? new Date(a.created_at * 1000) : new Date();
    const dateStr = `${String(ts.getMonth() + 1).padStart(2, "0")}-${String(ts.getDate()).padStart(2, "0")}`;
    return {
      id: `art-${i}`,
      rid,
      kind,
      badgeText: artifactBadge(type),
      title: localizeResourceText(a.metadata?.title || a.metadata?.topic || `${resourceTypeLabel(type)} ${rid.slice(-6)}`, "未命名资源"),
      desc: localizeResourceText(a.metadata?.summary || a.metadata?.description || `${providerDesc}资源类型：${resourceTypeLabel(type)}`, "暂无资源说明"),
      author: resourceAgentLabel(a.metadata?.agent || a.metadata?.agent_name || "AI"),
      date: dateStr,
      views: "—",
      tags: localizeResourceTags([type, providerTag, templateTag].filter(Boolean)),
      artifactType: type,
      filepath: a.filepath,
      session_id: a.session_id,
      fromChat: String(a.metadata?.source || "").toLowerCase() === "chat",
      personalized,
      personalizedHint: String(artifactMeta.profile_hint || ""),
    };
  });
  return [...resCards, ...real];
});

const learningCards = computed(() => cards.value.filter((card) => !card.fromChat));

function artifactTypeToKind(type: string): ResKind {
  const t = type.toLowerCase();
  if (t.includes("ppt")) return "ppt";
  if (t.includes("mp3") || t.includes("tts") || t.includes("audio")) return "mp3";
  if (t.includes("manim") || t.includes("video")) return "manim";
  if (t.includes("mermaid") || t.includes("mind") || t.includes("graph")) return "mind";
  if (t.includes("png") || t.includes("image")) return "pdf";
  if (t.includes("code")) return "note";
  return "note";
}

function artifactBadge(type: string): string {
  const t = type.toLowerCase();
  if (t.includes("ppt")) return "PPT";
  if (t.includes("mp3") || t.includes("tts")) return "MP3";
  if (t.includes("manim")) return "MP4";
  if (t.includes("mermaid")) return "◉";
  if (t.includes("png")) return "IMG";
  if (t.includes("code")) return "{";
  return "≡";
}

function resourceTypeToKind(type: string): ResKind {
  const t = type.toLowerCase();
  if (t.includes("video") || t.includes("manim") || t.includes("mp4")) return "video";
  if (t.includes("audio") || t.includes("tts") || t.includes("mp3")) return "mp3";
  if (t.includes("ppt")) return "ppt";
  if (t.includes("quiz")) return "quiz";
  if (t.includes("mindmap") || t.includes("mind") || t.includes("graph")) return "mind";
  if (t.includes("code")) return "note";
  if (t.includes("document") || t.includes("doc") || t.includes("reading")) return "pdf";
  return "note";
}

function resourceBadge(type: string): string {
  const t = type.toLowerCase();
  if (t.includes("video") || t.includes("manim") || t.includes("mp4")) return "▶";
  if (t.includes("audio") || t.includes("tts") || t.includes("mp3")) return "♫";
  if (t.includes("prompt")) return "✦";
  if (t.includes("ppt")) return "PPT";
  if (t.includes("quiz")) return "✓";
  if (t.includes("mindmap") || t.includes("mind")) return "◉";
  if (t.includes("code")) return "{ }";
  if (t.includes("document") || t.includes("doc") || t.includes("reading")) return "MD";
  return "≡";
}

function isVideoResourceType(type: unknown): boolean {
  const value = String(type || "").toLowerCase();
  return ["video", "manim", "mp4"].some((token) => value.includes(token));
}

function isAudioResourceType(type: unknown): boolean {
  const value = String(type || "").toLowerCase();
  return ["audio", "tts", "mp3"].some((token) => value.includes(token));
}

function generatedArtifactId(metadata: unknown): string {
  const meta = (metadata || {}) as Record<string, any>;
  const downloads = Array.isArray(meta.downloads) ? meta.downloads : [];
  const downloadable = downloads?.find((item: any) =>
    item && item.exists !== false && String(item.id || "").trim(),
  );
  return String(downloadable?.id || "");
}

/* -------------------- 下载 / 预览 -------------------- */
function safeDownloadName(card: CardItem, info?: ArtifactInfo): string {
  const path = String(info?.filepath || card.filepath || "");
  const pathName = path.split(/[\\/]/).pop() || "";
  if (pathName && pathName.includes(".")) return pathName;

  const type = String(info?.type || card.artifactType || card.resourceType || "").toLowerCase();
  const ext = type.includes("ppt") ? ".pptx"
    : type.includes("video") || type.includes("manim") ? ".mp4"
      : type.includes("audio") || type.includes("mp3") || type.includes("tts") ? ".mp3"
        : type.includes("mermaid") || type.includes("png") || type.includes("image") ? ".png"
          : type.includes("code") ? ".py"
            : ".txt";
  const stem = (card.title || "learning-resource")
    .replace(/[<>:"/\\|?*\u0000-\u001f]/g, "_")
    .slice(0, 80);
  return `${stem || "learning-resource"}${ext}`;
}

function triggerDownload(url: string, filename: string) {
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.rel = "noopener noreferrer";
  a.style.display = "none";
  document.body.appendChild(a);
  a.click();
  a.remove();
}

function triggerBlobDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  triggerDownload(url, filename);
  // 浏览器可能在 click 返回后才开始读取 Blob。立即 revoke 会造成偶发的
  // 0 字节文件或页面崩溃，因此给下载任务留出稳定的接管时间。
  window.setTimeout(() => URL.revokeObjectURL(url), 30_000);
}

async function handleDownload(card: CardItem) {
  // Artifact 类型：先验证 registry，再触发浏览器下载。禁止 window.open，
  // 避免 MP4/PPT 被新标签页尝试解析后占用大量内存或替换当前资源页。
  if (card.rid) {
    try {
      const info = await getArtifactInfo(card.rid);
      if (info.exists === false || info.download_ready === false) {
        throw new Error("artifact_not_ready");
      }
      triggerDownload(
        getArtifactDownloadFullUrl(card.rid),
        safeDownloadName(card, info),
      );
      showToast(`已开始下载 ${safeDownloadName(card, info)}`);
    } catch {
      showToast("该文件已失效或尚未生成完成，其他资源仍可正常使用");
    }
    return;
  }
  // Resource 类型：从 content 生成文件下载
  if (card.resourceId) {
    if (card.attachment) {
      try {
        const blob = await downloadResourceAttachment(card.resourceId, userId.value);
        const filename = card.attachment.filename || card.title || "course-resource";
        triggerBlobDownload(blob, filename);
        showToast(`已开始下载 ${filename}`);
      } catch {
        showToast("资料下载失败，请稍后重试");
      }
      return;
    }
    const resource = apiResources.value?.find(r => r.id === card.resourceId);
    const demo = demoContents[card.resourceId];
    if (isVideoResourceType(resource?.type || card.resourceType) || isAudioResourceType(resource?.type || card.resourceType)) {
      showToast("媒体文件尚未生成完成，请重新生成后再下载");
      return;
    }
    const content = resource?.content || demo?.content || "";
    if (!content) return;
    const ext = resource?.content_type === "markdown" || demo?.content_type === "markdown" ? ".md" : ".txt";
    const filename = (card.title || "resource").replace(/[^\w\u4e00-\u9fa5\-]/g, "_") + ext;
    const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
    triggerBlobDownload(blob, filename);
    showToast(`已开始下载: ${filename}`);
    return;
  }
}

const previewOpen = ref(false);
const previewCard = ref<CardItem | null>(null);
const previewDataUri = ref("");
const previewLoading = ref(false);
const previewType = ref<"image" | "audio" | "video" | "text" | "pptx" | "unsupported">("image");
const previewUrl = ref("");       // 音频/视频/图片直链
const previewText = ref("");        // 文本/代码内容
const previewIsMarkdown = ref(false); // 是否为 Markdown 文档（需要渲染为 HTML）
const previewInfo = ref<ArtifactInfo | null>(null); // artifact 元数据
const previewBlobUrl = ref("");

async function handleView(card: CardItem) {
  trackVisit(card);

  // 处理聊天存档问答卡片：完整展示提问与回答（Markdown 渲染）
  if (card.artifactType === "chat") {
    const recId = Number(String(card.id).replace("chat-", ""));
    const idx = chatArchiveRecords.value.findIndex((r) => r.id === recId);
    const question = idx >= 0 ? chatArchiveRecords.value[idx] : null;
    const answer = idx >= 0 ? chatArchiveRecords.value[idx + 1] : null;
    previewCard.value = card;
    previewOpen.value = true;
    previewLoading.value = false;
    previewType.value = "text";
    previewIsMarkdown.value = true;
    previewText.value = question
      ? `### 🙋 我的提问\n\n${localizeResourceText(question.content, "问题待补充")}\n\n---\n\n### 🤖 ${resourceAgentLabel(answer?.agent_name || "AI")} 的回答\n\n${localizeResourceText(answer?.content, "（暂无回复）")}`
      : `### 聊天记录\n\n${card.title}\n\n${card.desc}`;
    previewUrl.value = "";
    previewDataUri.value = "";
    previewInfo.value = null;
    return;
  }

  // 处理 Resource 类型（来自 /resources/list 或 demo 卡片，content 可直接预览）
  if (card.resourceId) {
    const resource = apiResources.value?.find(r => r.id === card.resourceId);
    const demo = demoContents[card.resourceId];
    if (resource || demo) {
      const mediaType = String(card.attachment?.media_type || "").toLowerCase();
      const resourceType = String(resource?.type || demo?.type || card.resourceType || "");
      const isTeacherVideo = mediaType.startsWith("video/") || isVideoResourceType(resourceType);
      if (resource && card.attachment && isTeacherVideo) {
        previewCard.value = card;
        previewOpen.value = true;
        previewLoading.value = true;
        previewType.value = "video";
        previewText.value = "";
        previewIsMarkdown.value = false;
        try {
          const blob = await downloadResourceAttachment(card.resourceId, userId.value);
          if (previewBlobUrl.value) URL.revokeObjectURL(previewBlobUrl.value);
          previewBlobUrl.value = URL.createObjectURL(blob);
          previewUrl.value = previewBlobUrl.value;
        } catch {
          previewUrl.value = "";
          showToast("课程视频加载失败，请稍后重试");
        } finally {
          previewLoading.value = false;
        }
        return;
      }
      if (isVideoResourceType(resourceType) || isAudioResourceType(resourceType)) {
        const artifactId = generatedArtifactId(resource?.metadata);
        previewCard.value = card;
        previewOpen.value = true;
        previewLoading.value = false;
        previewType.value = isVideoResourceType(resourceType) ? "video" : "audio";
        previewText.value = "";
        previewIsMarkdown.value = false;
        previewUrl.value = artifactId ? getArtifactDownloadFullUrl(artifactId) : "";
        previewDataUri.value = "";
        previewInfo.value = null;
        if (!artifactId) {
          showToast(isVideoResourceType(resourceType)
            ? "这条记录没有可播放的 MP4，请重新生成视频"
            : "这条记录没有可播放的音频，请重新生成语音");
        }
        return;
      }
      const content = resource?.content || demo?.content || "";
      const contentType = resource?.content_type || demo?.content_type || "markdown";
      const resType = resource?.type || demo?.type || "document";
      previewCard.value = card;
      previewOpen.value = true;
      previewLoading.value = false;
      previewType.value = "text";
      previewIsMarkdown.value = true;
      // 聊天回合落库的资源元数据没有正文：给出生成信息摘要而非「内容为空」
      previewText.value = content || buildResourceMetaPreview(resource, card);
      if (content) {
        previewIsMarkdown.value = contentType === "markdown" ||
                                   resType === "document" ||
                                   resType === "reading" ||
                                   (card.title || "").endsWith('.md');
      }
      previewUrl.value = "";
      previewDataUri.value = "";
      previewInfo.value = null;
      return;
    }
  }

  if (!card.rid) return;
  const type = (card.artifactType || "").toLowerCase();

  previewCard.value = card;
  previewOpen.value = true;
  previewLoading.value = true;
  previewDataUri.value = "";
  previewUrl.value = "";
  previewText.value = "";
  previewIsMarkdown.value = false;
  previewInfo.value = null;

  const t = type.toLowerCase();

  // ---- 图片类 (png / mermaid / mermaid_png / qr / svg / image) ----
  if (t.includes("png") || t.includes("mermaid") || t.includes("image") || t.includes("qr") || t.includes("svg")) {
    previewType.value = "image";
    // 思维导图直接显示为图片
    if (t.includes("mermaid")) {
      previewUrl.value = getArtifactDownloadFullUrl(card.rid);
    } else {
      try {
        const resp = await fetch(artifactDataUriUrl(card.rid));
        if (resp.ok) {
          const data = await resp.json();
          previewDataUri.value = data.data_uri || "";
        }
      } catch {
        previewDataUri.value = "";
      }
      // data-uri 失败时降级为直链
      if (!previewDataUri.value) {
        previewUrl.value = artifactDownloadUrl(card.rid, "png");
      }
    }
  }
  // ---- 音频类 (mp3 / tts / audio) ----
  else if (t.includes("mp3") || t.includes("tts") || t.includes("audio")) {
    previewType.value = "audio";
    previewUrl.value = getArtifactDownloadFullUrl(card.rid);
  }
  // ---- 视频类 (manim / video / mp4) ----
  else if (t.includes("manim") || t.includes("video") || t.includes("mp4")) {
    previewType.value = "video";
    // manim 类型使用通用下载端点，让后端根据实际文件类型返回
    previewUrl.value = getArtifactDownloadFullUrl(card.rid);
  }
  // ---- 文本/代码类 (code / md / json / txt / py / notebook / document / quiz / quiz_bank) ----
  else if (
    t.includes("code") || t.includes("md") || t.includes("json") ||
    t.includes("txt") || t.includes("py") || t.includes("notebook") ||
    t.includes("document") || t.includes("quiz") || t.includes("markdown")
  ) {
    previewType.value = "text";
    // Markdown 文件或文档类型需要渲染为 HTML
    previewIsMarkdown.value = t.includes("document") || t.includes("md") ||
                               t.includes("markdown") || card.title?.endsWith('.md');
    try {
      const resp = await fetch(getArtifactDownloadFullUrl(card.rid));
      if (resp.ok) {
        previewText.value = await resp.text();
        // 如果是 JSON，尝试格式化
        if (t.includes("json") || (t.includes("quiz") && previewText.value.trim().startsWith('['))) {
          previewIsMarkdown.value = false;
          try {
            previewText.value = JSON.stringify(JSON.parse(previewText.value), null, 2);
          } catch { /* 非 JSON 就原样展示 */ }
        }
      } else {
        previewText.value = "无法加载文件内容。";
      }
    } catch {
      previewText.value = "加载文件内容失败，请尝试下载。";
    }
  }
  // ---- PPT 课件类 ----
  else if (t.includes("ppt")) {
    previewType.value = "pptx";
    try {
      previewInfo.value = await getArtifactInfo(card.rid);
    } catch {
      previewInfo.value = null;
    }
  }
  // ---- 其他类型 ----
  else {
    previewType.value = "unsupported";
    try {
      previewInfo.value = await getArtifactInfo(card.rid);
    } catch {
      previewInfo.value = null;
    }
  }

  previewLoading.value = false;
}

/** 无正文资源（聊天回合落库的元数据记录）的预览兜底：展示生成信息 */
function buildResourceMetaPreview(resource: Resource | undefined, card: CardItem): string {
  const meta = (resource?.metadata || {}) as Record<string, any>;
  if (meta.attachment) {
    const attachment = meta.attachment as { filename?: string; size_bytes?: number };
    const size = attachment.size_bytes ? `（${Math.ceil(Number(attachment.size_bytes) / 1024)} KB）` : "";
    return [
      `### ${card.title}`,
      "",
      `教师已发布课程资料：**${attachment.filename || card.title}**${size}`,
      "",
      "> 此文件需要下载后在本地打开。请点击资源卡片的“下载”按钮获取原始资料。",
    ].join("\n");
  }
  const lines = [
    `### ${card.title}`,
    "",
    `- **类型**：${resourceTypeLabel(resource?.type || card.resourceType || "document")}`,
    `- **生成者**：${resourceAgentLabel(resource?.agent_name || card.author)}（群聊协作生成）`,
    meta.summary ? `- **摘要**：${String(meta.summary).slice(0, 200)}` : "",
    meta.kp_id ? `- **关联知识点**：${meta.kp_id}` : "",
    "",
    "> 这条记录是群聊对话中 Agent 生成资源的存档。完整内容请在「群聊协作」页的",
    "> 文件面板中查看，或重新在群聊中让 Agent 生成。",
  ].filter((l) => l !== "");
  return lines.join("\n");
}

function closePreview() {
  previewOpen.value = false;
  previewCard.value = null;
  previewDataUri.value = "";
  if (previewBlobUrl.value) URL.revokeObjectURL(previewBlobUrl.value);
  previewBlobUrl.value = "";
  previewUrl.value = "";
  previewText.value = "";
  previewIsMarkdown.value = false;
  previewInfo.value = null;
}

function useTeacherPrompt(card: CardItem) {
  const resource = card.resourceId ? apiResources.value?.find((item) => item.id === card.resourceId) : undefined;
  const prompt = String(resource?.content || "").trim();
  if (!prompt) {
    showToast("这条学习提示还没有正文");
    return;
  }
  closePreview();
  void router.push({ path: "/chat", query: { compose: "1", prompt } });
}

/* -------------------- Markdown 渲染 -------------------- */
// renderMarkdown 由 @/utils/markdown 导入（支持代码块保护、表格、图片等）

const previewHtml = computed(() => {
  if (!previewIsMarkdown.value) return "";
  return renderMarkdown(previewText.value);
});

/* -------------------- 概览（动态） -------------------- */
const overview = ref([
  { key: "total",     label: "全部资源", value: "0", color: "blue",   icon: FileText },
  { key: "today",     label: "今日更新", value: "0", color: "green",  icon: TrendingUp },
  { key: "favorites", label: "我的收藏", value: "0", color: "orange", icon: Star },
  { key: "downloads", label: "资源类型", value: "0", color: "purple", icon: Cloud },
]);

/* -------------------- 分类（动态） -------------------- */
interface Category {
  name: string;
  count: number;
  total: number;
  color: string;
}
const categories = ref<Category[]>([]);

/* -------------------- 最近访问（动态追踪） -------------------- */
interface RecentVisit {
  icon: string;
  kind: "pdf" | "video" | "mind";
  title: string;
  time: string;
}
const recent = ref<RecentVisit[]>([]);

function trackVisit(card: CardItem) {
  const kind: "pdf" | "video" | "mind" =
    card.kind === "video" || card.kind === "manim" || card.kind === "mp3" ? "video" :
    card.kind === "mind" ? "mind" : "pdf";
  const now = new Date();
  const time = `${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")} ${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
  const visit: RecentVisit = { icon: card.badgeText, kind, title: card.title, time };
  recent.value = [visit, ...recent.value.filter(v => v.title !== visit.title)].slice(0, 5);
}

/* -------------------- AI 推荐（BKT + 知识图谱精准推送） -------------------- */
const aiRecommendations = ref<RecommendationItem[]>([]);
const aiRecommendLoading = ref(false);

/* -------------------- 本周推荐（动态） -------------------- */
const weekly = ref<Array<{ rank: number; title: string; views: string }>>([]);

/* -------------------- 类型筛选 + 分页 -------------------- */
const filteredCards = computed(() => {
  // 聊天存档模式：直接使用聊天记录卡片
  if (sourceFilter.value === "chat") {
    let list = chatArchiveCards.value;
    if (activeTab.value !== "all") {
      list = list.filter((card) => cardMatchesCategory(card, activeTab.value));
    }
    if (keyword.value.trim()) {
      const kw = keyword.value.trim().toLowerCase();
      list = list.filter(c =>
        c.title?.toLowerCase().includes(kw) ||
        c.desc?.toLowerCase().includes(kw) ||
        c.tags?.some(t => t.toLowerCase().includes(kw))
      );
    }
    return list;
  }

  // 学习资源模式：排除聊天对话过程中生成的资源（归入聊天存档）
  let list = cards.value;
  if (sourceFilter.value === "learning") {
    list = learningCards.value;
  }
  // 「我的收藏」概览卡开启的收藏筛选
  if (favOnlyFilter.value) {
    list = list.filter(c => favoritedIds.value.has(c.id));
  }
  if (activeTab.value !== "all") {
    list = list.filter((card) => cardMatchesCategory(card, activeTab.value));
  }
  if (keyword.value.trim()) {
    const kw = keyword.value.trim().toLowerCase();
    list = list.filter(c =>
      c.title?.toLowerCase().includes(kw) ||
      c.desc?.toLowerCase().includes(kw) ||
      c.tags?.some(t => t.toLowerCase().includes(kw))
    );
  }
  return list;
});

const page = ref(1);
const pageSize = ref(12);
const totalPages = computed(() => Math.max(1, Math.ceil(filteredCards.value.length / pageSize.value)));
const pagedCards = computed(() => {
  const start = (page.value - 1) * pageSize.value;
  return filteredCards.value.slice(start, start + pageSize.value);
});
const visiblePages = computed(() => {
  const total = totalPages.value;
  const cur = page.value;
  const pages: number[] = [];
  if (total <= 7) {
    for (let i = 1; i <= total; i++) pages.push(i);
  } else {
    pages.push(1);
    if (cur > 4) pages.push(-1); // 省略号
    const start = Math.max(2, cur - 1);
    const end = Math.min(total - 1, cur + 1);
    for (let i = start; i <= end; i++) pages.push(i);
    if (cur < total - 3) pages.push(-1); // 省略号
    pages.push(total);
  }
  return pages;
});

function changePage(p: number) {
  if (p < 1 || p > totalPages.value) return;
  page.value = p;
}

/* -------------------- 加载 / 错误 -------------------- */
const loading = ref(false);
const error = ref<string>("");
const apiResources = ref<Resource[]>([]);
const RESOURCE_CACHE_PREFIX = "a3-resource-library:";
let refreshSequence = 0;

function resourceCacheKey(courseName = course.value) {
  return `${RESOURCE_CACHE_PREFIX}${userId.value || "anonymous"}:${courseName || "all"}`;
}

function restoreCachedResources() {
  try {
    const raw = localStorage.getItem(resourceCacheKey());
    if (!raw) return;
    const cached = asRecord(JSON.parse(raw));
    if (!cached) return;
    apiResources.value = normalizeResourceRows(cached.resources);
    realArtifacts.value = normalizeArtifactRows(cached.artifacts);
  } catch {
    // 缓存损坏时静默丢弃，不能阻塞真正的接口刷新。
  }
}

function cacheResources() {
  if (!apiResources.value.length && !realArtifacts.value.length) return;
  try {
    localStorage.setItem(resourceCacheKey(), JSON.stringify({
      resources: apiResources.value,
      artifacts: realArtifacts.value,
    }));
  } catch {
    // 配额不足或隐私模式不支持时仍保持在线接口可用。
  }
}

async function refresh() {
  const sequence = ++refreshSequence;
  const requestedCourse = course.value;
  loading.value = true;
  error.value = "";
  try {
    // 同时拉取 resources 和 artifacts
    const [resp, artResp] = await Promise.allSettled([
      listResources({ user_id: userId.value, course: requestedCourse, limit: 50 }),
      listArtifacts({ limit: 100 }),
    ]);
    // 首次进入和切换课程可能同时触发请求；只接受最后一次请求的结果，
    // 防止较慢的旧响应覆盖新课程数据，造成偶发整页空白。
    if (sequence !== refreshSequence) return;
    if (resp.status === "fulfilled") {
      apiResources.value = normalizeResourceRows(resp.value?.resources);
    }
    if (artResp.status === "fulfilled") {
      realArtifacts.value = normalizeArtifactRows(artResp.value?.artifacts);
    }
    if (resp.status === "fulfilled" || artResp.status === "fulfilled") cacheResources();
    if (resp.status === "rejected" && artResp.status === "rejected") {
      error.value = "资源服务暂时不可用，已保留当前页面中的资源；请稍后刷新。";
    } else if (resp.status === "rejected" || artResp.status === "rejected") {
      error.value = "部分资源暂未同步，当前可用资源不受影响。";
    }
    // 更新动态数据
    updateOverview();
    updateCategories();
    updateWeekly();
    updateTypeTabCounts();
  } catch (e: any) {
    if (sequence !== refreshSequence) return;
    error.value = e?.detail || e?.message || "加载失败";
  } finally {
    if (sequence === refreshSequence) loading.value = false;
  }
}
const route = useRoute();
const keyword = ref<string>("");
const kpFilterId = ref<string>("");
const kpFilterName = ref<string>("");

// 切换 tab / 搜索 / 排序时自动回到第 1 页
watch([activeTab, keyword, sortKey, viewMode, sourceFilter], () => { page.value = 1; });
watch(totalPages, (total) => {
  // 筛选条件变化后总页数可能减少，旧页码若越界会得到空切片。
  page.value = Math.min(Math.max(page.value, 1), total);
});
// 切换来源时更新 tab 计数
watch(sourceFilter, () => {
  updateTypeTabCounts();
  // 切到聊天存档时加载数据
  if (sourceFilter.value === "chat") {
    loadChatArchive();
  }
});

/* -------------------- 动态更新函数 -------------------- */
function updateOverview() {
  const now = new Date();
  const todayStr = `${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
  const todayCount = learningCards.value.filter(c => c.date === todayStr).length;
  const typeSet = new Set(learningCards.value.map(c => c.artifactType || c.resourceType || "").filter(Boolean));
  overview.value = [
    { key: "total",     label: "全部资源", value: String(learningCards.value.length), color: "blue",   icon: FileText },
    { key: "today",     label: "今日更新", value: String(todayCount),         color: "green",  icon: TrendingUp },
    { key: "favorites", label: "我的收藏", value: String(favoritedIds.value.size), color: "orange", icon: Star },
    { key: "downloads", label: "资源类型", value: String(typeSet.size),       color: "purple", icon: Cloud },
  ];
}

const categoriesAll = ref<Category[]>([]);

function updateCategories() {
  const typeCounts: Record<string, number> = {};
  for (const c of learningCards.value) {
    const type = c.artifactType || c.resourceType || "其他";
    typeCounts[type] = (typeCounts[type] || 0) + 1;
  }
  const total = learningCards.value.length || 1;
  const colors = ["#ea5a1a", "#d89229", "#c8480f", "#9a3608", "#b3413a", "#4a6b85"];
  categoriesAll.value = Object.entries(typeCounts)
    .map(([name, count], i) => ({ name, count, total, color: colors[i % colors.length] }))
    .sort((a, b) => b.count - a.count);
  categories.value = categoriesAll.value.slice(0, 6);
}

function updateWeekly() {
  weekly.value = learningCards.value
    .slice(0, 5)
    .map((c, i) => ({ rank: i + 1, title: c.title, views: c.views }));
}

async function loadRecommendations() {
  aiRecommendLoading.value = true;
  try {
    const resp = await getRecommendations(userId.value, 4, course.value);
    aiRecommendations.value = resp.items || [];
  } catch {
    // 后端未连接时静默失败
  } finally {
    aiRecommendLoading.value = false;
  }
}

function findCardByResourceId(resourceId: string): CardItem | undefined {
  return cards.value?.find(c => c.resourceId === resourceId);
}

/* -------------------- 侧栏模块点击行为 -------------------- */
/** 资源概览卡片：点击直接应用对应筛选 */
function handleOverviewClick(key: string) {
  favOnlyFilter.value = false;
  if (key === "total") {
    sourceFilter.value = "learning";
    activeTab.value = "all";
    keyword.value = "";
    showToast("已展示全部学习资源");
  } else if (key === "today") {
    sortKey.value = "latest";
    activeTab.value = "all";
    showToast("已按最新上传排序");
  } else if (key === "favorites") {
    favOnlyFilter.value = true;
    activeTab.value = "all";
    showToast(favoritedIds.value.size ? "只看我的收藏" : "还没有收藏，点卡片上的星标即可收藏");
  } else if (key === "downloads") {
    document.querySelector(".cat-list")?.scrollIntoView({ behavior: "smooth", block: "center" });
    showToast("资源类型分布见「资源分类」");
  }
  page.value = 1;
}

/** 资源分类：点击直接按该类型筛选主列表 */
function handleCategoryClick(c: Category) {
  const typeMap: Record<string, string[]> = {
    doc: ["document", "prompt", "md", "reading", "txt"],
    video: ["manim", "video", "mp4", "mp3", "tts", "audio"],
    quiz: ["quiz"],
    ppt: ["ppt"],
    kg: ["mermaid", "mindmap", "mind", "graph"],
  };
  const lower = c.name.toLowerCase();
  const hitTab = Object.entries(typeMap)?.find(([, types]) =>
    types.some((t) => lower.includes(t)),
  );
  favOnlyFilter.value = false;
  if (hitTab) {
    activeTab.value = hitTab[0];
    keyword.value = "";
  } else {
    activeTab.value = "all";
    keyword.value = c.name;
  }
  page.value = 1;
  showToast(`已筛选：${resourceTypeLabel(c.name)}（${c.count} 项）`);
}

// 资源分类「更多」：展开全部类型
const catShowAll = ref(false);
const visibleCategories = computed(() =>
  catShowAll.value ? categoriesAll.value : categoriesAll.value.slice(0, 6),
);

/** 最近访问 / 本周推荐：点击直接打开对应资源预览 */
function openCardByTitle(title: string) {
  const card = cards.value?.find((c) => c.title === title);
  if (card) {
    void handleView(card);
  } else {
    showToast("该资源已不在当前列表中");
  }
}

/** AI 推荐：resource 直接预览；generate 直接呈现生成指引 */
function handleAiRecoClick(item: RecommendationItem) {
  if (item.kind === "resource" && item.resource_id) {
    const card = findCardByResourceId(item.resource_id);
    if (card) {
      void handleView(card);
      return;
    }
  }
  // 生成类推荐 / 找不到资源卡：内联呈现推荐详情与生成指引
  previewCard.value = {
    id: `ai-reco-${item.kp_id}`,
    kind: "note",
    badgeText: "✨",
    title: localizeResourceText(item.title || item.topic, "AI 推荐"),
    desc: localizeResourceText(item.reason, "根据当前学习情况为你推荐"),
    author: "智狐 · 精准推送",
    date: "",
    views: "—",
    tags: ["AI推荐"],
  };
  previewOpen.value = true;
  previewLoading.value = false;
  previewType.value = "text";
  previewIsMarkdown.value = true;
  previewUrl.value = "";
  previewDataUri.value = "";
  previewInfo.value = null;
  previewText.value = [
    `### ${localizeResourceText(item.title || item.topic, "AI 推荐")}`,
    `**推荐理由**：${localizeResourceText(item.reason, "根据当前学习情况为你推荐")}`,
    item.kp_id ? `**关联知识点**：${item.kp_id}` : "",
    item.suggested_types?.length ? `**建议生成类型**：${item.suggested_types.map(resourceTypeLabel).join(" / ")}` : "",
    "",
    "**如何获取这份资源**",
    "- 群聊中对阿匠说「生成 " + String(item.topic || item.title || "该主题") + " 的讲义」；",
    "- 或到「Agent 编排」页勾选类型一键生成（支持 PPT / 讲义 / 题库 / 音频）。",
  ].filter(Boolean).join("\n\n");
}

function updateTypeTabCounts() {
  // 根据当前来源筛选计算 tab 计数
  const sourceList = sourceFilter.value === "learning"
    ? learningCards.value
    : sourceFilter.value === "chat"
      ? chatArchiveCards.value
      : cards.value;
  typeTabs.value[0].count = sourceList.length;
  for (let i = 1; i < typeTabs.value.length; i++) {
    const tab = typeTabs.value[i];
    tab.count = sourceList.filter((card) => cardMatchesCategory(card, tab.key)).length;
  }
}

function showAllCourseResources() {
  sourceFilter.value = "learning";
  activeTab.value = "all";
  keyword.value = "";
  favOnlyFilter.value = false;
  page.value = 1;
}

watch(course, async () => {
  activeTab.value = "all";
  keyword.value = "";
  page.value = 1;
  apiResources.value = [];
  realArtifacts.value = [];
  restoreCachedResources();
  await Promise.all([refresh(), loadRecommendations()]);
});

onMounted(async () => {
  // 知识图谱"查看资源"跳转参数
  const qKpId = route.query.kp_id;
  const qKpName = route.query.kp_name;
  if (typeof qKpId === "string" && qKpId.trim()) kpFilterId.value = qKpId.trim();
  if (typeof qKpName === "string" && qKpName.trim()) {
    kpFilterName.value = qKpName.trim();
    keyword.value = qKpName.trim();
  }
  const q = route.query.q;
  if (typeof q === "string" && q.trim() && !keyword.value) {
    keyword.value = q.trim();
  }
  await loadCourseOptions();
  // 先恢复最近一次成功列表，再由 refresh 用新数据校正；后端短暂重启时
  // 资源库不会先变成空白页。
  restoreCachedResources();
  await Promise.all([refresh(), loadRecommendations()]);
  // 点击外部关闭更多菜单
  document.addEventListener("click", closeMoreMenu);
});

onBeforeUnmount(() => {
  document.removeEventListener("click", closeMoreMenu);
  closePreview();
});

/* -------------------- 工具 -------------------- */
function kindAccent(kind: ResKind): string {
  switch (kind) {
    case "pdf":   return "#ea5a1a";
    case "video": return "#4a6b85";
    case "quiz":  return "#2f9f6b";
    case "mind":  return "#7a5bbf";
    case "note":  return "#d89229";
    case "ppt":   return "#c8480f";
    default:      return "#5b554c";
  }
}
function kindBg(kind: ResKind): string {
  const c = kindAccent(kind);
  return `${c}1A`; // 透明度 ~10%
}

/* -------------------- 收藏 / 分享 -------------------- */
const favoritedIds = ref<Set<string>>(new Set());

function toggleFavorite(card: CardItem) {
  if (favoritedIds.value.has(card.id)) {
    favoritedIds.value.delete(card.id);
    showToast(`已取消收藏"${card.title}"`);
  } else {
    favoritedIds.value.add(card.id);
    showToast(`⭐ 已收藏"${card.title}"`);
  }
  favoritedIds.value = new Set(favoritedIds.value);
}

function handleShare(card: CardItem) {
  const url = card.rid ? getArtifactDownloadFullUrl(card.rid) : window.location.href;
  if (navigator.clipboard) {
    navigator.clipboard.writeText(url).then(() => {
      showToast(`🔗 链接已复制到剪贴板`);
    }).catch(() => {
      showToast(`🔗 分享链接：${url}`);
    });
  } else {
    showToast(`🔗 分享链接：${url}`);
  }
}

/* -------------------- 更多按钮下拉菜单 -------------------- */
const moreMenuOpenId = ref<string | null>(null);

function toggleMoreMenu(card: CardItem) {
  const id = card.id;
  moreMenuOpenId.value = moreMenuOpenId.value === id ? null : id;
}

function closeMoreMenu() {
  moreMenuOpenId.value = null;
}

function handleMoreAction(action: string, card: CardItem) {
  closeMoreMenu();
  switch (action) {
    case "view":
      handleView(card);
      break;
    case "download":
      handleDownload(card);
      break;
    case "share":
      handleShare(card);
      break;
    case "favorite":
      toggleFavorite(card);
      break;
    case "copyTitle":
      if (navigator.clipboard) {
        navigator.clipboard.writeText(card.title).then(() => showToast("📋 标题已复制"));
      }
      break;
  }
}

/* -------------------- 上传资源 -------------------- */
const fileInputRef = ref<HTMLInputElement | null>(null);
const uploading = ref(false);
const toastMsg = ref("");
const toastVisible = ref(false);

function showToast(msg: string) {
  toastMsg.value = msg;
  toastVisible.value = true;
  setTimeout(() => { toastVisible.value = false; }, 3000);
}

function triggerFileUpload() {
  fileInputRef.value?.click();
}

async function handleFileSelected(e: Event) {
  const input = e.target as HTMLInputElement;
  if (!input.files?.length) return;
  const file = input.files[0];
  // 限制 10MB
  if (file.size > 10 * 1024 * 1024) {
    showToast("文件过大（超过 10MB），请选择更小的文件。");
    input.value = "";
    return;
  }

  uploading.value = true;
  try {
    // 读取文件内容
    const text = await file.text();
    const ext = file.name.split(".").pop()?.toLowerCase() || "";
    const typeMap: Record<string, string> = {
      md: "document", txt: "document", json: "quiz",
      py: "code", js: "code", ts: "code", java: "code",
      csv: "document", html: "code", css: "code",
    };
    const resType = typeMap[ext] || "document";
    const contentType = ext === "json" ? "json" : "markdown";

    await saveResource({
      user_id: userId.value,
      type: resType,
      title: file.name.replace(/\.[^.]+$/, ""),
      content: text,
      content_type: contentType,
      agent_name: "用户上传",
      tags: [ext, "上传"],
    });
    showToast(`✅ "${file.name}" 已成功上传到资源库`);
    await refresh();
  } catch (err: any) {
    showToast(`上传失败：${err?.detail || err?.message || "请检查后端连接"}`);
  } finally {
    uploading.value = false;
    input.value = "";
  }
}

/* -------------------- 新建文件夹 -------------------- */
const folderModalOpen = ref(false);
const folderName = ref("");
const creatingFolder = ref(false);

function openFolderModal() {
  folderName.value = "";
  folderModalOpen.value = true;
}

async function createFolder() {
  const name = folderName.value.trim();
  if (!name) return;
  creatingFolder.value = true;
  try {
    await saveResource({
      user_id: userId.value,
      type: "folder",
      title: name,
      content: "",
      content_type: "folder",
      agent_name: "用户创建",
      tags: ["文件夹"],
    });
    showToast(`✅ 文件夹 "${name}" 已创建`);
    folderModalOpen.value = false;
    await refresh();
  } catch (err: any) {
    showToast(`创建失败：${err?.detail || err?.message || "请检查后端连接"}`);
  } finally {
    creatingFolder.value = false;
  }
}
</script>

<template>
  <div class="resources-page teacher-skin">
    <!-- =================== 顶部标题 + 搜索 =================== -->
    <header class="page-header">
      <div class="title-block">
        <h2>资源库</h2>
        <p>课程资料、习题、笔记与多模态学习资源统一管理</p>
      </div>
      <div class="search-block">
        <label class="course-switcher">
          <span>当前课程</span>
          <select :value="course" aria-label="切换课程" @change="handleCourseChange">
            <option v-for="item in courseOptions" :key="item.value" :value="item.value">
              {{ item.label }}
            </option>
          </select>
        </label>
        <div class="search-input">
          <Search :size="16" />
          <input type="text" v-model="keyword" placeholder="搜索资源名称 / 课程 / 标签" />
        </div>
        <button class="advanced-btn" type="button">
          <SlidersHorizontal :size="14" />
          <span>高级筛选</span>
        </button>
      </div>
    </header>

    <!-- 知识点筛选横幅（从知识图谱跳转时显示） -->
    <div v-if="kpFilterName" class="kp-filter-banner">
      <span class="kp-banner-icon">📚</span>
      <span class="kp-banner-text">
        正在查看知识点 <b>{{ kpFilterName }}</b> 的相关资源
      </span>
      <button type="button" class="kp-banner-clear" @click="kpFilterName = ''; kpFilterId = ''; keyword = '';">✕ 清除筛选</button>
    </div>

    <!-- =================== 主区 + 侧栏 =================== -->
    <div class="layout-two">
      <!-- ============= 主区 ============= -->
      <div class="main-column">
        <!-- 来源筛选 -->
        <div class="source-bar">
          <button
            class="source-tab"
            :class="{ active: sourceFilter === 'learning' }"
            type="button"
            @click="sourceFilter = 'learning'"
          >
            📚 学习资源
          </button>
          <button
            class="source-tab"
            :class="{ active: sourceFilter === 'chat' }"
            type="button"
            @click="sourceFilter = 'chat'"
          >
            💬 聊天存档
          </button>
        </div>

        <!-- 类型 Tab + 排序 -->
        <div class="filter-bar">
          <div class="type-tabs">
            <button
              v-for="t in typeTabs"
              :key="t.key"
              class="type-tab"
              :class="{ active: activeTab === t.key }"
              type="button"
              @click="activeTab = t.key"
            >
              <component :is="resourceIconForType(t.key)" class="tab-icon" :size="14" />
              <span class="tab-label">{{ t.label }}</span>
              <span class="tab-count">{{ t.count }}</span>
            </button>
          </div>
          <div class="right-controls">
            <div class="sort-dropdown">
              <button class="sort-trigger" type="button" @click="sortOpen = !sortOpen">
                {{ sortOptions?.find((o) => o.key === sortKey)?.label || "最新上传" }}
                <ChevronDown :size="14" />
              </button>
              <ul v-if="sortOpen" class="sort-menu">
                <li
                  v-for="o in sortOptions"
                  :key="o.key"
                  class="sort-item"
                  :class="{ active: sortKey === o.key }"
                  @click="sortKey = o.key; sortOpen = false"
                >
                  {{ o.label }}
                </li>
              </ul>
            </div>
            <button
              class="view-btn"
              :class="{ active: viewMode === 'grid' }"
              type="button"
              @click="viewMode = 'grid'"
              title="网格视图"
            >
              <LayoutGrid :size="14" />
            </button>
            <button
              class="view-btn"
              :class="{ active: viewMode === 'list' }"
              type="button"
              @click="viewMode = 'list'"
              title="列表视图"
            >
              <List :size="14" />
            </button>
          </div>
        </div>

        <!-- Hero 精选专题 -->
        <section class="hero">
          <div class="hero-text">
                <span class="hero-tag">{{ hero?.tag || "精选课程" }}</span>
                <h3 class="hero-title">{{ hero?.title || "人工智能课程资源" }}</h3>
                <p class="hero-desc">{{ hero?.desc || "课程资料、习题、笔记与多模态学习资源统一管理。" }}</p>
            <div class="hero-stats">
              <span class="stat">
                <Users :size="14" /> {{ learningCards?.length || 0 }} 个真实资源
              </span>
            </div>
                <button class="hero-cta" type="button" @click="showAllCourseResources">{{ hero?.cta || "查看全部资源" }} →</button>
          </div>
          <div class="hero-visual" aria-hidden="true">
            <div class="visual-cube cube-back">
                <span>{{ hero?.formula || "AI" }}</span>
            </div>
            <div class="visual-cube cube-mid">
              <span class="cube-mark">∑</span>
            </div>
            <div class="visual-cube cube-front">
              <span class="cube-mark cube-mark-glyph">AI</span>
            </div>
            <div class="visual-ring" />
          </div>
        </section>

        <!-- 卡片网格 -->
        <section class="card-grid">
          <!-- 加载中 -->
          <div v-if="sourceFilter === 'learning' && loading && (pagedCards?.length || 0) === 0" class="empty-state resource-state-panel" role="status">
            <Loader2 :size="24" class="spin" />
            <p>正在加载课程资源…</p>
            <p class="empty-hint">已显示的数据不会在刷新时被清空</p>
          </div>
          <div v-else-if="sourceFilter === 'learning' && error && (pagedCards?.length || 0) === 0" class="empty-state resource-state-panel error-state" role="alert">
            <X :size="22" />
            <p>{{ error }}</p>
            <button class="state-retry-btn" type="button" @click="refresh">重新加载</button>
          </div>
          <div v-else-if="sourceFilter === 'chat' && chatArchiveLoading" class="empty-state resource-state-panel">
            <Loader2 :size="24" class="spin" />
            <p>正在加载聊天记录…</p>
          </div>
          <!-- 空状态 -->
          <div v-else-if="sourceFilter === 'chat' && (pagedCards?.length || 0) === 0" class="empty-state">
            <p>💬 暂无聊天记录</p>
            <p class="empty-hint">与智能体对话后，聊天记录会自动保存在这里</p>
          </div>
          <div v-else-if="sourceFilter === 'learning' && (pagedCards?.length || 0) === 0" class="empty-state resource-state-panel">
            <FileText :size="24" />
            <p>当前筛选条件下没有匹配资源</p>
            <p class="empty-hint">可清除类型、搜索与收藏筛选，或重新同步资源库</p>
            <div class="state-actions">
              <button class="state-secondary-btn" type="button" @click="activeTab = 'all'; keyword = ''; favOnlyFilter = false; page = 1">清除筛选</button>
              <button class="state-retry-btn" type="button" @click="refresh">重新同步</button>
            </div>
          </div>
          <article
            v-for="card in pagedCards"
            :key="card.id"
            class="res-card"
            :style="{ '--accent': kindAccent(card.kind), '--accent-bg': kindBg(card.kind) }"
          >
            <header class="res-head">
              <span class="res-badge">
                <component :is="resourceIconForType(card.artifactType || card.resourceType || card.kind)" :size="16" />
              </span>
              <div class="res-title-block">
                <h4 class="res-title">
                  {{ card.title }}
                  <em
                    v-if="card.personalized"
                    class="res-personalized-tag"
                    :title="card.personalizedHint ? `已按画像个性化：${card.personalizedHint}` : '生成时注入了学生画像，内容按你的画像调整'"
                  >✨ 个性化</em>
                </h4>
                <p class="res-desc">{{ card.desc }}</p>
              </div>
            </header>
            <div class="res-meta">
              <span class="meta-author">👤 {{ card.author }}</span>
              <span class="meta-date">{{ card.date }} 更新</span>
              <span class="meta-views"><Eye :size="12" /> {{ card.views }}</span>
            </div>
            <div class="res-tags">
              <span v-for="t in card.tags" :key="t" class="res-tag">{{ t }}</span>
            </div>
            <footer class="res-actions">
              <button class="act-btn" type="button" title="查看" @click="handleView(card)"><Eye :size="14" /></button>
              <button class="act-btn" type="button" title="下载" :disabled="!card.rid && !card.resourceId" @click="handleDownload(card)"><Cloud :size="14" /></button>
              <button class="act-btn" type="button" :class="{ active: favoritedIds.has(card.id) }" :title="favoritedIds.has(card.id) ? '取消收藏' : '收藏'" @click="toggleFavorite(card)"><Star :size="14" :fill="favoritedIds.has(card.id) ? 'currentColor' : 'none'" /></button>
              <button class="act-btn" type="button" title="分享" @click="handleShare(card)"><Share2 :size="14" /></button>
              <div class="more-wrapper">
                <button class="act-btn act-more" type="button" title="更多" @click.stop="toggleMoreMenu(card)"><MoreHorizontal :size="14" /></button>
                <ul v-if="moreMenuOpenId === card.id" class="more-dropdown" @click.stop>
                  <li @click="handleMoreAction('view', card)"><Eye :size="13" /> 查看详情</li>
                  <li @click="handleMoreAction('download', card)" :class="{ disabled: !card.rid && !card.resourceId }"><Cloud :size="13" /> 下载</li>
                  <li @click="handleMoreAction('favorite', card)"><Star :size="13" :fill="favoritedIds.has(card.id) ? 'currentColor' : 'none'" /> {{ favoritedIds.has(card.id) ? '取消收藏' : '收藏' }}</li>
                  <li @click="handleMoreAction('share', card)"><Share2 :size="13" /> 分享</li>
                  <li @click="handleMoreAction('copyTitle', card)"><FileText :size="13" /> 复制标题</li>
                </ul>
              </div>
            </footer>
          </article>
        </section>

        <!-- 分页 -->
        <footer class="pagination">
          <span class="page-total">共 {{ filteredCards?.length || 0 }} 个资源</span>
          <div class="page-controls">
            <button class="page-btn" type="button" :disabled="page === 1" @click="changePage(1)">
              <ChevronsLeft :size="14" />
            </button>
            <button class="page-btn" type="button" :disabled="page === 1" @click="changePage(page - 1)">
              <ChevronLeft :size="14" />
            </button>
            <template v-for="(p, idx) in visiblePages" :key="idx">
              <span v-if="p === -1" class="page-ellipsis">…</span>
              <button
                v-else
                class="page-num"
                :class="{ active: page === p }"
                type="button"
                @click="changePage(p)"
              >{{ p }}</button>
            </template>
            <button class="page-btn" type="button" :disabled="page === totalPages" @click="changePage(page + 1)">
              <ChevronRight :size="14" />
            </button>
            <button class="page-btn" type="button" :disabled="page === totalPages" @click="changePage(totalPages)">
              <ChevronsRight :size="14" />
            </button>
            <div class="page-size">
              <span>{{ pageSize }} 条/页</span>
              <ChevronDown :size="12" />
            </div>
          </div>
        </footer>

        <p v-if="error" class="error-banner">
          <X :size="14" /> {{ error }}
        </p>
      </div>

      <!-- ============= 侧栏 ============= -->
      <aside class="right-column">
        <!-- 资源概览 -->
        <section class="side-card">
          <header class="side-head">
            <h3>资源概览</h3>
            <button class="side-link" type="button" @click="refresh">刷新 ↻</button>
          </header>
          <div class="overview-grid">
            <!-- 点击直接应用对应筛选（全部/最新/收藏/类型） -->
            <div
              v-for="o in overview"
              :key="o.key"
              class="overview-item clickable"
              :class="[`ov-${o.color}`, { active: o.key === 'favorites' && favOnlyFilter }]"
              role="button"
              @click="handleOverviewClick(o.key)"
            >
              <div class="ov-value-row">
                <span class="ov-value">{{ o.value }}</span>
                <span class="ov-icon"><component :is="o.icon" :size="16" /></span>
              </div>
              <span class="ov-label">{{ o.label }}</span>
            </div>
          </div>
        </section>

        <!-- 资源分类 -->
        <section class="side-card">
          <header class="side-head">
            <h3>资源分类</h3>
            <button class="side-link" type="button" @click="catShowAll = !catShowAll">
              {{ catShowAll ? "收起 ‹" : "更多 ›" }}
            </button>
          </header>
          <ul class="cat-list">
            <!-- 点击直接按类型筛选主列表 -->
            <li
              v-for="c in visibleCategories"
              :key="c.name"
              class="cat-item clickable"
              role="button"
              @click="handleCategoryClick(c)"
            >
              <span class="cat-icon">
                <component :is="resourceIconForType(c.name)" :size="14" />
              </span>
              <span class="cat-name">{{ resourceTypeLabel(c.name) }}</span>
              <div class="cat-bar">
                <i :style="{ width: `${(c.count / c.total) * 100}%`, background: c.color }" />
              </div>
              <span class="cat-count">{{ c.count }}</span>
            </li>
          </ul>
        </section>

        <!-- 最近访问 -->
        <section class="side-card">
          <header class="side-head">
            <h3>最近访问</h3>
            <button v-if="recent?.length" class="side-link" type="button" @click="recent = []">清空</button>
          </header>
          <p v-if="!recent?.length" class="side-empty">预览过的资源会出现在这里。</p>
          <ul class="recent-list">
            <!-- 点击直接重新打开该资源预览 -->
            <li
              v-for="(r, i) in recent"
              :key="i"
              class="recent-item clickable"
              role="button"
              @click="openCardByTitle(r.title)"
            >
              <span class="recent-icon" :class="`rk-${r.kind}`">{{ r.icon }}</span>
              <span class="recent-title">{{ r.title }}</span>
              <span class="recent-time">{{ r.time }}</span>
            </li>
          </ul>
        </section>

        <!-- 上传入口 -->
        <section class="side-card upload-card">
          <button class="upload-btn primary" type="button" @click="triggerFileUpload" :disabled="uploading">
            <span class="upload-icon">
              <Loader2 v-if="uploading" :size="18" class="spin" />
              <CloudUpload v-else :size="18" />
            </span>
            <span class="upload-text">
              <strong>{{ uploading ? '上传中…' : '上传资源' }}</strong>
              <small>分享你的学习资源</small>
            </span>
          </button>
          <button class="upload-btn ghost" type="button" @click="openFolderModal">
            <span class="upload-icon"><FolderPlus :size="18" /></span>
            <span class="upload-text">
              <strong>新建文件夹</strong>
              <small>整理与分类资源</small>
            </span>
          </button>
        </section>

        <!-- AI 推荐（BKT + 知识图谱精准推送） -->
        <section class="side-card ai-card">
          <header class="side-head">
            <h3>
              <Sparkles :size="14" class="ai-spark" />
              AI推荐
            </h3>
            <button class="side-link ai-refresh" type="button" @click="loadRecommendations" :disabled="aiRecommendLoading">
              <RefreshCw :size="12" :class="{ spin: aiRecommendLoading }" /> 换一换
            </button>
          </header>
          <Loader2 v-if="aiRecommendLoading" :size="20" class="spin" style="margin: 0 auto; display: block;" />
          <div v-else-if="aiRecommendations?.length" class="ai-reco-list">
            <!-- 点击直接预览资源 / 呈现推荐详情与生成指引 -->
            <div
              v-for="(item, idx) in aiRecommendations"
              :key="idx"
              class="ai-reco-item"
              role="button"
              @click="handleAiRecoClick(item)"
            >
              <span class="ai-badge sm"><Sparkles :size="12" /></span>
              <div class="ai-reco-body">
                <div class="ai-title">{{ localizeResourceText(item.title || item.topic, '智能推荐') }}</div>
                <div class="ai-desc">{{ localizeResourceText(item.reason, '根据当前学习情况为你推荐') }}</div>
                <span v-if="item.kind === 'generate'" class="ai-reco-tag">建议生成</span>
              </div>
            </div>
          </div>
          <div v-else class="ai-row">
            <span class="ai-badge"><Sparkles :size="14" /></span>
            <div>
              <div class="ai-title">暂无推荐</div>
              <div class="ai-desc">完成更多练习后可获得精准推荐</div>
            </div>
          </div>
        </section>

        <!-- 本周推荐 -->
        <section class="side-card">
          <header class="side-head">
            <h3>本周推荐</h3>
            <button class="side-link" type="button" @click="sortKey = 'popular'; activeTab = 'all'; page = 1;">
              按热度看 ›
            </button>
          </header>
          <ul class="week-list">
            <!-- 点击直接打开该资源预览 -->
            <li
              v-for="w in weekly"
              :key="w.rank"
              class="week-item clickable"
              role="button"
              @click="openCardByTitle(w.title)"
            >
              <span class="week-rank" :class="`rank-${w.rank}`">{{ w.rank }}</span>
              <span class="week-title">{{ w.title }}</span>
              <span class="week-views">{{ w.views }}</span>
              <Star :size="12" class="week-star" />
            </li>
          </ul>
        </section>
      </aside>
    </div>

    <!-- 多类型预览弹窗 -->
    <div v-if="previewOpen" class="preview-overlay" @click.self="closePreview">
      <div class="preview-modal">
        <button class="preview-close" type="button" @click="closePreview"><X :size="18" /></button>
        <h3 v-if="previewCard" class="preview-title">
          {{ previewCard.title }}
          <em v-if="previewCard.personalized" class="res-personalized-tag">✨ 个性化生成</em>
        </h3>
        <p v-if="previewCard?.personalized && previewCard.personalizedHint" class="preview-personalized-note">
          本资源在生成时按你的画像做了个性化：{{ previewCard.personalizedHint }}
        </p>

        <!-- 类型标识条 -->
        <div v-if="previewCard" class="preview-meta-bar">
          <span class="preview-type-badge" :class="`pt-${previewType}`">
            <component :is="resourceIconForType(previewCard.artifactType || previewCard.resourceType)" :size="13" />
            {{ resourceTypeLabel(previewCard.artifactType || previewCard.resourceType || '文件') }}
          </span>
          <span v-if="previewCard.rid" class="preview-rid">ID: {{ previewCard.rid.slice(-8) }}</span>
        </div>

        <div class="preview-body">
          <Loader2 v-if="previewLoading" :size="28" class="spin" />

          <!-- 图片预览 -->
          <template v-else-if="previewType === 'image'">
            <img v-if="previewDataUri" :src="previewDataUri" alt="预览" class="preview-img" />
            <img v-else-if="previewUrl" :src="previewUrl" alt="预览" class="preview-img" />
            <p v-else class="preview-empty">图片加载失败，请尝试下载。</p>
          </template>

          <!-- 音频预览 -->
          <div v-else-if="previewType === 'audio'" class="preview-audio-wrap">
            <div class="preview-big-icon">🎵</div>
            <p class="preview-hint">音频文件</p>
            <audio v-if="previewUrl" :src="previewUrl" controls class="preview-audio" />
          </div>

          <!-- 视频预览 -->
          <div v-else-if="previewType === 'video'" class="preview-video-wrap">
            <video v-if="previewUrl" :src="previewUrl" controls class="preview-video" />
            <p v-else class="preview-empty">视频加载失败，请尝试下载。</p>
          </div>

          <!-- 文本/代码预览 -->
          <div v-else-if="previewType === 'text'" class="preview-text-wrap">
            <!-- Markdown 渲染为格式化 HTML -->
            <div v-if="previewIsMarkdown" class="preview-md" v-html="previewHtml"></div>
            <!-- 纯文本/代码用 <pre> 展示 -->
            <pre v-else class="preview-code">{{ previewText || '内容为空' }}</pre>
          </div>

          <!-- PPT 课件预览 -->
          <div v-else-if="previewType === 'pptx'" class="preview-pptx-wrap">
            <div class="preview-big-icon">📊</div>
            <p class="preview-hint">PPT 课件无法在浏览器中直接预览</p>
            <p class="preview-sub-hint">请点击下方"下载文件"按钮查看完整内容</p>
            <div v-if="previewInfo" class="preview-info-grid">
              <div class="preview-info-item">
                <span class="label">类型</span>
                <span class="value">{{ previewInfo.type }}</span>
              </div>
              <div class="preview-info-item">
                <span class="label">文件</span>
                <span class="value">{{ previewInfo.filepath?.split(/[\\/]/).pop() || '—' }}</span>
              </div>
            </div>
          </div>

          <!-- 不支持的类型 -->
          <div v-else class="preview-pptx-wrap">
            <div class="preview-big-icon">📄</div>
            <p class="preview-hint">此资源类型暂不支持在线预览</p>
            <p class="preview-sub-hint">请点击下方"下载文件"按钮查看</p>
          </div>
        </div>

        <div v-if="previewCard?.rid || previewCard?.resourceId" class="preview-footer">
          <button
            v-if="previewCard?.resourceType === 'prompt'"
            class="primary-btn"
            type="button"
            @click="useTeacherPrompt(previewCard)"
          >
            <Sparkles :size="14" /> 带入群聊学习
          </button>
          <button class="primary-btn secondary" type="button" @click="handleDownload(previewCard!)">
            <Cloud :size="14" /> 下载文件
          </button>
        </div>
      </div>
    </div>
    <!-- 隐藏的文件上传 input -->
    <input
      ref="fileInputRef"
      type="file"
      style="display:none"
      accept=".md,.txt,.json,.py,.js,.ts,.java,.csv,.html,.css,.xml,.yaml,.yml"
      @change="handleFileSelected"
    />

    <!-- Toast 通知 -->
    <transition name="toast-fade">
      <div v-if="toastVisible" class="res-toast">
        {{ toastMsg }}
      </div>
    </transition>

    <!-- 新建文件夹弹窗 -->
    <div v-if="folderModalOpen" class="folder-overlay" @click.self="folderModalOpen = false">
      <div class="folder-modal">
        <button class="preview-close" type="button" @click="folderModalOpen = false"><X :size="18" /></button>
        <h3 class="folder-modal-title">新建文件夹</h3>
        <input
          v-model="folderName"
          class="folder-input"
          placeholder="输入文件夹名称"
          @keyup.enter="createFolder"
        />
        <div class="folder-actions">
          <button class="ghost-btn" type="button" @click="folderModalOpen = false">取消</button>
          <button class="primary-btn" type="button" :disabled="!folderName.trim() || creatingFolder" @click="createFolder">
            <Loader2 v-if="creatingFolder" :size="14" class="spin" />
            创建
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ============== 容器 ============== */
.resources-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 0;
}

/* ============== 顶部标题 ============== */
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  flex-wrap: wrap;
}
.title-block h2 {
  margin: 0;
  font-family: var(--serif-cn);
  font-size: 26px;
  font-weight: 700;
  color: var(--ink);
  letter-spacing: -0.01em;
}
.title-block p {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--ink-muted);
}
.search-block {
  display: flex;
  gap: 10px;
  align-items: center;
}
.course-switcher {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  height: 38px;
  padding: 0 12px;
  border: 1px solid var(--paper-400);
  border-radius: 999px;
  background: #ffffff;
  color: var(--ink-muted);
  font-size: 12px;
  white-space: nowrap;
}
.course-switcher select {
  max-width: 180px;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--ink);
  font: inherit;
  font-weight: 600;
  cursor: pointer;
}
.search-input {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  width: 360px;
  height: 38px;
  padding: 0 14px;
  border-radius: 999px;
  background: #ffffff;
  border: 1px solid var(--paper-400);
  box-shadow: 0 1px 2px rgba(171, 111, 65, 0.05);
}
.search-input input {
  flex: 1;
  border: 0;
  outline: 0;
  background: transparent;
  font-size: 13px;
  color: var(--ink);
}
.search-input input::placeholder { color: var(--ink-muted); }
.search-input :deep(svg) { color: var(--ink-muted); }
.advanced-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 38px;
  padding: 0 16px;
  border-radius: 999px;
  background: #ffffff;
  border: 1px solid var(--paper-400);
  color: var(--ink);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s;
}
.advanced-btn:hover { background: var(--orange-soft, #fff0e4); }

/* ============== KP 筛选横幅 ============== */
.kp-filter-banner {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  margin-bottom: 16px;
  background: linear-gradient(135deg, rgba(234, 90, 26, 0.08), rgba(216, 146, 41, 0.06));
  border: 1px solid rgba(234, 90, 26, 0.2);
  border-radius: 10px;
  font-size: 13px;
}
.kp-filter-banner .kp-banner-icon { font-size: 16px; }
.kp-filter-banner .kp-banner-text { flex: 1; color: var(--ink-700, #4a443c); }
.kp-filter-banner .kp-banner-text b { color: var(--orange-600, #ea5a1a); }
.kp-filter-banner .kp-banner-clear {
  border: none;
  background: rgba(234, 90, 26, 0.1);
  color: var(--orange-600, #ea5a1a);
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
}
.kp-filter-banner .kp-banner-clear:hover { background: rgba(234, 90, 26, 0.2); }

/* ============== 双栏 ============== */
.layout-two {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 320px;
  gap: 18px;
  align-items: start;
}
.main-column {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
}
.right-column {
  display: flex;
  flex-direction: column;
  gap: 14px;
  position: sticky;
  top: 14px;
}

/* ============== Source Bar ============== */
.source-bar {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}
.source-tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 36px;
  padding: 0 18px;
  border-radius: 10px;
  background: #ffffff;
  border: 1px solid var(--paper-400);
  color: var(--ink);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
}
.source-tab:hover {
  background: var(--orange-soft, #fff0e4);
  border-color: var(--orange-400, #f08441);
}
.source-tab.active {
  background: linear-gradient(120deg, var(--orange-500, #ea5a1a), var(--orange-400, #f08441));
  color: #ffffff;
  border-color: transparent;
  box-shadow: 0 4px 12px rgba(234, 90, 26, 0.2);
}

/* ============== Filter Bar ============== */
.filter-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.type-tabs {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.type-tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 32px;
  padding: 0 14px;
  border-radius: 999px;
  background: #ffffff;
  border: 1px solid var(--paper-400);
  color: var(--ink);
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
}
.type-tab:hover { background: var(--orange-soft, #fff0e4); }
.type-tab.active {
  background: linear-gradient(120deg, var(--orange-500, #ea5a1a), var(--orange-400, #f08441));
  color: #ffffff;
  border-color: transparent;
  box-shadow: 0 6px 14px rgba(234, 90, 26, 0.25);
}
.tab-icon { flex: 0 0 auto; }
.tab-count {
  font-size: 11.5px;
  font-weight: 700;
  opacity: 0.85;
}
.right-controls {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.sort-dropdown { position: relative; }
.sort-trigger {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 32px;
  padding: 0 14px;
  border-radius: 8px;
  background: #ffffff;
  border: 1px solid var(--paper-400);
  font-size: 13px;
  color: var(--ink);
  cursor: pointer;
}
.sort-trigger:hover { background: var(--orange-soft, #fff0e4); }
.sort-menu {
  position: absolute;
  top: calc(100% + 4px);
  right: 0;
  z-index: 10;
  list-style: none;
  margin: 0;
  padding: 6px;
  min-width: 140px;
  background: #ffffff;
  border: 1px solid var(--paper-400);
  border-radius: 10px;
  box-shadow: 0 12px 28px rgba(103, 62, 22, 0.12);
}
.sort-item {
  padding: 6px 10px;
  font-size: 13px;
  border-radius: 6px;
  cursor: pointer;
  color: var(--ink);
}
.sort-item:hover { background: var(--orange-soft, #fff0e4); }
.sort-item.active { color: var(--orange-600, #c8480f); font-weight: 600; }
.view-btn {
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  background: #ffffff;
  border: 1px solid var(--paper-400);
  color: var(--ink-muted);
  cursor: pointer;
}
.view-btn.active {
  background: var(--orange-soft, #fff0e4);
  border-color: var(--orange-300, #f5a872);
  color: var(--orange-600, #c8480f);
}

/* ============== Hero ============== */
.hero {
  position: relative;
  display: grid;
  grid-template-columns: 1fr 280px;
  gap: 24px;
  align-items: center;
  padding: 28px 32px;
  border-radius: 16px;
  background:
    radial-gradient(circle at 20% 30%, rgba(255, 210, 141, 0.28), transparent 55%),
    radial-gradient(circle at 90% 80%, rgba(255, 230, 199, 0.45), transparent 50%),
    linear-gradient(120deg, #fff7ed 0%, #fdf2e1 60%, #fff 100%);
  border: 1px solid var(--paper-400);
  box-shadow: 0 8px 24px rgba(171, 111, 65, 0.08);
  overflow: hidden;
}
.hero-text { display: flex; flex-direction: column; gap: 12px; min-width: 0; }
.hero-tag {
  align-self: flex-start;
  padding: 3px 10px;
  font-size: 11px;
  font-weight: 700;
  color: var(--orange-700, #9a3608);
  background: var(--orange-100, #ffe6cf);
  border-radius: 999px;
}
.hero-title {
  margin: 0;
  font-family: var(--serif-cn);
  font-size: 26px;
  font-weight: 700;
  color: var(--ink);
  letter-spacing: -0.01em;
}
.hero-desc {
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
  color: var(--ink-muted);
  max-width: 480px;
}
.hero-stats {
  display: flex;
  gap: 18px;
  flex-wrap: wrap;
  font-size: 12.5px;
  color: var(--ink);
}
.hero-stats .stat {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.hero-stats .stat :deep(svg) { color: var(--orange-500, #ea5a1a); }
.hero-cta {
  align-self: flex-start;
  margin-top: 4px;
  height: 36px;
  padding: 0 20px;
  border-radius: 999px;
  background: linear-gradient(120deg, var(--orange-500, #ea5a1a), var(--orange-600, #c8480f));
  color: #fff;
  font-size: 13px;
  font-weight: 700;
  border: 0;
  cursor: pointer;
  box-shadow: 0 10px 22px rgba(234, 90, 26, 0.28);
  transition: transform 0.15s;
}
.hero-cta:hover { transform: translateY(-1px); }

/* Hero 视觉 */
.hero-visual {
  position: relative;
  height: 180px;
  display: flex;
  align-items: center;
  justify-content: center;
  perspective: 600px;
}
.visual-cube {
  position: absolute;
  width: 80px;
  height: 80px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--serif-cn);
  font-weight: 700;
  font-size: 22px;
  color: #fff;
  box-shadow: 0 18px 40px rgba(234, 90, 26, 0.25);
}
.cube-back {
  top: 18px;
  right: 24px;
  background: linear-gradient(135deg, #f5a872, #ea5a1a);
  transform: rotateX(8deg) rotateY(-18deg) rotateZ(-6deg);
  width: 92px;
  height: 92px;
  font-size: 18px;
}
.cube-mid {
  top: 50%;
  left: 30%;
  transform: translate(-50%, -50%) rotateX(10deg) rotateY(20deg);
  background: linear-gradient(135deg, #ffe6cf, #fbcfa3);
  color: var(--orange-700, #9a3608);
  width: 90px;
  height: 90px;
  border: 1px solid rgba(255, 255, 255, 0.6);
}
.cube-front {
  bottom: 14px;
  left: 14px;
  background: linear-gradient(135deg, #c8480f, #9a3608);
  width: 72px;
  height: 72px;
  font-size: 28px;
}
.cube-mark { letter-spacing: 0; }
.cube-mark-glyph {
  font-family: var(--serif-cn);
  font-weight: 800;
}
.visual-ring {
  position: absolute;
  width: 220px;
  height: 220px;
  border-radius: 50%;
  border: 1.5px dashed rgba(234, 90, 26, 0.3);
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%) rotate(-12deg);
  pointer-events: none;
}
.visual-arrow {
  position: absolute;
  right: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.85);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--orange-600, #c8480f);
  font-size: 18px;
  font-weight: 700;
  box-shadow: 0 6px 16px rgba(234, 90, 26, 0.18);
}
.hero-dots {
  position: absolute;
  bottom: 12px;
  left: 32px;
  display: flex;
  gap: 6px;
}
.hero-dots .dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: rgba(171, 111, 65, 0.3);
  cursor: pointer;
  transition: background 0.15s, width 0.15s;
}
.hero-dots .dot.active {
  width: 18px;
  border-radius: 999px;
  background: var(--orange-500, #ea5a1a);
}

/* ============== 卡片网格 ============== */
.card-grid {
display: grid;
grid-template-columns: repeat(3, minmax(0, 1fr));
gap: 14px;
}
.empty-state {
grid-column: 1 / -1;
text-align: center;
padding: 48px 16px;
color: var(--ink-600, #666);
}
.empty-state p { margin: 4px 0; }
.empty-hint { font-size: 13px; opacity: 0.7; }
.resource-state-panel {
  min-height: 220px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border: 1px dashed var(--paper-500, #d9d1c6);
  border-radius: 14px;
  background: #fffdf9;
}
.resource-state-panel.error-state { color: #9f2d20; background: #fff9f7; }
.state-actions { display: flex; gap: 10px; margin-top: 6px; }
.state-retry-btn,
.state-secondary-btn {
  min-height: 38px;
  padding: 0 16px;
  border-radius: 9px;
  border: 1px solid var(--orange-500, #ea5a1a);
  cursor: pointer;
  font-weight: 700;
}
.state-retry-btn { color: #fff; background: var(--orange-500, #ea5a1a); }
.state-secondary-btn { color: var(--orange-700, #a53b0d); background: #fff; }
.res-card {
  --accent: var(--orange-500);
  --accent-bg: rgba(234, 90, 26, 0.1);
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px;
  background: #ffffff;
  border: 1px solid var(--paper-400);
  border-radius: 12px;
  transition: transform 0.15s, box-shadow 0.15s;
}
.res-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 14px 28px rgba(103, 62, 22, 0.12);
}
.res-head {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}
.res-badge {
  flex: 0 0 auto;
  width: 48px;
  height: 48px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  background: var(--accent-bg);
  color: var(--accent);
  font-weight: 700;
  font-size: 13px;
  font-family: var(--serif-cn);
  letter-spacing: 0.5px;
}
.res-title-block { min-width: 0; flex: 1; }
.res-title {
  margin: 0;
  font-size: 14px;
  font-weight: 700;
  color: var(--ink);
  line-height: 1.4;
  display: inline-flex;
  align-items: baseline;
  gap: 6px;
  flex-wrap: wrap;
}
.res-personalized-tag {
  font-style: normal;
  font-size: 10.5px;
  font-weight: 700;
  padding: 1px 8px;
  border-radius: 999px;
  background: linear-gradient(135deg, #ffe6d0, #fff1e0);
  color: #b45309;
  border: 1px solid #fbd8b3;
  cursor: help;
}
.res-desc {
  margin: 4px 0 0;
  font-size: 12px;
  line-height: 1.5;
  color: var(--ink-muted);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.res-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 11.5px;
  color: var(--ink-muted);
}
.meta-views {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 3px;
}
.res-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.res-tag {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--orange-50, #fff7ed);
  color: var(--orange-700, #9a3608);
  border: 1px solid var(--orange-200, #fbcfa3);
}
.res-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  padding-top: 8px;
  border-top: 1px dashed var(--paper-400);
}
.act-btn {
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: 0;
  border-radius: 6px;
  color: var(--ink-muted);
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}
.act-btn:hover {
background: var(--orange-soft, #fff0e4);
color: var(--orange-600, #c8480f);
}
.act-btn.active {
color: var(--orange-500, #e88a30);
}
.act-more { margin-left: auto; }

/* ============== 更多按钮下拉菜单 ============== */
.more-wrapper { position: relative; }
.more-dropdown {
  position: absolute;
  right: 0;
  top: 100%;
  margin-top: 4px;
  background: #fff;
  border: 1px solid var(--paper-border, #e8d5c4);
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0,0,0,0.12);
  list-style: none;
  padding: 4px 0;
  margin: 0;
  z-index: 50;
  min-width: 140px;
}
.more-dropdown li {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  font-size: 12.5px;
  color: var(--ink-700, #444);
  cursor: pointer;
  transition: background 0.15s;
}
.more-dropdown li:hover {
  background: var(--paper-warm, #faf3eb);
}
.more-dropdown li.disabled {
  opacity: 0.4;
  pointer-events: none;
}

/* ============== 分页 ============== */
.pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding: 8px 4px 0;
}
.page-total { font-size: 12.5px; color: var(--ink-muted); }
.page-controls {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}
.page-btn,
.page-num {
  min-width: 30px;
  height: 30px;
  padding: 0 8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  background: #ffffff;
  border: 1px solid var(--paper-400);
  font-size: 12.5px;
  color: var(--ink);
  cursor: pointer;
}
.page-btn:hover,
.page-num:hover { background: var(--orange-soft, #fff0e4); }
.page-num.active {
  background: var(--orange-500, #ea5a1a);
  border-color: transparent;
  color: #fff;
  font-weight: 700;
}
.page-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.page-ellipsis { padding: 0 4px; color: var(--ink-muted); font-size: 12.5px; }
.page-size {
  margin-left: 8px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 30px;
  padding: 0 10px;
  border-radius: 6px;
  background: #ffffff;
  border: 1px solid var(--paper-400);
  font-size: 12.5px;
  color: var(--ink);
  cursor: pointer;
}

/* ============== 侧栏卡片 ============== */
.side-card {
  background: #ffffff;
  border: 1px solid var(--paper-400);
  border-radius: 12px;
  padding: 14px;
  box-shadow: 0 4px 12px rgba(103, 62, 22, 0.05);
}
.side-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.side-head h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 700;
  color: var(--ink);
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.side-link {
  font-size: 11.5px;
  color: var(--ink-muted);
  text-decoration: none;
  border: 0;
  background: transparent;
  cursor: pointer;
  font-family: inherit;
}
.side-link:hover { color: var(--orange-600, #c8480f); }

.side-empty {
  margin: 4px 0;
  font-size: 11.5px;
  color: #9ca3af;
  line-height: 1.6;
}

/* 侧栏可点击项统一反馈 */
.overview-item.clickable,
.cat-item.clickable,
.recent-item.clickable,
.week-item.clickable {
  cursor: pointer;
  transition: transform 0.12s ease, box-shadow 0.12s ease, background 0.12s ease;
}
.overview-item.clickable:hover,
.cat-item.clickable:hover,
.recent-item.clickable:hover,
.week-item.clickable:hover {
  transform: translateY(-1px);
  background: var(--orange-50, #fff5ec);
}
.overview-item.clickable.active {
  outline: 2px solid var(--orange-500, #ea5a1a);
  outline-offset: -2px;
}
.ai-refresh { display: inline-flex; align-items: center; gap: 4px; }
.ai-spark { color: var(--orange-500, #ea5a1a); }

/* 概览 */
.overview-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.overview-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px;
  border-radius: 10px;
  background: var(--orange-50, #fff7ed);
  border: 1px solid var(--paper-300);
}
.overview-item.ov-blue   { background: #f0f5fa; border-color: #d8e3ee; }
.overview-item.ov-green  { background: #ecf6f0; border-color: #d3e7db; }
.overview-item.ov-orange { background: var(--orange-50, #fff7ed); border-color: var(--orange-200, #fbcfa3); }
.overview-item.ov-purple { background: #f5f0fa; border-color: #e3d8ee; }
.ov-value-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.ov-value {
  font-size: 20px;
  font-weight: 800;
  color: var(--ink);
  font-family: var(--serif-cn);
}
.overview-item.ov-blue   .ov-value { color: #4a6b85; }
.overview-item.ov-green  .ov-value { color: #2f9f6b; }
.overview-item.ov-orange .ov-value { color: var(--orange-600, #c8480f); }
.overview-item.ov-purple .ov-value { color: #7a5bbf; }
.ov-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.7);
}
.overview-item.ov-blue   .ov-icon { color: #4a6b85; }
.overview-item.ov-green  .ov-icon { color: #2f9f6b; }
.overview-item.ov-orange .ov-icon { color: var(--orange-500, #ea5a1a); }
.overview-item.ov-purple .ov-icon { color: #7a5bbf; }
.ov-label {
  font-size: 11.5px;
  color: var(--ink-muted);
}

/* 分类 */
.cat-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.cat-item {
  display: grid;
  grid-template-columns: 18px 70px 1fr 30px;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--ink);
}
.cat-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--orange-600, #c8480f);
}
.cat-name { font-weight: 600; }
.cat-bar {
  position: relative;
  height: 6px;
  border-radius: 999px;
  background: var(--paper-200, #fbf2e5);
  overflow: hidden;
}
.cat-bar i {
  position: absolute;
  inset: 0 auto 0 0;
  border-radius: 999px;
  display: block;
}
.cat-count {
  font-size: 11.5px;
  color: var(--ink-muted);
  text-align: right;
  font-weight: 700;
}

/* 最近访问 */
.recent-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.recent-item {
  display: grid;
  grid-template-columns: 24px 1fr auto;
  gap: 8px;
  align-items: center;
  font-size: 12px;
  color: var(--ink);
}
.recent-icon {
  width: 24px;
  height: 24px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  font-size: 11px;
}
.recent-icon.rk-pdf   { background: rgba(234, 90, 26, 0.12); color: var(--orange-600, #c8480f); }
.recent-icon.rk-video { background: rgba(74, 107, 133, 0.12); color: #4a6b85; }
.recent-icon.rk-mind  { background: rgba(122, 91, 191, 0.12); color: #7a5bbf; }
.recent-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 600;
}
.recent-time {
  font-size: 11px;
  color: var(--ink-muted);
  white-space: nowrap;
}

/* 上传入口 */
.upload-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
}
.upload-btn {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid transparent;
  cursor: pointer;
  text-align: left;
  transition: transform 0.15s, box-shadow 0.15s;
}
.upload-btn:hover { transform: translateY(-1px); }
.upload-btn.primary {
  background: linear-gradient(120deg, var(--orange-500, #ea5a1a), var(--orange-600, #c8480f));
  color: #fff;
  box-shadow: 0 10px 22px rgba(234, 90, 26, 0.22);
}
.upload-btn.ghost {
  background: var(--orange-50, #fff7ed);
  border-color: var(--orange-200, #fbcfa3);
  color: var(--orange-700, #9a3608);
}
.upload-icon {
  width: 36px;
  height: 36px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.25);
}
.upload-btn.ghost .upload-icon {
  background: rgba(234, 90, 26, 0.12);
  color: var(--orange-600, #c8480f);
}
.upload-text { display: flex; flex-direction: column; gap: 2px; }
.upload-text strong { font-size: 13px; font-weight: 700; }
.upload-text small { font-size: 11px; opacity: 0.85; }

/* AI */
.ai-card { background: linear-gradient(135deg, #fff7ed 0%, #fdf2e1 100%); border-color: var(--orange-200, #fbcfa3); }
.ai-row {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}
.ai-badge {
  flex: 0 0 auto;
  width: 36px;
  height: 36px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  background: linear-gradient(135deg, var(--orange-400, #f08441), var(--orange-600, #c8480f));
  color: #fff;
}
.ai-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--ink);
}
.ai-desc {
  margin-top: 2px;
  font-size: 11.5px;
  line-height: 1.5;
  color: var(--ink-muted);
}

/* 周推荐 */
.week-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.week-item {
  display: grid;
  grid-template-columns: 22px 1fr auto auto;
  gap: 8px;
  align-items: center;
  font-size: 12.5px;
  color: var(--ink);
  padding: 6px 0;
}
.week-rank {
  width: 22px;
  height: 22px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  font-weight: 800;
  font-size: 11px;
  color: #fff;
}
.week-rank.rank-1 { background: linear-gradient(135deg, #f08441, #ea5a1a); }
.week-rank.rank-2 { background: linear-gradient(135deg, #d89229, #c8480f); }
.week-rank.rank-3 { background: linear-gradient(135deg, #c8480f, #9a3608); }
.week-title { font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.week-views { font-size: 11.5px; color: var(--ink-muted); }
.week-star { color: var(--orange-500, #ea5a1a); }

/* 错误提示 */
.error-banner {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  background: rgba(220, 38, 38, 0.06);
  border: 1px solid rgba(220, 38, 38, 0.25);
  border-radius: 8px;
  color: #b91c1c;
  font-size: 12.5px;
}

/* 响应式 */
@media (max-width: 1180px) {
  .layout-two { grid-template-columns: 1fr; }
  .right-column { position: static; }
  .hero { grid-template-columns: 1fr; }
  .hero-visual { display: none; }
  .card-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 720px) {
  .search-input { width: 220px; }
  .card-grid { grid-template-columns: 1fr; }
}

/* ============== 预览弹窗 ============== */
.preview-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: rgba(40, 30, 15, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.preview-modal {
  position: relative;
  background: #ffffff;
  border-radius: 16px;
  padding: 24px;
  max-width: 860px;
  width: 100%;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 24px 60px rgba(40, 30, 15, 0.3);
}

.preview-close {
  position: absolute;
  top: 12px;
  right: 12px;
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  border: 1px solid var(--paper-400);
  background: #ffffff;
  color: var(--ink-muted);
  cursor: pointer;
  z-index: 1;
}

.preview-close:hover {
  background: var(--orange-soft, #fff0e4);
  color: var(--orange-600, #c8480f);
}

.preview-title {
  margin: 0 0 8px;
  font-size: 16px;
  font-weight: 700;
  color: var(--ink);
  padding-right: 40px;
  display: inline-flex;
  align-items: baseline;
  gap: 8px;
  flex-wrap: wrap;
}
.preview-personalized-note {
  margin: 0 0 12px;
  padding: 8px 12px;
  border-radius: 8px;
  background: linear-gradient(90deg, #fff7ed, #fff2e0);
  border: 1px solid #fbd8b3;
  color: #7a5a3a;
  font-size: 12px;
  line-height: 1.6;
}

/* 类型标识条 */
.preview-meta-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
}

.preview-type-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.3px;
  background: var(--orange-50, #fff7ed);
  color: var(--orange-700, #9a3608);
  border: 1px solid var(--orange-200, #fbcfa3);
}
.preview-type-badge.pt-image { background: rgba(234,90,26,.08); color: #ea5a1a; border-color: rgba(234,90,26,.25); }
.preview-type-badge.pt-audio { background: rgba(122,91,191,.10); color: #7a5bbf; border-color: rgba(122,91,191,.25); }
.preview-type-badge.pt-video { background: rgba(74,107,133,.10); color: #4a6b85; border-color: rgba(74,107,133,.25); }
.preview-type-badge.pt-text  { background: rgba(216,146,41,.10); color: #b87a10; border-color: rgba(216,146,41,.25); }
.preview-type-badge.pt-pptx  { background: rgba(200,72,15,.10); color: #c8480f; border-color: rgba(200,72,15,.25); }
.preview-type-badge.pt-unsupported { background: #f5f5f5; color: #999; border-color: #e0e0e0; }

.preview-rid {
  font-size: 11px;
  color: var(--ink-muted);
  font-family: monospace;
}

.preview-body {
  flex: 1;
  overflow: auto;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 240px;
}

.preview-img {
  max-width: 100%;
  max-height: 60vh;
  border-radius: 8px;
  border: 1px solid var(--paper-400);
}

/* 音频预览 */
.preview-audio-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
  padding: 30px 20px;
}
.preview-big-icon {
  font-size: 48px;
  line-height: 1;
}
.preview-hint {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--ink);
}
.preview-sub-hint {
  margin: 0;
  font-size: 12.5px;
  color: var(--ink-muted);
}
.preview-audio {
  width: 100%;
  max-width: 500px;
}

/* 视频预览 */
.preview-video-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  width: 100%;
}
.preview-video {
  max-width: 100%;
  max-height: 60vh;
  border-radius: 8px;
  border: 1px solid var(--paper-400);
}

/* 文本/代码预览 */
.preview-text-wrap {
  width: 100%;
}
.preview-code {
  margin: 0;
  padding: 16px;
  background: #1e1e2e;
  color: #cdd6f4;
  border-radius: 10px;
  font-family: 'Fira Code', 'Cascadia Code', 'Consolas', monospace;
  font-size: 12.5px;
  line-height: 1.6;
  overflow: auto;
  max-height: 55vh;
  white-space: pre-wrap;
  word-break: break-word;
}

/* Markdown 格式化预览（浅色背景） — 容器样式在 scoped 中，子元素样式见底部非 scoped 块 */
.preview-md {
  max-height: 60vh;
  overflow-y: auto;
  padding: 28px 32px;
  background: #faf9f6;
  border-radius: 10px;
  color: #2c2c2c;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Noto Sans SC', sans-serif;
  font-size: 14px;
  line-height: 1.8;
}

/* PPT / 不支持类型 */
.preview-pptx-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 36px 20px;
  text-align: center;
}
.preview-info-grid {
  margin-top: 10px;
  display: flex;
  gap: 20px;
  flex-wrap: wrap;
  justify-content: center;
}
.preview-info-item {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding: 8px 14px;
  border-radius: 8px;
  background: var(--orange-50, #fff7ed);
  border: 1px solid var(--paper-300);
}
.preview-info-item .label {
  font-size: 10.5px;
  color: var(--ink-muted);
  text-transform: uppercase;
  letter-spacing: 0.3px;
}
.preview-info-item .value {
  font-size: 12.5px;
  color: var(--ink);
  font-weight: 600;
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.preview-empty {
  font-size: 13px;
  color: var(--ink-muted);
  padding: 40px;
  text-align: center;
}

.preview-footer {
  margin-top: 14px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
  padding-top: 12px;
  border-top: 1px solid var(--paper-400);
}

.primary-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 18px;
  border-radius: 9px;
  background: var(--orange-500, #ea5a1a);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  border: none;
  cursor: pointer;
}

.primary-btn:hover {
  background: var(--orange-600, #c8480f);
}

.primary-btn.secondary {
  border: 1px solid var(--paper-500, #d8d0c4);
  background: #fff;
  color: var(--ink-soft, #4f4a43);
}

.primary-btn.secondary:hover {
  border-color: var(--orange-500, #ea5a1a);
  color: var(--orange-600, #c8480f);
}

.spin {
  animation: res-spin 1s linear infinite;
}

@keyframes res-spin {
  to { transform: rotate(360deg); }
}

/* 下载按钮禁用态 */
.act-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

/* ============== Toast 通知 ============== */
.res-toast {
  position: fixed;
  bottom: 28px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 10000;
  padding: 12px 24px;
  border-radius: 10px;
  background: #1e1e2e;
  color: #cdd6f4;
  font-size: 13px;
  font-weight: 500;
  box-shadow: 0 12px 32px rgba(0,0,0,0.25);
  max-width: 460px;
  text-align: center;
}

.toast-fade-enter-active,
.toast-fade-leave-active {
  transition: all 0.3s ease;
}
.toast-fade-enter-from,
.toast-fade-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(12px);
}

/* ============== 文件夹弹窗 ============== */
.folder-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: rgba(40, 30, 15, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.folder-modal {
  position: relative;
  background: #ffffff;
  border-radius: 14px;
  padding: 24px;
  width: 100%;
  max-width: 400px;
  box-shadow: 0 24px 60px rgba(40, 30, 15, 0.3);
}

.folder-modal-title {
  margin: 0 0 16px;
  font-size: 16px;
  font-weight: 700;
  color: var(--ink);
  padding-right: 40px;
}

.folder-input {
  width: 100%;
  padding: 10px 14px;
  border-radius: 9px;
  border: 1px solid var(--paper-400, #e8d5b8);
  background: #ffffff;
  font-size: 13.5px;
  color: var(--ink);
  outline: none;
  transition: border-color 0.15s;
}

.folder-input:focus {
  border-color: var(--orange-500, #ea5a1a);
}

.folder-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 16px;
}

.ghost-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 8px 16px;
  border-radius: 9px;
  border: 1px solid var(--paper-400, #e8d5b8);
  background: #ffffff;
  color: var(--ink);
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s;
}

.ghost-btn:hover {
  background: var(--orange-50, #fff7ed);
}

/* 上传按钮禁用态 */
.upload-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* AI 推荐列表 */
.ai-reco-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.ai-reco-item {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.6);
  border: 1px solid var(--paper-300, #f0e0cc);
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
}
.ai-reco-item:hover {
  background: var(--orange-50, #fff7ed);
  border-color: var(--orange-200, #fbcfa3);
}
.ai-badge.sm {
  width: 28px;
  height: 28px;
  flex-shrink: 0;
}
.ai-reco-body {
  min-width: 0;
  flex: 1;
}
.ai-reco-body .ai-title {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ai-reco-body .ai-desc {
  margin-top: 2px;
  font-size: 11px;
  line-height: 1.4;
  color: var(--ink-muted);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.ai-reco-tag {
  display: inline-block;
  margin-top: 4px;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 600;
  background: var(--orange-100, #ffe6cf);
  color: var(--orange-700, #9a3608);
}
.side-link.ai-refresh {
  background: none;
  border: none;
  cursor: pointer;
  font-family: inherit;
  padding: 0;
}
.side-link.ai-refresh:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>

<!-- 非 scoped 样式：v-html 注入的 Markdown 内容需要非 scoped 样式才能生效 -->
<style>
.preview-md h1 {
  font-size: 24px;
  font-weight: 700;
  margin: 24px 0 14px;
  padding-bottom: 8px;
  border-bottom: 2px solid #e0e0e0;
  color: #1a1a1a;
}
.preview-md h2 {
  font-size: 20px;
  font-weight: 700;
  margin: 22px 0 12px;
  padding-bottom: 6px;
  border-bottom: 1px solid #e8e8e8;
  color: #1a1a1a;
}
.preview-md h3 {
  font-size: 17px;
  font-weight: 600;
  margin: 18px 0 10px;
  color: #333;
}
.preview-md h4 {
  font-size: 15px;
  font-weight: 600;
  margin: 16px 0 8px;
  color: #444;
}
.preview-md h5,
.preview-md h6 {
  font-size: 14px;
  font-weight: 600;
  margin: 14px 0 6px;
  color: #555;
}
.preview-md .md-p {
  margin: 8px 0;
  color: #333;
}
.preview-md strong {
  font-weight: 700;
  color: #1a1a1a;
}
.preview-md em {
  font-style: italic;
  color: #555;
}
.preview-md .md-inline-code {
  padding: 2px 6px;
  background: #f0ede6;
  border-radius: 4px;
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: 12.5px;
  color: #c0392b;
}
.preview-md .md-code-block {
  margin: 12px 0;
  padding: 14px 16px;
  background: #f5f3ef;
  border: 1px solid #e0ddd6;
  border-radius: 8px;
  overflow-x: auto;
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: 12.5px;
  line-height: 1.6;
  color: #444;
}
.preview-md .md-code-block code {
  font-family: inherit;
}
.preview-md .md-ul,
.preview-md .md-ol {
  margin: 8px 0;
  padding-left: 24px;
}
.preview-md .md-ul .md-li {
  list-style: disc;
  margin: 4px 0;
  color: #333;
}
.preview-md .md-ol .md-oli {
  list-style: decimal;
  margin: 4px 0;
  color: #333;
}
.preview-md .md-quote {
  margin: 10px 0;
  padding: 8px 14px;
  border-left: 4px solid #e89a4c;
  background: #f8f5f0;
  border-radius: 0 6px 6px 0;
  color: #666;
  font-style: italic;
}
.preview-md a {
  color: #e88a30;
  text-decoration: none;
  border-bottom: 1px dashed #e89a4c;
}
.preview-md a:hover {
  color: #d97a20;
  border-bottom-style: solid;
}
.preview-md .md-hr {
  border: none;
  height: 1px;
  background: linear-gradient(to right, transparent, #ddd, transparent);
  margin: 20px 0;
}
.preview-md .md-empty {
  color: #999;
  text-align: center;
  padding: 40px 0;
}
.preview-md .md-table {
  width: 100%;
  border-collapse: collapse;
  margin: 12px 0;
  font-size: 13px;
}
.preview-md .md-table th,
.preview-md .md-table td {
  border: 1px solid #e0ddd6;
  padding: 8px 12px;
  text-align: left;
}
.preview-md .md-table th {
  background: #f5f3ef;
  font-weight: 600;
  color: #444;
}
.preview-md .md-table tr:nth-child(even) {
  background: #faf9f6;
}
.preview-md .md-img {
  max-width: 100%;
  height: auto;
  border-radius: 6px;
  margin: 12px 0;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}

/* ============================================================
 * teacher-skin 页级修正（配色由全局皮肤接管，这里只调排版）
 * ============================================================ */
.resources-page.teacher-skin { padding-bottom: 40px; }
.resources-page.teacher-skin .title-block h2 {
  font-family: "Source Han Serif SC", "Noto Serif SC", "Songti SC", Georgia, serif;
  font-size: 32px;
  font-weight: 600;
  letter-spacing: -0.01em;
  color: #181612;
}
.resources-page.teacher-skin .title-block p {
  font-size: 14px;
  color: #68635b;
}
</style>
