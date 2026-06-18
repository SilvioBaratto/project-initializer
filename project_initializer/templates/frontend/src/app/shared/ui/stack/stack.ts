import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

type Direction = 'row' | 'col';
type Align = 'start' | 'center' | 'end' | 'stretch' | 'baseline';

const ALIGN_CLASSES: Record<Align, string> = {
  start: 'items-start',
  center: 'items-center',
  end: 'items-end',
  stretch: 'items-stretch',
  baseline: 'items-baseline',
};

@Component({
  selector: 'app-stack',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<div [class]="classes()"><ng-content /></div>`,
})
export class StackComponent {
  readonly direction = input<Direction>('col');
  readonly gap = input<number>(4);
  readonly wrap = input(false);
  readonly align = input<Align>('stretch');

  readonly classes = computed(() => {
    const dir = this.direction() === 'row' ? 'flex-row' : 'flex-col';
    const wrap = this.wrap() ? 'flex-wrap' : 'flex-nowrap';
    const align = ALIGN_CLASSES[this.align()] ?? 'items-stretch';
    return `flex ${dir} gap-${this.gap()} ${wrap} ${align}`;
  });
}
