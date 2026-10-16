<script setup lang="ts">
interface AgentNode {
  cls: string;
  img: string;
  name: string;
  english: string;
}

defineProps<{
  nodes: AgentNode[];
}>();
</script>

<template>
  <div class="agent-map" aria-label="个性化学习智能体协作图">
    <div class="map-inner">
      <svg class="orbit-svg" viewBox="0 0 900 580" aria-hidden="true">
        <g fill="none" stroke="#e1a85d" stroke-dasharray="6 8" stroke-width="1.5" opacity=".65">
          <circle cx="383" cy="244" r="120" />
          <line x1="383" y1="244" x2="288" y2="80" />
          <line x1="383" y1="244" x2="478" y2="80" />
          <line x1="383" y1="244" x2="573" y2="244" />
          <line x1="383" y1="244" x2="478" y2="408" />
          <line x1="383" y1="244" x2="288" y2="408" />
          <line x1="383" y1="244" x2="193" y2="244" />
        </g>
        <g fill="#e2aa5b" opacity=".65">
          <circle cx="383" cy="124" r="7" />
          <circle cx="503" cy="244" r="7" />
          <circle cx="383" cy="364" r="7" />
          <circle cx="263" cy="244" r="7" />
          <circle cx="468" cy="159" r="5.5" />
          <circle cx="468" cy="329" r="5.5" />
          <circle cx="298" cy="329" r="5.5" />
          <circle cx="298" cy="159" r="5.5" />
        </g>
      </svg>

      <div class="learner">
        <svg viewBox="0 0 260 190" aria-hidden="true">
          <defs>
            <linearGradient id="bookPage" x1="0" y1="0" x2="0" y2="1">
              <stop stop-color="#fff7e7" />
              <stop offset="1" stop-color="#f8dba2" />
            </linearGradient>
            <filter id="bookShadow" x="-30%" y="-30%" width="160%" height="160%">
              <feDropShadow dx="0" dy="10" stdDeviation="8" flood-color="#b27028" flood-opacity=".22" />
            </filter>
          </defs>
          <g filter="url(#bookShadow)">
            <path d="M34 60c33-22 69-23 96-2v82c-28-18-63-17-96 3Z" fill="url(#bookPage)" stroke="#d9821c" stroke-width="4" />
            <path d="M226 60c-33-22-69-23-96-2v82c28-18 63-17 96 3Z" fill="url(#bookPage)" stroke="#d9821c" stroke-width="4" />
            <path d="M130 58v83" stroke="#d9821c" stroke-width="4" />
            <path d="M58 104c22-8 40-9 58-2M147 102c21-8 37-8 58 1" stroke="#d9a157" stroke-width="2" opacity=".55" />
            <path d="M76 88 105 76l30 24 36-41 24 20" fill="none" stroke="#e96613" stroke-width="5" stroke-linecap="round" stroke-linejoin="round" />
            <g fill="#f2a12e" stroke="#e05d13" stroke-width="3">
              <circle cx="76" cy="88" r="7" />
              <circle cx="105" cy="76" r="7" />
              <circle cx="135" cy="100" r="7" />
              <circle cx="171" cy="59" r="7" />
            </g>
            <path d="M197 25v51" stroke="#e96613" stroke-width="4" />
            <path d="M197 25h38l-9 12 9 12h-38Z" fill="#e96613" />
          </g>
        </svg>
        <h2>学习者</h2>
        <p>LEARNER</p>
      </div>

      <article v-for="node in nodes" :key="node.cls" class="agent" :class="node.cls">
        <img :src="node.img" :alt="node.name" />
        <h3>{{ node.name }}</h3>
        <p>{{ node.english }}</p>
      </article>
    </div>
  </div>
</template>

<style scoped lang="scss">
.agent-map {
  position: relative;
  width: 100%;
  max-width: 855px;
  aspect-ratio: 900 / 580;
  container-type: inline-size;
  margin: 0 auto;
}

.map-inner {
  position: absolute;
  top: 0;
  left: 0;
  width: 900px;
  height: 580px;
  transform: scale(calc(100cqi / 900));
  transform-origin: top left;
}

.orbit-svg {
  position: absolute;
  top: 0;
  left: 0;
  width: 900px;
  height: 580px;
}

/* ── Center learner (shrunk ~18%) ── */
.learner {
  position: absolute;
  top: 171px;
  left: 283px;
  z-index: 3;
  width: 200px;
  text-align: center;
}

.learner svg {
  display: block;
  width: 185px;
  margin: 0 auto -10px;
}

.learner h2 {
  margin: 0;
  font-family: var(--serif-cn);
  font-size: 26px;
  font-weight: 900;
  line-height: 1.1;
  letter-spacing: 0.04em;
}

.learner p {
  margin: 4px 0 0;
  color: #a25b20;
  font-family: Georgia, "Times New Roman", serif;
  font-size: 14px;
  letter-spacing: 0.08em;
}

/* ── Agent cards (uniform size) ── */
.agent {
  position: absolute;
  z-index: 4;
  width: 140px;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.agent img {
  display: block;
  width: 110px;
  height: 110px;
  margin: 0 auto 6px;
  object-fit: contain;
  filter: drop-shadow(0 10px 14px rgba(99, 65, 34, 0.12));
}

.agent h3 {
  margin: 0;
  font-family: var(--serif-cn);
  font-size: 21px;
  font-weight: 900;
  line-height: 1.1;
}

.agent p {
  margin: 3px 0 0;
  color: #1d2024;
  font-size: 11px;
  opacity: 0.88;
}

/* ── Regular hexagonal positions (R=190, center 383,236) ── */
.agent-planner    { top: -18px; left: 218px; }
.agent-content    { top: -18px; left: 408px; }
.agent-tutor      { top: 189px; left: 503px; }
.agent-safety     { top: 353px; left: 408px; }
.agent-evaluation { top: 353px; left: 218px; }
.agent-quiz       { top: 189px; left: 123px; }

/* ── Top agents: text above image to avoid orbit overlap ── */
.agent-planner h3, .agent-content h3 { order: -2; }
.agent-planner p,  .agent-content p  { order: -1; margin: 0 0 2px; }
.agent-planner img, .agent-content img { order: 0; margin: 4px auto 0; }
</style>
