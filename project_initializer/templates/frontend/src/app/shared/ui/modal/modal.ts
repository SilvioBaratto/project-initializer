import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  TemplateRef,
  contentChild,
  effect,
  inject,
  input,
  model,
  output,
  untracked,
  viewChild,
} from '@angular/core';
import { MatButton } from '@angular/material/button';
import {
  MatDialog,
  MatDialogActions,
  MatDialogClose,
  MatDialogContent,
  MatDialogRef,
  MatDialogTitle,
} from '@angular/material/dialog';

import { ModalActionsComponent } from './modal-actions';

let nextTitleId = 0;

/** ARIA role of the dialog. `alertdialog` marks a confirmation that needs the user's response. */
export type ModalRole = 'dialog' | 'alertdialog';

/**
 * Declarative M3 simple dialog on top of MatDialog: `open` shows it, `label` is its
 * headline, the projected content is its body and an optional projected
 * `<app-modal-actions>` is its end-aligned action row. Without one, the row holds a single
 * Close text button, so every dialog keeps a visible way out. A simple dialog has no close
 * icon button: it is dismissed through an action, Esc or the scrim.
 *
 * MatDialog provides the scrim, the `role` labelled by the headline, the focus trap,
 * initial focus, Esc and scrim dismissal, and returning focus to the trigger on close. It keeps
 * the dialog modal for assistive technology by setting `aria-hidden="true"` on everything
 * outside the overlay container; `aria-modal` stays off (Material's default), because
 * it would also hide select and menu panels opened from inside the dialog.
 *
 * Initial focus goes to a projected `cdkFocusInitial` element, or else to the first tabbable
 * element in DOM order: a control in the content, then the first action. Mark the element that
 * serves the dialog's goal (a text field) with `cdkFocusInitial`. In a destructive confirmation,
 * put Cancel first in `<app-modal-actions>` so it is the one that takes focus.
 *
 * `role`: pass `role="alertdialog"` for a confirmation, such as "Delete report.pdf?", so screen
 * readers announce it as an alert. MatDialog reads it once, when the dialog opens, and puts it on
 * the dialog container. Angular would also write a static `role` attribute onto `<app-modal>`,
 * which stays empty in the page, so the host binds `attr.role` to null: the page never holds an
 * unnamed, empty dialog node.
 *
 * Closing from projected content: projected elements are created in the consumer's
 * view, which has no MatDialogRef, so `mat-dialog-close` on them throws when clicked
 * and the dialog stays open. Close through this component instead, with
 * `<app-modal #modal>` and `(click)="modal.close()"`, or by setting `[(open)]` to false.
 *
 * `closed` fires once each time the dialog closes for a reason other than `open`
 * turning false or this component being destroyed: Esc, a scrim click, the Close
 * action, `close()`, or MatDialog closing it on navigation. `open` is a model, so
 * `[(open)]` stays in sync by itself; with a one-way `[open]`, reset it from `(closed)`.
 */
@Component({
  selector: 'app-modal',
  templateUrl: './modal.html',
  styleUrl: './modal.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [MatDialogTitle, MatDialogContent, MatDialogActions, MatDialogClose, MatButton],
  host: {
    // The role input only configures MatDialog; the attribute belongs on the dialog container.
    '[attr.role]': 'null',
  },
})
export class ModalComponent {
  readonly open = model(false);
  /**
   * Required. Visible `h2` headline, which also names the dialog. There is no default: a generic
   * title such as "Dialog" would not describe the content. Pass a specific, sentence-case title
   * such as "Delete report.pdf?".
   */
  readonly label = input.required<string>();
  /** `dialog` (default) or `alertdialog` for confirmations. Read when the dialog opens. */
  readonly role = input<ModalRole>('dialog');
  readonly closed = output<void>();

  protected readonly titleId = `app-modal-title-${nextTitleId++}`;
  protected readonly actions = contentChild(ModalActionsComponent);

  private readonly dialog = inject(MatDialog);
  private readonly dialogTemplate = viewChild.required<TemplateRef<unknown>>('dialogTemplate');
  private dialogRef: MatDialogRef<unknown> | null = null;

  constructor() {
    effect(() => {
      const open = this.open();
      untracked(() => (open ? this.show() : this.hide()));
    });
    inject(DestroyRef).onDestroy(() => this.hide());
  }

  /**
   * Dismisses the dialog as the user would: `open` turns false and `closed` fires once.
   * Use it from projected buttons such as Cancel. Does nothing while the dialog is closed.
   */
  close(): void {
    this.dialogRef?.close();
  }

  private show(): void {
    if (this.dialogRef) return;

    const ref = this.dialog.open(this.dialogTemplate(), {
      panelClass: 'app-modal-panel',
      role: this.role(),
      ariaLabelledBy: this.titleId,
      autoFocus: 'first-tabbable',
      restoreFocus: true,
    });
    this.dialogRef = ref;

    ref.beforeClosed().subscribe(() => {
      // hide() releases the ref before closing it, so only a dismissal reaches past this guard.
      if (this.dialogRef !== ref) return;
      this.dialogRef = null;
      this.open.set(false);
      this.closed.emit();
    });
  }

  private hide(): void {
    const ref = this.dialogRef;
    if (!ref) return;
    this.dialogRef = null;
    ref.close();
  }
}
