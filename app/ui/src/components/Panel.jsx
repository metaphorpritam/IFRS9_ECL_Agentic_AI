import { useExplain } from './ExplainButton.jsx';

/**
 * The exhibit frame (FINAL_SPEC.md §5.2). Every chart/table panel gets a
 * numbered `Exhibit N` kicker (numbered top-to-bottom PER TAB — pass the
 * running number as `exhibit`) plus a mandatory `Source:` footer; panels
 * that are not numbered exhibits (control panels, guides, prose) simply omit
 * `exhibit`/`source`. Every panel — numbered or not — still gets the
 * AI-explain icon via `buildExplainQuestion` so no heading is ever missed
 * (operator request #3). The icon sits in the header action cluster; the
 * answer strip renders inline UNDER the panel body (§7.4).
 */
export default function Panel({
  id,
  exhibit,
  title,
  subtitle,
  source,
  actions,
  explainLabel,
  buildExplainQuestion,
  dense = true,
  className = '',
  children,
}) {
  const { button: explainBtn, strip: explainStrip } = useExplain({
    label: explainLabel || title,
    buildQuestion: buildExplainQuestion,
  });
  return (
    <section id={id} class={`panel exhibit-panel ${className}`}>
      <div class="panel-kicker-row">
        <span class="exhibit-kicker">{exhibit != null ? `Exhibit ${exhibit}` : ''}</span>
        <span class="panel-actions">
          {actions}
          {explainBtn}
        </span>
      </div>
      <h2>{title}</h2>
      {subtitle && <p class="panel-sub">{subtitle}</p>}
      {dense && <div class="panel-hr" />}
      <div class="panel-body">{children}</div>
      {explainStrip}
      {source && (
        <>
          <div class="panel-hr" />
          <p class="panel-source">
            Source: <code>{source.endpoint}</code> · run {source.runDate}
          </p>
        </>
      )}
    </section>
  );
}
