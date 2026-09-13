import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  TemplateRef,
  effect,
  inject,
  input,
  isDevMode,
  model,
  output,
  untracked,
  viewChild,
} from '@angular/core';
import { Directionality } from '@angular/cdk/bidi';
import { MatIconButton } from '@angular/material/button';
import { MatDialog, MatDialogRef, MatDialogTitle } from '@angular/material/dialog';
import { LucideAngularModule } from 'lucide-angular';

/**
 * Edge the sheet opens from. `left` is the leading edge and `right` the trailing edge, so both
 * mirror under RTL (the M3 Bidirectionality and RTL page names edges leading and trailing).
 */
export type DrawerSide = 'left' | 'right';

/** Class on the overlay pane; the panel itself is styled in `src/styles/overlays/_drawer.scss`. */
export const DRAWER_PANEL_CLASS = 'app-drawer-panel';
const LEADING_EDGE_CLASS = `${DRAWER_PANEL_CLASS}--start`;
const TRAILING_EDGE_CLASS = `${DRAWER_PANEL_CLASS}--end`;

/**
 * Modal side sheet (M3) on `MatDialog`.
 *
 * Declarative wrapper: the projected content lives in an `<ng-template>` that is opened as a dialog
 * while `open` is true. MatDialog provides the scrim, the focus trap, Esc, focus restore to the
 * trigger and hides the rest of the page from assistive technology while the sheet is open.
 *
 * Every user dismissal (Esc, scrim click, the close button, a route change) sets `open` to false
 * and emits `close`. Setting `open` to false from the parent closes the sheet without emitting.
 * Bind `[(open)]`, or `[open]` plus `(close)` to clear the parent's own state.
 *
 * The trigger that opens the sheet takes `aria-haspopup="dialog"`. It needs no `aria-expanded`:
 * while the sheet is open, MatDialog hides the trigger from assistive technology.
 */
@Component({
  selector: 'app-drawer',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [LucideAngularModule, MatDialogTitle, MatIconButton],
  templateUrl: './drawer.html',
  styleUrl: './drawer.css',
})
export class DrawerComponent {
  readonly side = input<DrawerSide>('left');
  readonly open = model(false);
  /**
   * Id of the sheet's dialog element. That element exists only while the sheet is open, so a
   * trigger that references it binds `[attr.aria-controls]="open ? drawerId : null"`.
   * When empty, Material generates an id with the `mat-mdc-dialog-` prefix.
   */
  readonly drawerId = input('');
  /**
   * Visible headline and accessible name of the sheet. It stays the name while it changes, and
   * clearing it removes both. Pass it (or `ariaLabel`) on every usage: without a name the sheet
   * is an unnamed dialog and a dev-mode warning is logged when it opens.
   */
  readonly label = input('');
  /**
   * Accessible name for a sheet without a visible headline. Used only when `label` is empty at the
   * moment the sheet opens (MatDialog reads it once) and then wins over a later `label`.
   */
  readonly ariaLabel = input('');
  /** Accessible name of the close icon button. */
  readonly closeLabel = input('Close');
  /**
   * @deprecated Has no effect. A modal side sheet always traps focus (MatDialog creates a CDK
   * FocusTrap for every dialog). Kept so existing `[trapFocus]` bindings still compile.
   */
  readonly trapFocus = input(true);
  readonly close = output<void>();

  private readonly dialog = inject(MatDialog);
  private readonly dir = inject(Directionality);
  private readonly sheet = viewChild.required<TemplateRef<unknown>>('sheet');
  private ref: MatDialogRef<unknown> | null = null;

  constructor() {
    effect(() => {
      const isOpen = this.open();
      untracked(() => (isOpen ? this.show() : this.hide()));
    });

    effect(() => {
      const side = this.side();
      untracked(() => this.ref && this.place(this.ref, side));
    });

    inject(DestroyRef).onDestroy(() => this.hide());
  }

  /** Dismisses the sheet as the user would: closes it, then sets `open` to false and emits `close`. */
  handleClose(): void {
    this.ref?.close();
  }

  private show(): void {
    if (this.ref) return;

    const hasHeadline = !!this.label();
    if (!hasHeadline && !this.ariaLabel() && isDevMode()) {
      console.warn(
        'app-drawer: the side sheet has no accessible name. Pass label, or ariaLabel when it has no visible headline.',
      );
    }

    const ref = this.dialog.open(this.sheet(), {
      id: this.drawerId() || undefined,
      panelClass: DRAWER_PANEL_CLASS,
      direction: this.dir.value,
      // With a headline, matDialogTitle on the <h2> registers it as aria-labelledby.
      ariaLabel: hasHeadline ? null : this.ariaLabel() || null,
    });
    this.ref = ref;
    this.place(ref, this.side());

    // Esc, scrim click, the close button and closeOnNavigation all end here.
    ref.afterClosed().subscribe(() => {
      if (this.ref !== ref) return; // closed through `open` or by destroying the component
      this.ref = null;
      this.open.set(false);
      this.close.emit();
    });
  }

  private hide(): void {
    const ref = this.ref;
    this.ref = null;
    ref?.close();
  }

  /**
   * MatDialog positions are physical, so resolve the leading edge from the direction here.
   * The edge class lets the overlay partial round the inner corners with logical properties.
   */
  private place(ref: MatDialogRef<unknown>, side: DrawerSide): void {
    const leading = side === 'left';
    const physicalLeft = leading === (this.dir.value !== 'rtl');
    ref.updatePosition(physicalLeft ? { top: '0', left: '0' } : { top: '0', right: '0' });
    ref.removePanelClass([LEADING_EDGE_CLASS, TRAILING_EDGE_CLASS]);
    ref.addPanelClass(leading ? LEADING_EDGE_CLASS : TRAILING_EDGE_CLASS);
  }
}
