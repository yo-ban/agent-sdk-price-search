import { useCallback, useEffect, useMemo, useState } from "react";
import { cancelRun, deleteRun, getRun, listRuns, startRun } from "./api/client";
import type { RunData, SearchFormValues } from "./types";
import { SearchForm } from "./components/SearchForm";
import { RunView, HistoryList } from "./components/RunView";
import appIcon from "./assets/icon.svg";

type View = "search" | "run" | "history";

export default function App() {
  const [view, setView] = useState<View>("search");
  const [runs, setRuns] = useState<Record<string, RunData>>({});
  const [currentRunId, setCurrentRunId] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [pendingCancels, setPendingCancels] = useState<Record<string, boolean>>({});
  const [pendingDeletes, setPendingDeletes] = useState<Record<string, boolean>>({});

  const currentRun = currentRunId ? runs[currentRunId] ?? null : null;
  const historyRuns = useMemo(
    () =>
      Object.entries(runs).sort(([, left], [, right]) =>
        right.started_at.localeCompare(left.started_at),
      ),
    [runs],
  );

  const refreshHistory = useCallback(async () => {
    const fetchedRuns = await listRuns();
    setRuns(Object.fromEntries(fetchedRuns.map((run) => [run.run_id, run])));
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

    const poll = async () => {
      const snapshot = await getRun(currentRunId);
      if (!snapshot || cancelled) {
        if (!cancelled) {
          setRuns((prev) => {
            const next = { ...prev };
            delete next[currentRunId];
            return next;
          });
          setCurrentRunId(null);
          setView("history");
        }
        return;
      }

      setRuns((prev) => ({
        ...prev,
        [snapshot.run_id]: snapshot,
      }));

      if (snapshot.status === "researching") {
        timeoutId = window.setTimeout(() => {
          poll().catch((error: unknown) => {
            console.error(error);
            setSubmitError("run の更新取得に失敗しました。");
          });
        }, 1000);
        return;
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
      setRuns((prev) => ({
        ...prev,
        [run.run_id]: run,
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
    const run = runs[key];
    if (!run) return;
    setCurrentRunId(key);
    setView("run");
  }, [runs]);

  const handleCancelRun = useCallback(async (runId: string) => {
    setPendingCancels((prev) => ({ ...prev, [runId]: true }));
    setSubmitError(null);
    try {
      const snapshot = await cancelRun(runId);
      if (snapshot) {
        setRuns((prev) => ({
          ...prev,
          [snapshot.run_id]: snapshot,
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
      setRuns((prev) => {
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
