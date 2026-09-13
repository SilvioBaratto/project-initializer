import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { LucideAngularModule } from 'lucide-angular';

import type { IconName } from '../../../icons';
import { CardComponent } from '../card/card';

export type DeltaDirection = 'up' | 'down' | 'neutral';

interface DeltaConfig {
  /** Registered lucide icon (icons.ts), or null for none. The shape keeps color from being the only signal. */
  readonly icon: IconName | null;
  /** Visually hidden word announced before the delta text. Empty when there is no direction to name. */
  readonly label: string;
}

const DELTAS: Record<DeltaDirection, DeltaConfig> = {
  up: { icon: 'ChevronUp', label: 'Up' },
  down: { icon: 'ChevronDown', label: 'Down' },
  neutral: { icon: null, label: '' },
};

function isDeltaDirection(value: string): value is DeltaDirection {
  return Object.hasOwn(DELTAS, value);
}

/**
 * Key metric tile (KPI) on the Material 3 card. Angular Material has no stat component, so the content is laid
 * out on `--mat-sys-*` type and color roles (see stat-card.css):
 *
 * - `label`: label-large in on-surface-variant, read first.
 * - `metric`: headline-medium, stepping up to display-small once the card is wide enough (a container query on
 *   the card's own width, so the same tile works in a wide row and a narrow pane).
 * - `delta`: optional change text. `up` renders in the success role with an up chevron, `down` in the error role
 *   with a down chevron, `neutral` in on-surface-variant without an icon. The chevron is decorative; a visually
 *   hidden "Up" / "Down" names the direction for screen readers, so color is never the only signal.
 *
 * The tile is not interactive and never picks a heading level.
 */
@Component({
  selector: 'app-stat-card',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [CardComponent, LucideAngularModule],
  templateUrl: './stat-card.html',
  styleUrl: './stat-card.css',
})
export class StatCardComponent {
  readonly metric = input.required<string>();
  readonly label = input.required<string>();
  readonly delta = input<string | null>(null);
  readonly deltaDirection = input<DeltaDirection>('neutral');

  /** The direction actually applied, falling back to `neutral` for values outside {@link DeltaDirection}. */
  readonly resolvedDirection = computed<DeltaDirection>(() => {
    const direction = this.deltaDirection();
    return isDeltaDirection(direction) ? direction : 'neutral';
  });

  /** Icon drawn before the delta text, or null for `neutral`. */
  readonly deltaIcon = computed(() => DELTAS[this.resolvedDirection()].icon);

  /** Screen-reader word for the direction, or an empty string for `neutral`. */
  readonly deltaLabel = computed(() => DELTAS[this.resolvedDirection()].label);
}
