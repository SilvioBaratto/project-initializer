import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  computed,
  inject,
  input,
  viewChild,
} from '@angular/core';
import type { FocusableOption, FocusOrigin } from '@angular/cdk/a11y';
import {
  MatExpansionPanel,
  MatExpansionPanelHeader,
  MatExpansionPanelTitle,
} from '@angular/material/expansion';

import { ACCORDION_CONTEXT } from './accordion-context';

/**
 * One row of a `ui-accordion`, rendered as a Material expansion panel.
 *
 * Material's header supplies the button semantics (`role="button"`, `aria-expanded`,
 * `aria-controls`, Enter/Space) and the panel body is a `role="region"` labelled by
 * the header. The accordion's expansion state stays the source of truth: the panel
 * reflects it through `[expanded]` and reports user toggles back through `expandedChange`.
 */
@Component({
  selector: 'ui-accordion-item',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [MatExpansionPanel, MatExpansionPanelHeader, MatExpansionPanelTitle],
  templateUrl: './accordion-item.html',
  styleUrl: './accordion-item.css',
})
export class AccordionItemComponent implements FocusableOption {
  protected readonly ctx = inject(ACCORDION_CONTEXT);

  readonly index = input.required<number>();

  readonly expanded = computed(() => this.ctx.isExpanded(this.index()));

  private readonly header = viewChild.required(MatExpansionPanelHeader);
  private readonly headerElement = viewChild.required(MatExpansionPanelHeader, {
    read: ElementRef,
  });

  /** Moves focus to this item's header (used by the accordion's arrow-key navigation). */
  focus(origin: FocusOrigin = 'program'): void {
    this.header().focus(origin);
  }

  /** Whether `target` is this item's header element. */
  isHeader(target: EventTarget | null): boolean {
    return this.headerElement().nativeElement === target;
  }

  /** Mirrors a toggle made through the panel (pointer, Enter/Space, or a sibling closing in single mode). */
  protected syncExpanded(expanded: boolean): void {
    if (expanded !== this.expanded()) {
      this.ctx.toggle(this.index());
    }
  }
}
