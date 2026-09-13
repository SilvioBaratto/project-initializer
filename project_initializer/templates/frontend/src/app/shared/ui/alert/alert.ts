import { InteractivityChecker } from '@angular/cdk/a11y';
import {
  booleanAttribute,
  ChangeDetectionStrategy,
  Component,
  computed,
  DOCUMENT,
  ElementRef,
  inject,
  input,
  model,
  output,
} from '@angular/core';
import { MatIconButton } from '@angular/material/button';
import { LucideAngularModule } from 'lucide-angular';

export type AlertVariant = 'info' | 'success' | 'warning' | 'danger';

interface AlertVariantConfig {
  /** Registered lucide icon name (icons.ts). The shape keeps color from being the only signal. */
  readonly icon: string;
  /** Visually hidden prefix announced before the message. */
  readonly statusLabel: string;
  /** `alert` interrupts the screen reader; `status` waits for a pause. */
  readonly role: 'alert' | 'status';
}

const VARIANTS: Record<AlertVariant, AlertVariantConfig> = {
  info: { icon: 'Info', statusLabel: 'Information', role: 'status' },
  success: { icon: 'CircleCheckBig', statusLabel: 'Success', role: 'status' },
  warning: { icon: 'TriangleAlert', statusLabel: 'Warning', role: 'status' },
  danger: { icon: 'CircleAlert', statusLabel: 'Error', role: 'alert' },
};

/**
 * Persistent, non-blocking status message (M3 banner pattern; Angular Material has none).
 *
 * Only `danger` is an assertive `role="alert"` region; the other variants are polite
 * `role="status"` regions.
 *
 * Visibility is the two-way `open` model: with `dismissible`, the dismiss icon button sets
 * `open` to false and emits `dismissed`, and a consumer shows the alert again with
 * `[(open)]`. Before the alert hides, focus that was inside it moves to `restoreFocusTo`,
 * or to the nearest tabbable control after (then before) the alert, so it never drops to
 * `<body>`. A consumer that sets `open` to false while focus is inside the alert must move
 * focus itself.
 */
@Component({
  selector: 'app-alert',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [LucideAngularModule, MatIconButton],
  templateUrl: './alert.html',
  styleUrl: './alert.css',
  host: {
    '[class]': 'hostClass()',
    '[hidden]': '!open()',
  },
})
export class AlertComponent {
  readonly variant = input<AlertVariant>('info');
  readonly dismissible = input(false, { transform: booleanAttribute });
  /** Accessible name of the dismiss button. Name what is dismissed, for example "Dismiss payment warning". */
  readonly dismissLabel = input('Dismiss message');
  /** Whether the alert is shown. Two-way bindable: `[(open)]`. */
  readonly open = model(true);
  /**
   * Focusable element that receives focus when the alert is dismissed while focus is inside it,
   * for example the control that caused the message. Defaults to the nearest tabbable control.
   */
  readonly restoreFocusTo = input<HTMLElement | null>(null);

  readonly dismissed = output<void>();

  private readonly host: HTMLElement = inject(ElementRef).nativeElement;
  private readonly document = inject(DOCUMENT);
  private readonly interactivity = inject(InteractivityChecker);

  private readonly config = computed(() => VARIANTS[this.variant()]);
  protected readonly icon = computed(() => this.config().icon);
  protected readonly statusLabel = computed(() => this.config().statusLabel);
  protected readonly role = computed(() => this.config().role);

  protected readonly hostClass = computed(() => {
    const dismissible = this.dismissible() ? ' alert-dismissible' : '';
    return `alert alert-${this.variant()}${dismissible}`;
  });

  dismiss(): void {
    if (this.containsFocus()) {
      this.moveFocusOutside();
    }
    this.open.set(false);
    this.dismissed.emit();
  }

  private containsFocus(): boolean {
    return this.host.contains(this.document.activeElement);
  }

  /** Tries each target in order until focus has left the alert. */
  private moveFocusOutside(): void {
    const targets: (() => HTMLElement | null)[] = [
      () => this.restoreFocusTo(),
      () => this.nearestTabbable('next'),
      () => this.nearestTabbable('previous'),
    ];
    for (const target of targets) {
      target()?.focus();
      if (!this.containsFocus()) {
        return;
      }
    }
  }

  /** Closest tabbable element outside the alert, in document order. */
  private nearestTabbable(direction: 'next' | 'previous'): HTMLElement | null {
    const walker = this.document.createTreeWalker(this.document.body, NodeFilter.SHOW_ELEMENT);
    walker.currentNode = this.host;
    const step = () => (direction === 'next' ? walker.nextNode() : walker.previousNode());

    for (let node = step(); node; node = step()) {
      if (
        node instanceof HTMLElement &&
        !this.host.contains(node) &&
        this.interactivity.isFocusable(node) &&
        this.interactivity.isTabbable(node)
      ) {
        return node;
      }
    }
    return null;
  }
}
