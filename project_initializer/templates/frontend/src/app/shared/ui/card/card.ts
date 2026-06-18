import { ChangeDetectionStrategy, Component, input } from '@angular/core';

@Component({
  selector: 'app-card',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="rounded-lg border border-border bg-surface-raised text-text">
      <div class="border-b border-border px-4 py-3">
        <ng-content select="[slot-header]" />
      </div>
      <div [class]="bodyClass()">
        <ng-content />
      </div>
      <div class="border-t border-border px-4 py-3">
        <ng-content select="[slot-footer]" />
      </div>
    </div>
  `,
})
export class CardComponent {
  /** Controls inner body padding; use 'none' to remove padding for full-bleed content. */
  readonly padding = input('md');

  bodyClass() {
    const map: Record<string, string> = { sm: 'px-3 py-2', md: 'px-4 py-4', lg: 'px-6 py-6', none: '' };
    return map[this.padding()] ?? 'px-4 py-4';
  }
}
