import {
  ChangeDetectionStrategy,
  Component,
  InjectionToken,
  Signal,
  computed,
  inject,
  input,
  signal,
} from '@angular/core';
import { LucideAngularModule } from 'lucide-angular';

// ---------------------------------------------------------------------------
// Context token
// ---------------------------------------------------------------------------

export interface AccordionContext {
  readonly accordionId: string;
  isExpanded(index: number): boolean;
  toggle(index: number): void;
}

export const ACCORDION_CONTEXT = new InjectionToken<AccordionContext>('ACCORDION_CONTEXT');

// ---------------------------------------------------------------------------
// Accordion item — header button + region panel
// ---------------------------------------------------------------------------

let nextItemId = 0;

@Component({
  selector: 'ui-accordion-item',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [LucideAngularModule],
  template: `
    <div class="border-b border-border dark:border-border last:border-b-0">
      <button
        [id]="headerId"
        [attr.aria-expanded]="expanded()"
        [attr.aria-controls]="panelId"
        (click)="ctx.toggle(index())"
        class="flex w-full items-center justify-between gap-2 px-4 py-3 text-left text-sm font-medium text-text
               hover:bg-surface-inset dark:text-text dark:hover:bg-surface-inset
               focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-inset
               transition-colors"
      >
        <ng-content select="[slot=header]" />
        <lucide-icon
          name="ChevronDown"
          [size]="16"
          aria-hidden="true"
          class="shrink-0 transition-transform duration-200"
          [class]="expanded() ? 'rotate-180' : ''"
        />
      </button>
      @if (expanded()) {
        <div
          [id]="panelId"
          role="region"
          [attr.aria-labelledby]="headerId"
          class="px-4 pb-4 text-sm text-text-secondary dark:text-text-secondary"
        >
          <ng-content />
        </div>
      }
    </div>
  `,
})
export class AccordionItemComponent {
  protected readonly ctx = inject(ACCORDION_CONTEXT);

  readonly index = input.required<number>();

  private readonly _itemId = nextItemId++;
  readonly headerId = `accordion-header-${this._itemId}`;
  readonly panelId = `accordion-panel-${this._itemId}`;

  readonly expanded = computed(() => this.ctx.isExpanded(this.index()));
}

// ---------------------------------------------------------------------------
// Accordion container
// ---------------------------------------------------------------------------

let nextAccordionId = 0;

@Component({
  selector: 'ui-accordion',
  changeDetection: ChangeDetectionStrategy.OnPush,
  providers: [{ provide: ACCORDION_CONTEXT, useExisting: AccordionComponent }],
  host: { '(keydown)': 'onKeydown($event)' },
  template: `
    <div class="rounded-lg border border-border bg-surface-raised dark:border-border dark:bg-surface-raised overflow-hidden">
      <ng-content />
    </div>
  `,
})
export class AccordionComponent implements AccordionContext {
  readonly accordionId = `ui-accordion-${nextAccordionId++}`;

  /** When true, only one item can be open at a time. */
  readonly single = input(false);

  private readonly _expanded = signal<Set<number>>(new Set());

  isExpanded(index: number): boolean {
    return this._expanded().has(index);
  }

  toggle(index: number): void {
    this._expanded.update((prev) => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        if (this.single()) next.clear();
        next.add(index);
      }
      return next;
    });
  }

  onKeydown(event: KeyboardEvent): void {
    const key = event.key;
    if (key !== 'Enter' && key !== ' ') return;
    const target = event.target as HTMLElement;
    if (target.tagName !== 'BUTTON') return;
    // Native button already handles Enter/Space — prevent scroll on Space.
    if (key === ' ') event.preventDefault();
  }
}
