import { Component, Signal, signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HarnessLoader } from '@angular/cdk/testing';
import { TestbedHarnessEnvironment } from '@angular/cdk/testing/testbed';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { MatButtonHarness } from '@angular/material/button/testing';
import { MatActionListHarness, MatNavListHarness, MatSelectionListHarness } from '@angular/material/list/testing';
import { MatMenuHarness } from '@angular/material/menu/testing';
import { MATERIAL_ANIMATIONS } from '@angular/material/core';
import { Router, Routes, provideRouter } from '@angular/router';
import { vi } from 'vitest';
import { LucideIconConfig } from 'lucide-angular';

import { authGuard, guestGuard } from '../../guards/auth.guard';
import { ICON_PROVIDER } from '../../icons';
import { AuthService } from '../../services/auth';
import { ThemeMode, ThemeService } from '../../services/theme';
import { NAV_ITEMS } from '../nav-item';
import { SidebarComponent, SidebarMode } from './sidebar';

/**
 * Token-auth overlay of the base sidebar spec, replacing it by path. Run against this
 * overlay's SidebarComponent, the base spec fails: its log out clicks navigate to /login
 * with no such route (unhandled NG04002 rejections) and never check the sign-out, and it
 * expects the placeholder "User" account row, which the token rail omits. The rail
 * contract assertions match the base spec; the log out assertions cover the token
 * sign-out (clear the token, replace history with /login, close the modal rail), and the
 * account assertions cover the omitted row and its accountName hook.
 * The base theme-menu.integration.spec.ts runs unchanged against this component.
 */

@Component({ selector: 'app-route-stub', template: '' })
class RouteStubComponent {}

/** Radio items of the open theme menu, rendered in the body-level overlay container. */
function themeMenuItems(): HTMLElement[] {
  return Array.from(document.querySelectorAll<HTMLElement>('.sidebar-theme-menu [role="menuitemradio"]'));
}

