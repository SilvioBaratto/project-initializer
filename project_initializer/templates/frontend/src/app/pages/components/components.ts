import { ChangeDetectionStrategy, Component, signal } from '@angular/core';

import { CoreSectionComponent } from './sections/core-section';
import { FormsSectionComponent } from './sections/forms-section';
import { NavigationSectionComponent } from './sections/navigation-section';
import { OverlaysSectionComponent } from './sections/overlays-section';
import { DataDisplaySectionComponent } from './sections/data-display-section';

@Component({
  selector: 'app-components',
  templateUrl: './components.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    CoreSectionComponent,
    FormsSectionComponent,
    NavigationSectionComponent,
    OverlaysSectionComponent,
    DataDisplaySectionComponent,
  ],
  host: { class: 'block p-6 md:p-8' },
})
export class ComponentsComponent {
  /** Tracks which overlay is currently open to prevent focus/inert conflicts. */
  readonly activeOverlay = signal<string | null>(null);

  openOverlay(name: string): void {
    this.activeOverlay.set(name);
  }

  closeOverlay(): void {
    this.activeOverlay.set(null);
  }
}
