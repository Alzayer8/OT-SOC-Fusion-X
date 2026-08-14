import type { FullConfig } from "@playwright/test";

const BACKEND_URL = process.env.OTSOC_E2E_BACKEND_URL ?? "http://127.0.0.1:8000";

export default async function globalSetup(config: FullConfig): Promise<void> {
  if (!process.env.OTSOC_E2E_USERNAME?.trim() || !process.env.OTSOC_E2E_PASSWORD) {
    throw new Error(
      "Set OTSOC_E2E_USERNAME and OTSOC_E2E_PASSWORD to a provisioned local ADMIN account. " +
        "The repository intentionally contains no working Playwright credential.",
    );
  }

  const frontendUrl = String(
    config.projects[0]?.use.baseURL ?? process.env.OTSOC_E2E_BASE_URL ?? "http://127.0.0.1:5173",
  );
  await waitForEndpoint(`${BACKEND_URL}/health/ready`, async (response) => {
    if (!response.ok) return false;
    const body = (await response.json()) as { status?: string };
    return body.status === "ready";
  });
  await waitForEndpoint(`${frontendUrl}/login`, (response) => response.ok);
}

async function waitForEndpoint(
  url: string,
  accepts: (response: Response) => boolean | Promise<boolean>,
): Promise<void> {
  const deadline = Date.now() + 90_000;
  let lastError = "no response";
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url, { signal: AbortSignal.timeout(5_000) });
      if (await accepts(response)) return;
      lastError = `HTTP ${response.status}`;
    } catch (error) {
      lastError = error instanceof Error ? error.message : String(error);
    }
    await new Promise((resolve) => setTimeout(resolve, 1_000));
  }
  throw new Error(`The required real-stack endpoint did not become ready: ${url} (${lastError}).`);
}
