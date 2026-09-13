import { ChangeDetectionStrategy, Component, computed, input, output } from '@angular/core';
import { MatButtonAppearance, MatButtonModule } from '@angular/material/button';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';
export type ButtonSize = 'sm' | 'md' | 'lg';
export type ButtonType = 'button' | 'submit' | 'reset';

/**
 * Material 3 button appearance for each variant. `danger` stays a filled button; button.css
 * swaps its container, label and state-layer tokens to the error roles.
 */
const VARIANT_APPEARANCE: Record<ButtonVariant, MatButtonAppearance> = {
  primary: 'filled',
  secondary: 'outlined',
  ghost: 'text',
  danger: 'filled',
};

/**
 * Button built on Angular Material's `matButton`.
 *
 * - `type` defaults to `button`, so an app-button inside a `<form>` never submits it by accident.
 *   Pass `type="submit"` for the form's primary action.
 * - `size` keeps the 40px container and the 48px touch target at every size (baseline M3 has a
 *   single button height); it only changes the horizontal padding. See button.css.
 * - `disabled` natively disables the button: it leaves the tab order and ignores activation.
 * - `loading` shows an indeterminate spinner in the leading icon slot, sets `aria-busy` and marks
 *   the button disabled while keeping it focusable (`disabledInteractive`: Material renders
 *   `aria-disabled="true"` instead of the native attribute). A natively disabled button that has
 *   focus drops keyboard focus to `<body>`, and a busy state usually starts from a click on this
 *   very button. Activation is ignored while loading, including a form submission.
 * - `loadingText` names the in-progress state, for example "Uploading file…". aria-busy and the
 *   aria-hidden spinner are silent to screen readers, so while `loading` the text is announced
 *   from a visually hidden `role="status"` region next to the button, outside its aria-busy
 *   subtree. The region renders only when `loadingText` is set, so pass it up front rather than
 *   together with `loading`: a live region added along with its text may go unannounced.
 * - ARIA state lives on the inner `<button>` only; the `<app-button>` host is a generic wrapper.
 * - Projected content is label-only. It renders inside Material's label span
 *   (`span.mdc-button__label`); a projected icon, even one marked `matButtonIcon`, does not
 *   reach Material's icon slots and gets no icon spacing. For a button with an icon, use
 *   `<button matButton>` directly with a `matButtonIcon` icon.
 */
@Component({
  selector: 'app-button',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [MatButtonModule, MatProgressSpinnerModule],
  templateUrl: './button.html',
  styleUrl: './button.css',
})
export class ButtonComponent {
  readonly variant = input<ButtonVariant>('primary');
  readonly size = input<ButtonSize>('md');
  readonly type = input<ButtonType>('button');
  readonly loading = input(false);
  /** Status text announced while loading; empty renders no status region. */
  readonly loadingText = input('');
  readonly disabled = input(false);

  readonly clicked = output<void>();

  /** Appearance passed to `matButton`. */
  readonly appearance = computed(() => VARIANT_APPEARANCE[this.variant()]);

  /** Busy but not disabled: the button stays focusable and reports aria-disabled. */
  readonly focusableWhileBusy = computed(() => this.loading() && !this.disabled());

  handleClick(event?: Event): void {
    if (this.disabled() || this.loading()) {
      // The busy button isn't natively disabled, so cancel its default action (a form submit).
      event?.preventDefault();
      return;
    }
    this.clicked.emit();
  }
}
