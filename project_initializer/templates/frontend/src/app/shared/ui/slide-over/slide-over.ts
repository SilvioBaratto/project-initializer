import {
  ChangeDetectionStrategy,
  Component,
  input,
  model,
  output,
  viewChild,
} from '@angular/core';
import { DrawerComponent, DrawerSide } from '../drawer/drawer';

/**
 * Edge the panel opens from. `right` (the default) is the trailing edge and `left` the leading
 * edge, so both mirror under RTL. Same values as `DrawerSide`.
 */
export type SlideOverSide = DrawerSide;

/**
 * Modal side sheet (M3) at the trailing edge.
 *
 * A thin wrapper around `<app-drawer>`, which opens the projected content as a `MatDialog` side
 * sheet: the scrim, the focus trap, Esc, focus restore to the trigger and hiding the rest of the
 * page from assistive technology all come from there, and so do the pane styles
 * (`src/styles/overlays/_drawer.scss`). The sheet header shows `label` as its `h2` headline, which
 * also names the dialog, and a close icon button named "Close panel".
 *
 * Every user dismissal (Esc, scrim click, the close button, a route change) sets `open` to false
 * and emits `closed`. Setting `open` to false from the parent closes the panel without emitting.
 * Bind `[(open)]`, or `[open]` plus `(closed)` to clear the parent's own state.
 *
 * The trigger that opens the panel takes `aria-haspopup="dialog"`. It needs no `aria-expanded`:
 * while the panel is open, MatDialog hides the trigger from assistive technology.
 *
 * The open panel renders the lucide `X` icon in its close button, so the injector needs a lucide
 * icon provider that registers `X`: `ICON_PROVIDER` from `src/app/icons.ts`, which `app.config.ts`
 * already provides. A TestBed that opens the panel must add `ICON_PROVIDER` to its providers,
 * otherwise lucide-angular throws "The "X" icon has not been provided by any available icon
 * providers."
 */
@Component({
  selector: 'app-slide-over',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DrawerComponent],
  templateUrl: './slide-over.html',
  styleUrl: './slide-over.css',
})
export class SlideOverComponent {
  readonly open = model(false);
  readonly side = input<SlideOverSide>('right');
  /**
   * Required. Visible `h2` headline of the panel, which also names the dialog. There is no default:
   * a generic title such as "Panel" would not describe the content. Pass a specific, sentence-case
   * title such as "Order details".
   */
  readonly label = input.required<string>();
  readonly closed = output<void>();

  private readonly drawer = viewChild.required(DrawerComponent);

  /** Dismisses the panel as the user would: closes it, then sets `open` to false and emits `closed`. */
  handleClose(): void {
    this.drawer().handleClose();
  }
}
