import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

@Component({
  selector: 'app-grid',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div [class]="wrapperClass()">
      <div [class]="gridClasses()">
        <ng-content />
      </div>
    </div>
  `,
})
export class GridComponent {
  readonly gap = input<number>(4);
  readonly containerQuery = input(false);

  readonly wrapperClass = computed(() => (this.containerQuery() ? '@container' : ''));

  readonly gridClasses = computed(
    () => `grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-${this.gap()}`,
  );
}
