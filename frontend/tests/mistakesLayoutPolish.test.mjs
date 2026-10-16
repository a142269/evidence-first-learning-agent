import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(join(__dirname, "../src/views/MistakesView.vue"), "utf8");

const gridRule = source.match(/\.mk-grid \{[\s\S]*?\n\}/)?.[0] ?? "";
assert.match(
  gridRule,
  /display:\s*grid/,
  "Mistakes grid should use CSS grid instead of masonry columns so cards line up evenly",
);
assert.match(
  gridRule,
  /grid-template-columns:\s*repeat\(3,\s*minmax\(0,\s*1fr\)\)/,
  "Mistakes grid should keep three equal-width card columns on desktop",
);
assert.match(
  gridRule,
  /align-items:\s*stretch/,
  "Mistakes grid should stretch cards within each row",
);

const cardRule = source.match(/\n\.mk-card \{[\s\S]*?\n\}/)?.[0] ?? "";
assert.match(
  cardRule,
  /height:\s*100%/,
  "Mistake cards should fill the grid track height",
);
assert.match(
  cardRule,
  /min-height:\s*156px/,
  "Mistake cards should have a shared compact height",
);
assert.doesNotMatch(
  cardRule,
  /break-inside|margin-bottom/,
  "Mistake cards should not keep masonry-only spacing rules",
);

assert.match(
  source,
  /\.mk-card:not\(\.expanded\) \{[\s\S]*?height:\s*156px[\s\S]*?\n\}/,
  "Collapsed mistake cards should be equal height even when titles wrap",
);
assert.match(
  source,
  /\.mk-card\.expanded \{[\s\S]*?height:\s*auto[\s\S]*?\n\}/,
  "Expanded mistake cards should still grow naturally for details",
);
assert.match(
  source,
  /\.mk-grid\.list-view \.mk-card \{[\s\S]*?height:\s*auto[\s\S]*?\n\}/,
  "List view should not be forced into the compact grid-card height",
);

const compactRule = source.match(/\.mk-card-compact \{[\s\S]*?\n\}/)?.[0] ?? "";
assert.match(
  compactRule,
  /height:\s*100%/,
  "Compact mistake card body should fill the equal-height card",
);

const titleRule = source.match(/\.mk-card-title \{[\s\S]*?\n\}/)?.[0] ?? "";
assert.match(
  titleRule,
  /min-height:\s*38px/,
  "Mistake card titles should reserve two-line space for consistent vertical rhythm",
);
