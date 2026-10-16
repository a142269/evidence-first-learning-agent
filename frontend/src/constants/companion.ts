export interface CompanionPartner {
  key: string;
  name: string;
  title: string;
  role: string;
  avatar: string;
  accent: string;
  state: string;
  status: "done" | "running" | "queue";
}

export interface CompanionNavItem {
  id: string;
  label: string;
  icon: "chat" | "path" | "library" | "partners" | "profile" | "lab";
}

export interface CompanionResource {
  type: string;
  typeKey: "doc" | "ppt" | "video" | "quiz" | "code" | "anim" | "mind";
  tag: string;
  title: string;
  desc: string;
  author: string;
  meta: string;
}

export const partners: CompanionPartner[] = [
  { key: "planner", name: "智狐", title: "学习规划师", role: "任务规划 · 路径编排", avatar: "/avatars/zhihu.png", accent: "#ea5a1a", state: "在线", status: "done" },
  { key: "tutor", name: "智灵", title: "知识讲师", role: "知识讲解 · 答疑引导", avatar: "/avatars/zhiling.png", accent: "#2f9f6b", state: "在线", status: "running" },
  { key: "content", name: "阿匠", title: "内容工匠", role: "资料生成 · 资源制作", avatar: "/avatars/ajiang.png", accent: "#d89229", state: "在线", status: "running" },
  { key: "quiz", name: "小龙", title: "小龙挑战", role: "题库生成 · 难度分层", avatar: "/avatars/xiaolong.png", accent: "#8f5b32", state: "忙碌中", status: "queue" },
  { key: "evaluation", name: "团团", title: "熊猫评分", role: "学习评估 · 效果反馈", avatar: "/avatars/tuantuan.png", accent: "#4a8c78", state: "在线", status: "running" },
  { key: "safety", name: "球球", title: "刺猬守护", role: "安全审核 · 防幻觉校验", avatar: "/avatars/qiuqiu.png", accent: "#3b7f88", state: "在线", status: "done" },
];

export const demoLearner: CompanionPartner = {
  key: "student",
  name: "杜同学",
  title: "学习者",
  role: "提问 · 学习 · 反馈",
  avatar: "/avatars/demo-learner.png",
  accent: "#ea5a1a",
  state: "在线",
  status: "running",
};

/** 教师身份的展示形象。不复用学生头像，避免王老师与杜同学撞脸。 */
export const teacherPartner: CompanionPartner = {
  key: "teacher",
  name: "王老师",
  title: "教师",
  role: "答疑 · 指派资源 · 推荐路径",
  avatar: "/avatars/wang-teacher.svg",
  accent: "#6c5cab",
  state: "在线",
  status: "done",
};

const GENERIC_LEARNER_NAMES = new Set([
  "",
  "演示学习者",
  "张三",
  "小明",
  "demo-student-1",
  "demo-student-21",
]);

/**
 * 按真实学生 ID 返回展示身份。杜同学沿用照片头像；林同学使用独立的
 * 蓝色姓名头像，避免双学生演示时仍像同一个账号。
 */
export function getLearnerPartner(
  userId = "demo-student-1",
  displayName = "",
): CompanionPartner {
  const isLin = userId === "demo-student-21";
  const fallbackName = isLin ? "林同学" : "杜同学";
  const normalizedName = String(displayName || "").trim();
  const mismatchedDemoName = isLin
    ? normalizedName === "杜同学"
    : normalizedName === "林同学";
  const name = GENERIC_LEARNER_NAMES.has(normalizedName) || mismatchedDemoName
    ? fallbackName
    : normalizedName;

  return {
    ...demoLearner,
    name,
    avatar: isLin ? "/avatars/lin-learner.svg" : "/avatars/demo-learner.png",
    accent: isLin ? "#356b82" : "#ea5a1a",
  };
}

export const navItems: CompanionNavItem[] = [
  { id: "cockpit", label: "群聊协作", icon: "chat" },
  { id: "path", label: "学习路径", icon: "path" },
  { id: "resources", label: "资源库", icon: "library" },
  { id: "workflow", label: "伙伴编排", icon: "partners" },
  { id: "profile", label: "学习画像", icon: "profile" },
  { id: "lab", label: "桃园学宫", icon: "lab" },
];

export const resources: CompanionResource[] = [
  { type: "文档", typeKey: "doc", tag: "推荐", title: "机器学习基础_课程讲义", desc: "系统介绍机器学习的基本概念、常见算法与学习路线。", author: "阿匠", meta: "Markdown · 32KB" },
  { type: "PPT", typeKey: "ppt", tag: "推荐", title: "机器学习基础_全流程解析.pptx", desc: "从数据到模型：机器学习项目全流程拆解。", author: "智狐", meta: "PPTX · 18.6MB" },
  { type: "视频", typeKey: "video", tag: "视频", title: "线性回归算法_动画讲解.mp4", desc: "直观理解线性回归的原理与实现过程。", author: "智灵", meta: "MP4 · 24:35" },
  { type: "题库", typeKey: "quiz", tag: "题库", title: "机器学习基础_练习题库", desc: "包含选择题、填空题、简答题及编程题。", author: "小龙", meta: "10题 · 3种难度" },
  { type: "代码", typeKey: "code", tag: "代码案例", title: "K-Means算法_代码实现.py", desc: "使用 Python 从零实现 K-Means 聚类。", author: "阿匠", meta: "Python · 4.8KB" },
  { type: "动画", typeKey: "anim", tag: "动画", title: "K-Means聚类_原理演示.html", desc: "动态可视化展示 K-Means 聚类过程。", author: "智灵", meta: "HTML · 980KB" },
  { type: "思维导图", typeKey: "mind", tag: "推荐", title: "机器学习_知识图谱总览.mind", desc: "梳理机器学习核心概念之间的关联与依赖。", author: "团团", meta: "PNG · 1.2MB" },
];

