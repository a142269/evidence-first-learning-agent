<script setup lang="ts">
withDefaults(
  defineProps<{
    variant?: "hero" | "sub";
    showBotany?: boolean;
  }>(),
  {
    variant: "sub",
    showBotany: true,
  },
);
</script>

<template>
  <main class="paper-background" :class="`paper-background--${variant}`">
    <div class="paper-background__noise" aria-hidden="true"></div>

    <template v-if="showBotany">
      <svg class="paper-background__botany paper-background__botany--left" viewBox="0 0 420 420" aria-hidden="true">
        <g fill="none" stroke="#cbbca7" stroke-width="2" opacity=".48">
          <path d="M52 365C110 276 105 188 68 91" />
          <path d="M154 390C198 285 188 218 145 143" />
          <path d="M282 400C255 300 283 214 348 128" />
        </g>
        <g opacity=".58">
          <ellipse cx="65" cy="286" rx="54" ry="15" fill="#b9baaa" transform="rotate(-34 65 286)" />
          <ellipse cx="128" cy="237" rx="52" ry="14" fill="#d7c5aa" transform="rotate(26 128 237)" />
          <ellipse cx="172" cy="312" rx="62" ry="17" fill="#a4aa9a" transform="rotate(-22 172 312)" />
          <ellipse cx="246" cy="318" rx="55" ry="15" fill="#cec5b3" transform="rotate(31 246 318)" />
        </g>
      </svg>

      <svg class="paper-background__botany paper-background__botany--right" viewBox="0 0 360 520" aria-hidden="true">
        <g fill="none" stroke="#d2c0aa" stroke-width="2" opacity=".42">
          <path d="M184 506C207 384 190 256 126 88" />
          <path d="M188 410C246 332 288 264 308 162" />
          <path d="M152 338C94 290 62 228 46 136" />
        </g>
        <g opacity=".38">
          <ellipse cx="108" cy="140" rx="66" ry="18" fill="#c8c3b0" transform="rotate(51 108 140)" />
          <ellipse cx="156" cy="220" rx="72" ry="20" fill="#abae9d" transform="rotate(-51 156 220)" />
          <ellipse cx="206" cy="286" rx="74" ry="20" fill="#d5c5a9" transform="rotate(34 206 286)" />
          <ellipse cx="272" cy="226" rx="60" ry="17" fill="#b0b29f" transform="rotate(-36 272 226)" />
        </g>
      </svg>
    </template>

    <div class="paper-background__silk paper-background__silk--a" aria-hidden="true"></div>
    <div class="paper-background__silk paper-background__silk--b" aria-hidden="true"></div>

    <div class="paper-background__content">
      <slot />
    </div>
  </main>
</template>

<style scoped lang="scss">
.paper-background {
  position: relative;
  min-height: 100vh;
  overflow: hidden;
  color: var(--ink);
  background:
    radial-gradient(circle at 62% 30%, rgba(255, 210, 141, 0.22), transparent 32%),
    radial-gradient(circle at 18% 88%, rgba(238, 203, 158, 0.25), transparent 26%),
    linear-gradient(112deg, var(--paper-50) 0%, var(--paper-200) 58%, var(--paper-300) 100%);
}

.paper-background--hero {
  padding: 38px 64px 34px;
}

.paper-background--sub {
  padding: 32px;
}

.paper-background__content {
  position: relative;
  z-index: 1;
}

.paper-background__noise {
  position: absolute;
  inset: 0;
  pointer-events: none;
  opacity: 0.22;
  background-image:
    radial-gradient(rgba(164, 125, 83, 0.15) 0.7px, transparent 0.7px),
    radial-gradient(rgba(255, 255, 255, 0.75) 0.8px, transparent 0.8px);
  background-position: 0 0, 12px 15px;
  background-size: 24px 24px;
}

.paper-background__botany {
  position: absolute;
  z-index: 0;
  pointer-events: none;
}

.paper-background__botany--left {
  left: -8px;
  bottom: 0;
  width: 420px;
}

.paper-background__botany--right {
  top: 80px;
  right: 18%;
  width: 360px;
}

.paper-background__silk {
  position: absolute;
  pointer-events: none;
  border-radius: 999px;
  background: linear-gradient(110deg, transparent, rgba(222, 170, 109, 0.16), transparent);
  transform: rotate(-22deg);
}

.paper-background__silk--a {
  top: 330px;
  left: -60px;
  width: 880px;
  height: 120px;
}

.paper-background__silk--b {
  top: 440px;
  left: 500px;
  width: 720px;
  height: 140px;
  opacity: 0.7;
}

@media (max-width: 720px) {
  .paper-background--hero,
  .paper-background--sub {
    padding: 22px 16px;
  }
}
</style>