describe('SidebarComponent (token auth)', () => {
  let themeSpy: { setTheme: ReturnType<typeof vi.fn>; theme: ReturnType<typeof signal<ThemeMode>> };
  let authSpy: { logout: ReturnType<typeof vi.fn> };
  let fixture: ComponentFixture<SidebarComponent>;
  let loader: HarnessLoader;

  async function render(
    mode?: SidebarMode,
    routes: Routes = [],
    url?: string,
    accountName?: string,
  ): Promise<HTMLElement> {
    await TestBed.configureTestingModule({
      imports: [SidebarComponent],
      providers: [
        provideRouter(routes),
        ICON_PROVIDER,
        LucideIconConfig,
        { provide: ThemeService, useValue: themeSpy },
        { provide: AuthService, useValue: authSpy },
        { provide: MATERIAL_ANIMATIONS, useValue: { animationsDisabled: true } },
      ],
    }).compileComponents();

    if (url) {
      await TestBed.inject(Router).navigateByUrl(url);
    }
    fixture = TestBed.createComponent(SidebarComponent);
    if (mode) {
      fixture.componentRef.setInput('mode', mode);
    }
    if (accountName) {
      // Stands in for an identity source a product would wire into the token rail.
      (fixture.componentInstance as { accountName: Signal<string | null> }).accountName = signal(accountName);
    }
    loader = TestbedHarnessEnvironment.loader(fixture);
    fixture.detectChanges();
    await fixture.whenStable();
    return fixture.nativeElement;
  }

  function themeMenu(): Promise<MatMenuHarness> {
    return loader.getHarness(MatMenuHarness.with({ selector: '.sidebar-theme-toggle' }));
  }

  /** Spies on navigation after render, so a route set up by render() is not recorded. */
  function spyOnNavigate() {
    return vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);
  }

  function expectSignedOut(navigate: ReturnType<typeof spyOnNavigate>, emitted: ReturnType<typeof vi.fn>): void {
    expect(authSpy.logout).toHaveBeenCalledTimes(1);
    expect(navigate).toHaveBeenCalledTimes(1);
    expect(navigate).toHaveBeenCalledWith(['/login'], { replaceUrl: true });
    // The token is cleared before navigating, otherwise guestGuard would bounce /login back to /.
    expect(authSpy.logout.mock.invocationCallOrder[0]).toBeLessThan(navigate.mock.invocationCallOrder[0]);
    expect(emitted).toHaveBeenCalledTimes(1);
  }

  beforeEach(() => {
    themeSpy = { setTheme: vi.fn(), theme: signal<ThemeMode>('light') };
    authSpy = { logout: vi.fn() };
  });

  describe('expanded rail (default mode)', () => {
    it('when the rail renders, destinations sit in a mat-nav-list labelled Primary', async () => {
      const el = await render();
      const list = el.querySelector('mat-nav-list');
      expect(list?.getAttribute('role')).toBe('navigation');
      expect(list?.getAttribute('aria-label')).toBe('Primary');

      const navList = await loader.getHarness(MatNavListHarness);
      const items = await navList.getItems();
      expect(await Promise.all(items.map((i) => i.getTitle()))).toEqual(NAV_ITEMS.map((i) => i.name));
      expect(await Promise.all(items.map((i) => i.getHref()))).toEqual(NAV_ITEMS.map((i) => i.route));
    });

    it('when a destination is current, its item is activated with aria-current="page"', async () => {
      const routes = NAV_ITEMS.map((item) => ({ path: item.route.slice(1), component: RouteStubComponent }));
      const last = NAV_ITEMS[NAV_ITEMS.length - 1];
      const el = await render('expanded', routes, last.route);

      const items = await (await loader.getHarness(MatNavListHarness)).getItems();
      expect(await Promise.all(items.map((i) => i.isActivated()))).toEqual(NAV_ITEMS.map((i) => i === last));
      const current = el.querySelectorAll('a[aria-current="page"]');
      expect(current.length).toBe(1);
      expect(current[0].textContent).toContain(last.name);
    });

    it('when the rail renders, each item carries a decorative lucide-icon and no inline svg markup', async () => {
      const el = await render();
      const icons = el.querySelectorAll('mat-nav-list lucide-icon');
      expect(icons.length).toBe(NAV_ITEMS.length);
      icons.forEach((icon) => expect(icon.getAttribute('aria-hidden')).toBe('true'));
      // Every svg in the rail is rendered by a lucide-icon host.
      el.querySelectorAll('svg').forEach((svg) => expect(svg.closest('lucide-icon')).not.toBeNull());
    });

    it('when a destination is clicked, closeSidebar is emitted and the user stays signed in', async () => {
      await render('expanded', NAV_ITEMS.map((item) => ({ path: item.route.slice(1), component: RouteStubComponent })));
      const emitted = vi.fn();
      fixture.componentInstance.closeSidebar.subscribe(emitted);
      const [first] = await (await loader.getHarness(MatNavListHarness)).getItems();
      await first.click();
      expect(emitted).toHaveBeenCalledTimes(1);
      expect(authSpy.logout).not.toHaveBeenCalled();
    });

    it('when the actions render, Change theme and log out are list items and no placeholder account row shows', async () => {
      const el = await render();
      const actions = await (await loader.getHarness(MatActionListHarness)).getItems();
      expect(await Promise.all(actions.map((a) => a.getTitle()))).toEqual(['Change theme', 'Sign out']);
      // The base template shows Sign out through canSignOut; this overlay ships no template of its own.
      expect(fixture.componentInstance.canSignOut()).toBe(true);
      // LogOut's arrow points toward the inline end, so the icon is marked to mirror in RTL.
      const signOutIcon = el.querySelector('button.sidebar-logout lucide-icon');
      expect(signOutIcon?.classList.contains('sidebar-icon-directional')).toBe(true);
      // A bearer token names no user, so the rail shows no account name at all.
      expect(fixture.componentInstance.accountName()).toBeNull();
      expect(el.querySelector('.sidebar-account')).toBeNull();
      expect(el.textContent).not.toContain('User');
    });

    it('when log out is chosen, the token is cleared, /login replaces the history entry and the rail closes', async () => {
      await render();
      const navigate = spyOnNavigate();
      const emitted = vi.fn();
      fixture.componentInstance.closeSidebar.subscribe(emitted);

      const [, logout] = await (await loader.getHarness(MatActionListHarness)).getItems();
      await logout.click();
      expectSignedOut(navigate, emitted);
    });
  });

  describe('account row', () => {
    it('when an account name is provided, the modal and expanded rails show it above the actions and the collapsed rail omits it', async () => {
      const el = await render('modal', [], undefined, 'Sam Rivera');
      const row = el.querySelector('.sidebar-account');
      expect(row?.textContent?.trim()).toBe('Sam Rivera');
      expect(row?.querySelector('lucide-icon')?.getAttribute('aria-hidden')).toBe('true');
      const list = el.querySelector('mat-action-list')!;
      expect(row!.compareDocumentPosition(list) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();

      fixture.componentRef.setInput('mode', 'expanded');
      fixture.detectChanges();
      await fixture.whenStable();
      expect(el.querySelector('.sidebar-account')?.textContent?.trim()).toBe('Sam Rivera');

      fixture.componentRef.setInput('mode', 'collapsed');
      fixture.detectChanges();
      await fixture.whenStable();
      expect(el.querySelector('.sidebar-account')).toBeNull();
    });
  });

  describe('theme menu', () => {
    it('when a mode is chosen from the Change theme menu, ThemeService.setTheme receives it and the user stays signed in', async () => {
      await render();
      await (await themeMenu()).clickItem({ text: 'Dark' });
      expect(themeSpy.setTheme).toHaveBeenCalledTimes(1);
      expect(themeSpy.setTheme).toHaveBeenCalledWith('dark');
      expect(authSpy.logout).not.toHaveBeenCalled();
    });

    it('when the menu opens, its radio items check the current mode and follow a change', async () => {
      const el = await render();
      const button = el.querySelector<HTMLButtonElement>('button.sidebar-theme-toggle')!;
      expect(button.getAttribute('aria-haspopup')).toBe('menu');
      // Named by its visible text. No supporting line: the menu shows the current mode.
      expect(button.hasAttribute('aria-label')).toBe(false);
      expect(button.querySelector('.mat-mdc-list-item-line')).toBeNull();

      const menu = await themeMenu();
      await menu.open();
      expect(themeMenuItems().map((i) => i.textContent?.trim())).toEqual(['System', 'Light', 'Dark']);
      expect(themeMenuItems().map((i) => i.getAttribute('aria-checked'))).toEqual(['false', 'true', 'false']);
      await menu.close();

      themeSpy.theme.set('dark');
      fixture.detectChanges();
      await fixture.whenStable();
      await menu.open();
      expect(themeMenuItems().map((i) => i.getAttribute('aria-checked'))).toEqual(['false', 'false', 'true']);
    });
  });

  describe('collapsed rail', () => {
    it('when collapsed, destinations are icon-over-label links in a nav labelled Primary', async () => {
      const el = await render('collapsed');
      expect(el.querySelector('mat-nav-list')).toBeNull();
      const nav = el.querySelector('nav');
      expect(nav?.getAttribute('aria-label')).toBe('Primary');

      const links = Array.from(nav!.querySelectorAll<HTMLAnchorElement>('a.rail-item'));
      expect(links.map((a) => a.textContent?.trim())).toEqual(NAV_ITEMS.map((i) => i.name));
      for (const link of links) {
        expect(link.hasAttribute('aria-label')).toBe(false);
        expect(link.querySelector('.rail-indicator lucide-icon')?.getAttribute('aria-hidden')).toBe('true');
      }
    });

    it('when collapsed and a destination is current, that link has aria-current="page"', async () => {
      const routes = NAV_ITEMS.map((item) => ({ path: item.route.slice(1), component: RouteStubComponent }));
      const [first] = NAV_ITEMS;
      const el = await render('collapsed', routes, first.route);
      const current = el.querySelectorAll('a.rail-item[aria-current="page"]');
      expect(current.length).toBe(1);
      expect(current[0].textContent?.trim()).toBe(first.name);
    });

    it('when collapsed, Change theme and log out are icon buttons named by their action', async () => {
      await render('collapsed');
      const theme = await loader.getHarness(MatButtonHarness.with({ selector: '.sidebar-theme-toggle' }));
      const logout = await loader.getHarness(MatButtonHarness.with({ selector: '.sidebar-logout' }));
      expect(await theme.getVariant()).toBe('icon');
      expect(await logout.getVariant()).toBe('icon');
      expect(await (await theme.host()).getAttribute('aria-label')).toBe('Change theme');
      expect(await (await theme.host()).getAttribute('aria-haspopup')).toBe('menu');
      expect(await (await logout.host()).getAttribute('aria-label')).toBe('Sign out');

      // The icon hosts are grid boxes (.sidebar-icon), so the 24px svg centres in the 40px state layer.
      for (const selector of ['.sidebar-theme-toggle', '.sidebar-logout']) {
        const icon = fixture.nativeElement.querySelector(`button${selector} lucide-icon`);
        expect(icon?.classList.contains('sidebar-icon')).toBe(true);
        expect(icon?.getAttribute('aria-hidden')).toBe('true');
      }
      // Only the Sign out icon is directional (it mirrors in RTL).
      const logoutIcon = fixture.nativeElement.querySelector('button.sidebar-logout lucide-icon');
      expect(logoutIcon?.classList.contains('sidebar-icon-directional')).toBe(true);

      await (await themeMenu()).clickItem({ text: 'System' });
      expect(themeSpy.setTheme).toHaveBeenCalledWith('system');
      expect(authSpy.logout).not.toHaveBeenCalled();
    });

    it('when collapsed and log out is clicked, the token is cleared, /login replaces history and closeSidebar is emitted', async () => {
      await render('collapsed');
      const navigate = spyOnNavigate();
      const emitted = vi.fn();
      fixture.componentInstance.closeSidebar.subscribe(emitted);
      await (await loader.getHarness(MatButtonHarness.with({ selector: '.sidebar-logout' }))).click();
      expectSignedOut(navigate, emitted);
    });
  });

  describe('modal rail (compact)', () => {
    it('when modal, no destination is repeated from the navigation bar', async () => {
      const el = await render('modal');
      expect(el.querySelector('nav')).toBeNull();
      expect(el.querySelector('mat-nav-list')).toBeNull();
      expect(el.querySelectorAll('a').length).toBe(0);
    });

    it('when modal, it holds the theme choices and log out, with no placeholder account row', async () => {
      const el = await render('modal');
      expect(el.querySelector('.sidebar-account')).toBeNull();
      expect(el.querySelector('.sidebar-theme-toggle')).toBeNull();
      const options = await (await loader.getHarness(MatSelectionListHarness)).getItems();
      expect(await Promise.all(options.map((o) => o.getTitle()))).toEqual(['System', 'Light', 'Dark']);
      const actions = await (await loader.getHarness(MatActionListHarness)).getItems();
      expect(await Promise.all(actions.map((a) => a.getTitle()))).toEqual(['Sign out']);

      const [, , dark] = options;
      await dark.select();
      expect(themeSpy.setTheme).toHaveBeenCalledWith('dark');
      expect(authSpy.logout).not.toHaveBeenCalled();
    });

    it('when modal, log out is a focusable native button and clicking it clears the token, replaces history with /login and emits closeSidebar', async () => {
      const el = await render('modal');
      const navigate = spyOnNavigate();
      const emitted = vi.fn();
      fixture.componentInstance.closeSidebar.subscribe(emitted);

      // A native <button type="button">: the browser turns Enter/Space into this click (jsdom does not synthesize it).
      const button = el.querySelector<HTMLButtonElement>('button.sidebar-logout')!;
      expect(button.type).toBe('button');
      button.focus();
      expect(document.activeElement).toBe(button);
      button.click();
      expectSignedOut(navigate, emitted);
    });
  });
});

