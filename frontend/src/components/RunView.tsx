import { useEffect, useEffectEvent, useRef, useState, type CSSProperties } from "react";
import type { RunData, RunStatus, TimelineItem } from "../types";
import {
  RUN_STATUS_LABELS,
  AVAILABILITY_LABELS,
  formatDuration,
  formatPrice,
  formatDate,
} from "../lib/format";

type TabKind = "summary" | "timeline";

const TL_ICONS: Record<string, { cls: string; letter: string }> = {
  tool:     { cls: "tool",   letter: "T" },
  thinking: { cls: "think",  letter: "?" },
  system:   { cls: "system", letter: "S" },
  result:   { cls: "result", letter: "R" },
  error:    { cls: "error",  letter: "!" },
  text:     { cls: "text",   letter: "A" },
};

interface Props {
  run: RunData;
  instant?: boolean;
  onCancel?: (runId: string) => void;
  onDelete?: (runId: string) => void;
  isCancelling?: boolean;
  isDeleting?: boolean;
}

export function RunView({
  run,
  instant = false,
  onCancel,
  onDelete,
  isCancelling = false,
  isDeleting = false,
}: Props) {
  const [items, setItems] = useState<TimelineItem[]>(() =>
    instant ? run.timeline : [],
  );
  const [idx, setIdx] = useState(instant ? run.timeline.length : 0);
  const [activeTab, setActiveTab] = useState<TabKind>(
    instant && run.status === "finished" ? "summary" : "timeline",
  );
  const [expandedItems, setExpandedItems] = useState<Set<number>>(new Set());
  const tlRef = useRef<HTMLDivElement>(null);
  const timelineWrapRef = useRef<HTMLDivElement>(null);
  const [timelineMaxHeight, setTimelineMaxHeight] = useState<number | null>(null);

  const displayedItems = instant ? run.timeline : items;
  const isReplaying = instant ? run.status === "researching" : idx < run.timeline.length;
  const displayStatus = isReplaying ? "researching" : run.status;
  const isTerminal = displayStatus !== "researching";

  // Replay timeline items one by one
  useEffect(() => {
    if (instant) return;
    if (idx >= run.timeline.length) return;
    const item = run.timeline[idx];
    const prev = idx > 0 ? run.timeline[idx - 1].t : 0;
    const delay = Math.min(item.t - prev, 4000);
    const timer = setTimeout(() => {
      setItems((p) => [...p, item]);
      setIdx((i) => i + 1);
    }, delay);
    return () => clearTimeout(timer);
  }, [idx, run.timeline, instant]);

  // Auto-scroll timeline to bottom while replaying
  useEffect(() => {
    if (!isReplaying) return;
    const el = tlRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [displayedItems.length, isReplaying]);

  const syncTimelineHeight = useEffectEvent(() => {
    if (activeTab !== "timeline") return;
    const wrap = timelineWrapRef.current;
    if (!wrap) return;
    const viewportHeight = window.visualViewport?.height ?? window.innerHeight;
    const visualBottomGap = 24;
    const minimumTimelineHeight = 280;
    const main = wrap.closest("main");
    const mainPaddingBottom = main
      ? Number.parseFloat(window.getComputedStyle(main).paddingBottom) || 0
      : 0;
    const nextHeight = Math.max(
      minimumTimelineHeight,
      Math.floor(
        viewportHeight
          - wrap.getBoundingClientRect().top
          - visualBottomGap
          - mainPaddingBottom,
      ),
    );
    setTimelineMaxHeight((prev) => (prev === nextHeight ? prev : nextHeight));
  });

  // Keep the timeline scroller sized to the remaining viewport height.
  useEffect(() => {
    if (activeTab !== "timeline") return;

    syncTimelineHeight();
    const handleViewportChange = () => syncTimelineHeight();
    const viewport = window.visualViewport;

    window.addEventListener("resize", handleViewportChange);
    viewport?.addEventListener("resize", handleViewportChange);

    return () => {
      window.removeEventListener("resize", handleViewportChange);
      viewport?.removeEventListener("resize", handleViewportChange);
    };
  }, [activeTab, syncTimelineHeight]);

  useEffect(() => {
    syncTimelineHeight();
  });

  // Switch to Summary tab when replay finishes with a result
  const handleComplete = useEffectEvent(() => setActiveTab("summary"));
  useEffect(() => {
    if (!isReplaying && run.status === "finished" && run.result) {
      handleComplete();
    }
  }, [isReplaying, run.status, run.result]);

  const toggleItem = (i: number) => {
    setExpandedItems((p) => {
      const next = new Set(p);
      if (next.has(i)) {
        next.delete(i);
      } else {
        next.add(i);
      }
      return next;
    });
  };

  const elapsedMs = isReplaying
    ? Math.max(run.duration_ms, displayedItems.at(-1)?.t ?? 0)
    : run.duration_ms;
  const offersFound = !isReplaying && run.result ? run.result.offers.length : null;
  const bestPrice =
    !isReplaying && run.result
      ? formatPrice(run.result.offers[0].item_price, run.currency)
      : "--";

  return (
    <>
      <div className="run-header">
        <div>
          <h2>{run.product_name}</h2>
          <p className="run-header-sub">
            {formatDate(run.started_at)} / {run.market} / {run.currency} / 最大
            {run.max_offers}件 / {run.model}
          </p>
        </div>
        <div className="run-header-controls">
          <span className={`phase-badge ${displayStatus}`}>
            {!isTerminal && <span className="spinner" />}
            {RUN_STATUS_LABELS[displayStatus]}
          </span>
          {displayStatus === "researching" && onCancel && (
            <button
              type="button"
              className="btn-secondary"
              onClick={() => onCancel(run.run_id)}
              disabled={isCancelling}
            >
              {isCancelling ? "停止中..." : "停止"}
            </button>
          )}
          {displayStatus !== "researching" && onDelete && (
            <button
              type="button"
              className="btn-danger"
              onClick={() => onDelete(run.run_id)}
              disabled={isDeleting}
            >
              {isDeleting ? "削除中..." : "削除"}
            </button>
          )}
        </div>
      </div>

      <div className="view-tabs">
        <button
          className={`view-tab-btn${activeTab === "summary" ? " active" : ""}`}
          onClick={() => setActiveTab("summary")}
        >
          Summary
        </button>
        <button
          className={`view-tab-btn${activeTab === "timeline" ? " active" : ""}`}
          onClick={() => setActiveTab("timeline")}
        >
          Timeline
          {isReplaying && <span className="tl-live-dot" />}
        </button>
      </div>

      {activeTab === "summary" && (
        <SummaryTab
          run={run}
          isReplaying={isReplaying}
          displayStatus={displayStatus}
          elapsedMs={elapsedMs}
          offersFound={offersFound}
          bestPrice={bestPrice}
        />
      )}

      {activeTab === "timeline" && (
        <div
          className="timeline-wrap"
          ref={timelineWrapRef}
          style={
            {
              "--timeline-max-height": timelineMaxHeight
                ? `${timelineMaxHeight}px`
                : undefined,
            } as CSSProperties
          }
        >
          <div className="timeline" ref={tlRef}>
            {displayedItems.length === 0 ? (
              <div className="tl-empty">調査を開始しています...</div>
            ) : (
              displayedItems.map((item, i) => {
                const icon = TL_ICONS[item.kind] ?? { cls: "system", letter: "·" };
                const expanded = expandedItems.has(i);
                const images = item.images ?? [];
                const detailSummary =
                  item.detail || (images.length > 0 ? `画像 ${images.length}件` : "");
                const hasDetail = Boolean(item.detail || images.length > 0);
                return (
                  <div
                    key={i}
                    className={`tl-event${expanded ? " expanded" : ""}`}
                    onClick={() => toggleItem(i)}
                  >
                    <div className="tl-time">{formatDuration(item.t)}</div>
                    <div className={`tl-icon ${icon.cls}`}>{icon.letter}</div>
                    <div className="tl-body">
                      <div className="tl-title">{item.label}</div>
                      {hasDetail && (
                        <>
                          <div className="tl-snippet">{detailSummary}</div>
                          <div className="tl-detail">
                            {item.detail && <div className="tl-detail-text">{item.detail}</div>}
                            {images.length > 0 && (
                              <div className="tl-preview-grid">
                                {images.map((image, imageIndex) => (
                                  <img
                                    key={`${i}-${imageIndex}-${image.src}`}
                                    className="tl-preview-image"
                                    src={image.src}
                                    alt={`${item.label} の画像プレビュー ${imageIndex + 1}`}
                                    loading="lazy"
                                  />
                                ))}
                              </div>
                            )}
                          </div>
                        </>
                      )}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}
    </>
  );
}

// ── Summary Tab ──────────────────────────────────────────────────────────────

interface SummaryProps {
  run: RunData;
  isReplaying: boolean;
  displayStatus: RunStatus;
  elapsedMs: number;
  offersFound: number | null;
  bestPrice: string;
}

function SummaryTab({
  run,
  isReplaying,
  displayStatus,
  elapsedMs,
  offersFound,
  bestPrice,
}: SummaryProps) {
  const costText =
    run.total_cost_usd === null ? "--" : `$${run.total_cost_usd.toFixed(3)}`;
  const turnsText = run.num_turns === null ? "--" : String(run.num_turns);

  if (isReplaying || !run.result) {
    return (
      <>
        <div className="summary-grid">
          <div className="card">
            <div className="card-label">状況</div>
            <div className="card-value">{RUN_STATUS_LABELS[displayStatus]}</div>
          </div>
          <div className="card">
            <div className="card-label">経過時間</div>
            <div className="card-value">{formatDuration(elapsedMs)}</div>
          </div>
          <div className="card">
            <div className="card-label">候補件数</div>
            <div className="card-value">
              {offersFound === null ? "--" : `${offersFound}件`}
            </div>
          </div>
          <div className="card">
            <div className="card-label">最安値</div>
            <div className="card-value">{bestPrice}</div>
          </div>
        </div>

        {displayStatus === "failed" && (
          <div className="failed-banner">
            <h3>調査に失敗しました</h3>
            <p>
              所要時間: {formatDuration(run.duration_ms)} / ターン数: {turnsText}{" "}
              / 費用: {costText}
            </p>
          </div>
        )}
        {displayStatus === "interrupted" && (
          <div className="failed-banner interrupted-banner">
            <h3>調査は途中で中断されました</h3>
            <p>
              所要時間: {formatDuration(run.duration_ms)} / ターン数: {turnsText}
            </p>
          </div>
        )}
      </>
    );
  }

  const { result, currency } = run;
  const offers = [...result.offers].sort(
    (a, b) => parseFloat(a.item_price) - parseFloat(b.item_price),
  );
  const best = offers[0];
  const maxPrice = Math.max(...offers.map((o) => parseFloat(o.item_price)));

  return (
    <>
      {/* Stats row */}
      <div className="summary-grid">
        <div className="card">
          <div className="card-label">ステータス</div>
          <div className="card-value success">完了</div>
        </div>
        <div className="card">
          <div className="card-label">所要時間</div>
          <div className="card-value">{formatDuration(run.duration_ms)}</div>
          <div className="card-sub">{turnsText} ターン</div>
        </div>
        <div className="card">
          <div className="card-label">候補件数</div>
          <div className="card-value">{offers.length}件</div>
        </div>
        <div className="card">
          <div className="card-label">費用</div>
          <div className="card-value">{costText}</div>
        </div>
      </div>

      {/* Identified product */}
      <div className="result-section">
        <h3>特定された商品</h3>
        <div className="product-card">
          <div className="product-name">{result.identified_product.name}</div>
          <div className="product-meta">
            <span className="meta-item">
              <strong>製造元:</strong> {result.identified_product.manufacturer}
            </span>
            <span className="meta-item">
              <strong>型番:</strong> {result.identified_product.model_number}
            </span>
            <span className="meta-item">
              <strong>発売日:</strong> {result.identified_product.release_date}
            </span>
            {result.identified_product.product_url && (
              <a
                className="meta-item"
                href={result.identified_product.product_url}
                target="_blank"
                rel="noopener noreferrer"
              >
                製品ページ →
              </a>
            )}
          </div>
          {result.identified_product.is_substitute && (
            <div className="substitute-badge">
              代替商品: {result.identified_product.substitution_reason}
            </div>
          )}
        </div>
      </div>

      {/* Best offer */}
      <div className="result-section">
        <h3>最安値の候補</h3>
        <div className="best-offer">
          <div>
            <div className="offer-label">最安値</div>
            <div className="offer-price">
              {formatPrice(best.item_price, currency)}
            </div>
            <div className="offer-merchant">
              {best.merchant_name} /{" "}
              {AVAILABILITY_LABELS[best.availability] ?? best.availability}
            </div>
          </div>
          {best.merchant_product_url && (
            <a
              className="btn-link"
              href={best.merchant_product_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              商品ページを見る
            </a>
          )}
        </div>
      </div>

      {/* Price comparison chart */}
      <div className="result-section">
        <h3>価格比較</h3>
        <div className="chart-container">
          <div className="bar-chart">
            {offers.map((offer) => {
              const price = parseFloat(offer.item_price);
              const pct = (price / maxPrice) * 100;
              const isBest = price === parseFloat(best.item_price);
              return (
                <div
                  key={offer.merchant_name}
                  className={`bar-row${isBest ? " best" : ""}`}
                >
                  <div className="bar-label">{offer.merchant_name}</div>
                  <div className="bar-track">
                    <div
                      className={`bar-fill ${isBest ? "cheapest" : "other"}`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <div className="bar-price">
                    {formatPrice(offer.item_price, currency)}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Offer cards */}
      <div className="result-section">
        <h3>候補一覧</h3>
        <div className="offer-grid">
          {offers.map((offer) => {
            const isBest =
              parseFloat(offer.item_price) === parseFloat(best.item_price);
            return (
              <div
                key={offer.merchant_name}
                className={`offer-card${isBest ? " best" : ""}`}
              >
                <div className="card-header">
                  <span className="merchant-name">
                    {offer.merchant_name}
                    {isBest && " ★ 最安値"}
                  </span>
                </div>
                <div className="card-price">
                  {formatPrice(offer.item_price, currency)}
                </div>
                <div className="card-title">{offer.merchant_product_name}</div>
                <div className="card-details">
                  <span className={`detail-tag ${offer.availability}`}>
                    {AVAILABILITY_LABELS[offer.availability] ?? offer.availability}
                  </span>
                </div>
                <div className="card-evidence">{offer.evidence}</div>
                {offer.merchant_product_url && (
                  <a
                    className="card-link"
                    href={offer.merchant_product_url}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    商品ページを見る →
                  </a>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Summary / caveat */}
      <div className="result-section">
        <h3>調査サマリ</h3>
        <div className="caveat">
          <p>{result.summary}</p>
          <p className="caveat-note">
            ※ 価格は観測時点のスナップショットです。在庫や価格は変動する可能性があります。
          </p>
        </div>
      </div>
    </>
  );
}

// ── History List ─────────────────────────────────────────────────────────────

export function HistoryList({
  runs,
  onSelect,
  onCancel,
  onDelete,
  pendingCancels,
  pendingDeletes,
}: {
  runs: [string, RunData][];
  onSelect: (key: string) => void;
  onCancel: (key: string) => void;
  onDelete: (key: string) => void;
  pendingCancels: Record<string, boolean>;
  pendingDeletes: Record<string, boolean>;
}) {
  return (
    <>
      <div className="history-header">
        <h2>調査履歴</h2>
      </div>
      <div className="run-list">
        {runs.map(([key, run]) => (
          <div
            key={key}
            className={`run-card ${run.status}`}
            onClick={() => onSelect(key)}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => e.key === "Enter" && onSelect(key)}
          >
            <div className="run-info">
              <h3>
                <span className={`run-status-label ${run.status}`}>
                  {RUN_STATUS_LABELS[run.status]}
                </span>
                {run.product_name}
              </h3>
              <p>
                {formatDate(run.started_at)} / {run.model} / 最大{run.max_offers}件
              </p>
            </div>
            <div className="run-card-side">
              <div className="run-meta">{formatRunMeta(run)}</div>
              <div className="run-card-actions">
                {run.status === "researching" ? (
                  <button
                    type="button"
                    className="btn-inline"
                    onClick={(event) => {
                      event.stopPropagation();
                      onCancel(key);
                    }}
                    disabled={pendingCancels[key] === true}
                  >
                    {pendingCancels[key] === true ? "停止中..." : "停止"}
                  </button>
                ) : (
                  <button
                    type="button"
                    className="btn-inline danger"
                    onClick={(event) => {
                      event.stopPropagation();
                      onDelete(key);
                    }}
                    disabled={pendingDeletes[key] === true}
                  >
                    {pendingDeletes[key] === true ? "削除中..." : "削除"}
                  </button>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}

function formatRunMeta(run: RunData): string {
  const durationText = `所要 ${formatDuration(run.duration_ms)}`;
  const costText =
    run.total_cost_usd === null ? null : `$${run.total_cost_usd.toFixed(3)}`;
  if (run.status === "finished") {
    return [durationText, costText].filter(Boolean).join(" / ");
  }
  return durationText;
}
