import { useId, useState, type FormEvent } from "react";
import { createTask } from "../api";
import { defaultTime, shiftDate } from "../time";
import type { Category, Task } from "../types";

const CATEGORIES: { id: Category; label: string }[] = [
  { id: "medicine", label: "Medicine" },
  { id: "appointment", label: "Appointment" },
  { id: "checkin", label: "Check-in" },
];

type Props = {
  timeZone: string;
  todayDate: string;
  nowIso: string;
  onAdded: (task: Task) => void;
  onError: (message: string) => void;
};

export function AddTaskForm({ timeZone, todayDate, nowIso, onAdded, onError }: Props) {
  const titleId = useId();
  const noteId = useId();
  const timeId = useId();
  const initial = defaultTime(timeZone, nowIso);
  const [title, setTitle] = useState("");
  const [notes, setNotes] = useState("");
  const [category, setCategory] = useState<Category>("medicine");
  const [day, setDay] = useState<"today" | "tomorrow">(initial.day);
  const [time, setTime] = useState(initial.time);
  const [saving, setSaving] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const trimmed = title.trim();
    if (!trimmed || saving) return;
    setSaving(true);
    try {
      const task = await createTask({
        title: trimmed,
        category,
        due_date: shiftDate(todayDate, day === "tomorrow" ? 1 : 0),
        due_time: time,
        notes: notes.trim(),
      });
      setTitle("");
      setNotes("");
      onAdded(task);
    } catch (error) {
      onError(error instanceof Error ? error.message : "Couldn't add that task.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form id="add-task" className="panel" onSubmit={(event) => void submit(event)}>
      <h2>Add a task</h2>
      <label htmlFor={titleId}>What needs doing</label>
      <input
        id={titleId}
        value={title}
        maxLength={200}
        autoComplete="off"
        enterKeyHint="done"
        placeholder="Evening blood pressure tablet"
        onChange={(event) => setTitle(event.target.value)}
      />
      <p className="field-label" id="category-label">
        Kind
      </p>
      <div className="segment" role="radiogroup" aria-labelledby="category-label">
        {CATEGORIES.map((item) => (
          <button
            key={item.id}
            type="button"
            role="radio"
            aria-checked={category === item.id}
            onClick={() => setCategory(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>
      <p className="field-label" id="day-label">
        When
      </p>
      <div className="segment two" role="radiogroup" aria-labelledby="day-label">
        {(["today", "tomorrow"] as const).map((value) => (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={day === value}
            onClick={() => setDay(value)}
          >
            {value === "today" ? "Today" : "Tomorrow"}
          </button>
        ))}
      </div>
      <label htmlFor={timeId}>Time</label>
      <input id={timeId} type="time" value={time} required onChange={(event) => setTime(event.target.value)} />
      <label htmlFor={noteId}>Note, optional</label>
      <input
        id={noteId}
        value={notes}
        maxLength={500}
        placeholder="After food"
        onChange={(event) => setNotes(event.target.value)}
      />
      <button type="submit" className="done-btn" disabled={saving || title.trim() === ""}>
        {saving ? "Adding…" : "Add task"}
      </button>
    </form>
  );
}
