import { Component } from '@angular/core';
import { Location } from '@angular/common';
import { provideLocationMocks } from '@angular/common/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { MediaMatcher } from '@angular/cdk/layout';
import { TestbedHarnessEnvironment } from '@angular/cdk/testing/testbed';
import { MatBottomSheetHarness } from '@angular/material/bottom-sheet/testing';
import { MatButtonHarness } from '@angular/material/button/testing';
import { MATERIAL_ANIMATIONS } from '@angular/material/core';
import { Router, Routes, provideRouter } from '@angular/router';
import { LucideIconConfig } from 'lucide-angular';

import { ICON_PROVIDER } from '../../icons';
import { WINDOW_SIZE_QUERIES, WindowSizeClass } from '../../services/window-size-class';
import { RAIL_ACTIONS_SHEET } from '../sidebar/sidebar';
import { LayoutComponent } from './layout';

@Component({ selector: 'app-route-stub', template: '' })
class RouteStubComponent {}

/** jsdom has no matchMedia: a MediaMatcher that matches exactly one M3 window size class. */
function mediaMatcherFor(active: WindowSizeClass): Partial<MediaMatcher> {
  return {
    matchMedia: (query: string) =>
      ({
        matches: query === WINDOW_SIZE_QUERIES[active],
        media: query,
        addListener: () => undefined,
        removeListener: () => undefined,
        addEventListener: () => undefined,
        removeEventListener: () => undefined,
      }) as unknown as MediaQueryList,
  };
}

/** ThemeService (rendered by the rail) reads window.matchMedia directly. */
function defineWindowMatchMedia(): void {
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    writable: true,
    value: (query: string) =>
      ({
        matches: false,
        media: query,
        addEventListener: () => undefined,
        removeEventListener: () => undefined,
      }) as unknown as MediaQueryList,
  });
}

/** Lets overlays (the bottom sheet) finish opening or closing, then renders. */
async function flush(fixture: ComponentFixture<unknown>): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve));
  fixture.detectChanges();
  await fixture.whenStable();
}

