<script setup lang="ts">
import { AlertCircle, Inbox, LoaderCircle, RefreshCw } from "lucide-vue-next";
defineProps<{ kind: "loading" | "empty" | "error"; title?: string; message?: string }>();
defineEmits<{ retry: [] }>();
</script>
<template>
  <div class="page-state" role="status">
    <LoaderCircle v-if="kind === 'loading'" class="spin" :size="30" />
    <Inbox v-else-if="kind === 'empty'" :size="30" />
    <AlertCircle v-else :size="30" />
    <strong>{{ title || (kind === 'loading' ? '正在加载' : kind === 'empty' ? '这里还没有内容' : '加载失败') }}</strong>
    <p v-if="message">{{ message }}</p>
    <button v-if="kind === 'error'" class="text-button" type="button" @click="$emit('retry')"><RefreshCw :size="16" />重试</button>
  </div>
</template>
