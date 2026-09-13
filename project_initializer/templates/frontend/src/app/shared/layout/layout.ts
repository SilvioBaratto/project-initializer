import { DOCUMENT } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  Injector,
  afterNextRender,
  computed,
  effect,
  inject,
  signal,
  untracked,
  viewChild,
} from '@angular/core';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { MatBottomSheet, MatBottomSheetRef } from '@angular/material/bottom-sheet';
import { MatIconButton } from '@angular/material/button';
import { MatSidenav, MatSidenavContainer, MatSidenavContent } from '@angular/material/sidenav';
import { Title } from '@angular/platform-browser';
import { NavigationEnd, NavigationStart, Router, RouterOutlet, TitleStrategy } from '@angular/router';
import { LucideAngularModule } from 'lucide-angular';
import { filter, map } from 'rxjs/operators';

import { WindowSizeClassService } from '../../services/window-size-class';
import { BottomTabBarComponent } from '../bottom-tab-bar/bottom-tab-bar';
import { RailActionsSheet, SidebarMode } from '../nav-item';
import { RAIL_ACTIONS_SHEET, SidebarComponent } from '../sidebar/sidebar';
import { HamburgerComponent } from '../ui/hamburger/hamburger';
import { NavbarComponent } from '../ui/navbar/navbar';
import { ShellActionsSheetComponent } from './shell-actions-sheet';

/** localStorage key of the user's rail choice: 'true' (expanded) or 'false' (collapsed). */
export const RAIL_EXPANDED_STORAGE_KEY = 'app-rail-expanded';

/**
 * The stored rail choice, or `null` when the user hasn't picked one. The localStorage getter
 * throws when the browser blocks site data, so any failure reads as no choice.
 */
function readRailChoice(): boolean | null {
  try {
    const value = localStorage.getItem(RAIL_EXPANDED_STORAGE_KEY);
    return value === 'true' ? true : value === 'false' ? false : null;
  } catch {
    return null;
  }
}

function persistRailChoice(expanded: boolean): void {
  try {
    localStorage.setItem(RAIL_EXPANDED_STORAGE_KEY, String(expanded));
  } catch {
    // Storage is blocked or full: the choice lasts while the shell lives.
  }
}

/**
 * A shell control that had focus when the window size class changed, named by what it does:
 * the new navigation form renders a different element for the same destination or action.
 */
type ShellFocusTarget =
  | { kind: 'destination'; href: string }
  | { kind: 'action'; selector: '.sidebar-theme-toggle' | '.sidebar-logout' }
  | { kind: 'railToggle' };

/**
 * App shell: M3 navigation per window size class, hosted in `mat-sidenav-container`.
 *
 * | Window size class         | Navigation and actions                                            |
 * |---------------------------|-------------------------------------------------------------------|
 * | compact (< 600px)         | Top app bar + navigation bar; the top app bar button opens a      |
 * |                           | modal bottom sheet with the rail's actions (no destinations)      |
 * | medium (600–839px)        | Collapsed rail, docked, no expand toggle                          |
 * | expanded, large (840–1599)| Collapsed rail by default; the toggle docks an expanded rail      |
 * | extra-large (>= 1600px)   | Expanded rail by default                                          |
 *
 * Once the user toggles the rail, that choice holds across size classes, reloads and the
 * shell being recreated after signing in again (it is kept in localStorage).
 * When a size class change removes the focused shell control, focus moves to the same
 * destination or action in the new form instead of dropping to <body>.
 * `<main>` is the only scroll container, so the shell resets and restores its scroll
 * offset on navigation (the router's scroll restoration only drives the window).
 */
