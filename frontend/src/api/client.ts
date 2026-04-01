import type { RunData, SearchFormValues } from "../types";

/** Launcher-backed API endpoint prefix. */
const API_PREFIX = "/api";
const DEFAULT_TIMEOUT_MS = 10_000;
const START_RUN_TIMEOUT_MS = 30_000;

/**
 * Start a new run through the launcher-backed API.
 */
export async function startRun(values: SearchFormValues): Promise<RunData> {
  return normalizeRunData(await requestJson<RunData>(`${API_PREFIX}/runs`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      product: buildProductQuery(values),
      market: values.market,
      currency: values.currency,
      maxOffers: values.maxOffers,
    }),
  }, START_RUN_TIMEOUT_MS));
}

/**
 * Request cancellation for one in-flight run.
 */
export async function cancelRun(runId: string): Promise<RunData | null> {
  const response = await fetchWithTimeout(
    `${API_PREFIX}/runs/${runId}/cancel`,
    { method: "POST" },
    DEFAULT_TIMEOUT_MS,
  );
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`run cancel failed: ${response.status}`);
  }
  return normalizeRunData((await response.json()) as RunData);
}

/**
 * Soft-delete one completed run.
 */
export async function deleteRun(runId: string): Promise<boolean> {
  const response = await fetchWithTimeout(
    `${API_PREFIX}/runs/${runId}`,
    { method: "DELETE" },
    DEFAULT_TIMEOUT_MS,
  );
  if (response.status === 404) {
    return false;
  }
  if (!response.ok) {
    throw new Error(`run delete failed: ${response.status}`);
  }
  return true;
}

/**
 * Load a single run snapshot from the API.
 */
export async function getRun(runId: string): Promise<RunData | null> {
  const response = await fetchWithTimeout(
    `${API_PREFIX}/runs/${runId}`,
    undefined,
    DEFAULT_TIMEOUT_MS,
  );
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`run fetch failed: ${response.status}`);
  }
  return normalizeRunData((await response.json()) as RunData);
}

/**
 * Load the available run history from the API.
 */
export async function listRuns(): Promise<RunData[]> {
  return normalizeRunList(
    await requestJson<RunData[]>(`${API_PREFIX}/runs`, undefined, DEFAULT_TIMEOUT_MS),
  );
}

/**
 * Execute a JSON request and validate the HTTP status.
 */
async function requestJson<T>(
  url: string,
  init?: RequestInit,
  timeoutMs = DEFAULT_TIMEOUT_MS,
): Promise<T> {
  const response = await fetchWithTimeout(url, init, timeoutMs);
  if (!response.ok) {
    throw new Error(`request failed: ${response.status}`);
  }
  return (await response.json()) as T;
}

/**
 * Execute fetch with an abort timeout so the UI does not hang forever.
 */
async function fetchWithTimeout(
  url: string,
  init?: RequestInit,
  timeoutMs = DEFAULT_TIMEOUT_MS,
): Promise<Response> {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);

  try {
    return await fetch(url, {
      ...init,
      signal: controller.signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error(`request timed out after ${timeoutMs}ms`);
    }
    throw error;
  } finally {
    window.clearTimeout(timeoutId);
  }
}

/**
 * Build the launcher-facing product query from structured form fields.
 */
function buildProductQuery(values: SearchFormValues): string {
  return [
    values.productNameAndModelNumber,
    values.color.trim(),
    values.manufacturer.trim(),
  ]
    .map((value) => value.trim())
    .filter(Boolean)
    .join(" ");
}

/**
 * Normalize one run payload so older API responses still satisfy the UI contract.
 */
function normalizeRunData(run: RunData): RunData {
  return {
    ...run,
    timeline: (run.timeline ?? []).map((item) => ({
      ...item,
      images: item.images ?? [],
    })),
  };
}

/**
 * Normalize the run list returned from the API.
 */
function normalizeRunList(runs: RunData[]): RunData[] {
  return runs.map(normalizeRunData);
}
