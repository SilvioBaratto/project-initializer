import { booleanAttribute, ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';

export type SpinnerSize = 'sm' | 'md' | 'lg';

/**
 * Indicator diameter per size, in CSS px. `md` is Angular Material's M3 default
 * (`progress-spinner-size: 48px`); `sm` sits beside body text and `lg` suits a
 * page-level wait. Progress indicators carry no text, so the diameter stays fixed
 * when the user enlarges text.
 */
export const SPINNER_DIAMETERS: Readonly<Record<SpinnerSize, number>> = {
  sm: 24,
  md: 48,
  lg: 64,
};

/** M3 active indicator thickness (`progress-spinner-active-indicator-width: 4px`) at every size. */
const STROKE_WIDTH = 4;

/**
 * Indeterminate loading indicator: an M3 circular progress indicator
 * (`mat-progress-spinner`) inside a `role="status"` live region.
 *
 * The label is the accessible state. It is always rendered as text in the status
 * region, so screen readers announce it, and it is visually hidden unless
 * `showLabel` is set. The indicator itself is decorative (`aria-hidden`), so no
 * unnamed progressbar reaches assistive technology. Under reduced motion Material
 * keeps the indeterminate animation running at 1.25x its duration (the global
 * reduced-motion rule in styles.scss exempts it), so the label stays screen-reader-only
 * unless `showLabel` is set.
 */
@Component({
  selector: 'app-spinner',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [MatProgressSpinnerModule],
  templateUrl: './spinner.html',
  styleUrl: './spinner.css',
})
export class SpinnerComponent {
  /** Names what is loading. An ellipsis is right here: it marks an action in progress. */
  readonly label = input('Loading…');

  /** Indicator diameter; see {@link SPINNER_DIAMETERS}. */
  readonly size = input<SpinnerSize>('md');

  /** Shows the label next to the indicator instead of keeping it screen-reader-only. */
  readonly showLabel = input(false, { transform: booleanAttribute });

  protected readonly diameter = computed(() => SPINNER_DIAMETERS[this.size()]);
  protected readonly strokeWidth = STROKE_WIDTH;
}