@Component({
  selector: 'app-layout',
  imports: [
    RouterOutlet,
    MatSidenavContainer,
    MatSidenav,
    MatSidenavContent,
    MatIconButton,
    LucideAngularModule,
    SidebarComponent,
    BottomTabBarComponent,
    NavbarComponent,
    HamburgerComponent,
  ],
  templateUrl: './layout.html',
  styleUrl: './layout.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class LayoutComponent {
  private readonly router = inject(Router);
  private readonly title = inject(Title);
  private readonly titleStrategy = inject(TitleStrategy);
  private readonly sizeClass = inject(WindowSizeClassService);
  private readonly injector = inject(Injector);
  private readonly bottomSheet = inject(MatBottomSheet);
  private readonly document = inject(DOCUMENT);
  private readonly host: ElementRef<HTMLElement> = inject(ElementRef);

  private readonly main = viewChild<ElementRef<HTMLElement>>('main');
  private readonly sidenavContainer = viewChild.required(MatSidenavContainer);
  private readonly rail = viewChild(MatSidenav, { read: ElementRef<HTMLElement> });

  /** Current M3 window size class. */
  readonly windowSize = this.sizeClass.current;

  /** Compact window: top app bar, navigation bar and the actions bottom sheet. */
  readonly isMobile = this.sizeClass.isCompact;

  /**
   * Accessible names and icon of the compact actions sheet and its trigger. Each layer's
   * sidebar.ts exports them, because only the auth variants hold an account and Sign out.
   */
  readonly actionsSheet: RailActionsSheet = RAIL_ACTIONS_SHEET;

  /** The open compact actions sheet, if any. */
  private actionsSheetRef: MatBottomSheetRef<ShellActionsSheetComponent> | null = null;

  /** The user's expand/collapse choice; `null` until they toggle (size-class default applies). */
  private readonly expandedChoice = signal<boolean | null>(readRailChoice());

  /** M3 lists a docked expanded rail from the expanded size class up; medium only docks the collapsed rail. */
  readonly canExpandRail = computed(() => this.sizeClass.atLeast('expanded'));

  /** Whether the docked rail is expanded: the user's choice, else expanded only at extra-large. */
  readonly railExpanded = computed(
    () => this.expandedChoice() ?? this.windowSize() === 'extraLarge',
  );

  /** Form of app-sidebar: `modal` in the compact sheet, else the docked rail's form. */
  readonly sidebarMode = computed<SidebarMode>(() => {
    if (this.isMobile()) return 'modal';
    return this.canExpandRail() && this.railExpanded() ? 'expanded' : 'collapsed';
  });

  /**
   * Page title for the route announcer, built from the new router state when the
   * navigation ends. Read from the state rather than document.title, which the
   * TitleStrategy may not have updated yet when NavigationEnd is emitted.
   */
  readonly announced = toSignal(
    this.router.events.pipe(
      filter((e): e is NavigationEnd => e instanceof NavigationEnd),
      map(
        () =>
          this.titleStrategy.buildTitle(this.router.routerState.snapshot) ?? this.title.getTitle(),
      ),
    ),
    { initialValue: '' },
  );

  /**
   * Scroll offset of `<main>` per page, keyed by the id of the navigation that showed it.
   * Same bookkeeping as the router's own RouterScroller, applied to the shell's scroll container.
   */
  private readonly scrollOffsets = new Map<number, number>();
  private shownNavigationId = 0;
  private restoreFromId: number | null = null;

  constructor() {
    // A size class change can remove the focused shell control: the sheet and its trigger at
    // 600px, the rail toggle below 840px, the rail or the bar at 600px, the expanded rail's items
    // when it collapses. Component effects run before the component's template updates, so the
    // control still has focus here; once it is gone, focus moves to its counterpart.
    effect(() => {
      this.windowSize();
      untracked(() => {
        const target = this.focusedShellControl();
        // From 600px the docked rail shows the same actions, and the sheet's trigger is gone.
        const sheet = this.isMobile() ? null : this.actionsSheetRef;
        if (target && sheet) {
          // Focus drops out when the sheet detaches, which is after the docked rail renders.
          sheet.afterDismissed().subscribe(() => this.restoreShellFocus(target));
        } else if (target) {
          afterNextRender(() => this.restoreShellFocus(target), { injector: this.injector });
        }
        if (sheet) {
          this.closeActionsSheet();
        }
      });
    });
    inject(DestroyRef).onDestroy(() => this.closeActionsSheet());

    // The collapsed rail sizes to its labels (layout.css), so it can widen with no change
    // detection run or window resize (a web font finishing loading, text enlarged in place),
    // and Material re-measures the drawer only on those. Re-measure when the rail's box changes.
    effect((onCleanup) => {
      const rail = this.rail()?.nativeElement;
      const container = this.sidenavContainer();
      if (!rail || typeof ResizeObserver === 'undefined') {
        return;
      }
      const observer = new ResizeObserver(() => container.updateContentMargins());
      observer.observe(rail);
      onCleanup(() => observer.disconnect());
    });

    this.router.events.pipe(takeUntilDestroyed()).subscribe((event) => {
      if (event instanceof NavigationStart) {
        this.scrollOffsets.set(this.shownNavigationId, this.main()?.nativeElement.scrollTop ?? 0);
        // Back/forward returns to where that page was left; any other navigation starts at the top.
        this.restoreFromId =
          event.navigationTrigger === 'popstate' ? (event.restoredState?.navigationId ?? null) : null;
      } else if (event instanceof NavigationEnd) {
        this.shownNavigationId = event.id;
        const top = this.restoreFromId === null ? 0 : (this.scrollOffsets.get(this.restoreFromId) ?? 0);
        this.scrollMainTo(top);
        this.focusMain();
      }
    });
  }

  /**
   * Opens the compact actions bottom sheet. MatBottomSheet traps focus, closes on Esc and on
   * the scrim, and returns focus to the trigger.
   */
  openActionsSheet(): void {
    const ref = this.bottomSheet.open(ShellActionsSheetComponent, {
      ariaLabel: this.actionsSheet.sheetLabel,
      panelClass: 'app-shell-actions-sheet',
    });
    this.actionsSheetRef = ref;
    ref.afterDismissed().subscribe(() => {
      if (this.actionsSheetRef === ref) {
        this.actionsSheetRef = null;
      }
    });
  }

  /** Expands or collapses the docked rail (expanded size class and up) and remembers the choice. */
  toggleRail(): void {
    const expanded = !this.railExpanded();
    this.expandedChoice.set(expanded);
    persistRailChoice(expanded);
  }

  /**
   * Skip link activation. index.html sets `<base href="/">`, so following
   * `href="#main-content"` would resolve to `/#main-content` and reload the app;
   * move focus in code instead.
   */
  skipToMain(event: Event): void {
    event.preventDefault();
    this.focusMain();
  }

  private closeActionsSheet(): void {
    this.actionsSheetRef?.dismiss();
  }

  /** The shell control that has focus (in the rail, the top app bar, the bar or the sheet), if any. */
  private focusedShellControl(): ShellFocusTarget | null {
    const focused = this.document.activeElement;
    if (!focused || focused === this.document.body) {
      return null;
    }
    const inSheet = focused.closest('.app-shell-actions-sheet') !== null;
    const inChrome =
      this.host.nativeElement.contains(focused) &&
      focused.closest('.rail-content, .shell-top-app-bar, .shell-nav-bar') !== null;
    if (!inSheet && !inChrome) {
      return null;
    }
    if (focused.closest('app-hamburger')) {
      return { kind: 'railToggle' };
    }
    const link = focused.closest('a[href]');
    if (link) {
      return { kind: 'destination', href: link.getAttribute('href') ?? '' };
    }
    if (focused.closest('.sidebar-logout')) {
      return { kind: 'action', selector: '.sidebar-logout' };
    }
    // The theme toggle, the top app bar button that opens the sheet, or the sheet itself.
    return { kind: 'action', selector: '.sidebar-theme-toggle' };
  }

  /**
   * Moves focus to the counterpart of `target` in the current navigation form, or to main when
   * there is none. Does nothing unless focus was lost: focus that survived, or that the user
   * has moved on, stays where it is.
   */
  private restoreShellFocus(target: ShellFocusTarget): void {
    const focused = this.document.activeElement;
    if (!this.host.nativeElement.isConnected || (focused && focused !== this.document.body)) {
      return;
    }
    const counterpart = this.shellControlFor(target);
    if (counterpart) {
      counterpart.focus();
    } else {
      this.focusMain();
    }
  }

  private shellControlFor(target: ShellFocusTarget): HTMLElement | null {
    const host = this.host.nativeElement;
    switch (target.kind) {
      case 'destination': {
        const links = host.querySelectorAll<HTMLElement>('.rail-content a[href], .shell-nav-bar a[href]');
        return Array.from(links).find((link) => link.getAttribute('href') === target.href) ?? null;
      }
      case 'action': {
        // Below 600px the rail's actions live in the sheet, opened from the top app bar.
        const rail = host.querySelector('.rail-content');
        return rail
          ? rail.querySelector<HTMLElement>(`.sidebar-footer ${target.selector}`)
          : host.querySelector<HTMLElement>('.shell-actions-toggle');
      }
      case 'railToggle':
        // Below 840px there is no toggle: the current destination sits where it was.
        return (
          host.querySelector<HTMLElement>('.rail-header app-hamburger button') ??
          host.querySelector<HTMLElement>('.rail-content a[aria-current="page"], .shell-nav-bar a[aria-current="page"]')
        );
    }
  }

  /** Applied after the new route renders, so a restored offset isn't clamped to the old page's height. */
  private scrollMainTo(top: number): void {
    afterNextRender(
      {
        write: () => {
          const main = this.main()?.nativeElement;
          if (main) {
            main.scrollTop = top;
          }
        },
      },
      { injector: this.injector },
    );
  }

  private focusMain(): void {
    // Undefined before the first render (the initial NavigationEnd can precede it).
    this.main()?.nativeElement.focus({ preventScroll: true });
  }
}
