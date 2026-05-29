/**
 * Toast — static notification manager.
 *
 * Usage:
 *   Toast.error('Something went wrong');
 *   Toast.success('Playlist created!');
 *   Toast.warning('Some tracks are missing', 6000);
 *   Toast.info('Artist added', 3000);
 *
 * Stacks up to 5; oldest auto-removed when limit reached.
 * Auto-dismisses after `duration` ms (pass 0 to persist).
 * Respects prefers-reduced-motion.
 */
export class Toast {
  static #container = null;
  static #MAX = 5;

  static #init() {
    if (this.#container) return;
    this.#container = document.createElement('div');
    this.#container.className = 'toast-container';
    this.#container.setAttribute('aria-label', 'Notifications');
    document.body.appendChild(this.#container);
  }

  static #show(message, variant, duration = 4000) {
    this.#init();

    // Prune oldest when at limit
    const existing = this.#container.querySelectorAll('.toast');
    if (existing.length >= this.#MAX) this.#dismiss(existing[0], true);

    const icons = { error: '✕', success: '✓', warning: '⚠', info: 'ℹ' };
    const isAlert = variant === 'error' || variant === 'warning';

    const toast = document.createElement('div');
    toast.className = `toast toast--${variant}`;
    toast.setAttribute('role', isAlert ? 'alert' : 'status');
    if (isAlert) toast.setAttribute('aria-live', 'assertive');

    // Build inner HTML with static content; message set via textContent
    toast.innerHTML = `
      <span class="toast__icon" aria-hidden="true">${icons[variant]}</span>
      <span class="toast__message"></span>
      <button class="toast__close" aria-label="Dismiss notification">✕</button>
      ${duration > 0 ? `<div class="toast__progress" style="--toast-duration:${duration}ms"></div>` : ''}
    `;

    toast.querySelector('.toast__message').textContent = message;
    toast.querySelector('.toast__close').addEventListener('click', () => this.#dismiss(toast));

    this.#container.appendChild(toast);

    // Double rAF ensures layout is settled before adding transition class
    requestAnimationFrame(() => {
      requestAnimationFrame(() => toast.classList.add('toast--in'));
    });

    if (duration > 0) {
      const timer = setTimeout(() => this.#dismiss(toast), duration);
      toast._dismissTimer = timer;
    }

    return toast;
  }

  static #dismiss(toast, immediate = false) {
    clearTimeout(toast._dismissTimer);
    if (immediate) { toast.remove(); return; }
    toast.classList.remove('toast--in');
    toast.classList.add('toast--out');
    const cleanup = () => toast.remove();
    toast.addEventListener('transitionend', cleanup, { once: true });
    setTimeout(cleanup, 350); // fallback if transition doesn't fire
  }

  static error(msg, duration)   { return this.#show(msg, 'error',   duration ?? 5000); }
  static success(msg, duration) { return this.#show(msg, 'success', duration ?? 3500); }
  static warning(msg, duration) { return this.#show(msg, 'warning', duration ?? 6000); }
  static info(msg, duration)    { return this.#show(msg, 'info',    duration ?? 4000); }
}
