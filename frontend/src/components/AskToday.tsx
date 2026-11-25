import { useState } from "react";

const SUGGESTIONS = ["What's still left?", "What did we miss?", "Who has helped today?"];

type EventPayload = {
  token?: string;
  done?: boolean;
  error?: string;
};

export function AskToday() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [asking, setAsking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function ask(text: string) {
    const trimmed = text.trim();
    if (!trimmed || asking) return;
    setQuestion(trimmed);
    setAnswer("");
    setError(null);
    setAsking(true);
    let spoken = "";
    try {
      const response = await fetch("/api/assistant/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
        body: JSON.stringify({ question: trimmed }),
      });
      if (!response.ok || !response.body) {
        setError(await plainError(response));
        return;
      }
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parsed = takeEvents(buffer);
        buffer = parsed.rest;
        for (const payload of parsed.events) {
          if (payload.token) {
            spoken += payload.token;
            setAnswer(spoken);
          }
          if (payload.error) setError(payload.error);
        }
      }
      if (!spoken) setError("No answer came back. Try again.");
    } catch {
      setError("The assistant didn't answer. Try again.");
    } finally {
      setAsking(false);
    }
  }

  return (
    <section id="ask" className="panel" aria-labelledby="ask-heading">
      <h2 id="ask-heading">Ask about today</h2>
      <p className="hint">It only reads this list. It won't suggest a dose or a change in care.</p>
      <div className="suggestions">
        {SUGGESTIONS.map((suggestion) => (
          <button
            key={suggestion}
            type="button"
            className="chip"
            disabled={asking}
            onClick={() => void ask(suggestion)}
          >
            {suggestion}
          </button>
        ))}
      </div>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void ask(question);
        }}
      >
        <label htmlFor="ask-input">Your question</label>
        <input
          id="ask-input"
          value={question}
          maxLength={500}
          enterKeyHint="send"
          placeholder="Ask in your own words"
          onChange={(event) => setQuestion(event.target.value)}
        />
        <button type="submit" className="done-btn" disabled={asking || question.trim() === ""}>
          {asking ? "Answering…" : "Ask"}
        </button>
      </form>
      <div className={answer ? "answer" : "answer placeholder"} aria-live="polite">
        {answer ||
          (asking
            ? "Looking at today's list…"
            : "The answer will show up here, a few words at a time.")}
        {asking && answer ? <span className="caret" aria-hidden="true" /> : null}
      </div>
      {error ? (
        <p className="banner" role="alert">
          {error}
        </p>
      ) : null}
    </section>
  );
}

function takeEvents(buffer: string): { events: EventPayload[]; rest: string } {
  const chunks = buffer.split("\n\n");
  const rest = chunks.pop() ?? "";
  const events: EventPayload[] = [];
  for (const chunk of chunks) {
    const line = chunk.split("\n").find((item) => item.startsWith("data:"));
    if (!line) continue;
    try {
      events.push(JSON.parse(line.slice(5).trim()) as EventPayload);
    } catch {
      /* ignore a malformed event */
    }
  }
  return { events, rest };
}

async function plainError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body.detail === "string") return body.detail;
  } catch {
    /* ignore */
  }
  return "The assistant didn't answer. Try again.";
}
