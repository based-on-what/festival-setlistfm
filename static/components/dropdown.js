import { SkeletonLoader } from './skeleton.js';

/**
 * SearchDropdown — accessible combobox dropdown.
 *
 * Manages its own ARIA attributes (aria-expanded, aria-activedescendant,
 * aria-selected) and keyboard navigation (ArrowUp/Down, Enter, Escape).
 *
 * Usage:
 *   const dd = new SearchDropdown('search-results', 'artist-input', artist => addArtist(artist));
 *   dd.showSkeleton();       // show shimmer rows while search is in flight
 *   dd.hideSkeleton();       // close without results (error / empty)
 *   dd.render(artists);      // replace skeleton with real results
 *   dd.close();              // hide + reset
 *   dd.isOpen();             // → boolean
 *   input.addEventListener('keydown', e => dd.handleKeydown(e));
 */
export class SearchDropdown {
  #container;
  #input;
  #onSelect;
  #activeIndex = -1;
  #skeleton;
  #loadMoreBtn = null;

  constructor(containerId, inputId, onSelect, { skeletonCount = 3 } = {}) {
    this.#container = document.getElementById(containerId);
    this.#input     = document.getElementById(inputId);
    this.#onSelect  = onSelect;
    this.#skeleton  = new SkeletonLoader(this.#container, { count: skeletonCount });
  }

  showSkeleton() {
    this.#activeIndex = -1;
    this.#input.removeAttribute('aria-activedescendant');
    this.#skeleton.show();
    this.#input.setAttribute('aria-expanded', 'true');
  }

  hideSkeleton() {
    this.#skeleton.hide();
    this.#input.setAttribute('aria-expanded', 'false');
    this.#activeIndex = -1;
    this.#input.removeAttribute('aria-activedescendant');
  }

  render(artists, { append = false, hasMore = false, onLoadMore = null } = {}) {
    this.#skeleton.hide();
    this.#activeIndex = -1;

    if (!append) {
      this.#container.innerHTML = '';
      this.#loadMoreBtn = null;
    } else {
      this.#loadMoreBtn?.remove();
      this.#loadMoreBtn = null;
    }

    if (artists.length === 0 && !append) {
      const empty = document.createElement('div');
      empty.className = 'dropdown-empty';
      empty.textContent = 'No artists found. Check the spelling and try again.';
      this.#container.appendChild(empty);
      this.open();
      return;
    }

    const frag   = document.createDocumentFragment();
    const offset = this.#container.querySelectorAll('[role="option"]').length;

    artists.forEach((artist, i) => {
      const item = document.createElement('div');
      item.className = 'dropdown-item';
      item.setAttribute('role', 'option');
      item.setAttribute('id', `option-${offset + i}`);
      item.setAttribute('aria-selected', 'false');
      item.tabIndex = -1;

      const metaHtml = artist.disambiguation
        ? `<span class="dropdown-meta"></span>`
        : '';

      item.innerHTML = `
        <span class="dropdown-name"></span>
        ${metaHtml}`;

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

    if (hasMore && onLoadMore) {
      this.#loadMoreBtn = document.createElement('button');
      this.#loadMoreBtn.type = 'button';
      this.#loadMoreBtn.className = 'dropdown-load-more';
      this.#loadMoreBtn.textContent = 'Load more results';
      this.#loadMoreBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        onLoadMore();
      });
      this.#container.appendChild(this.#loadMoreBtn);
    }

    this.open();
  }

  setLoadMoreLoading(loading) {
    if (!this.#loadMoreBtn) return;
    this.#loadMoreBtn.disabled = loading;
    this.#loadMoreBtn.textContent = loading ? 'Loading…' : 'Load more results';
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
    if (e.key === 'Escape') {
      this.close();
      return;
    }
    const items = [...this.#container.querySelectorAll('[role="option"]')];
    if (!items.length) return;

    switch (e.key) {
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
