const AGENT_AVATAR_BY_ID: Record<string, string> = {
  "agent-planner": "/avatars/zhihu.png",
  "agent-content": "/avatars/ajiang.png",
  "ai-assistant": "/avatars/zhiling.png",
  "agent-quiz": "/avatars/xiaolong.png",
  "agent-evaluation": "/avatars/tuantuan.png",
  "agent-safety": "/avatars/qiuqiu.png",
};

const AGENT_AVATAR_BY_NAME: Array<[string, string]> = [
  ["智狐", "/avatars/zhihu.png"],
  ["阿匠", "/avatars/ajiang.png"],
  ["智灵", "/avatars/zhiling.png"],
  ["学习助理", "/avatars/zhiling.png"],
  ["小龙", "/avatars/xiaolong.png"],
  ["团团", "/avatars/tuantuan.png"],
  ["球球", "/avatars/qiuqiu.png"],
];

export function agentAvatarFor(userId: string, displayName = "") {
  const byId = AGENT_AVATAR_BY_ID[userId];
  if (byId) return byId;
  return AGENT_AVATAR_BY_NAME.find(([name]) => displayName.includes(name))?.[1] ?? "/avatars/zhiling.png";
}
