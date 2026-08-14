import { mkdir, writeFile } from "node:fs/promises";
import { dirname } from "node:path";

import { generatedTarget, renderContract, repositoryGeneratedTarget } from "./contract-render.mjs";

const rendered = await renderContract();
for (const target of [generatedTarget, repositoryGeneratedTarget]) {
  await mkdir(dirname(target), { recursive: true });
  await writeFile(target, rendered, "utf8");
  console.log(`Wrote generated TypeScript contract: ${target}`);
}
