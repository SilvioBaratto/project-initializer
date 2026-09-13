import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

/** Max inline size of the container: `sm` 24rem, `md` 42rem, `lg` 56rem, `xl` 72rem, `full` uncapped. */
export type ContainerSize = 'sm' | 'md' | 'lg' | 'xl' | 'full';

const CONTAINER_SIZES: readonly string[] = ['sm', 'md', 'lg', 'xl', 'full'] satisfies ContainerSize[];

function isContainerSize(value: string): value is ContainerSize {
  return CONTAINER_SIZES.includes(value);
}

/**
 * Page-width layout primitive: centers its projected content at a max inline size and applies the
 * Material 3 window margins (16px below 600px, 24px from 600px) on top of the device safe-area
 * insets, so content never sits under a notch or curved screen corner.
 *
 * Purely structural: no landmark, heading or color of its own.
 */
@Component({
  selector: 'app-container',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './container.html',
  styleUrl: './container.css',
  host: {
    '[attr.data-size]': 'resolvedSize()',
  },
})
export class ContainerComponent {
  /** Max inline size: `'sm' | 'md' | 'lg' | 'xl' | 'full'` (see {@link ContainerSize}). Unknown values fall back to `'lg'`. */
  readonly size = input('lg');

  /** The size actually applied, after falling back to `'lg'` for unknown values. */
  readonly resolvedSize = computed<ContainerSize>(() => {
    const value = this.size();
    return isContainerSize(value) ? value : 'lg';
  });
}
