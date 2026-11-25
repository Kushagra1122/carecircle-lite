import type { Bucket, Task } from "../types";
import { clockTime, duePhrase } from "../time";

const COPY: Record<Bucket, { title: string; empty: string; kicker: string }> = {
  overdue: { title: "Overdue", empty: "Nothing overdue.", kicker: "Overdue" },
  due: { title: "Due", empty: "Nothing else due today.", kicker: "Due" },
  done: { title: "Done", empty: "Nothing marked done yet today.", kicker: "Done" },
};

const CATEGORY: Record<Task["category"], string> = {
  medicine: "Medicine",
  appointment: "Appointment",
  checkin: "Check-in",
};

type Props = {
  bucket: Bucket;
  tasks: Task[];
  memberName: string;
  busyId: number | null;
  timeZone: string;
  todayDate: string;
  onDone: (task: Task) => void;
  onUndo: (task: Task) => void;
};

export function TaskSection({
  bucket,
  tasks,
  memberName,
  busyId,
  timeZone,
  todayDate,
  onDone,
  onUndo,
}: Props) {
  const copy = COPY[bucket];
  return (
    <section className={`section ${bucket}`} aria-labelledby={`${bucket}-heading`}>
      <div className="section-head">
        <h2 id={`${bucket}-heading`}>{copy.title}</h2>
        <span className="count">{tasks.length}</span>
      </div>
      {tasks.length === 0 ? (
        <p className="empty">{copy.empty}</p>
      ) : (
        <ul className="tasks">
          {tasks.map((task) => (
            <li key={task.id} id={`task-${task.id}`} className={`card ${bucket}`}>
              <p className="kicker">
                {copy.kicker} · {CATEGORY[task.category]}
              </p>
              <h3>{task.title}</h3>
              <p className="when">Due {duePhrase(task.due_at, timeZone, todayDate)}</p>
              {task.notes ? <p className="note">{task.notes}</p> : null}
              {task.status === "done" ? (
                <>
                  <p className="who">
                    {task.completed_by?.name ?? "Someone"} at{" "}
                    {task.completed_at ? clockTime(task.completed_at, timeZone) : "an unknown time"}
                  </p>
                  <button
                    type="button"
                    className="undo"
                    disabled={busyId !== null}
                    onClick={() => onUndo(task)}
                  >
                    {busyId === task.id ? "Saving…" : "Undo"}
                  </button>
                </>
              ) : (
                <button
                  type="button"
                  className="done-btn"
                  disabled={busyId !== null}
                  onClick={() => onDone(task)}
                >
                  {busyId === task.id ? "Saving…" : `${memberName} did this`}
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
