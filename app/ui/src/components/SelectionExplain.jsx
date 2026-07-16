import { useEffect, useRef, useState } from 'preact/hooks';
import { askAgent, explainSelectionQuestion } from '../api.js';
import { ExplainStrip, SparkIcon } from './ExplainButton.jsx';

// Never trigger inside input fields or either chat surface (MiniChatDock,
// ChatPanel) or the explain popover itself (FINAL_SPEC scope note).
function inExcludedZone(node) {
  const el = node && (node.nodeType === 3 ? node.parentElement : node);
  if (!el || typeof el.closest !== 'function') return false;
  return !!el.closest(
    'input, textarea, select, [contenteditable="true"], .chat-panel, .mini-dock, .explain-strip, .selection-explain',
  );
}

/**
 * Selection-explain (operator request #4): highlight any text in the main
 * app area -> a floating "Explain with AI" chip appears near the selection
 * -> click posts `/api/agent/ask` with the tab-scoped prefix and renders the
 * grounded answer in the same inline popover style as the panel explain
 * affordance. Debounced; dismissed on scroll or click-away; inert over
 * inputs and both chat surfaces.
 */
export default function SelectionExplain({ tabLabel }) {
  const [chip, setChip] = useState(null); // {x, y, text}
  const [popover, setPopover] = useState(null);
  const debounceRef = useRef(null);

  useEffect(() => {
    const clear = () => {
      setChip(null);
      setPopover(null);
    };

    const onSelectionChange = () => {
      clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => {
        const sel = typeof window.getSelection === 'function' ? window.getSelection() : null;
        const text = sel ? sel.toString().trim() : '';
        if (!sel || !text || text.length < 2 || sel.rangeCount === 0) {
          clear();
          return;
        }
        if (inExcludedZone(sel.anchorNode) || inExcludedZone(sel.focusNode)) {
          clear();
          return;
        }
        const main = document.querySelector('.app-main');
        const range = sel.getRangeAt(0);
        if (!main || !main.contains(range.commonAncestorContainer)) {
          clear();
          return;
        }
        const rect = range.getBoundingClientRect();
        if (!rect || (rect.width === 0 && rect.height === 0)) {
          clear();
          return;
        }
        setChip({ x: rect.left + rect.width / 2, y: rect.bottom, text });
        setPopover(null);
      }, 220);
    };

    const onMouseDown = (e) => {
      if (e.target && e.target.closest && e.target.closest('.selection-explain')) return;
      clear();
    };
    const onScroll = () => clear();

    document.addEventListener('selectionchange', onSelectionChange);
    document.addEventListener('mousedown', onMouseDown);
    window.addEventListener('scroll', onScroll, true);
    return () => {
      document.removeEventListener('selectionchange', onSelectionChange);
      document.removeEventListener('mousedown', onMouseDown);
      window.removeEventListener('scroll', onScroll, true);
      clearTimeout(debounceRef.current);
    };
  }, []);

  const ask = async () => {
    if (!chip) return;
    setPopover({ status: 'loading' });
    try {
      const question = explainSelectionQuestion(tabLabel, chip.text);
      const res = await askAgent(question);
      setPopover({ status: 'done', ...res });
    } catch (err) {
      setPopover({ status: 'network-error', message: err.message });
    }
  };

  if (!chip) return null;

  return (
    <div class="selection-explain" style={{ left: `${chip.x}px`, top: `${chip.y + 8}px` }}>
      {!popover && (
        <button type="button" class="selection-chip" onClick={ask}>
          <SparkIcon size={12} />
          Explain with AI
        </button>
      )}
      {popover && <ExplainStrip state={popover} floating />}
    </div>
  );
}
