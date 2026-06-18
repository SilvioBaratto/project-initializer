import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

const SIZE_CLASSES: Record<string, string> = {
  sm: 'max-w-sm',
  md: 'max-w-2xl',
  lg: 'max-w-4xl',
  xl: 'max-w-6xl',
  full: 'max-w-full',
};

@Component({
  selector: 'app-container',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div [class]="innerClasses()">
      <ng-content />
    </div>
  `,
})
export class ContainerComponent {
  readonly size = input('lg');

  readonly innerClasses = computed(
    () => `mx-auto w-full px-safe ${SIZE_CLASSES[this.size()] ?? 'max-w-4xl'}`,
  );
}
