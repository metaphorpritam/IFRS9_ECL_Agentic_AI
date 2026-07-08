import { useState } from 'preact/hooks';
import ChatPanel from './ChatPanel.jsx';

/** Collapsed mini-chat dock, present on tabs 1-4 (Copilot has its own
 * full-page chat instead). Reuses ChatPanel with the current tab name
 * prefixed into the question context. */
export default function MiniChatDock({ tabLabel }) {
  const [open, setOpen] = useState(false);

  return (
    <div class="mini-dock">
      {open && (
        <div class="mini-dock-panel">
          <div class="mini-dock-head">
            <span>Copilot — {tabLabel}</span>
            <button
              class="mini-dock-close"
              type="button"
              aria-label="Collapse chat"
              onClick={() => setOpen(false)}
            >
              ×
            </button>
          </div>
          <ChatPanel mode="dock" contextLabel={tabLabel} />
        </div>
      )}
      <button
        type="button"
        class="mini-dock-fab"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        {open ? 'Close' : 'Ask Copilot'}
      </button>
    </div>
  );
}
