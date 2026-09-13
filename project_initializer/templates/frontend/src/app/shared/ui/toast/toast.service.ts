import { Injectable, OnDestroy, inject, signal } from '@angular/core';
import { MatSnackBar, MatSnackBarRef } from '@angular/material/snack-bar';

import { ToastComponent } from './toast';

export type ToastVariant = 'info' | 'success' | 'warning' | 'error';

export interface Toast {
  id: number;
  variant: ToastVariant;
  message: string;
}

/** What ToastComponent receives through MAT_SNACK_BAR_DATA. */
export interface ToastData extends Toast {
  /** No duration: the toast waits for its one action, a dismiss button. */
  readonly dismissible: boolean;
}

/** Auto-dismiss delay for toasts without an action. */
const DEFAULT_DURATION_MS = 5000;

/** Snackbar container class, styled globally in src/styles/overlays/_toast.scss. */
const PANEL_CLASS = 'app-toast';

/**
 * Brief feedback after an action, shown as a Material 3 snackbar (MatSnackBar).
 *
 * - MatSnackBar shows one snackbar at a time, so a new toast replaces the one on
 *   screen and `toasts()` holds at most one entry.
 * - A toast has either a duration or one action (a dismiss button), never both.
 * - When a toast that holds keyboard focus is replaced or closed through `dismiss(id)`, focus
 *   returns to the element it came from instead of dropping to <body>.
 * - Errors are announced assertively and, unless a duration is passed, wait for the
 *   user. Every other variant is announced politely and auto-dismisses.
 * - The snackbar sits bottom center. While the shell's navigation bar is on screen,
 *   _toast.scss lifts it above the bar. That rule follows the bar itself, not the window
 *   size at open time, because MatSnackBar applies panelClass only once and pages routed
 *   outside the shell (login) have no bar.
 */
@Injectable({ providedIn: 'root' })
export class ToastService implements OnDestroy {
  private readonly snackBar = inject(MatSnackBar);
  private readonly _toasts = signal<Toast[]>([]);
  private readonly _refs = new Map<number, MatSnackBarRef<ToastComponent>>();
  private _nextId = 0;

  /** The toast on screen (empty when none is). */
  readonly toasts = this._toasts.asReadonly();

  /**
   * Opens a toast and returns its id.
   *
   * @param duration Auto-dismiss delay in ms. Defaults to 5000, and to 0 for errors.
   *   0 (or less) keeps the toast open with a dismiss button instead.
   */
  show(variant: ToastVariant, message: string, duration?: number): number {
    const id = this._nextId++;
    const toast: Toast = { id, variant, message };
    const autoDismissMs = duration ?? (variant === 'error' ? 0 : DEFAULT_DURATION_MS);
    const dismissible = !(autoDismissMs > 0);

    // MatSnackBar closes the toast on screen when another opens: hand focus back first.
    this._refs.forEach((open) => open.instance.releaseFocus());

    const ref = this.snackBar.openFromComponent<ToastComponent, ToastData>(ToastComponent, {
      data: { ...toast, dismissible },
      // A snackbar with an action never auto-dismisses: keyboard and screen reader users need time to reach it.
      duration: dismissible ? 0 : autoDismissMs,
      politeness: variant === 'error' ? 'assertive' : 'polite',
      horizontalPosition: 'center',
      verticalPosition: 'bottom',
      panelClass: PANEL_CLASS,
    });

    this._refs.set(id, ref);
    this._toasts.set([toast]);
    ref.afterDismissed().subscribe(() => this._forget(id));
    return id;
  }

  /** Closes the toast with this id. Does nothing when it is no longer on screen. */
  dismiss(id: number): void {
    const ref = this._refs.get(id);
    ref?.instance.releaseFocus();
    ref?.dismiss();
    this._forget(id);
  }

  ngOnDestroy(): void {
    this._refs.forEach((ref) => ref.dismiss());
    this._refs.clear();
  }

  private _forget(id: number): void {
    this._refs.delete(id);
    this._toasts.update((list) => list.filter((t) => t.id !== id));
  }
}
