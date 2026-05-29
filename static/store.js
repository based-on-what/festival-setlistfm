/**
 * ArtistStore — single source of truth for the festival lineup.
 * Extends EventTarget so consumers can listen for 'change' events.
 *
 * Usage:
 *   const store = new ArtistStore();
 *   store.addEventListener('change', ({ detail }) => render(detail));
 *   store.add(artist);   // → true if added, false if duplicate
 *   store.remove(id);    // → removed artist object, or null
 *   store.move(0, 2);    // reorder by index
 *   store.clear();
 */
export class ArtistStore extends EventTarget {
  #artists = [];

  get artists() { return [...this.#artists]; }
  get count()   { return this.#artists.length; }

  has(id) {
    return this.#artists.some(a => a.id === id);
  }

  add(artist) {
    if (this.has(artist.id)) return false;
    this.#artists.push(artist);
    this.#dispatch();
    return true;
  }

  remove(id) {
    const idx = this.#artists.findIndex(a => a.id === id);
    if (idx === -1) return null;
    const [removed] = this.#artists.splice(idx, 1);
    this.#dispatch();
    return removed;
  }

  move(fromIdx, toIdx) {
    if (fromIdx === toIdx) return;
    const [item] = this.#artists.splice(fromIdx, 1);
    this.#artists.splice(toIdx, 0, item);
    this.#dispatch();
  }

  clear() {
    this.#artists = [];
    this.#dispatch();
  }

  #dispatch() {
    this.dispatchEvent(new CustomEvent('change', { detail: this.artists }));
  }
}
