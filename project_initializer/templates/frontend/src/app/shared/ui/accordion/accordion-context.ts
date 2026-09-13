import { InjectionToken } from '@angular/core';

/** Expansion state shared by a `ui-accordion` and the `ui-accordion-item`s projected into it. */
export interface AccordionContext {
  readonly accordionId: string;
  isExpanded(index: number): boolean;
  toggle(index: number): void;
}

export const ACCORDION_CONTEXT = new InjectionToken<AccordionContext>('ACCORDION_CONTEXT');
