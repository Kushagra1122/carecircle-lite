import { useCallback, useEffect, useRef, useState } from "react";
import { completeTask, getFamily, getToday, reopenTask } from "./api";
import { AskToday } from "./components/AskToday";
import { AddTaskForm } from "./components/AddTaskForm";
import { MemberPicker } from "./components/MemberPicker";
import { TaskSection } from "./components/TaskSection";
import { clockTime, longDate } from "./time";
import type { Family, Task, Today } from "./types";

const MEMBER_KEY = "carecircle.memberId";

export function App() {
  const [phase, setPhase] = useState<"loading" | "ready" | "error">("loading");
  const [family, setFamily] = useState<Family | null>(null);
  const [today, setToday] = useState<Today | null>(null);
  const [memberId, setMemberId] = useState<number | null>(null);
  const [banner, setBanner] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const generation = useRef(0);

  const reload = useCallback(async (reportError = true): Promise<boolean> => {
    const ticket = ++generation.current;
    setRefreshing(true);
    try {
      const next = await getToday();
      if (ticket === generation.current) setToday(next);
      return true;
    } catch {
      if (reportError && ticket === generation.current) {
        setBanner("Couldn't refresh. The list on screen may be old.");
      }
      return false;
    } finally {
      if (ticket === generation.current) setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const [nextFamily, nextToday] = await Promise.all([getFamily(), getToday()]);
        if (cancelled) return;
        setFamily(nextFamily);
        setToday(nextToday);
        setMemberId(chooseInitial(nextFamily));
        setPhase("ready");
      } catch {
        if (!cancelled) setPhase("error");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!today) return;
    document.title =
      today.overdue.length > 0 ? `CareCircle · ${today.overdue.length} overdue` : "CareCircle";
  }, [today]);

  useEffect(() => {
    if (phase !== "ready") return;
    const id = window.setInterval(() => void reload(false), 60_000);
    const onVisible = () => {
      if (document.visibilityState === "visible") void reload(false);
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      window.clearInterval(id);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [phase, reload]);

  function selectMember(id: number) {
    setMemberId(id);
    try {
      localStorage.setItem(MEMBER_KEY, String(id));
    } catch {
      /* private mode */
    }
  }

  async function onDone(task: Task) {
    if (memberId === null) return;
    setBusyId(task.id);
    setBanner(null);
    try {
      const result = await completeTask(task.id, memberId);
      const refreshed = await reload(false);
      if (!result.ok) setBanner(result.message);
      else if (!refreshed) setBanner("Saved, but the list didn't refresh.");
    } catch (error) {
      setBanner(error instanceof Error ? error.message : "Couldn't mark that done. Try again.");
    } finally {
      setBusyId(null);
    }
  }

  async function onUndo(task: Task) {
    setBusyId(task.id);
    setBanner(null);
    try {
      await reopenTask(task.id);
      const refreshed = await reload(false);
      if (!refreshed) setBanner("Undone, but the list didn't refresh.");
    } catch (error) {
      setBanner(error instanceof Error ? error.message : "Couldn't undo that.");
    } finally {
      setBusyId(null);
    }
  }

  async function onAdded(task: Task) {
    const refreshed = await reload(false);
    if (refreshed) setBanner(`Added "${task.title}".`);
    else setBanner("Added, but the list didn't refresh.");
  }

  if (phase === "loading") {
    return (
      <main className="wrap">
        <p className="brand">CareCircle</p>
        <h1>Loading today…</h1>
      </main>
    );
  }

  if (phase === "error" || !family || !today) {
    return (
      <main className="wrap">
        <p className="brand">CareCircle</p>
        <h1>Couldn't load today</h1>
        <p>Check that the app is running, then try again.</p>
        <button type="button" className="done-btn" onClick={() => window.location.reload()}>
          Try again
        </button>
      </main>
    );
  }

  const member = family.members.find((item) => item.id === memberId) ?? family.members[0];
  if (!member) {
    return (
      <main className="wrap">
        <p className="brand">CareCircle</p>
        <h1>No family members yet</h1>
      </main>
    );
  }

  return (
    <main className="wrap">
      <header>
        <p className="brand">CareCircle</p>
        <h1>{today.recipient.preferred_name}</h1>
        <p className="sub">
          {today.recipient.name} · {longDate(today.date)}
        </p>
      </header>
      <div className="summary-row">
        <p className="summary">
          {today.overdue.length} overdue · {today.due.length} still due · {today.done.length} done
        </p>
        <div className="actions">
          <a className="text-btn" href="#add-task">
            Add a task
          </a>
          <button type="button" className="text-btn" onClick={() => void reload()}>
            {refreshing ? "Updating…" : "Refresh"}
          </button>
        </div>
      </div>
      <p className="as-of">As of {clockTime(today.now, today.timezone)}</p>
      {banner ? (
        <p className="banner" role="status">
          {banner}
        </p>
      ) : null}
      <MemberPicker members={family.members} selectedId={member.id} onSelect={selectMember} />
      <TaskSection
        bucket="overdue"
        tasks={today.overdue}
        memberName={member.name}
        busyId={busyId}
        timeZone={today.timezone}
        todayDate={today.date}
        onDone={(task) => void onDone(task)}
        onUndo={(task) => void onUndo(task)}
      />
      <TaskSection
        bucket="due"
        tasks={today.due}
        memberName={member.name}
        busyId={busyId}
        timeZone={today.timezone}
        todayDate={today.date}
        onDone={(task) => void onDone(task)}
        onUndo={(task) => void onUndo(task)}
      />
      <TaskSection
        bucket="done"
        tasks={today.done}
        memberName={member.name}
        busyId={busyId}
        timeZone={today.timezone}
        todayDate={today.date}
        onDone={(task) => void onDone(task)}
        onUndo={(task) => void onUndo(task)}
      />
      <AddTaskForm
        timeZone={today.timezone}
        todayDate={today.date}
        nowIso={today.now}
        onAdded={(task) => void onAdded(task)}
        onError={setBanner}
      />
      <AskToday />
      <footer>
        <p>Times are India time ({today.timezone.replace("_", " ")}).</p>
        <p>The assistant only reads this list and does not give medical advice.</p>
      </footer>
    </main>
  );
}

function chooseInitial(family: Family): number | null {
  if (family.members.length === 0) return null;
  try {
    const saved = Number(localStorage.getItem(MEMBER_KEY));
    if (family.members.some((member) => member.id === saved)) return saved;
  } catch {
    /* private mode */
  }
  return family.members[0].id;
}
