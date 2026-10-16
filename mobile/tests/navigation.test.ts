import { shallowMount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import MobileShell from "@/components/MobileShell.vue";

describe("mobile navigation", () => {
  it("renders the four student areas", async () => {
    const wrapper = shallowMount(MobileShell, { global: { stubs: {
      RouterView: true,
      RouterLink: { template: "<a><slot /></a>" },
    } } });
    expect(wrapper.findAll(".bottom-nav__item")).toHaveLength(4);
    expect(wrapper.text()).toContain("消息");
    expect(wrapper.text()).toContain("错题");
    expect(wrapper.text()).toContain("资源");
    expect(wrapper.text()).toContain("我的");
  });
});
