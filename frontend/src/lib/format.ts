import type { RunStatus } from "../types";

export const RUN_STATUS_LABELS: Record<RunStatus, string> = {
  researching: "調査中",
  finished: "完了",
  failed: "失敗",
  interrupted: "中断",
};

const AVAILABILITY_LABELS: Record<string, string> = {
  in_stock: "在庫あり",
  limited_stock: "在庫わずか",
  out_of_stock: "在庫なし",
  unknown: "在庫確認中",
};

export function formatPrice(priceStr: string, currency: string): string {
  const n = parseFloat(priceStr);
  if (currency === "JPY") return `¥${n.toLocaleString()}`;
  return `${currency} ${n.toLocaleString()}`;
}

export function formatDuration(ms: number): string {
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}秒`;
  const m = Math.floor(s / 60);
  const rem = s % 60;
  return `${m}分${rem}秒`;
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleString("ja-JP", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).replace(/\//g, "-");
}

export { AVAILABILITY_LABELS };
