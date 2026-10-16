import { beforeEach, describe, expect, it, vi } from "vitest";

const preferences = new Map<string, string>();
vi.mock("@capacitor/preferences", () => ({
  Preferences: {
    get: vi.fn(async ({ key }: { key: string }) => ({ value: preferences.get(key) ?? null })),
    set: vi.fn(async ({ key, value }: { key: string; value: string }) => { preferences.set(key, value); }),
    remove: vi.fn(async ({ key }: { key: string }) => { preferences.delete(key); }),
  },
}));

describe("API client", () => {
  beforeEach(() => { preferences.clear(); vi.restoreAllMocks(); });

  it("adds the bearer token to mobile requests", async () => {
    const client = await import("@/api/client");
    await client.saveToken("student-token");
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ ok: true }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }));
    await client.request("/api/v1/mobile/rooms");
    expect((fetchMock.mock.calls[0][1]?.headers as Record<string, string>).Authorization).toBe("Bearer student-token");
  });

  it("creates a client message id on insecure mobile HTTP origins", async () => {
    const { createClientMessageId } = await import("@/api/client");
    const first = createClientMessageId({});
    const second = createClientMessageId({});
    expect(first).toMatch(/^mobile-[a-z0-9]+-[a-z0-9]+$/);
    expect(second).not.toBe(first);
  });
});
