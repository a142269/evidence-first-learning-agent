/**
 * Agent Avatar 映射 · Plan 1.1 / 1.3 / 3.2 唯一真相源
 *
 * 2026-07-04 Plan D · 用户确认的 6 个 Agent 角色映射 + ProfileAgent emoji fallback
 *
 * 设计原则
 * =========
 * 1. 不复制 agentTypes.ts —— 保持旧代码兼容，AgentTracePanel 用此映射
 * 2. Avatar 组件对不存在 png 的 Agent（ProfileAgent）走 emoji fallback
 * 3. emoji 字段确保气泡 / 列表 / 折叠面板在任何地方渲染都能拿到一致的形象
 */
export type AvatarKind =
  | "planner"
  | "content"
  | "tutor"
  | "quiz"
  | "evaluation"
  | "safety"
  | "profile";

export interface AvatarEntry {
  kind: AvatarKind;
  /** 中文昵称（用户确认） */
  nick: string;
  /** 中文角色（用户确认） */
  role: string;
  /** 英文身份（用户确认） */
  englishName: string;
  /** 一句话职责 */
  responsibility: string;
  /** PNG 头像的相对路径；为 null 时走 emoji fallback */
  png: string | null;
  /** fallback emoji（同时用于列表 / Hover 提示） */
  emoji: string;
  /** 主色调（hex），方便 AgentTracePanel 上色 */
  color: string;
}

/**
 * 6 Agent 头像映射（用户确认）。
 * 头像 PNG 路径沿用已有 `frontend/public/integrated-map/avatars/*.png`。
 */
export const AGENT_AVATARS: Record<AvatarKind, AvatarEntry> = {
  planner: {
    kind: "planner",
    nick: "智狐",
    role: "规划伙伴",
    englishName: "Planner Agent",
    responsibility:
      "任务规划专家 —— 根据学习画像、课程进度和薄弱点，生成动态学习路径和今日任务优先级",
    png: "/integrated-map/avatars/zhihu.png",
    emoji: "🦊",
    color: "#D97706",
  },
  content: {
    kind: "content",
    nick: "阿匠",
    role: "资源伙伴",
    englishName: "Content Agent",
    responsibility:
      "内容生成专家 —— 把知识点转换成讲义、PPT、动画、代码案例等多模态资源",
    png: "/integrated-map/avatars/ajiang.png",
    emoji: "🦫",
    color: "#0EA5E9",
  },
  tutor: {
    kind: "tutor",
    nick: "智灵",
    role: "讲解伙伴",
    englishName: "Tutor Agent",
    responsibility:
      "知识讲解专家 —— 围绕线性回归、决策树等重点难点即时讲解 + 图解式答疑",
    png: "/integrated-map/avatars/zhiling.png",
    emoji: "🦉",
    color: "#8B5CF6",
  },
  quiz: {
    kind: "quiz",
    nick: "小龙",
    role: "练习伙伴",
    englishName: "Quiz Agent",
    responsibility:
      "题库生成专家 —— 按「基础 / 进阶 / 挑战」三档难度出题，支持即时反馈与错题闭环",
    png: "/integrated-map/avatars/xiaolong.png",
    emoji: "🐉",
    color: "#DC2626",
  },
  evaluation: {
    kind: "evaluation",
    nick: "团团",
    role: "评估伙伴",
    englishName: "Evaluation Agent",
    responsibility:
      "学习评估专家 —— 根据练习记录、学习时长、资源反馈，评估能力变化并调整计划",
    png: "/integrated-map/avatars/tuantuan.png",
    emoji: "🐼",
    color: "#059669",
  },
  safety: {
    kind: "safety",
    nick: "球球",
    role: "守护伙伴",
    englishName: "Safety Agent",
    responsibility:
      "内容安全卫士 —— 事实性校验、敏感内容过滤、引用完整性检查，降低幻觉风险",
    png: "/integrated-map/avatars/qiuqiu.png",
    emoji: "🦔",
    color: "#F59E0B",
  },
  profile: {
    kind: "profile",
    nick: "画像",
    role: "画像分析师",
    englishName: "Profile Agent",
    responsibility:
      "学习画像专家 —— 从对话中自动提取 8 维画像 / 9 种学习者分型，驱动个性化路径",
    png: null,
    emoji: "🎯",
    color: "#EC4899",
  },
};

/**
 * 后端 agents_invoked 字符串列表 → 前端 AvatarKind 映射
 *
 * 后端传来形如 ["planner_agent", "course_expert", "tutor_agent"]
 * 我们归一化到 kind
 */
