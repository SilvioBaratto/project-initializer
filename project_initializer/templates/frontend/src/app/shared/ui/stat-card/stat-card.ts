import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

import { CardComponent } from '../card/card';

export type DeltaDirection = 'up' | 'down' | 'neutral';

const DELTA_CLASSES: Record<DeltaDirection, string> = {
  up: 'text-success',
  down: 'text-danger',
  neutral: 'text-text-secondary',
};

@Component({
  selector: 'app-stat-card',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [CardComponent],
  template: `
    <app-card>
      <div class="@container flex flex-col gap-1">
        <span class="text-sm text-text-secondary truncate">{{ label() }}</span>
        <span class="text-2xl @sm:text-3xl font-semibold text-text tabular-nums">{{ metric() }}</span>
        @if (delta()) {
          <span [class]="deltaClasses()" class="text-xs font-medium mt-0.5">
            {{ deltaPrefix() }}{{ delta() }}
          </span>
        }
      </div>
    </app-card>
  `,
})
export class StatCardComponent {
  readonly metric = input.required<string>();
  readonly label = input.required<string>();
  readonly delta = input<string | null>(null);
  readonly deltaDirection = input<DeltaDirection>('neutral');

  readonly deltaClasses = computed(() => DELTA_CLASSES[this.deltaDirection()]);

  readonly deltaPrefix = computed(() => {
    if (this.deltaDirection() === 'up') return '↑ ';
    if (this.deltaDirection() === 'down') return '↓ ';
    return '';
  });
}
