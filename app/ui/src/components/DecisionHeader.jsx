/** Every Policy-tab panel is paired with the decision it informs (north-star
 * requirement) — this is the one-line header that names it. */
export default function DecisionHeader({ children }) {
  return (
    <div class="decision-header">
      <span class="decision-tag">Decision this informs</span>
      <span class="decision-text">{children}</span>
    </div>
  );
}
