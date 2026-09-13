import { ChangeDetectionStrategy, Component } from '@angular/core';
import { MatToolbar } from '@angular/material/toolbar';

/**
 * M3 small top app bar built on `mat-toolbar`.
 *
 * The toolbar sits inside a `<header>`, which keeps banner landmark semantics
 * wherever the bar is rendered outside `<main>`. The header pads by the top and
 * horizontal safe-area insets in navbar.css, so the bar stays below the system
 * status region while its surface color still paints behind it.
 *
 * Colors and type come from mat-toolbar's own tokens (surface, on-surface,
 * title-large by default), so `mat.toolbar-overrides()` restyles the bar, its
 * safe-area strip and the brand together.
 *
 * Content projection slots:
 * - `[navbarBrand]`: leading content, such as the navigation toggle and the app
 *   title. The title inherits title-large; a long title wraps and the bar grows
 *   past its 64px minimum instead of clipping it.
 * - `[navbarActions]`: trailing actions (M3 recommends 1–2 essential actions),
 *   which keep their size at the inline end.
 */
@Component({
  selector: 'app-navbar',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [MatToolbar],
  templateUrl: './navbar.html',
  styleUrl: './navbar.css',
})
export class NavbarComponent {}
