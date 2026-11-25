export type Category = "medicine" | "appointment" | "checkin";

export type Member = {
  id: number;
  name: string;
  relationship: string;
};

export type Recipient = {
  id: number;
  name: string;
  preferred_name: string;
  timezone: string;
};

export type Task = {
  id: number;
  title: string;
  category: Category;
  due_at: string;
  status: "pending" | "done";
  notes: string | null;
  completed_at: string | null;
  completed_by: Member | null;
  created_at: string;
};

export type Today = {
  timezone: string;
  now: string;
  date: string;
  recipient: Recipient;
  overdue: Task[];
  due: Task[];
  done: Task[];
};

export type Family = {
  recipient: Recipient;
  members: Member[];
};

export type Bucket = "overdue" | "due" | "done";
