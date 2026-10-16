export type AgentKind =
  | "planner"
  | "content"
  | "tutor"
  | "safety"
  | "evaluation"
  | "quiz"
  | "learner";

export type AgentMood = "idle" | "thinking" | "talking" | "celebrating";

export interface AgentInfo {
  kind: AgentKind;
  name: string;
  english: string;
}

export const AGENT_ROSTER: AgentInfo[] = [
  { kind: "planner", name: "小狐规划", english: "Planner Agent" },
  { kind: "content", name: "河狸工匠", english: "Content Agent" },
  { kind: "tutor", name: "猫头讲师", english: "Tutor Agent" },
  { kind: "safety", name: "刺猬守护", english: "Safety Agent" },
  { kind: "evaluation", name: "熊猫评分", english: "Evaluation Agent" },
  { kind: "quiz", name: "小龙挑战", english: "Quiz Agent" },
];
