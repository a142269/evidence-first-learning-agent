<script setup lang="ts">
import type { RoleCard, RoleKind } from "./roleTypes";

defineProps<{
  roles: RoleCard[];
  activeRole: RoleKind;
}>();

const emit = defineEmits<{
  select: [kind: RoleKind];
}>();
</script>

<template>
  <div class="role-list">
    <button
      v-for="role in roles"
      :key="role.kind"
      type="button"
      class="role"
      :class="{ active: activeRole === role.kind }"
      @click="emit('select', role.kind)"
    >
      <strong>{{ role.index }}</strong>
      <span>
        <b>{{ role.title }}</b>
        <small>{{ role.subtitle }}</small>
      </span>
      <i></i>
    </button>
  </div>
</template>

<style scoped lang="scss">
.role-list {
  display: grid;
  gap: 12px;
  margin-bottom: 22px;
}

.role {
  display: grid;
  grid-template-columns: 50px 1fr 24px;
  align-items: center;
  width: 100%;
  min-height: 74px;
  padding: 0 18px;
  border: 1px solid rgba(29, 32, 36, 0.1);
  border-radius: 8px;
  color: inherit;
  font-family: inherit;
  text-align: left;
  background: rgba(255, 255, 255, 0.86);
  cursor: pointer;
  transition: 0.2s ease;
}

.role.active {
  border-color: rgba(233, 85, 20, 0.72);
  background: linear-gradient(180deg, rgba(255, 250, 243, 0.98), rgba(255, 247, 236, 0.98));
  box-shadow: inset 0 0 0 1px rgba(233, 85, 20, 0.12);
}

.role strong {
  color: #1d2024;
  font-size: 16px;
}

.role.active strong {
  color: var(--orange);
}

.role b {
  display: block;
  font-size: 17px;
  line-height: 1.5;
}

.role small {
  display: block;
  color: #b28560;
  font-size: 13px;
  font-family: Georgia, "Times New Roman", serif;
  letter-spacing: .08em;
  text-transform: uppercase;
  margin-top: 2px;
}

.role i {
  justify-self: end;
  width: 18px;
  height: 18px;
  border: 2px solid #c9c0b6;
  border-radius: 99px;
}

.role.active i {
  border: 2px solid var(--orange);
  background: var(--orange);
  box-shadow: inset 0 0 0 4px #fff;
}
</style>
