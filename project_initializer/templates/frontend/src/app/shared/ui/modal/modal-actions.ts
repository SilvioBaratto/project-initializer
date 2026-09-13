import { ChangeDetectionStrategy, Component } from '@angular/core';

/**
 * Action row slot for `app-modal`. Wrap the dialog's buttons in it inside `<app-modal>`;
 * the modal renders them in an end-aligned `mat-dialog-actions` row below the scrolling
 * content, so they stay visible when the content is long.
 *
 * Put the dismissive action first and the confirming action last, with specific verbs
 * ("Cancel", "Delete file"). Close from here with `modal.close()` or by setting the
 * `[(open)]` state to false, never with `mat-dialog-close`: projected buttons belong to
 * the consumer's view, which has no MatDialogRef.
 */
@Component({
  selector: 'app-modal-actions',
  templateUrl: './modal-actions.html',
  styleUrl: './modal-actions.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ModalActionsComponent {}
