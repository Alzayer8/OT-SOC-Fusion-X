import { astToString } from "openapi-typescript";
import openapiTS from "openapi-typescript";
import { fileURLToPath, pathToFileURL } from "node:url";

export const contractSource = fileURLToPath(
  new URL("../../contracts/openapi.json", import.meta.url),
);

export const generatedTarget = fileURLToPath(
  new URL("../src/api/generated/schema.d.ts", import.meta.url),
);

export const repositoryGeneratedTarget = fileURLToPath(
  new URL("../../contracts/generated/schema.d.ts", import.meta.url),
);

export async function renderContract() {
  const ast = await openapiTS(pathToFileURL(contractSource));
  return astToString(ast);
}
