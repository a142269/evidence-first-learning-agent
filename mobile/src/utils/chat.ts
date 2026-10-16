import type { MobileMember } from "@/types";

export function shortMemberName(member: MobileMember) {
  return member.display_name.split(" · ")[0];
}

export function buildAgentMentions(content: string, agents: MobileMember[]) {
  const lowered = content.toLowerCase();
  const ids = agents
    .filter((member) => lowered.includes(`@${shortMemberName(member).toLowerCase()}`))
    .map((member) => member.user_id);
  if (lowered.includes("@ai") && !ids.includes("ai-assistant")) ids.push("ai-assistant");
  return ids.length ? ids : ["ai-assistant"];
}

export function markdownToChatText(raw: string) {
  const lines = String(raw ?? "")
    .replace(/\r\n?/g, "\n")
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/```[^\n]*\n?/g, "")
    .replace(/!\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/<[^>]+>/g, "")
    .split("\n")
    .map((source) => {
      let line = source.replace(/^\s{0,3}#{1,6}\s*/, "").replace(/^\s*>+\s?/, "");
      if (/^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(line)) return "\u0000";
      if ((line.match(/\|/g)?.length ?? 0) >= 2) {
        line = line.trim().replace(/^\||\|$/g, "").split("|").map((cell) => cell.trim()).filter(Boolean).join(" · ");
      }
      return line.replace(/^\s*[-+*]\s+/, "• ").trimEnd();
    })
    .filter((line) => line !== "\u0000");

  return lines
    .join("\n")
    .replace(/(\*\*|__)(.*?)\1/gs, "$2")
    .replace(/(?<!\*)\*([^*\n]+)\*(?!\*)/g, "$1")
    .replace(/(?<!_)_([^_\n]+)_(?!_)/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/~~([^~]+)~~/g, "$1")
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}
