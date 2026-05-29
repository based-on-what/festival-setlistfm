/**
 * SkeletonLoader — shimmer placeholder rows for search results.
 *
 * Renders into a dropdown container while a search is in flight,
 * giving users spatial context before real results arrive.
 * Animation is CSS-driven and respects prefers-reduced-motion.
 *
 * Usage:
 *   const sk = new SkeletonLoader(containerEl, { count: 3 });
 *   sk.show();   // clears container, appends shimmer rows, removes .hidden
 *   sk.hide();   // clears container, adds .hidden
 */
export class SkeletonLoader {
  #container;
  #count;

  constructor(container, { count = 3 } = {}) {
    this.#container = container;
    this.#count     = count;
  }

  show() {
    this.#container.innerHTML = '';
    const frag = document.createDocumentFragment();
    for (let i = 0; i < this.#count; i++) {
      frag.appendChild(this.#makeItem());
    }
    this.#container.appendChild(frag);
    this.#container.classList.remove('hidden');
  }

  hide() {
    this.#container.innerHTML = '';
    this.#container.classList.add('hidden');
  }

  #makeItem() {
    const item = document.createElement('div');
    item.className = 'skeleton-item';
    item.setAttribute('aria-hidden', 'true');

    const avatar = document.createElement('div');
    avatar.className = 'skeleton-pulse skeleton-avatar';

    const text = document.createElement('div');
    text.className = 'skeleton-text';

    const name = document.createElement('div');
    name.className = 'skeleton-pulse skeleton-name';

    const meta = document.createElement('div');
    meta.className = 'skeleton-pulse skeleton-meta';

    text.append(name, meta);
    item.append(avatar, text);
    return item;
  }
}
