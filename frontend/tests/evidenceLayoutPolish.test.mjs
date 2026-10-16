import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(join(__dirname, "../src/views/EvidenceView.vue"), "utf8");

const pageRule = source.match(/\.toolbox-page \{[\s\S]*?\n\}/)?.[0] ?? "";
assert.match(
  pageRule,
  /--tb-bg:\s*var\(--neutral-0\)/,
  "Toolbox should use a white main canvas so warm orange remains an accent",
);
assert.match(
  pageRule,
  /--tb-panel-2:\s*var\(--neutral-50\)/,
  "Toolbox secondary surfaces should use neutral white-gray instead of orange tint",
);
assert.match(
  pageRule,
  /max-width:\s*1320px/,
  "Toolbox content should use the same controlled reading width as adjacent student pages",
);

const bodyRule = source.match(/\.toolbox-body \{[\s\S]*?\n\}/)?.[0] ?? "";
assert.match(bodyRule, /gap:\s*20px/, "Toolbox grid should keep a consistent 20px gutter");

const cardRule = source.match(/\n\.tool-block \{[\s\S]*?\n\}/)?.[0] ?? "";
assert.match(cardRule, /padding:\s*24px/, "Tool cards should share compact 24px inner spacing");
assert.match(cardRule, /background:\s*var\(--tb-panel\)/, "Tool cards should use an opaque surface");

const heroRule = source.match(/\.toolbox-hero \{[\s\S]*?\n\}/)?.[0] ?? "";
assert.match(
  heroRule,
  /linear-gradient\(120deg,\s*var\(--orange-50\)/,
  "Toolbox should concentrate its warm orange atmosphere in the hero, like MistakesView",
);

assert.doesNotMatch(
  source,
  /UI\/UX PRO MAX REDESIGN|\.toolbox-page \.tool-block[\s\S]*?!important/,
  "Toolbox should not keep a second !important override layer that breaks the base grid rhythm",
);

assert.match(
  source,
  /@media \(max-width:\s*768px\)[\s\S]*?\.tool-block-wide[\s\S]*?grid-column:\s*1 \/ -1/,
  "All tool cards should collapse to one column on mobile",
);
assert.match(
  source,
  /@media \(max-width:\s*768px\)[\s\S]*?\.toolbox-page \{[\s\S]*?max-width:\s*calc\(100vw - 24px\)/,
  "Toolbox should clamp itself to the mobile viewport even when the app shell has a wider content track",
);
