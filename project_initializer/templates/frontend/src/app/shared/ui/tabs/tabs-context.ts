import { InjectionToken, Signal } from '@angular/core';

/** State `ui-tab` and `ui-tab-panel` read from their `ui-tabs` container, without importing its class. */
export interface TabsContext {
  /** `tabIndex` of the selected tab. */
  readonly activeIndex: Signal<number>;
  /** Stable per-instance prefix. Material generates the tab and panel ARIA ids itself. */
  readonly tabsId: string;
  /** Selects the tab with this `tabIndex` and emits `tabChanged`. */
  activate(index: number): void;
}

export const TABS_CONTEXT = new InjectionToken<TabsContext>('TABS_CONTEXT');
