import { readFile } from "node:fs/promises";

import { generatedTarget, renderContract, repositoryGeneratedTarget } from "./contract-render.mjs";

const expected = await renderContract();
for (const target of [generatedTarget, repositoryGeneratedTarget]) {
  let current = "";
  try {
    current = await readFile(target, "utf8");
  } catch {
    // A missing generated file is stale by definition.
  }

  if (current !== expected) {
    console.error(`Generated API contract is stale: ${target}`);
    process.exitCode = 1;
  } else {
    console.log(`Generated API contract is current: ${target}`);
  }
}

if (process.exitCode) {
  console.error("Run: npm run contract:generate");
}
