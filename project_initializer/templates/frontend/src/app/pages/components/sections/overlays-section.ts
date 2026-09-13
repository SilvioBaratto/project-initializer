import { ChangeDetectionStrategy, Component, inject, output } from '@angular/core';
import { MatButton, MatIconButton } from '@angular/material/button';
import { LucideAngularModule } from 'lucide-angular';

import { ButtonComponent } from '../../../shared/ui/button/button';
import { StackComponent } from '../../../shared/ui/stack/stack';
import { ToastService } from '../../../shared/ui/toast/toast.service';
import { TooltipComponent } from '../../../shared/ui/tooltip/tooltip';
import { TooltipDirective } from '../../../shared/ui/tooltip/tooltip.directive';

import { ThemePreviewComponent } from '../theme-preview';

/**
 * Overlays group of the /components catalog: the triggers for the page's modal, slide-over and
 * drawer, two snackbar triggers, and the two tooltip APIs, each under an h3 and previewed in a light
 * and a dark region.
 *
 * The page owns the `h1` and the group's `h2`; this section adds one `h3` per demo group, outside
 * the stamped `<ng-template>`, so each heading appears once in the outline, like the other sections.
 *
 * Triggers only. The page mounts this section once, owns the single instance of each dialog and the
 * active-overlay state, and opens one when `opened` emits `'modal'`, `'slide-over'` or `'drawer'`.
 * All three are modal dialogs, so their triggers take `aria-haspopup="dialog"` and no
 * `aria-expanded`, which belongs to disclosures. The snackbar triggers call the app-wide
 * ToastService, which shows one snackbar at a time.
 *
 * Every overlay renders in the CDK overlay container under `<body>`: MatDialog hosts the modal,
 * slide-over and drawer, MatSnackBar the snackbars, and MatTooltip's own CDK overlay the tooltip
 * panels. An overlay opened from the dark region therefore follows the global theme, because
 * `--mat-sys-*` colors resolve against the `color-scheme` the element inherits through the DOM tree,
 * not the region it visually came from.
 */
@Component({
  selector: 'app-overlays-section',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    ThemePreviewComponent,
    StackComponent,
    ButtonComponent,
    TooltipComponent,
    TooltipDirective,
    MatButton,
    MatIconButton,
    LucideAngularModule,
  ],
  templateUrl: './overlays-section.html',
  styleUrl: './overlays-section.css',
})
export class OverlaysSectionComponent {
  private readonly toast = inject(ToastService);

  /** Name of the overlay to open: `'modal'`, `'slide-over'` or `'drawer'`. */
  readonly opened = output<string>();

  /** Success snackbar: it has no action, so it announces politely and dismisses itself. */
  showSnackbar(): void {
    this.toast.show('success', 'Changes saved');
  }

  /** Error snackbar: it announces assertively and waits for its one action, a dismiss button. */
  showErrorSnackbar(): void {
    this.toast.show('error', "Couldn't save changes");
  }
}
