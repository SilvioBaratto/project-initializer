import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  Renderer2,
  ViewEncapsulation,
  afterRenderEffect,
  contentChildren,
  inject,
  input,
  isDevMode,
} from '@angular/core';
import { MatList, MatListItem } from '@angular/material/list';

/**
 * Visual treatment of the list:
 * - `default`: outlined group on `surface`.
 * - `divided`: adds an `outline-variant` divider between adjacent items.
 * - `striped`: odd items sit on `surface-container`.
 */
export type ListVariant = 'default' | 'divided' | 'striped';

/**
 * Material 3 static list built on `<mat-list>`, inside an outlined container (explicit grouping).
 *
 * Project `<mat-list-item>` elements (import `MatListModule` in the consumer). Item slots come from
 * Angular Material:
 * - `[matListItemTitle]` + `[matListItemLine]` for two- and three-line items;
 * - `[matListItemIcon]` or `[matListItemAvatar]` for the leading element, such as
 *   `<lucide-icon matListItemIcon name="Mail" />`;
 * - `[matListItemMeta]` for trailing supporting text or an icon button.
 *
 * `mat-list` sets no ARIA role, so the list carries `role="list"` and every projected
 * `<mat-list-item>` without its own `role` gets `role="listitem"`, keeping count and position
 * announced. Native `<a mat-list-item>` and `<button mat-list-item>` hosts are never given
 * `listitem`, which would replace their link or button role; in dev mode they log a warning.
 *
 * This component is for static content only. For links use `mat-nav-list` (a labelled navigation
 * landmark); for rows that are all buttons use `mat-action-list`; for picking items use
 * `mat-selection-list`.
 *
 * Styles use `ViewEncapsulation.None` because the items are projected content, which emulated styles
 * cannot reach; every selector in `list.css` is scoped under the `app-list` host class.
 */
@Component({
  selector: 'ui-list',
  changeDetection: ChangeDetectionStrategy.OnPush,
  encapsulation: ViewEncapsulation.None,
  imports: [MatList],
  templateUrl: './list.html',
  styleUrl: './list.css',
  host: {
    class: 'app-list',
  },
})
export class ListComponent {
  /** Visual treatment: `'default' | 'divided' | 'striped'` (see {@link ListVariant}). */
  readonly variant = input<ListVariant>('default');

  private readonly items = contentChildren(MatListItem, { read: ElementRef });
  private readonly renderer = inject(Renderer2);
  /** Interactive hosts already reported, so a re-render does not repeat the dev-mode warning. */
  private readonly warnedHosts = new WeakSet<HTMLElement>();

  constructor() {
    afterRenderEffect({
      write: () => {
        for (const { nativeElement } of this.items()) {
          const host = nativeElement as HTMLElement;
          if (host.hasAttribute('role')) {
            continue;
          }
          if (isNativeInteractive(host)) {
            this.warnInteractiveRow(host);
            continue;
          }
          this.renderer.setAttribute(host, 'role', 'listitem');
        }
      },
    });
  }

  private warnInteractiveRow(host: HTMLElement): void {
    if (!isDevMode() || this.warnedHosts.has(host)) {
      return;
    }
    this.warnedHosts.add(host);
    console.warn(
      `ui-list: <${host.nodeName.toLowerCase()} mat-list-item> keeps its native role. ` +
        'Interactive rows belong in mat-action-list (buttons) or mat-nav-list (links).',
    );
  }
}

/** `MatListItem` also matches `a[mat-list-item]` and `button[mat-list-item]`, which keep their native role. */
function isNativeInteractive(host: HTMLElement): boolean {
  const name = host.nodeName.toLowerCase();
  return name === 'a' || name === 'button';
}
