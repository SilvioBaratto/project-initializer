import { Injectable, DestroyRef, computed, effect, inject, signal } from '@angular/core';

export type ThemeMode = 'light' | 'dark' | 'system';

const STORAGE_KEY = 'app-theme';
const TRANSITION_MS = 150;

@Injectable({ providedIn: 'root' })
export class ThemeService {
  private readonly destroyRef = inject(DestroyRef);

  private readonly _theme = signal<ThemeMode>(this._readStorage());
  private readonly _osPrefersDark = signal<boolean>(this._readOs());

  readonly theme = this._theme.asReadonly();
  readonly isDark = computed(
    () => this._theme() === 'dark' || (this._theme() === 'system' && this._osPrefersDark()),
  );

  constructor() {
    this._initOsListener();
    effect(() => this._applyClass(this.isDark()));
  }

  /** Every path to a new scheme (the rail's theme menu, the compact sheet, the Settings page) switches instantly, without transitions. */
  setTheme(theme: ThemeMode): void {
    if (theme !== this._theme()) {
      this._beginTransition();
    }
    this._theme.set(theme);
    this._persist(theme);
  }

  /**
   * The localStorage getter throws a SecurityError when the browser blocks site data. This runs
   * during app initialization, so a throw here would fail bootstrap: fall back to `system`.
   */
  private _readStorage(): ThemeMode {
    if (typeof window === 'undefined') return 'system';
    try {
      const value = localStorage.getItem(STORAGE_KEY);
      return value === 'light' || value === 'dark' || value === 'system' ? value : 'system';
    } catch {
      return 'system';
    }
  }

  private _readOs(): boolean {
    if (!this._canMatchMedia()) return false;
    return window.matchMedia('(prefers-color-scheme: dark)').matches;
  }

  /** False on the server and in DOM shims without matchMedia (jsdom). */
  private _canMatchMedia(): boolean {
    return typeof window !== 'undefined' && typeof window.matchMedia === 'function';
  }

  private _initOsListener(): void {
    if (!this._canMatchMedia()) return;
    const query = window.matchMedia('(prefers-color-scheme: dark)');
    const onChange = (e: MediaQueryListEvent) => this._osPrefersDark.set(e.matches);
    query.addEventListener('change', onChange);
    this.destroyRef.onDestroy(() => query.removeEventListener('change', onChange));
  }

  /**
   * Exactly one of `.dark` / `.light` sits on <html>. styles.scss maps each to a
   * `color-scheme`, which resolves the `light-dark()` values that `mat.theme()`
   * emits for every `--mat-sys-*` token.
   *
   * Until Angular boots, a script in index.html pins a stored choice as an inline
   * `color-scheme`, because the inlined critical CSS has no `.light` / `.dark` rule.
   * The class takes over here; left in place, that inline value would override every later switch.
   */
  private _applyClass(isDark: boolean): void {
    if (typeof window === 'undefined') return;
    const root = document.documentElement;
    root.classList.toggle('dark', isDark);
    root.classList.toggle('light', !isDark);
    root.style.removeProperty('color-scheme');
  }

  private _persist(theme: ThemeMode): void {
    if (typeof window === 'undefined') return;
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch {
      // Storage is blocked or full: the choice lasts for this session only.
    }
  }

  private _beginTransition(): void {
    if (typeof window === 'undefined') return;
    const root = document.documentElement;
    root.classList.add('theme-transitioning');
    setTimeout(() => root.classList.remove('theme-transitioning'), TRANSITION_MS);
  }
}
