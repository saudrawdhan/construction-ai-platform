// Verifies the two translation dictionaries stay in step.
//
// Two failure modes this catches, both of which occurred during development and neither of which
// breaks a build: a key present in one dictionary but not the other (the UI silently falls back to
// English mid-page), and a duplicate key within one dictionary (the later value silently wins).
// Comparing key SETS alone misses the second case, so counts are compared too.

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const dictionaries = ["en", "ar"].map((name) => {
  const source = readFileSync(join(here, "..", "src", "lib", "i18n", `${name}.ts`), "utf8");
  const keys = (source.match(/^\s+"[^"]+":/gm) ?? []).map((line) =>
    line.trim().replace(/":$/, "").replace(/^"/, ""),
  );
  return { name, keys };
});

const problems = [];

for (const { name, keys } of dictionaries) {
  const seen = new Set();
  const duplicates = new Set();
  for (const key of keys) {
    if (seen.has(key)) duplicates.add(key);
    seen.add(key);
  }
  if (duplicates.size) {
    problems.push(`${name}.ts has duplicate keys: ${[...duplicates].join(", ")}`);
  }
}

const [en, ar] = dictionaries;
const missingInAr = en.keys.filter((key) => !ar.keys.includes(key));
const missingInEn = ar.keys.filter((key) => !en.keys.includes(key));

if (missingInAr.length) problems.push(`missing from ar.ts: ${missingInAr.join(", ")}`);
if (missingInEn.length) problems.push(`missing from en.ts: ${missingInEn.join(", ")}`);

if (problems.length) {
  console.error("Translation check failed:");
  for (const problem of problems) console.error(`  - ${problem}`);
  process.exit(1);
}

console.log(`Translations match: ${en.keys.length} keys in both dictionaries.`);
