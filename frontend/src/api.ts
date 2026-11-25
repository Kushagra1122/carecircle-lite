import type { Family, Task, Today } from "./types";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  });
  if (!response.ok) {
    throw new ApiError(response.status, await errorMessage(response));
  }
  return response.json() as Promise<T>;
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body.detail === "string") return body.detail;
    if (typeof body.detail?.message === "string") return body.detail.message;
  } catch {
    /* the body was not JSON */
  }
  return `Request failed (${response.status})`;
}

export function getFamily(): Promise<Family> {
  return request("/api/family");
}

export function getToday(): Promise<Today> {
  return request("/api/today");
}

export function createTask(input: {
  title: string;
  category: Task["category"];
  due_date: string;
  due_time: string;
  notes: string;
}): Promise<Task> {
  return request("/api/tasks", { method: "POST", body: JSON.stringify(input) });
}

export function reopenTask(id: number): Promise<Task> {
  return request(`/api/tasks/${id}/reopen`, { method: "POST" });
}

export async function completeTask(
  id: number,
  memberId: number,
): Promise<
  | { ok: true; task: Task }
  | { ok: false; status: number; message: string; completedById: number | null }
> {
  const response = await fetch(`/api/tasks/${id}/complete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ member_id: memberId }),
  });
  const body = await response.json().catch(() => null);
  if (response.ok) return { ok: true, task: body as Task };
  const detail = body?.detail;
  const message =
    typeof detail === "string"
      ? detail
      : (detail?.message ?? "Couldn't mark that done. Try again.");
  const completedById =
    typeof detail?.completed_by_id === "number" ? detail.completed_by_id : null;
  return { ok: false, status: response.status, message, completedById };
}