describe('LayoutComponent', () => {
  let fixture: ComponentFixture<LayoutComponent>;
  let host: HTMLElement;

  const routes: Routes = [
    { path: 'home', component: RouteStubComponent, title: 'Home' },
    { path: 'dashboard', component: RouteStubComponent, title: 'Dashboard' },
  ];

  async function render(size: WindowSizeClass = 'compact'): Promise<void> {
    defineWindowMatchMedia();
    await TestBed.configureTestingModule({
      imports: [LayoutComponent],
      providers: [
        provideRouter(routes),
        // SpyLocation: back() emits a popstate the router handles like the browser's.
        provideLocationMocks(),
        ICON_PROVIDER,
        LucideIconConfig,
        { provide: MediaMatcher, useValue: mediaMatcherFor(size) },
        { provide: MATERIAL_ANIMATIONS, useValue: { animationsDisabled: true } },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(LayoutComponent);
    host = fixture.nativeElement;
    fixture.detectChanges();
    await fixture.whenStable();
  }

  async function navigate(url: string): Promise<void> {
    await TestBed.inject(Router).navigateByUrl(url);
    fixture.detectChanges();
    await fixture.whenStable();
  }

  function actionsButton(): HTMLButtonElement {
    return host.querySelector<HTMLButtonElement>('app-navbar button[navbarActions]')!;
  }

  afterEach(() => {
    document.documentElement.classList.remove('dark', 'light', 'theme-transitioning');
    localStorage.clear();
  });

  it('when the shell renders from 600px, app-sidebar is hosted in the docked mat-sidenav rail', async () => {
    await render('medium');
    expect(host.querySelector('mat-sidenav-container mat-sidenav#app-rail app-sidebar')).toBeTruthy();
  });

  it('when the shell renders at compact, no rail renders and the navigation bar closes mat-sidenav-content', async () => {
    await render();
    expect(host.querySelector('mat-sidenav')).toBeNull();
    const content = host.querySelector('mat-sidenav-content')!;
    expect(content.lastElementChild?.tagName.toLowerCase()).toBe('app-bottom-tab-bar');
  });

  it('when the shell renders, main is the single, unlabelled main landmark and the skip-link target', async () => {
    await render();
    const main = host.querySelector('mat-sidenav-content main');
    expect(host.querySelectorAll('main').length).toBe(1);
    expect(main?.id).toBe('main-content');
    expect(main?.getAttribute('tabindex')).toBe('-1');
    // One main landmark needs no label; "Main content" would only repeat the role.
    expect(main?.hasAttribute('aria-label')).toBe(false);
  });

  it('when the shell renders, a skip link to main-content is the first element', async () => {
    await render();
    const skipLink = host.firstElementChild;
    expect(skipLink?.matches('a.skip-link[href="#main-content"]')).toBe(true);
    expect(skipLink?.textContent?.trim()).toBe('Skip to content');
  });

  it('when the skip link is activated, focus moves to main in code instead of following the hash', async () => {
    await render();
    const skipLink = host.querySelector<HTMLAnchorElement>('a.skip-link')!;
    const main = host.querySelector<HTMLElement>('#main-content')!;

    const click = new MouseEvent('click', { bubbles: true, cancelable: true });
    skipLink.dispatchEvent(click);

    // <base href="/"> would turn the hash into a full navigation to /#main-content.
    expect(click.defaultPrevented).toBe(true);
    expect(document.activeElement).toBe(main);
  });

  it('when the shell renders, a visually hidden aria-live route announcer is present', async () => {
    await render();
    const announcer = host.querySelector('.cdk-visually-hidden[aria-live="polite"]');
    expect(announcer).toBeTruthy();
    expect(announcer?.getAttribute('aria-atomic')).toBe('true');
  });

  it('when navigation ends, the announcer reads the new page title', async () => {
    await render();
    await navigate('/dashboard');
    expect(host.querySelector('[aria-live="polite"]')?.textContent?.trim()).toBe('Dashboard');
  });

  it('when the shell renders, no toast outlet exists (toasts open as MatSnackBar overlays)', async () => {
    await render();
    expect(host.querySelector('#toast-outlet')).toBeNull();
    expect(host.querySelector('app-toast')).toBeNull();
  });

  it('when the top app bar renders at compact, it holds the brand and a trailing icon button that opens the actions sheet', async () => {
    await render();
    const navbar = host.querySelector('app-navbar')!;
    expect(navbar.querySelector('header')).toBeTruthy();
    expect(navbar.querySelector('[navbarBrand]')?.textContent?.trim()).toBe('Acme');

    const toggle = await TestbedHarnessEnvironment.loader(fixture).getHarness(
      MatButtonHarness.with({ selector: 'app-navbar [navbarActions]' }),
    );
    expect(await toggle.getVariant()).toBe('icon');
    const button = actionsButton();
    expect(button.getAttribute('aria-haspopup')).toBe('dialog');
    // Named for the layer's sheet contents (theme only in the base scaffold), never "navigation".
    expect(button.getAttribute('aria-label')).toBe(RAIL_ACTIONS_SHEET.triggerLabel);
    expect(button.hasAttribute('aria-expanded')).toBe(false);
    expect(button.hasAttribute('aria-controls')).toBe(false);
    expect(button.querySelector('lucide-icon')?.getAttribute('aria-hidden')).toBe('true');
  });

  it('when the actions button is clicked, a modal bottom sheet opens with app-sidebar in its modal form', async () => {
    await render();
    actionsButton().click();
    await flush(fixture);

    const sheet = await TestbedHarnessEnvironment.documentRootLoader(fixture).getHarness(MatBottomSheetHarness);
    expect(await sheet.getAriaLabel()).toBe(RAIL_ACTIONS_SHEET.sheetLabel);
    // The panel class the global overlay partial can select the sheet by.
    const pane = document.querySelector('.cdk-overlay-pane.app-shell-actions-sheet');
    expect(pane?.querySelector('.mat-bottom-sheet-container[role="dialog"] app-shell-actions-sheet app-sidebar')).toBeTruthy();
    expect(pane?.querySelector('app-sidebar mat-selection-list.sidebar-theme-options')).toBeTruthy();
    expect(pane?.querySelectorAll('a').length).toBe(0);
  });

  it('when the shell is destroyed with the actions sheet open, the sheet closes with it', async () => {
    await render();
    actionsButton().click();
    await flush(fixture);
    expect(document.querySelector('app-shell-actions-sheet')).toBeTruthy();

    fixture.destroy();
    await new Promise((resolve) => setTimeout(resolve));
    await new Promise((resolve) => setTimeout(resolve));
    expect(document.querySelector('app-shell-actions-sheet')).toBeNull();
  });

  it('when navigation ends, focus moves to main-content', async () => {
    await render();
    const main = host.querySelector<HTMLElement>('#main-content')!;
    await navigate('/home');
    expect(document.activeElement).toBe(main);
  });

  it('when a navigation ends, main (the only scroll container) starts the new page at the top', async () => {
    await render();
    await navigate('/home');
    const main = host.querySelector<HTMLElement>('#main-content')!;
    main.scrollTop = 240;

    await navigate('/dashboard');
    expect(main.scrollTop).toBe(0);
  });

  it('when the browser goes back, main restores the offset the previous page was left at', async () => {
    await render();
    // TestBed never bootstraps, so the router's popstate listener has to be attached by hand.
    TestBed.inject(Router).setUpLocationChangeListener();
    await navigate('/home');
    const main = host.querySelector<HTMLElement>('#main-content')!;
    main.scrollTop = 240;
    await navigate('/dashboard');
    main.scrollTop = 60;

    TestBed.inject(Location).back();
    // The router schedules a popstate navigation in a timeout, which whenStable() can't see yet.
    await new Promise((resolve) => setTimeout(resolve));
    fixture.detectChanges();
    await fixture.whenStable();

    expect(TestBed.inject(Router).url).toBe('/home');
    expect(main.scrollTop).toBe(240);
    expect(document.activeElement).toBe(main);
  });

  it('when the window is medium or wider, neither the top app bar nor the navigation bar renders', async () => {
    await render('medium');
    expect(host.querySelector('app-navbar')).toBeNull();
    expect(host.querySelector('app-bottom-tab-bar')).toBeNull();
    expect(host.querySelector('mat-sidenav-content main#main-content')).toBeTruthy();
  });
});
