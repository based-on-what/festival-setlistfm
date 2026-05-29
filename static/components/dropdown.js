import { escapeHtml } from './utils.js';

/**
 * SearchDropdown — accessible combobox dropdown.
 *
 * Manages its own ARIA attributes (aria-expanded, aria-activedescendant,
 * aria-selected) and keyboard navigation (ArrowUp/Down, Enter, Escape).
 *
 * Usage:
 *   const dd = new SearchDropdown('search-results', 'artist-input', artist => addArtist(artist));
 *   dd.render(artists);   // show list
 *   dd.close();           // hide + reset active index
 *   dd.isOpen();          // → boolean
 *   // Wire up keydown on the input:
 *   input.addEventListener('keydown', e => dd.handleKeydown(e));
 */
export class SearchDropdown {
  #container;
  #input;
  #onSelect;
  #activeIndex = -1;

  constructor(containerId, inputId, onSelect) {
    this.#container = document.getElementById(containerId);
    this.#input     = document.getElementById(inputId);
    this.#onSelect  = onSelect;
  }

  render(artists) {
    this.#activeIndex = -1;
    this.#container.innerHTML = '';

    if (!artists.length) {
      this.close();
      return;
    }

    const frag = document.createDocumentFragment();

    artists.forEach((artist, i) => {
      const item = document.createElement('div');
      item.className = 'dropdown-item';
      item.setAttribute('role', 'option');
      item.setAttribute('id', `option-${i}`);
      item.setAttribute('aria-selected', 'false');
      item.tabIndex = -1;

      const thumbHtml = artist.imageUrl
        ? `<img class="dropdown-thumb" src="${escapeHtml(artist.imageUrl)}" alt="" loading="lazy">`
        : `<div class="dropdown-thumb-placeholder" aria-hidden="true">🎤</div>`;

      const metaHtml = artist.disambiguation
        ? `<span class="dropdown-meta"></span>`
        : '';

      item.innerHTML = `
        ${thumbHtml}
        <div class="dropdown-info">
          <span class="dropdown-name"></span>
          ${metaHtml}
        </div>`;

      item.querySelector('.dropdown-name').textContent = artist.name;
      if (artist.disambiguation) {
        item.querySelector('.dropdown-meta').textContent = artist.disambiguation;
      }

      item.addEventListener('click', () => {
        this.#onSelect(artist);
        this.close();
      });

      frag.appendChild(item);
    });

    this.#container.appendChild(frag);
    this.open();
  }

  open() {
    this.#container.classList.remove('hidden');
    this.#input.setAttribute('aria-expanded', 'true');
  }

  close() {
    this.#container.classList.add('hidden');
    this.#input.setAttribute('aria-expanded', 'false');
    this.#activeIndex = -1;
    this.#input.removeAttribute('aria-activedescendant');
  }

  isOpen() {
    return !this.#container.classList.contains('hidden');
  }

  handleKeydown(e) {
    if (!this.isOpen()) return;
    const items = [...this.#container.querySelectorAll('[role="option"]')];
    if (!items.length) return;

    switch (e.key) {
      case 'Escape':
        this.close();
        break;
      case 'ArrowDown':
        e.preventDefault();
        this.#activeIndex = Math.min(this.#activeIndex + 1, items.length - 1);
        this.#updateActive(items);
        break;
      case 'ArrowUp':
        e.preventDefault();
        this.#activeIndex = Math.max(this.#activeIndex - 1, -1);
        this.#updateActive(items);
        break;
      case 'Enter':
        if (this.#activeIndex >= 0) {
          e.preventDefault();
          items[this.#activeIndex].click();
        }
        break;
    }
  }

  #updateActive(items) {
    items.forEach((item, i) => {
      item.setAttribute('aria-selected', String(i === this.#activeIndex));
    });
    if (this.#activeIndex >= 0) {
      this.#input.setAttribute('aria-activedescendant', `option-${this.#activeIndex}`);
      items[this.#activeIndex].scrollIntoView({ block: 'nearest' });
    } else {
      this.#input.removeAttribute('aria-activedescendant');
    }
  }
}
