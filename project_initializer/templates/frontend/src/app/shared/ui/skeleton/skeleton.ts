import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

export type SkeletonShape = 'line' | 'block' | 'avatar';

/**
 * Loading placeholder that reserves the space of content still on its way.
 *
 * Material 3 and Angular Material ship no skeleton, so this one is built on
 * `--mat-sys-*` tokens (see skeleton.css): a `surface-container-high` shape with
 * a shimmer toward `surface-container-highest`, shaped by the corner tokens.
 * The shimmer stops under `prefers-reduced-motion`.
 *
 * The placeholder is decorative and hidden from assistive technology. Mark the
 * loading region itself (`aria-busy="true"`, or a spinner with `role="status"`)
 * so screen readers learn that content is loading.
 *
 * Default sizes: `line` is 16px tall, `block` 96px tall, and `avatar` a 40px
 * circle. `line` and `block` fill the width of their containing block
 * (`inline-size: 100%`), so give them a container with a definite width or pass
 * `width`. In a shrink-to-fit container (a flex item in a row, or a column sized
 * to its content) the percentage has nothing to resolve against and the
 * placeholder collapses to zero width.
 */
@Component({
  selector: 'app-skeleton',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './skeleton.html',
  styleUrl: './skeleton.css',
  host: {
    class: 'app-skeleton',
    '[attr.data-shape]': 'shape()',
  },
})
export class SkeletonComponent {
  readonly shape = input<SkeletonShape>('line');

  /**
   * Inline size as a CSS length (`100%`, `192px`, `12rem`). Empty keeps the
   * shape's default. For `avatar` it sets the diameter.
   */
  readonly width = input('');

  /**
   * Block size as a CSS length (`12px`, `4rem`). Empty keeps the shape's default.
   * An `avatar` has one diameter: `height` sets it only when `width` is empty, and
   * never stretches the circle out of round.
   */
  readonly height = input('');

  /** Inline size written on the placeholder. An avatar falls back to `height` for its diameter. */
  protected readonly inlineSize = computed(
    () => (this.shape() === 'avatar' ? this.width() || this.height() : this.width()) || null,
  );

  /** Block size written on the placeholder. None for an avatar: its aspect ratio keeps it round. */
  protected readonly blockSize = computed(() =>
    this.shape() === 'avatar' ? null : this.height() || null,
  );
}
