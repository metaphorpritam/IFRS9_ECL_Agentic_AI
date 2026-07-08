import { useState } from 'preact/hooks';

/** A consultant-curated static exhibit: PNG + title + caption, from
 * /api/exhibits/list or an inline {title, png_url, caption}. */
export default function ExhibitImage({ title, png_url, caption, tall }) {
  const [broken, setBroken] = useState(false);
  return (
    <figure class={`exhibit ${tall ? 'exhibit-tall' : ''}`}>
      {title && <figcaption class="exhibit-title">{title}</figcaption>}
      {!broken ? (
        <img
          src={png_url}
          alt={title || caption || 'exhibit'}
          loading="lazy"
          onError={() => setBroken(true)}
        />
      ) : (
        <div class="exhibit-missing">exhibit unavailable ({png_url})</div>
      )}
      {caption && <p class="exhibit-caption">{caption}</p>}
    </figure>
  );
}