describe('SidebarComponent (token auth, real guards)', () => {
  const TOKEN_KEY = 'app_auth_token';

  beforeEach(() => localStorage.clear());
  afterEach(() => localStorage.clear());

  it('when a signed-in user logs out, the stored token is removed and guestGuard lets /login through', async () => {
    localStorage.setItem(TOKEN_KEY, 'secret-token');
    await TestBed.configureTestingModule({
      imports: [SidebarComponent],
      providers: [
        provideRouter([
          { path: 'login', component: RouteStubComponent, canActivate: [guestGuard] },
          { path: '', component: RouteStubComponent, canActivate: [authGuard] },
        ]),
        provideHttpClient(),
        provideHttpClientTesting(),
        ICON_PROVIDER,
        LucideIconConfig,
        // The real AuthService and guards are under test here; the theme is not.
        { provide: ThemeService, useValue: { setTheme: vi.fn(), theme: signal<ThemeMode>('light') } },
        { provide: MATERIAL_ANIMATIONS, useValue: { animationsDisabled: true } },
      ],
    }).compileComponents();

    const router = TestBed.inject(Router);
    const auth = TestBed.inject(AuthService);
    expect(auth.isAuthenticated()).toBe(true);
    await router.navigateByUrl('/');
    expect(router.url).toBe('/');

    const fixture = TestBed.createComponent(SidebarComponent);
    fixture.componentRef.setInput('mode', 'modal');
    fixture.detectChanges();
    await fixture.whenStable();

    fixture.nativeElement.querySelector('button.sidebar-logout').click();
    await fixture.whenStable();

    expect(auth.isAuthenticated()).toBe(false);
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull();
    expect(router.url).toBe('/login');
  });
});
