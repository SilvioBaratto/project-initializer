import {
  ChangeDetectionStrategy,
  Component,
  DOCUMENT,
  DestroyRef,
  ElementRef,
  afterNextRender,
  inject,
} from '@angular/core';
import { MatRipple } from '@angular/material/core';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { LucideAngularModule } from 'lucide-angular';

import { NavItem, NAV_ITEMS } from '../nav-item';

/** Custom property on <html> that holds the bar's rendered block size (read by styles/overlays/_toast.scss). */
export const NAV_BAR_BLOCK_SIZE_PROPERTY = '--app-nav-bar-block-size';

/**
 * M3 navigation bar for the compact window size class (< 600px).
 *
 * Angular Material has no navigation bar, so it is built on `--mat-sys-*` tokens:
 * a surface-container bar, a 56x32 secondary-container active indicator, labels
 * that always stay visible, hover and focus state layers, a ripple for the pressed
 * state and a focus ring outside the indicator. The current destination carries
 * `aria-current="page"`.
 *
 * Block size: at least 64px + env(safe-area-inset-bottom), taller when enlarged text or a
 * wrapped label needs it. The bar publishes its rendered block size as
 * `--app-nav-bar-block-size` on <html>, and the toast unit lifts compact snackbars by it:
 * the snackbar renders in the body-level overlay container, so it can only inherit from the root.
 */
@Component({
  selector: 'app-bottom-tab-bar',
  imports: [RouterLink, RouterLinkActive, MatRipple, LucideAngularModule],
  templateUrl: './bottom-tab-bar.html',
  styleUrl: './bottom-tab-bar.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class BottomTabBarComponent {
  tabs: NavItem[] = NAV_ITEMS;

  constructor() {
    const host = inject<ElementRef<HTMLElement>>(ElementRef).nativeElement;
    const root = inject(DOCUMENT).documentElement;
    const destroyRef = inject(DestroyRef);

    // afterNextRender runs in the browser only. Without ResizeObserver, the toast unit falls
    // back to the bar's minimum block size.
    afterNextRender(() => {
      if (typeof ResizeObserver === 'undefined') {
        return;
      }
      const observer = new ResizeObserver(([entry]) => {
        const blockSize = entry?.borderBoxSize?.[0]?.blockSize ?? host.getBoundingClientRect().height;
        root.style.setProperty(NAV_BAR_BLOCK_SIZE_PROPERTY, `${blockSize}px`);
      });
      observer.observe(host);
      // The bar leaves at 600px, and the snackbar rule it feeds only applies while a bar is on screen.
      destroyRef.onDestroy(() => {
        observer.disconnect();
        root.style.removeProperty(NAV_BAR_BLOCK_SIZE_PROPERTY);
      });
    });
  }
}
