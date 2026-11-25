# CareCircle Lite

A shared today list for one family looking after a parent. It shows what is overdue, still due, and already done, on a phone, and one tap records who did it and when.

## Run

```bash
docker compose up --build
```

Open [http://localhost:8080](http://localhost:8080).

API docs: [http://localhost:8000/docs](http://localhost:8000/docs).

The first startup loads a sample day for Asha Menon (“Mum”), with Ravi, Priya, and Anita on the shared phone. The sample times move with the clock, so overdue, due, and done are all visible whenever that is possible. After 9:12am, Ravi has given the morning blood pressure tablet and the 8pm tablet is still open.

Reset the database:

```bash
docker compose down -v
```

The Postgres password in `docker-compose.yml` is for this local demo only.

### Optional assistant model

With no key, “Ask about today” is answered from the task list by a template, and the words are streamed to the page. To stream from Groq instead, copy `.env.example` to `.env` and set `GROQ_API_KEY`. If Groq fails, the template answer is used.

### Tests

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest
```

The tests use an in-memory SQLite database. The running app uses Postgres. CI runs the same pytest suite and a frontend typecheck.

For local UI work without Docker:

```bash
cd backend && source .venv/bin/activate
DATABASE_URL=sqlite:///./carecircle.db uvicorn app.main:app --reload

cd frontend && npm run dev
```

The dev server proxies `/api` to port 8000. Use Docker for the real run.

## What it does

- Today is three groups: overdue, due, and done.
- Add a medicine, an appointment, or a check-in for today or tomorrow.
- Tap your name, then “Ravi did this”. That stores who and when.
- Undo puts the task back.
- If two people mark the same task, the first write wins and the second person sees who already did it.
- Ask about today. The answer streams in. Each question is stored with the context that was sent, the answer, and the latency.

Look at the log:

```bash
docker compose exec db psql -U carecircle -d carecircle \
  -c "select created_at, latency_ms, source, question, answer from assistant_logs order by id desc limit 5;"
```

## Design choices

**One family, one parent.** The brief is a shared place for one household, not a clinic product. There is one care recipient per database. Family members are seeded, not signed up.

**Today is one function.** `classify_task` in `backend/app/today.py` is the whole rule, and both the Today screen and the assistant use it.

- Finished today stays in done, including a task that was due earlier or finished early.
- Anything unfinished whose time has already passed is overdue, including earlier days. A missed tablet from yesterday is still missed.
- Unfinished tasks later today are due.
- Tomorrow, and anything finished on another day, stays off the board.

A task due at 23:59 India time is still today. One minute later, in UTC, is tomorrow and is not on the board. That boundary is tested. Grouping happens in Python because one family has a small list, and the timezone rule should exist in one place rather than be rewritten as SQL.

**The day is Mum’s, not the phone’s.** Times are wall-clock times in `Asia/Kolkata`. A phone in another timezone still shows her day. The API stores UTC.

**Who did it, without accounts.** The phone by the bed is shared. The names stay on screen, and the button says “Ravi did this”, so the choice is not buried in a menu. I did not add login. I also did not deploy this: a care list with no accounts should not be on the public internet. The part I would rather show is two people tapping Done at once. `complete_task` does not trust the row it just read. It runs one `UPDATE ... WHERE status = 'pending'`. One tap changes the row. The other changes nothing, and the response names the person and the time that were saved first.

**The assistant only reads the list.** It does not invent a dose or tell anyone to change care. That line is on the screen as well as in the prompt. The template and Groq both narrate the same grouped tasks the screen shows. “What did we miss?” talks about overdue tasks. The log still stores the full context, including tasks the answer did not mention, so a later review can see what the assistant was looking at.

**Streaming is the behaviour, not the model.** The endpoint is server-sent events. The template is sent a word at a time. Groq is forwarded token by token. Nginx turns proxy buffering off so the words are not held until the end.

**The type is large on purpose.** Atkinson Hyperlegible is a face designed for low vision, which fits a tired caregiver. It is bundled with the app. The page does not call a font CDN. State is a word on the card (“Overdue”, “Due”, “Done”), not only a colour. The add form and the name picker are on the page, not behind a menu.

**Tables are created on startup.** `create_all` is enough while the schema is still this small. Alembic belongs with the first real migration, not before there is data to protect.

## Assumptions

- One care recipient per database.
- “Done today” means `completed_at` falls on today’s date in the family’s timezone.
- An unfinished task from a previous day stays overdue until someone deals with it.
- The person who taps their name is telling the truth. There is no password.
- A time entered in the form is India time, even if the phone is set to something else.
- The assistant is a reader of the list, not a clinician.

## What I would do next

- An account per person, so the name on a tap cannot be switched by whoever is holding the phone.
- Repeating medicines, so the 8pm tablet does not have to be added again every day.
- A reminder before a dose is due, while the task is still in “due” rather than after it has slipped.
- Alembic, once the schema has to change under real rows.
- A private page over `assistant_logs` for reviewing bad answers.
- A hosted deploy only after login exists.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/family` | The parent and the people who can mark tasks |
| GET | `/api/today` | Overdue, due, and done |
| GET | `/api/tasks` | Every task |
| POST | `/api/tasks` | Add a task (`due_date` and `due_time` are local) |
| PATCH | `/api/tasks/{id}` | Change the title, time, note, or reopen it |
| POST | `/api/tasks/{id}/complete` | Record who did it. `409` if someone already has |
| POST | `/api/tasks/{id}/reopen` | Undo |
| POST | `/api/assistant/ask` | Stream an answer as server-sent events |

## Tools

Cursor, with the Grok coding assistant, to implement the app from the brief. The tests were run locally with pytest, and the screen was checked in a browser. I can walk through and change the today rules and the conditional update.

## Hours

Replace this with the hours you spent before you submit.
