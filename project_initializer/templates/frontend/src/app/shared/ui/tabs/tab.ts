import {
  ChangeDetectionStrategy,
  Component,
  TemplateRef,
  computed,
  inject,
  input,
  viewChild,
} from '@angular/core';

import { TABS_CONTEXT } from './tabs-context';

/**
 * Label of one tab. The element renders nothing where it is written: `ui-tabs` stamps its
 * `label` template into the matching `mat-tab` header, so the projected content becomes the
 * text of Material's `role="tab"` element (48px target, title-small type, active indicator).
 */
@Component({
  selector: 'ui-tab',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './tab.html',
  styleUrl: './tab.css',
})
export class TabComponent {
  protected readonly ctx = inject(TABS_CONTEXT);

  /** 0-based position of this tab; matched against `ui-tab-panel`'s `panelIndex`. */
  readonly tabIndex = input.required<number>();

  readonly isActive = computed(() => this.ctx.activeIndex() === this.tabIndex());

  /** Projected label content, rendered by `ui-tabs` inside the Material tab header. */
  readonly label = viewChild.required<TemplateRef<unknown>>('label');
}
