import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  Injector,
  booleanAttribute,
  contentChildren,
  effect,
  inject,
  input,
  signal,
} from '@angular/core';
import { FocusKeyManager } from '@angular/cdk/a11y';
import { MatAccordion } from '@angular/material/expansion';

import { ACCORDION_CONTEXT, AccordionContext } from './accordion-context';
import { AccordionItemComponent } from './accordion-item';

export { ACCORDION_CONTEXT } from './accordion-context';
export type { AccordionContext } from './accordion-context';
export { AccordionItemComponent } from './accordion-item';

let nextAccordionId = 0;

/**
 * Accordion container built on Material's `mat-accordion` (applied as a host directive,
 * so the host carries `.mat-accordion` and provides the accordion to the panels).
 *
 * `single` maps onto Material's `multi` (inverted): with `single` the opening panel closes
 * its siblings. Up/Down arrows move focus between headers (wrapping) and Home/End jump to
 * the first/last header; Material's own header navigation only sees panels that are direct
 * children, which the `ui-accordion-item` wrapper hides from it.
 */
@Component({
  selector: 'ui-accordion',
  changeDetection: ChangeDetectionStrategy.OnPush,
  hostDirectives: [MatAccordion],
  providers: [{ provide: ACCORDION_CONTEXT, useExisting: AccordionComponent }],
  host: { '(keydown)': 'onKeydown($event)' },
  templateUrl: './accordion.html',
  styleUrl: './accordion.css',
})
export class AccordionComponent implements AccordionContext {
  readonly accordionId = `ui-accordion-${nextAccordionId++}`;

  /** When true, only one item can be open at a time. Accepts the bare attribute (`<ui-accordion single>`). */
  readonly single = input(false, { transform: booleanAttribute });

  private readonly _expanded = signal<Set<number>>(new Set());

  private readonly items = contentChildren(AccordionItemComponent);

  private readonly keyManager = new FocusKeyManager(this.items, inject(Injector))
    .withWrap()
    .withHomeAndEnd()
    .setFocusOrigin('keyboard');

  constructor() {
    const matAccordion = inject(MatAccordion);
    // Rows of one outlined container: no detached, spaced-out expanded panel.
    matAccordion.displayMode = 'flat';
    // Runs before the host's `.mat-accordion-multi` binding is checked, so both stay in step.
    effect(() => {
      matAccordion.multi = !this.single();
    });
    inject(DestroyRef).onDestroy(() => this.keyManager.destroy());
  }

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

  /** Arrow/Home/End navigation between this accordion's headers. Enter/Space are handled by Material's header. */
  onKeydown(event: KeyboardEvent): void {
    const item = this.items().find((candidate) => candidate.isHeader(event.target));
    if (!item) return;
    this.keyManager.updateActiveItem(item);
    this.keyManager.onKeydown(event);
  }
}
