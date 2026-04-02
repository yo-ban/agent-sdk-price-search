import { useCallback, useEffect, useMemo, useState } from "react";
import { cancelRun, deleteRun, getRun, listRuns, startRun } from "./api/client";
import type { RunData, RunSummary, SearchFormValues } from "./types";
import { SearchForm } from "./components/SearchForm";
import { RunView, HistoryList } from "./components/RunView";
import appIcon from "./assets/icon.svg";

type View = "search" | "run" | "history";
const RESULT_SETTLE_POLL_LIMIT = 10;

export default function App() {
  const [view, setView] = useState<View>("search");
  const [runSummaries, setRunSummaries] = useState<Record<string, RunSummary>>({});
  const [runDetails, setRunDetails] = useState<Record<string, RunData>>({});
  const [currentRunId, setCurrentRunId] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [pendingCancels, setPendingCancels] = useState<Record<string, boolean>>({});
  const [pendingDeletes, setPendingDeletes] = useState<Record<string, boolean>>({});

  const currentRun = currentRunId ? runDetails[currentRunId] ?? null : null;
  const historyRuns = useMemo(
    () =>
      Object.entries(runSummaries).sort(([, left], [, right]) =>
        right.started_at.localeCompare(left.started_at),
      ),
    [runSummaries],
  );

  const refreshHistory = useCallback(async () => {
    const fetchedRuns = await listRuns();
    setRunSummaries(Object.fromEntries(fetchedRuns.map((run) => [run.run_id, run])));
  }, []);

  useEffect(() => {
    refreshHistory().catch((error: unknown) => {
      console.error(error);
      setSubmitError("履歴の取得に失敗しました。Web API が起動しているか確認してください。");
    });
  }, [refreshHistory]);

  useEffect(() => {
    if (!currentRunId) {
      return;
    }

    let timeoutId: number | undefined;
    let cancelled = false;
    let resultSettlePollCount = 0;

    const poll = async () => {
      const snapshot = await getRun(currentRunId);
      if (!snapshot || cancelled) {
        if (!cancelled) {
          setRunSummaries((prev) => {
            const next = { ...prev };
            delete next[currentRunId];
            return next;
          });
          setRunDetails((prev) => {
            const next = { ...prev };
            delete next[currentRunId];
            return next;
          });
          setCurrentRunId(null);
          setView("history");
        }
        return;
      }

      setRunDetails((prev) => ({
        ...prev,
        [snapshot.run_id]: snapshot,
      }));
      setRunSummaries((prev) => ({
        ...prev,
        [snapshot.run_id]: toRunSummary(snapshot),
      }));

      if (snapshot.status === "finished" && snapshot.result === null) {
        resultSettlePollCount += 1;
      } else {
        resultSettlePollCount = 0;
      }

      if (shouldContinuePolling(snapshot, resultSettlePollCount)) {
        timeoutId = window.setTimeout(() => {
          poll().catch((error: unknown) => {
            console.error(error);
            setSubmitError("run の更新取得に失敗しました。");
          });
        }, 1000);
        return;
      }

      if (snapshot.status === "finished" && snapshot.result === null) {
        setSubmitError("調査は完了しましたが、結果の反映が遅れています。");
      }

      refreshHistory().catch((error: unknown) => {
        console.error(error);
      });
    };

    poll().catch((error: unknown) => {
      console.error(error);
      setSubmitError("run の取得に失敗しました。");
    });

    return () => {
      cancelled = true;
      if (timeoutId !== undefined) {
        window.clearTimeout(timeoutId);
      }
    };
  }, [currentRunId, refreshHistory]);

  const handleSearch = useCallback(async (values: SearchFormValues) => {
    setIsSubmitting(true);
    setSubmitError(null);
    try {
      const run = await startRun(values);
      setRunDetails((prev) => ({
        ...prev,
        [run.run_id]: run,
      }));
      setRunSummaries((prev) => ({
        ...prev,
        [run.run_id]: toRunSummary(run),
      }));
      setCurrentRunId(run.run_id);
      setView("run");
    } catch (error) {
      console.error(error);
      setSubmitError("調査の開始に失敗しました。Web API と launcher の状態を確認してください。");
    } finally {
      setIsSubmitting(false);
    }
  }, []);

  const handleHistorySelect = useCallback((key: string) => {
    setCurrentRunId(key);
    setView("run");
  }, []);

  const handleCancelRun = useCallback(async (runId: string) => {
    setPendingCancels((prev) => ({ ...prev, [runId]: true }));
    setSubmitError(null);
    try {
      const snapshot = await cancelRun(runId);
      if (snapshot) {
        setRunDetails((prev) => ({
          ...prev,
          [snapshot.run_id]: snapshot,
        }));
        setRunSummaries((prev) => ({
          ...prev,
          [snapshot.run_id]: toRunSummary(snapshot),
        }));
      }
    } catch (error) {
      console.error(error);
      setSubmitError("調査の停止に失敗しました。");
    } finally {
      setPendingCancels((prev) => {
        const next = { ...prev };
        delete next[runId];
        return next;
      });
    }
  }, []);

  const handleDeleteRun = useCallback(async (runId: string) => {
    setPendingDeletes((prev) => ({ ...prev, [runId]: true }));
    setSubmitError(null);
    try {
      const deleted = await deleteRun(runId);
      if (!deleted) {
        return;
      }
      setRunSummaries((prev) => {
        const next = { ...prev };
        delete next[runId];
        return next;
      });
      setRunDetails((prev) => {
        const next = { ...prev };
        delete next[runId];
        return next;
      });
      if (currentRunId === runId) {
        setCurrentRunId(null);
        setView("history");
      }
    } catch (error) {
      console.error(error);
      setSubmitError("履歴の削除に失敗しました。");
    } finally {
      setPendingDeletes((prev) => {
        const next = { ...prev };
        delete next[runId];
        return next;
      });
      refreshHistory().catch((error: unknown) => {
        console.error(error);
      });
    }
  }, [currentRunId, refreshHistory]);

  return (
    <>
      <header>
        <div className="logo">
          <img src={appIcon} alt="" width={22} height={22} style={{ marginRight: 7, borderRadius: 5, flexShrink: 0 }} />
          Price Search <span>/ 価格調査</span>
        </div>
        <nav>
          <button
            className={view === "search" ? "active" : ""}
            onClick={() => setView("search")}
          >
            調査
          </button>
          <button
            className={view === "history" ? "active" : ""}
            onClick={() => setView("history")}
          >
            履歴
          </button>
        </nav>
      </header>

      <main>
        {submitError && <div className="app-error">{submitError}</div>}

        {view === "search" && (
          <SearchForm onSubmit={handleSearch} isSubmitting={isSubmitting} />
        )}

        {view === "run" && currentRun && (
          <RunView
            key={currentRun.run_id}
            run={currentRun}
            instant
            onCancel={handleCancelRun}
            onDelete={handleDeleteRun}
            isCancelling={pendingCancels[currentRun.run_id] === true}
            isDeleting={pendingDeletes[currentRun.run_id] === true}
          />
        )}

        {view === "run" && currentRunId && !currentRun && (
          <div className="tl-empty">調査詳細を読み込んでいます...</div>
        )}

        {view === "history" && (
          <HistoryList
            runs={historyRuns}
            onSelect={handleHistorySelect}
            onCancel={handleCancelRun}
            onDelete={handleDeleteRun}
            pendingCancels={pendingCancels}
            pendingDeletes={pendingDeletes}
          />
        )}
      </main>
    </>
  );
}

function toRunSummary(run: RunData): RunSummary {
  return {
    run_id: run.run_id,
    product_name: run.product_name,
    market: run.market,
    currency: run.currency,
    max_offers: run.max_offers,
    model: run.model,
    status: run.status,
    started_at: run.started_at,
    finished_at: run.finished_at,
    duration_ms: run.duration_ms,
    total_cost_usd: run.total_cost_usd,
    num_turns: run.num_turns,
  };
}

function shouldContinuePolling(
  run: RunData,
  resultSettlePollCount: number,
): boolean {
  if (run.status === "researching") {
    return true;
  }
  return (
    run.status === "finished"
    && run.result === null
    && resultSettlePollCount < RESULT_SETTLE_POLL_LIMIT
  );
}