const BACKEND_NAME_TO_KIND: Record<string, AvatarKind> = {
  planner_agent: "planner",
  course_expert: "content",
  content_agent: "content",
  tutor_agent: "tutor",
  quiz_agent: "quiz",
  quiz_generator: "quiz",
  evaluator_agent: "evaluation",
  evaluator: "evaluation",
  safety_agent: "safety",
  cov_verifier: "safety",
  reviewer_agent: "evaluation",
  critic_agent: "evaluation",
  debate_moderator: "evaluation",
  profile_agent: "profile",
  textbook_qa_agent: "content",
  multimodal_agent: "content",
  path_planner_agent: "planner",
  safe_decline: "safety",
  safe_decline_agent: "safety",
  doc_gen: "content",
  exercise: "quiz",
  resource_generator: "content",
  resource_generator_agent: "content",
  // —— 后端 orchestrator._run_agent 会把 response.agent_name 覆写为
  //    AGENT_ROUTING 中的 agent 键（如 "tutor"、"mindmap"、"path_planner"），
  //    这些裸名必须在此映射，否则 normalizeAgentNames 返回空数组，
  //    前端回退到默认 tutor（智灵），导致"发什么都显示智灵"。
  tutor: "tutor",
  profile: "profile",
  path_planner: "planner",
  mindmap: "content",
  video: "content",
  audio: "content",
  reading: "content",
};

/**
 * 把后端 agents_invoked 数组归一为前端 AvatarKind 数组，去重保序
 */
export function normalizeAgentNames(names: string[]): AvatarKind[] {
  const seen = new Set<AvatarKind>();
  const out: AvatarKind[] = [];
  for (const raw of names) {
    const norm = raw.toLowerCase().replace(/[\s-]+/g, "_");
    const kind = BACKEND_NAME_TO_KIND[norm];
    if (!kind) continue;
    if (seen.has(kind)) continue;
    seen.add(kind);
    out.push(kind);
  }
  return out;
}

/**
 * 一个安全的 lookup，不会因为没有 png 而炸
 */
export function getAvatar(kind: AvatarKind): AvatarEntry {
  return AGENT_AVATARS[kind] ?? AGENT_AVATARS.profile;
}

// ============================================================
// 前端预推断 —— 在 SSE meta 事件到来前，根据 @ 提及 / 关键词
// 猜测最可能的 Agent，避免思考阶段错误地显示智灵。
// 与后端 orchestrator._classify_intent 的关键词表保持同步。
// ============================================================

/** @ 提及 → AvatarKind 映射（与后端 mentions 字典一致） */
const MENTION_TO_KIND: Record<string, AvatarKind> = {
  "@阿匠": "content",
  "@智狐": "planner",
  "@智灵": "tutor",
  "@小龙": "quiz",
  "@团团": "evaluation",
  "@球球": "safety",
};

/** 返回消息里所有显式 @ 的 Agent，去重并保留文本出现顺序。 */
export function getMentionedAgentKinds(message: string): AvatarKind[] {
  if (!message) return [];
  return Object.entries(MENTION_TO_KIND)
    .filter(([mention]) => message.includes(mention))
    .sort(([a], [b]) => message.indexOf(a) - message.indexOf(b))
    .map(([, kind]) => kind);
}

/** 关键词 → AvatarKind 映射（精简版，只取高置信度关键词） */
const KEYWORD_TO_KIND: Array<{ keywords: string[]; kind: AvatarKind }> = [
  { keywords: ["思维导图", "脑图", "知识图谱", "画个图"], kind: "content" },
  { keywords: ["题目", "练习", "测试", "习题", "出题", "考考我", "刷题"], kind: "quiz" },
  { keywords: ["学习计划", "路径", "下一步", "怎么学", "帮我规划", "学习路线"], kind: "planner" },
  { keywords: ["诊断", "评估", "测评", "水平", "掌握了吗", "薄弱"], kind: "evaluation" },
  { keywords: ["视频", "动画", "演示", "做个动图"], kind: "content" },
  { keywords: ["扩展", "拓展阅读", "参考资料", "延伸材料", "论文"], kind: "content" },
  { keywords: ["讲解", "文档", "笔记", "讲义", "课件", "资料", "ppt", "代码"], kind: "content" },
  { keywords: ["为什么", "怎么办", "不太懂", "什么是", "怎么理解", "教我"], kind: "tutor" },
];

/**
 * 根据用户消息预推断最可能的 Agent kind。
 *
 * 优先级：@ 提及 > 关键词匹配 > null（未知）
 *
 * @returns AvatarKind 或 null（无法预判时）
 */
export function guessAgentFromMessage(message: string): AvatarKind | null {
  if (!message) return null;

  // 1. @ 提及（最高优先级）
  const mentioned = getMentionedAgentKinds(message);
  if (mentioned.length) return mentioned[0];

  // 2. 关键词匹配（按优先级顺序，命中即返回）
  for (const { keywords, kind } of KEYWORD_TO_KIND) {
    if (keywords.some((kw) => message.includes(kw))) return kind;
  }

  // 3. 无法预判
  return null;
}
