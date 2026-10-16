export interface CockpitTab {
  id: "chat" | "tasks" | "files" | "knowledge" | "profile";
  label: string;
}

export const cockpitTabs: CockpitTab[] = [
  { id: "chat", label: "群聊" },
  { id: "tasks", label: "任务流" },
  { id: "files", label: "文件" },
  { id: "knowledge", label: "知识库" },
  { id: "profile", label: "学习画像" },
];

interface PartnerMention {
  keyword: string;
  partnerKey: string;
  name: string;
  focus: string;
}

const partnerMentions: PartnerMention[] = [
  { keyword: "智灵", partnerKey: "tutor", name: "智灵", focus: "知识讲解" },
  { keyword: "阿匠", partnerKey: "content", name: "阿匠", focus: "资料生成" },
  { keyword: "小龙", partnerKey: "quiz", name: "小龙", focus: "练习设计" },
  { keyword: "团团", partnerKey: "evaluation", name: "团团", focus: "学习评估" },
  { keyword: "球球", partnerKey: "safety", name: "球球", focus: "内容校验" },
  { keyword: "智狐", partnerKey: "planner", name: "智狐", focus: "任务规划" },
];

export interface InlineResourcePayload {
  type?: string;
  typeKey?: string;
  title: string;
  desc: string;
  action?: string;
}

export type CockpitAttachment =
  | { type: "tasks" }
  | { type: "resource"; payload: InlineResourcePayload };

export interface CockpitMessage {
  id: string;
  sender: "student" | "partner";
  time: string;
  name?: string;
  partnerKey?: string;
  text: string;
  attachment?: CockpitAttachment;
  pending?: boolean;
}

const initialMessages: CockpitMessage[] = [
  {
    id: "student-0930",
    sender: "student",
    time: "09:30",
    name: "杜同学",
    text: "@全体 帮我生成“机器学习基础”学习资料，包括知识讲解、PPT、练习题和学习路径规划。",
  },
  {
    id: "planner-0930",
    sender: "partner",
    partnerKey: "planner",
    time: "09:30",
    text: "收到。我将拆解任务，并交给最合适的学习伙伴处理。",
    attachment: { type: "tasks" },
  },
  {
    id: "tutor-0931",
    sender: "partner",
    partnerKey: "tutor",
    time: "09:31",
    text: "知识点梳理完成。这是《机器学习基础》核心知识点讲解：",
    attachment: {
      type: "resource",
      payload: {
        title: "监督学习 vs 无监督学习",
        desc: "详细对比两种学习范式的定义、特点、常见算法及应用场景。",
      },
    },
  },
  {
    id: "content-0932",
    sender: "partner",
    partnerKey: "content",
    time: "09:32",
    text: "PPT课件已生成完毕。",
    attachment: {
      type: "resource",
      payload: {
        typeKey: "ppt",
        title: "机器学习基础_课程课件.pptx",
        desc: "18.6 MB · 可加入学习路径",
        action: "下载",
      },
    },
  },
  {
    id: "quiz-0933",
    sender: "partner",
    partnerKey: "quiz",
    time: "09:33",
    text: "练习题已生成，共10题，分为基础 / 进阶 / 挑战三种难度。",
    attachment: {
      type: "resource",
      payload: {
        typeKey: "quiz",
        title: "机器学习基础_练习题库",
        desc: "10题 ｜ 3种难度",
        action: "在线练习",
      },
    },
  },
];

export function createInitialCockpitMessages(): CockpitMessage[] {
  return initialMessages.map((message) => ({
    ...message,
    attachment: message.attachment
      ? message.attachment.type === "resource"
        ? { type: "resource", payload: { ...message.attachment.payload } }
        : { type: "tasks" }
      : undefined,
  }));
}

export function pickReplyPartner(text: string): PartnerMention {
  return (
    partnerMentions.find((partner) => text.includes(`@${partner.keyword}`) || text.includes(partner.keyword)) ??
    partnerMentions[5]
  );
}

export function appendCockpitMessage(
  messages: CockpitMessage[],
  text: string,
  options: { time?: string } = {},
): CockpitMessage[] {
  const trimmed = text.trim();
  if (!trimmed) return messages;

  const time = options.time ?? "现在";
  const partner = pickReplyPartner(trimmed);
  const stamp = Date.now();

  return [
    ...messages,
    {
      id: `student-${stamp}`,
      sender: "student",
      time,
      name: "杜同学",
      text: trimmed,
    },
    {
      id: `partner-${partner.partnerKey}-${stamp}`,
      sender: "partner",
      partnerKey: partner.partnerKey,
      time,
      text: `${partner.name}已接收，我会优先处理${partner.focus}，并把结果同步到任务流与资源区。`,
      pending: true,
    },
  ];
}
