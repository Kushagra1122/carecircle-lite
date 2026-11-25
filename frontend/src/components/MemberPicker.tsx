import type { Member } from "../types";

type Props = {
  members: Member[];
  selectedId: number;
  onSelect: (id: number) => void;
};

export function MemberPicker({ members, selectedId, onSelect }: Props) {
  return (
    <section className="who-bar" aria-labelledby="who-heading">
      <h2 id="who-heading">Who is marking tasks?</h2>
      <p className="hint">Tap your name. Done records who and when.</p>
      <div className="members" role="radiogroup" aria-label="Who is marking tasks">
        {members.map((member) => {
          const selected = member.id === selectedId;
          return (
            <button
              key={member.id}
              type="button"
              role="radio"
              aria-checked={selected}
              className="member"
              onClick={() => onSelect(member.id)}
            >
              {member.name}
              <small>{label(member.relationship)}</small>
            </button>
          );
        })}
      </div>
    </section>
  );
}

function label(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}
