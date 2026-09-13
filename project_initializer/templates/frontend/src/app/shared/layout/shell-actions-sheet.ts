import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { MatBottomSheetRef } from '@angular/material/bottom-sheet';

import { SidebarComponent } from '../sidebar/sidebar';

/**
 * Compact action surface of the shell (< 600px), opened in a modal `MatBottomSheet` from the
 * top app bar. M3 puts actions in a bottom sheet at compact and keeps the navigation bar for
 * destinations, so the sheet renders the rail's actions only (`app-sidebar` in `modal` mode:
 * the theme choices, plus the account and Sign out in the auth variants).
 *
 * MatBottomSheet brings the focus trap, Esc and scrim dismissal, and focus restore to the
 * trigger. Sign out emits `closeSidebar`, so the sheet dismisses before the auth overlays
 * navigate away.
 */
@Component({
  selector: 'app-shell-actions-sheet',
  imports: [SidebarComponent],
  templateUrl: './shell-actions-sheet.html',
  styleUrl: './shell-actions-sheet.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ShellActionsSheetComponent {
  private readonly sheetRef = inject<MatBottomSheetRef<ShellActionsSheetComponent>>(MatBottomSheetRef);

  dismiss(): void {
    this.sheetRef.dismiss();
  }
}
