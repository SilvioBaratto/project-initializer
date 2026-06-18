import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';

import { ModalComponent } from '../../../shared/ui/modal/modal';
import { SlideOverComponent } from '../../../shared/ui/slide-over/slide-over';
import { DrawerComponent } from '../../../shared/ui/drawer/drawer';
import { TooltipComponent } from '../../../shared/ui/tooltip/tooltip';
import { ButtonComponent } from '../../../shared/ui/button/button';
import { StackComponent } from '../../../shared/ui/stack/stack';

/**
 * Overlay trigger buttons. Overlays use fixed positioning and escape any local
 * dark container — the dual-region layout is managed by the parent page.
 * At most one overlay is open at a time to prevent focus-trap/inert conflicts.
 */
@Component({
  selector: 'app-overlays-section',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    StackComponent,
    ButtonComponent,
    ModalComponent,
    SlideOverComponent,
    DrawerComponent,
    TooltipComponent,
  ],
  template: `
    <app-stack direction="row" [gap]="2" align="center">
      <app-button variant="secondary" (clicked)="opened.emit('modal')">Modal</app-button>
      <app-button variant="secondary" (clicked)="opened.emit('slide-over')">Slide-over</app-button>
      <app-button variant="secondary" (clicked)="opened.emit('drawer')">Drawer</app-button>
      <ui-tooltip text="Tooltip text">
        <app-button variant="ghost" size="sm">Hover me</app-button>
      </ui-tooltip>
    </app-stack>

    <!-- Overlays rendered once globally — at most one open at a time -->
    @if (activeOverlay() === 'modal') {
      <app-modal [open]="true" label="Demo Modal" (closed)="closed.emit()">
        <p class="text-sm text-text">This is a demo modal dialog.</p>
        <div class="mt-4">
          <app-button variant="secondary" (clicked)="closed.emit()">Close</app-button>
        </div>
      </app-modal>
    }
    @if (activeOverlay() === 'slide-over') {
      <app-slide-over [open]="true" label="Demo Slide-over" (closed)="closed.emit()">
        <p class="p-4 text-sm text-text">Demo slide-over panel content.</p>
        <div class="p-4">
          <app-button variant="secondary" (clicked)="closed.emit()">Close</app-button>
        </div>
      </app-slide-over>
    }
    @if (activeOverlay() === 'drawer') {
      <app-drawer [open]="true" side="right" (close)="closed.emit()">
        <p class="p-4 text-sm text-text">Demo drawer panel content.</p>
        <div class="p-4">
          <app-button variant="secondary" (clicked)="closed.emit()">Close</app-button>
        </div>
      </app-drawer>
    }
  `,
})
export class OverlaysSectionComponent {
  readonly activeOverlay = input<string | null>(null);
  readonly opened = output<string>();
  readonly closed = output<void>();
}