export const resourceTypeKeys = ["doc", "ppt", "video", "quiz", "code", "anim", "mind"] as const;
export const resourceTypeNameMap: Record<string, CompanionResource["typeKey"]> = {
  文档: "doc",
  PPT: "ppt",
  视频: "video",
  题库: "quiz",
  代码: "code",
  动画: "anim",
  思维导图: "mind",
};

export interface LabSceneHotspot {
  id: string;
  label: string;
  action: string;
}

export interface LabScene {
  id: string;
  partnerId: string;
  label: string;
  title: string;
  interiorImage: string;
  bounds: { minX: number; maxX: number; minY: number; maxY: number };
  hotspots: LabSceneHotspot[];
}

export const labSceneConfig: LabScene[] = [
  {
    id: "library",
    partnerId: "planner",
    label: "图书馆",
    title: "图书馆 · 学习规划中枢",
    interiorImage: "/pixel-campus/interiors/library-interior.png",
    bounds: { minX: 43, maxX: 57, minY: 34, maxY: 47 },
    hotspots: [
      { id: "plan", label: "学习路径", action: "生成今日学习路线" },
      { id: "archive", label: "知识库", action: "查看沉淀资料" },
      { id: "reading", label: "拓展阅读", action: "推荐延伸材料" },
    ],
  },
  {
    id: "teaching",
    partnerId: "quiz",
    label: "教学楼 A",
    title: "教学楼 A · 闯关教室",
    interiorImage: "/pixel-campus/interiors/teaching-interior.png",
    bounds: { minX: 14, maxX: 25, minY: 43, maxY: 58 },
    hotspots: [
      { id: "quiz", label: "练习挑战", action: "生成练习题" },
      { id: "blackboard", label: "课堂板书", action: "整理章节重点" },
      { id: "review", label: "错题回顾", action: "查看薄弱点" },
    ],
  },
  {
    id: "lab",
    partnerId: "content",
    label: "实验楼",
    title: "实验楼 · 资源生成工坊",
    interiorImage: "/pixel-campus/interiors/lab-interior.png",
    bounds: { minX: 78, maxX: 89, minY: 45, maxY: 60 },
    hotspots: [
      { id: "courseware", label: "课件生成", action: "制作课程资料" },
      { id: "code", label: "代码案例", action: "生成实践案例" },
      { id: "dataset", label: "实验数据", action: "准备实验素材" },
    ],
  },
  {
    id: "study",
    partnerId: "safety",
    label: "自习空间",
    title: "自习空间 · 内容守护站",
    interiorImage: "/pixel-campus/interiors/study-interior.png",
    bounds: { minX: 13, maxX: 25, minY: 70, maxY: 84 },
    hotspots: [
      { id: "guard", label: "内容巡检", action: "检查生成内容" },
      { id: "citation", label: "引用核查", action: "补全资料来源" },
      { id: "focus", label: "专注模式", action: "开启学习守护" },
    ],
  },
  {
    id: "life",
    partnerId: "evaluation",
    label: "学生活动中心",
    title: "学生活动中心 · 测评反馈站",
    interiorImage: "/pixel-campus/interiors/activity-interior.png",
    bounds: { minX: 78, maxX: 91, minY: 71, maxY: 86 },
    hotspots: [
      { id: "score", label: "学习测评", action: "分析学习效果" },
      { id: "badge", label: "近期成果", action: "查看成长徽章" },
      { id: "advice", label: "改进建议", action: "生成调整方案" },
    ],
  },
  {
    id: "lawn",
    partnerId: "tutor",
    label: "中央草坪学习区",
    title: "中央草坪 · 知识讲解区",
    interiorImage: "/pixel-campus/interiors/lawn-interior.png",
    bounds: { minX: 45, maxX: 59, minY: 55, maxY: 72 },
    hotspots: [
      { id: "lecture", label: "重点讲解", action: "讲解核心知识" },
      { id: "question", label: "即时答疑", action: "回答学习问题" },
      { id: "mindmap", label: "思维导图", action: "生成知识结构" },
    ],
  },
];

export function getLabSceneById(id: string): LabScene | null {
  return labSceneConfig.find((scene) => scene.id === id) ?? null;
}

export function getLabSceneByPartnerId(partnerId: string): LabScene | null {
  return labSceneConfig.find((scene) => scene.partnerId === partnerId) ?? null;
}
