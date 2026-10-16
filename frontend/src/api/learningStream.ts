export interface LearningEvent {
  name: string;
  data: Record<string, any>;
}

/** Parse SSE across arbitrary byte boundaries, including split UTF-8 / CRLF. */
export async function consumeLearningStream(
  stream: ReadableStream<Uint8Array>, onEvent: (event: LearningEvent) => void,
): Promise<void> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let terminal = false;
  try {
    while (true) {
      const { done, value } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      let match: RegExpExecArray | null;
      while ((match = /\r?\n\r?\n/.exec(buffer))) {
        const block = buffer.slice(0, match.index);
        buffer = buffer.slice(match.index + match[0].length);
        const lines = block.split(/\r?\n/);
        const name = lines.find(line => line.startsWith("event:"))?.slice(6).trim() || "message";
        const data = lines.filter(line => line.startsWith("data:")).map(line => line.slice(5).trimStart()).join("\n");
        if (!data) continue;
        const parsed = JSON.parse(data);
        if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) throw new Error("invalid_stream_event");
        if (terminal) throw new Error("event_after_terminal");
        onEvent({ name, data: parsed });
        terminal = ["run.completed", "run.failed", "review.required"].includes(name);
      }
      if (buffer.length > 1_000_000) throw new Error("stream_event_too_large");
      if (done) break;
    }
    if (!terminal) throw new Error("stream_incomplete");
  } finally {
    await reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
}
