/** Wrap every numeric token in agent-answer prose in a `.num` span
 * (tabular-nums, `--ink` — FINAL_SPEC §2 "numbers quoted inline in agent
 * answers"). Display-only formatting; never re-parses/re-computes the
 * number, just re-wraps the substring the answer already contains. */
const NUM_RE = /([+\-−]?\$?\d[\d,]*\.?\d*(?:pp|%|x|m)?\b)/g;

export function renderWithNums(text) {
  if (!text) return text;
  const parts = String(text).split(NUM_RE);
  return parts.map((part, i) => (i % 2 === 1 ? <span class="num" key={i}>{part}</span> : part));
}
