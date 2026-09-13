import {
  ChangeDetectionStrategy,
  Component,
  afterRenderEffect,
  computed,
  contentChildren,
  input,
  model,
  output,
  untracked,
} from '@angular/core';
import { NgTemplateOutlet } from '@angular/common';
import { MatTabsModule } from '@angular/material/tabs';

import { TABS_CONTEXT, TabsContext } from './tabs-context';
import { TabComponent } from './tab';
import { TabPanelComponent } from './tab-panel';

export { TABS_CONTEXT } from './tabs-context';
export type { TabsContext } from './tabs-context';
export { TabComponent } from './tab';
export { TabPanelComponent } from './tab-panel';

let nextTabsId = 0;

/**
 * In-page content tabs built on Material's `mat-tab-group`.
 *
 * Each `ui-tab` becomes a `mat-tab` label, and the `ui-tab-panel` with the same index becomes its
 * body. Material provides the WAI-ARIA tabs pattern: `role="tablist"`/`"tab"`/`"tabpanel"`,
 * `aria-selected`, `aria-controls` and `aria-labelledby`, and a roving `tabindex`. Its keyboard
 * handling is ArrowLeft/ArrowRight (wrapping, mirrored in RTL) and Home/End to move focus,
 * with Enter/Space to select the focused tab.
 */
@Component({
  selector: 'ui-tabs',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [MatTabsModule, NgTemplateOutlet],
  providers: [{ provide: TABS_CONTEXT, useExisting: TabsComponent }],
  templateUrl: './tabs.html',
  styleUrl: './tabs.css',
})
export class TabsComponent implements TabsContext {
  readonly tabsId = `ui-tabs-${nextTabsId++}`;

  /**
   * `tabIndex` of the selected tab. Supports two-way binding: `[(activeIndex)]`.
   * Material always shows one selected tab, so a value that names no tab (an unknown index, or
   * the selected tab was removed) is replaced with the first tab's `tabIndex`.
   */
  readonly activeIndex = model(0);

  /** Accessible name for the tab list when no visible heading names it. */
  readonly ariaLabel = input<string>();

  /** Id of a visible element that names the tab list. */
  readonly ariaLabelledby = input<string>();

  /**
   * Emits the `tabIndex` of a tab the user selects (a click, or Enter/Space on the focused tab) or
   * `activate()` selects. Setting `activeIndex`, and the fallback to the first tab when the
   * selected tab is removed or unknown, don't emit.
   */
  readonly tabChanged = output<number>();

  private readonly tabItems = contentChildren(TabComponent);
  private readonly panelItems = contentChildren(TabPanelComponent);

  /** Tabs in content order, each paired with the panel whose `panelIndex` matches its `tabIndex`. */
  protected readonly entries = computed(() => {
    const panels = this.panelItems();
    return this.tabItems().map((tab) => ({
      tab,
      panel: panels.find((panel) => panel.panelIndex() === tab.tabIndex()),
    }));
  });

  /** Material selects by position; `activeIndex` holds the selected tab's `tabIndex`. */
  protected readonly selectedPosition = computed(() =>
    Math.max(0, this.tabItems().findIndex((tab) => tab.tabIndex() === this.activeIndex())),
  );

  constructor() {
    // Keep the model in step with what Material renders. Without this, an `activeIndex` that names
    // no tab leaves Material's first tab aria-selected while every `isActive()` is false, and a
    // click on that tab changes nothing. This is a sync, not a selection, so it doesn't emit.
    // It runs after render: a plain effect runs with the host view, before a `ui-tab` added by
    // `@if` or `@for` has its required `tabIndex` bound.
    afterRenderEffect({
      write: () => {
        const tabs = this.tabItems();
        const active = this.activeIndex();
        if (tabs.length > 0 && !tabs.some((tab) => tab.tabIndex() === active)) {
          untracked(() => this.activeIndex.set(tabs[0].tabIndex()));
        }
      },
    });
  }

  activate(index: number): void {
    this.activeIndex.set(index);
    this.tabChanged.emit(index);
  }

  /**
   * Material also emits after code or a change to the tab list moves the selection. In those cases
   * `activeIndex` already names the tab, or names a tab that no longer exists, so only a user's
   * selection reaches `activate` and emits `tabChanged`.
   */
  protected onSelectedIndexChange(position: number): void {
    const tabs = this.tabItems();
    const tab = tabs[position];
    const active = this.activeIndex();
    if (!tab || tab.tabIndex() === active) {
      return;
    }
    if (tabs.some((item) => item.tabIndex() === active)) {
      this.activate(tab.tabIndex());
    } else {
      this.activeIndex.set(tab.tabIndex());
    }
  }
}
