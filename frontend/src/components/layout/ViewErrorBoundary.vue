<script setup lang="ts">
import { nextTick, onErrorCaptured, ref } from "vue";

const props = withDefaults(defineProps<{ label?: string }>(), {
  label: "这个页面",
});

const failed = ref(false);
const detail = ref("");
const retryKey = ref(0);

onErrorCaptured((error) => {
  failed.value = true;
  detail.value = error instanceof Error ? error.message : String(error || "未知错误");
  // 已在页面上提供可恢复的状态，不再让异常冒泡到整棵应用树。
  return false;
});

async function retry() {
  failed.value = false;
  detail.value = "";
  retryKey.value += 1;
  await nextTick();
}
</script>

<template>
  <div v-if="failed" class="view-error-boundary" role="alert">
    <div class="view-error-icon">!</div>
    <h2>{{ props.label }}暂时没有加载出来</h2>
    <p>刚才的数据没有影响其它页面。你可以重试，已完成的学习记录和文件仍会保留。</p>
    <small v-if="detail">错误详情：{{ detail.slice(0, 160) }}</small>
    <button type="button" @click="retry">重新加载</button>
  </div>
  <slot v-else :key="retryKey" />
</template>

<style scoped>
.view-error-boundary {
  min-height: 240px;
  display: grid;
  place-items: center;
  align-content: center;
  gap: 10px;
  padding: 32px;
  color: #2b2520;
  text-align: center;
  background: #fffdf8;
}

.view-error-icon {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  color: #fff;
  background: #c2410c;
  font-weight: 800;
}

h2 { margin: 0; font-size: 18px; }
p { max-width: 440px; margin: 0; color: #6b6259; font-size: 13px; line-height: 1.6; }
small { max-width: 520px; color: #9a8e82; font-size: 11px; overflow-wrap: anywhere; }
button {
  margin-top: 4px;
  padding: 8px 14px;
  border: 0;
  border-radius: 8px;
  color: #fff;
  background: #e95514;
  cursor: pointer;
}
</style>
