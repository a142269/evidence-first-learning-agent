import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import PageState from "@/components/PageState.vue";

describe("PageState", () => {
  it("offers retry for network errors", async () => {
    const wrapper = mount(PageState, { props: { kind: "error", message: "连接失败" } });
    expect(wrapper.text()).toContain("连接失败");
    await wrapper.get("button").trigger("click");
    expect(wrapper.emitted("retry")).toHaveLength(1);
  });

  it("shows an accessible empty state", () => {
    const wrapper = mount(PageState, { props: { kind: "empty", title: "暂无课程群" } });
    expect(wrapper.attributes("role")).toBe("status");
    expect(wrapper.text()).toContain("暂无课程群");
  });
});
