import { describe, expect, it } from "vitest";

import { agentAvatarFor } from "@/constants/agentAvatars";
import type { MobileMember } from "@/types";
import { buildAgentMentions, markdownToChatText } from "@/utils/chat";

const agents: MobileMember[] = [
  { user_id: "agent-planner", display_name: "智狐 · 规划伙伴", role: "agent", joined_at: 1 },
  { user_id: "agent-quiz", display_name: "小龙 · 练习伙伴", role: "agent", joined_at: 1 },
  { user_id: "ai-assistant", display_name: "智灵 · 讲解伙伴", role: "agent", joined_at: 1 },
];

describe("mobile chat agents", () => {
  it("routes ordinary messages to the tutor and named mentions to their agent", () => {
    expect(buildAgentMentions("你好", agents)).toEqual(["ai-assistant"]);
    expect(buildAgentMentions("@小龙 请出一道题", agents)).toEqual(["agent-quiz"]);
  });

  it("uses the established avatar for each agent", () => {
    expect(agentAvatarFor("agent-planner")).toBe("/avatars/zhihu.png");
    expect(agentAvatarFor("agent-quiz")).toBe("/avatars/xiaolong.png");
  });

  it("shows historical agent Markdown as plain chat text", () => {
    const markdown = "### 分析\n**重点**<br>| 方向 | 建议 |\n|---|---|\n| 复习 | 做题 |";
    expect(markdownToChatText(markdown)).toBe("分析\n重点\n方向 · 建议\n复习 · 做题");
  });
});
