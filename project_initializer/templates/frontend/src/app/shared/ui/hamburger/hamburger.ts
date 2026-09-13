import {
  ChangeDetectionStrategy,
  Component,
  computed,
  input,
  output,
} from '@angular/core';
import { MatIconButton } from '@angular/material/button';
import { LucideAngularModule } from 'lucide-angular';

import type { IconName } from '../../../icons';

/**
 * Which navigation surface the toggle drives.
 * - `modal`: opens and closes the modal expanded rail (compact window size class).
 * - `rail`: expands and collapses a docked navigation rail (medium and up).
 */
export type HamburgerVariant = 'modal' | 'rail';

/**
 * Navigation toggle built on the M3 standard icon button (`matIconButton`).
 * The accessible name names the action and flips with `open`; `aria-expanded`
 * and `aria-controls` tie the button to the surface it drives.
 */
@Component({
  selector: 'app-hamburger',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [MatIconButton, LucideAngularModule],
  templateUrl: './hamburger.html',
  styleUrl: './hamburger.css',
})
export class HamburgerComponent {
  /** Whether the controlled navigation surface is open (modal) or expanded (rail). */
  readonly open = input(false);
  /** Id of the element the button controls; omitted from the DOM when empty. */
  readonly controls = input('');
  /** Navigation surface the toggle drives; picks the icon pair and label wording. */
  readonly variant = input<HamburgerVariant>('modal');

  readonly toggle = output<void>();

  readonly label = computed(() => {
    if (this.variant() === 'rail') {
      return this.open() ? 'Collapse navigation' : 'Expand navigation';
    }
    return this.open() ? 'Close navigation' : 'Open navigation';
  });

  /**
   * Closed or collapsed: the menu icon at the top of every M3 side rail.
   * Open: X closes the modal rail; PanelLeftClose collapses the docked rail.
   */
  readonly icon = computed<IconName>(() => {
    if (!this.open()) {
      return 'Menu';
    }
    return this.variant() === 'rail' ? 'PanelLeftClose' : 'X';
  });

  /** Only PanelLeftClose points at an edge, so only it mirrors in RTL; Menu and X are symmetric. */
  readonly directional = computed(() => this.icon() === 'PanelLeftClose');
}
