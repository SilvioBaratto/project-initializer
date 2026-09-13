import { ChangeDetectionStrategy, Component, signal } from '@angular/core';
import { MatButton } from '@angular/material/button';

import { CoreSectionComponent } from './sections/core-section';
import { FormsSectionComponent } from './sections/forms-section';
import { NavigationSectionComponent } from './sections/navigation-section';
import { OverlaysSectionComponent } from './sections/overlays-section';
import { DataDisplaySectionComponent } from './sections/data-display-section';

import { ModalComponent } from '../../shared/ui/modal/modal';
import { ModalActionsComponent } from '../../shared/ui/modal/modal-actions';
import { SlideOverComponent } from '../../shared/ui/slide-over/slide-over';
import { DrawerComponent } from '../../shared/ui/drawer/drawer';

/**
 * /components catalog: every shared UI component, grouped into Core, Forms, Navigation, Overlays and
 * Data display, each demo rendered in a light and a dark region for cross-browser QA.
 *
 * Rendered inside the shell's main element, which adds no padding, so the page owns its margins
 * (components.css). One h1; each group is a `<section>` region named by its h2, and the section
 * components render h3 demo headings.
 *
 * Overlays: the page owns a single modal, slide-over and drawer. All three are Material dialogs that
 * render in the CDK overlay container under `<body>`, so they follow the global theme rather than
 * the region whose trigger opened them. `activeOverlay` names the one that is open; each overlay's
 * `open` is derived from it, so at most one is open at a time and no two focus traps run together.
 * A user dismissal (Esc, the scrim, a close or Cancel button) clears it through `closeOverlay(name)`,
 * which ignores a dismissal that arrives after a different overlay has already been opened.
 */
@Component({
  selector: 'app-components',
  templateUrl: './components.html',
  styleUrl: './components.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    CoreSectionComponent,
    FormsSectionComponent,
    NavigationSectionComponent,
    OverlaysSectionComponent,
    DataDisplaySectionComponent,
    ModalComponent,
    ModalActionsComponent,
    SlideOverComponent,
    DrawerComponent,
    MatButton,
  ],
})
export class ComponentsComponent {
  /** Which overlay is open (`'modal'`, `'slide-over'` or `'drawer'`), or `null` when none is. */
  readonly activeOverlay = signal<string | null>(null);

  openOverlay(name: string): void {
    this.activeOverlay.set(name);
  }

  /**
   * Clears the open overlay. With a `name`, clears it only while that overlay is still the active one.
   *
   * The drawer and slide-over report a dismissal from `afterClosed()`, once their exit animation ends,
   * and the scrim stops taking clicks as soon as it starts. Once change detection has turned the
   * previous overlay's `open` false, that overlay never reports the dismissal. It can still arrive
   * after a trigger has set `activeOverlay` but before change detection runs, and it must not clear
   * the overlay the user just opened. Without a `name` it clears whatever is open.
   */
  closeOverlay(name?: string): void {
    this.activeOverlay.update((active) => (name === undefined || active === name ? null : active));
  }
}
