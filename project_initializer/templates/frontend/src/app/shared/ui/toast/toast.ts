import { ChangeDetectionStrategy, Component, DOCUMENT, ElementRef, inject } from '@angular/core';
import { MatIconButton } from '@angular/material/button';
import {
  MAT_SNACK_BAR_DATA,
  MatSnackBarAction,
  MatSnackBarActions,
  MatSnackBarLabel,
  MatSnackBarRef,
} from '@angular/material/snack-bar';
import { LucideAngularModule } from 'lucide-angular';

import type { ToastData, ToastVariant } from './toast.service';

interface ToastVariantConfig {
  /** Registered lucide icon name (icons.ts). The shape keeps color from being the only signal. */
  readonly icon: string;
  /** Visually hidden prefix announced before the message. */
  readonly statusLabel: string;
}

const VARIANTS: Record<ToastVariant, ToastVariantConfig> = {
  info: { icon: 'Info', statusLabel: 'Information' },
  success: { icon: 'CircleCheckBig', statusLabel: 'Success' },
  warning: { icon: 'TriangleAlert', statusLabel: 'Warning' },
  error: { icon: 'CircleAlert', statusLabel: 'Error' },
};

/**
 * Snackbar content opened by ToastService (MatSnackBar.openFromComponent). Not placed
 * in templates: it needs the MAT_SNACK_BAR_DATA and MatSnackBarRef the snackbar provides.
 *
 * A dismissible toast shows one action, a dismiss icon button. Escape inside the toast
 * closes it too, and focus goes back to the element it came from.
 */
@Component({
  selector: 'app-toast',
  imports: [LucideAngularModule, MatIconButton, MatSnackBarLabel, MatSnackBarActions, MatSnackBarAction],
  templateUrl: './toast.html',
  styleUrl: './toast.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    '[class]': 'hostClass',
    '(focusin)': 'rememberFocusOrigin($event)',
    '(keydown.escape)': 'dismiss()',
  },
})
export class ToastComponent {
  protected readonly data = inject<ToastData>(MAT_SNACK_BAR_DATA);
  private readonly snackBarRef = inject<MatSnackBarRef<ToastComponent>>(MatSnackBarRef);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly document = inject(DOCUMENT);

  protected readonly icon = VARIANTS[this.data.variant].icon;
  protected readonly statusLabel = VARIANTS[this.data.variant].statusLabel;
  protected readonly hostClass = `toast toast-${this.data.variant}`;

  /** The element that had focus before focus moved into the toast. */
  private focusOrigin: HTMLElement | null = null;

  /** Closes the snackbar, returning focus to where it came from if it was inside. */
  dismiss(): void {
    this.releaseFocus();
    this.snackBarRef.dismissWithAction();
  }

  /**
   * Returns focus to the element it came from, if focus is inside this toast. ToastService calls
   * it before the app closes or replaces the toast: removing a focused dismiss button would
   * otherwise drop focus to <body>.
   */
  releaseFocus(): void {
    const origin = this.focusOrigin;
    if (origin?.isConnected && this.host.nativeElement.contains(this.document.activeElement)) {
      origin.focus({ preventScroll: true });
    }
  }

  protected rememberFocusOrigin(event: FocusEvent): void {
    const origin = event.relatedTarget;
    if (origin instanceof HTMLElement && !this.host.nativeElement.contains(origin)) {
      this.focusOrigin = origin;
    }
  }
}
