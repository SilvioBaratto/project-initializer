import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

export type AlertVariant = 'info' | 'success' | 'warning' | 'danger';

const VARIANT_CLASSES: Record<AlertVariant, string> = {
  info: 'bg-info/10 border-info/30 text-info',
  success: 'bg-success/10 border-success/30 text-success',
  warning: 'bg-warning/10 border-warning/30 text-warning',
  danger: 'bg-danger/10 border-danger/30 text-danger',
};

@Component({
  selector: 'app-alert',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div role="alert" [class]="classes()">
      <ng-content />
    </div>
  `,
})
export class AlertComponent {
  readonly variant = input<AlertVariant>('info');

  readonly classes = computed(() => {
    const base = 'flex items-start gap-3 rounded-lg border px-4 py-3 text-sm';
    return `${base} ${VARIANT_CLASSES[this.variant()]}`;
  });
}
