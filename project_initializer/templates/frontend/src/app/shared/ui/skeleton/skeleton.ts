import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

export type SkeletonShape = 'line' | 'block' | 'avatar';

@Component({
  selector: 'app-skeleton',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<div [class]="classes()" aria-hidden="true"></div>`,
})
export class SkeletonComponent {
  readonly shape = input<SkeletonShape>('line');
  readonly width = input('w-full');
  readonly height = input('h-4');

  readonly classes = computed(() => {
    const base = `animate-shimmer rounded ${this.width()} ${this.height()}`;
    return this.shape() === 'avatar' ? `${base} !rounded-full` : base;
  });
}
