const RESOURCE_TYPE_LABELS: Record<string, string> = {
  document: "文档",
  doc: "文档",
  txt: "文本文档",
  markdown: "Markdown 文档",
  md: "Markdown 文档",
  reading: "拓展阅读",
  prompt: "学习提示",
  video: "视频",
  mp4: "视频",
  manim: "动画视频",
  audio: "音频",
  mp3: "音频",
  tts: "语音讲解",
  quiz: "练习题库",
  question_bank: "练习题库",
  ppt: "演示文稿",
  pptx: "演示文稿",
  mindmap: "思维导图",
  mermaid: "Mermaid 图表",
  mermaid_png: "思维导图图片",
  graph: "知识图谱",
  knowledge_graph: "知识图谱",
  image: "图片",
  png: "图片",
  svg: "矢量图",
  code: "代码示例",
  tutoring: "辅导答疑",
  evaluation_report: "学习评估报告",
  report: "学习报告",
  chat: "聊天记录",
  folder: "文件夹",
  file: "其他资源",
};

const RESOURCE_AGENT_LABELS: Record<string, string> = {
  tutor: "辅导教师",
  tutor_agent: "辅导教师",
  evaluator: "学习评估员",
  evaluator_agent: "学习评估员",
  resource_generator: "资源生成助手",
  resource_generator_agent: "资源生成助手",
  course_expert: "课程专家",
  quiz_generator: "习题生成助手",
  multimodal: "多模态资源助手",
  planner: "学习规划师",
  teacher: "课程教师",
  system: "系统",
};

// 兼容历史数据示例："What is gradient descent?" → "什么是梯度下降？"；
// "Use Socratic questions to help" → "使用苏格拉底式提问进行引导"；"??" → "问题待补充"。
const TEXT_REPLACEMENTS: Array<[RegExp, string]> = [
  [/What is gradient descent\?/gi, "什么是梯度下降？"],
  [/Use Socratic questions to help/gi, "使用苏格拉底式提问进行引导"],
  [/generated document resource/gi, "生成的文档资源"],
  [/generated\s+resource/gi, "生成的资源"],
  [/documento/gi, "文档"],
  [/gradient descent/gi, "梯度下降"],
  [/Socratic questions/gi, "苏格拉底式提问"],
  [/\bdocument\b/gi, "文档"],
  [/\btutoring\b/gi, "辅导"],
  [/\bevaluation report\b/gi, "学习评估报告"],
];

function normalizedKey(value: unknown): string {
  return String(value ?? "")
    .trim()
    .toLowerCase()
    .replace(/[\s-]+/g, "_");
}

function hasChinese(value: string): boolean {
  return /[\u3400-\u9fff]/.test(value);
}

export function resourceTypeLabel(type: unknown): string {
  const raw = String(type ?? "").trim();
  const key = normalizedKey(raw);
  if (!key) return "其他资源";
  if (RESOURCE_TYPE_LABELS[key]) return RESOURCE_TYPE_LABELS[key];
  if (key.includes("mermaid")) return key.includes("png") ? "思维导图图片" : "Mermaid 图表";
  if (key.includes("ppt")) return "演示文稿";
  if (key.includes("audio") || key.includes("mp3") || key.includes("tts")) return "音频";
  if (key.includes("video") || key.includes("mp4") || key.includes("manim")) return "视频";
  if (key.includes("image") || key.includes("png") || key.includes("svg")) return "图片";
  if (key.includes("quiz") || key.includes("question")) return "练习题库";
  if (key.includes("code")) return "代码示例";
  if (key.includes("tutor")) return "辅导答疑";
  return hasChinese(raw) ? raw : "其他资源";
}

export function resourceAgentLabel(agent: unknown): string {
  const raw = String(agent ?? "").trim();
  const key = normalizedKey(raw);
  if (!key) return "系统";
  if (RESOURCE_AGENT_LABELS[key]) return RESOURCE_AGENT_LABELS[key];
  if (key.includes("tutor")) return "辅导教师";
  if (key.includes("evaluat")) return "学习评估员";
  if (key.includes("resource") && key.includes("generat")) return "资源生成助手";
  return hasChinese(raw) || /^(AI|RAG|CNN|MLP)$/i.test(raw) ? raw : "智能学习助手";
}

export function localizeResourceText(value: unknown, fallback = "未命名资源"): string {
  let text = String(value ?? "").trim();
  if (!text) return fallback;
  if (/^[\s?？!！._-]+$/.test(text)) return text.includes("?") || text.includes("？") ? "问题待补充" : fallback;

  for (const [pattern, replacement] of TEXT_REPLACEMENTS) {
    text = text.replace(pattern, replacement);
  }

  text = text
    .replace(/答疑\s*[:：]\s*(?:\?\?|问题待补充)/gi, "答疑：问题待补充")
    .replace(/生成的\s*文档\s*资源/gi, "生成的文档资源")
    .replace(/\s{2,}/g, " ")
    .trim();

  return text || fallback;
}

export function localizeResourceTags(tags: unknown[]): string[] {
  return tags
    .map((tag) => {
      const raw = String(tag ?? "").trim();
      if (!raw) return "";
      const key = normalizedKey(raw);
      if (RESOURCE_AGENT_LABELS[key]) return RESOURCE_AGENT_LABELS[key];
      const typeLabel = resourceTypeLabel(raw);
      if (typeLabel !== "其他资源" || key === "file") return typeLabel;
      const agentLabel = resourceAgentLabel(raw);
      if (agentLabel !== "智能学习助手") return agentLabel;
      return localizeResourceText(raw, "");
    })
    .filter(Boolean);
}
