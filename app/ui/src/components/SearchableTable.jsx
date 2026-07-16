import { useMemo, useState } from 'preact/hooks';

/** Generic searchable table. `columns`: [{key, label, render?}]. `rows`: array
 * of plain objects. Search matches any column's stringified value. Renders
 * markdown-lite backtick/glyph cells as-is (the API sends raw source cells). */
export default function SearchableTable({ columns, rows, placeholder, caption }) {
  const [q, setQ] = useState('');

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return rows;
    return rows.filter((r) =>
      columns.some((c) => String(r[c.key] ?? '').toLowerCase().includes(needle)),
    );
  }, [q, rows, columns]);

  return (
    <div class="searchable-table">
      <div class="table-toolbar">
        <input
          type="search"
          class="table-search"
          placeholder={placeholder || 'Search…'}
          value={q}
          onInput={(e) => setQ(e.currentTarget.value)}
        />
        <span class="table-count">
          {filtered.length} / {rows.length} rows
        </span>
      </div>
      {caption && <p class="panel-sub">{caption}</p>}
      <div class="table-scroll">
        <table class="data-table">
          <thead>
            <tr>
              {columns.map((c) => (
                <th class={c.align === 'right' ? 'num' : ''} key={c.key}>{c.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 && (
              <tr>
                <td class="empty-note" colSpan={columns.length}>
                  No rows match “{q}”.
                </td>
              </tr>
            )}
            {filtered.map((r, i) => (
              <tr key={i}>
                {columns.map((c) => (
                  <td class={c.align === 'right' ? 'num' : ''} key={c.key}>
                    {c.render ? c.render(r) : r[c.key]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
