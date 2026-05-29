import { escapeHtml } from './utils.js';

/**
 * createArtistItem — factory for a draggable artist list item.
 *
 * Returns a <li> element. Drag event handlers are attached by the caller
 * (app.js) via attachDragHandlers(), since they need access to store state.
 *
 * Data-action attributes drive delegated click handling in app.js:
 *   data-action="remove" data-id="..."   → remove artist
 *   data-action="swap"   data-index="N"  → mobile swap-reorder
 *
 * @param {object} artist          - { id, name, imageUrl? }
 * @param {number} index           - position in list (for data-index)
 * @param {object} [opts]
 * @param {boolean} [opts.isSwapSelected=false]
 * @returns {HTMLLIElement}
 */
export function createArtistItem(artist, index, { isSwapSelected = false } = {}) {
  const li = document.createElement('li');
  li.className = 'artist-item';
  li.draggable = true;

  const handleClass = `drag-handle${isSwapSelected ? ' swap-selected' : ''}`;

  li.innerHTML = `
    <span class="${handleClass}"
          data-action="swap" data-index="${index}"
          role="button" tabindex="0"
          title="Drag to reorder, or tap to swap">⠿</span>
    ${artist.imageUrl
      ? `<img class="artist-item-thumb"
              src="${escapeHtml(artist.imageUrl)}"
              alt=""
              loading="lazy">`
      : `<div class="artist-item-thumb-placeholder" aria-hidden="true">🎤</div>`
    }
    <span class="artist-item-name"></span>
    <button class="remove-btn"
            data-action="remove"
            data-id="${escapeHtml(String(artist.id))}">✕</button>
  `;

  // Safe text — not in innerHTML
  li.querySelector('.artist-item-name').textContent = artist.name;
  li.querySelector('.remove-btn').setAttribute('aria-label', `Remove ${artist.name} from lineup`);

  return li;
}
