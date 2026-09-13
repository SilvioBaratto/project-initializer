import {
  ChangeDetectionStrategy,
  Component,
  TemplateRef,
  booleanAttribute,
  computed,
  inject,
  input,
  viewChild,
} from '@angular/core';

import { TABS_CONTEXT } from './tabs-context';

/**
 * Content of one tab. Like `ui-tab`, the element renders nothing in place: `ui-tabs` stamps its
 * `content` template into the `mat-tab` whose `ui-tab` has the same index. Material renders it
 * inside the `role="tabpanel"` body only while that tab is selected.
 *
 * By default the panel content is a tab stop, so keyboard users can reach text-only content. When
 * the panel's first content is a control (a form field, button or link), set `[focusable]="false"`
 * or `focusable="false"` so Tab moves from the tab list straight to that control (WAI-ARIA APG
 * tabs pattern).
 */
@Component({
  selector: 'ui-tab-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './tab-panel.html',
  styleUrl: './tab-panel.css',
})
export class TabPanelComponent {
  protected readonly ctx = inject(TABS_CONTEXT);

  /** Index of the `ui-tab` this panel belongs to. */
  readonly panelIndex = input.required<number>();

  /** Whether the panel content is a tab stop. Turn it off when the panel starts with a control. */
  readonly focusable = input(true, { transform: booleanAttribute });

  readonly isActive = computed(() => this.ctx.activeIndex() === this.panelIndex());

  /** Projected panel content, rendered by `ui-tabs` inside the Material tab body. */
  readonly content = viewChild.required<TemplateRef<unknown>>('content');
}
