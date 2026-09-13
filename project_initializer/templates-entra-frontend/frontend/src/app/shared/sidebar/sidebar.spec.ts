import { Component, WritableSignal, signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HarnessLoader } from '@angular/cdk/testing';
import { TestbedHarnessEnvironment } from '@angular/cdk/testing/testbed';
import { MatButtonHarness } from '@angular/material/button/testing';
import { MatActionListHarness, MatNavListHarness, MatSelectionListHarness } from '@angular/material/list/testing';
import { MatMenuHarness } from '@angular/material/menu/testing';
import { MATERIAL_ANIMATIONS } from '@angular/material/core';
import { Router, Routes, provideRouter } from '@angular/router';
import { MsalService } from '@azure/msal-angular';
import type { AccountInfo } from '@azure/msal-browser';
import { vi } from 'vitest';
import { LucideIconConfig } from 'lucide-angular';

import { AuthService } from '../../core/services/auth.service';
import { ICON_PROVIDER } from '../../icons';
import { ThemeMode, ThemeService } from '../../services/theme';
import { NAV_ITEMS } from '../nav-item';
import { RAIL_ACTIONS_SHEET, SidebarComponent, SidebarMode } from './sidebar';

@Component({ selector: 'app-route-stub', template: '' })
class RouteStubComponent {}

const NAV_ROUTES: Routes = NAV_ITEMS.map((item) => ({ path: item.route.slice(1), component: RouteStubComponent }));

/** Radio items of the open theme menu, rendered in the body-level overlay container. */
function themeMenuItems(): HTMLElement[] {
  return Array.from(document.querySelectorAll<HTMLElement>('.sidebar-theme-menu [role="menuitemradio"]'));
}

/**
 * Entra overlay spec: replaces the base sidebar.spec.ts, keeps every base rail assertion
 * (the template and styles are the base layer's) and covers the account area this overlay
 * switches on: the signed-in Microsoft account's name and Sign out through MSAL.
 * AuthService and MsalService are stubbed, so no MSAL client runs.
 */
describe('SidebarComponent (Entra)', () => {
  let themeSpy: { setTheme: ReturnType<typeof vi.fn>; theme: ReturnType<typeof signal<ThemeMode>> };
  let authSpy: { logout: ReturnType<typeof vi.fn>; isAuthenticated: WritableSignal<boolean> };
  let activeAccount: Partial<AccountInfo> | null;
  let fixture: ComponentFixture<SidebarComponent>;
  let loader: HarnessLoader;

  async function render(mode?: SidebarMode, routes: Routes = [], url?: string): Promise<HTMLElement> {
    await TestBed.configureTestingModule({
      imports: [SidebarComponent],
      providers: [
        provideRouter(routes),
        ICON_PROVIDER,
        LucideIconConfig,
        { provide: ThemeService, useValue: themeSpy },
        { provide: AuthService, useValue: authSpy },
        { provide: MsalService, useValue: { instance: { getActiveAccount: () => activeAccount } } },
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
    loader = TestbedHarnessEnvironment.loader(fixture);
    fixture.detectChanges();
    await fixture.whenStable();
    return fixture.nativeElement;
  }

  function themeMenu(): Promise<MatMenuHarness> {
    return loader.getHarness(MatMenuHarness.with({ selector: '.sidebar-theme-toggle' }));
  }

  /** Subscribes to closeSidebar and spies on router navigation for the sign out assertions. */
  function watchLogout(): { emitted: ReturnType<typeof vi.fn>; navigate: ReturnType<typeof vi.fn> } {
    const emitted = vi.fn();
    fixture.componentInstance.closeSidebar.subscribe(emitted);
    const router = TestBed.inject(Router);
    const navigate = vi.fn();
    vi.spyOn(router, 'navigate').mockImplementation((...args) => {
      navigate(...args);
      return Promise.resolve(true);
    });
    vi.spyOn(router, 'navigateByUrl').mockImplementation((...args) => {
      navigate(...args);
      return Promise.resolve(true);
    });
    return { emitted, navigate };
  }

  /** Signs out through AuthService first, then closes the surface, with no in-app navigation. */
  function expectMsalLogout(emitted: ReturnType<typeof vi.fn>, navigate: ReturnType<typeof vi.fn>): void {
    expect(authSpy.logout).toHaveBeenCalledTimes(1);
    expect(emitted).toHaveBeenCalledTimes(1);
    expect(authSpy.logout.mock.invocationCallOrder[0]).toBeLessThan(emitted.mock.invocationCallOrder[0]);
    expect(navigate).not.toHaveBeenCalled();
  }

  beforeEach(() => {
    themeSpy = { setTheme: vi.fn(), theme: signal<ThemeMode>('light') };
    authSpy = { logout: vi.fn(), isAuthenticated: signal(true) };
    activeAccount = { name: 'Ada Lovelace', username: 'ada@contoso.com' };
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
      const el = await render('expanded', NAV_ROUTES, '/settings');

      const items = await (await loader.getHarness(MatNavListHarness)).getItems();
      expect(await Promise.all(items.map((i) => i.isActivated()))).toEqual(
        NAV_ITEMS.map((i) => i.route === '/settings'),
      );
      const current = el.querySelectorAll('a[aria-current="page"]');
      expect(current.length).toBe(1);
      expect(current[0].textContent).toContain('Settings');
    });

    it('when the rail renders, each item carries a decorative lucide-icon', async () => {
      const el = await render();
      const icons = el.querySelectorAll('mat-nav-list lucide-icon');
      expect(icons.length).toBe(NAV_ITEMS.length);
      icons.forEach((icon) => expect(icon.getAttribute('aria-hidden')).toBe('true'));
    });

    it('when a destination is clicked, closeSidebar is emitted and AuthService is not touched', async () => {
      await render('expanded', NAV_ROUTES);
      const emitted = vi.fn();
      fixture.componentInstance.closeSidebar.subscribe(emitted);
      const [home] = await (await loader.getHarness(MatNavListHarness)).getItems();
      await home.click();
      expect(emitted).toHaveBeenCalledTimes(1);
      expect(authSpy.logout).not.toHaveBeenCalled();
    });

    it('when the actions render, Change theme and Sign out are list items under the signed-in account', async () => {
      const el = await render();
      const actions = await (await loader.getHarness(MatActionListHarness)).getItems();
      expect(await Promise.all(actions.map((a) => a.getTitle()))).toEqual(['Change theme', 'Sign out']);
      expect(el.querySelector('.sidebar-account-name')?.textContent?.trim()).toBe('Ada Lovelace');
      expect(el.textContent).not.toContain('User');
      // LogOut's arrow points toward the inline end, so the icon is marked to mirror in RTL.
      const signOutIcon = el.querySelector('button.sidebar-logout lucide-icon');
      expect(signOutIcon?.classList.contains('sidebar-icon-directional')).toBe(true);
    });

    it('when Sign out is chosen, it signs out through MSAL and then closes the surface', async () => {
      await render();
      const { emitted, navigate } = watchLogout();
      const [, logout] = await (await loader.getHarness(MatActionListHarness)).getItems();
      await logout.click();
      expectMsalLogout(emitted, navigate);
    });
  });

  describe('account row', () => {
    it('when the active account has no display name, the row shows its username', async () => {
      activeAccount = { username: 'ada@contoso.com' };
      const el = await render();
      expect(el.querySelector('.sidebar-account-name')?.textContent?.trim()).toBe('ada@contoso.com');
    });

    it('when signed out, no account row shows rather than a placeholder', async () => {
      authSpy.isAuthenticated.set(false);
      const el = await render();
      expect(fixture.componentInstance.accountName()).toBeNull();
      expect(el.querySelector('.sidebar-account')).toBeNull();
    });

    it('when the session starts after the rail renders, the row follows it', async () => {
      authSpy.isAuthenticated.set(false);
      activeAccount = null;
      const el = await render();
      expect(el.querySelector('.sidebar-account')).toBeNull();

      activeAccount = { name: 'Grace Hopper', username: 'grace@contoso.com' };
      authSpy.isAuthenticated.set(true);
      fixture.detectChanges();
      await fixture.whenStable();
      expect(el.querySelector('.sidebar-account-name')?.textContent?.trim()).toBe('Grace Hopper');
    });
  });

  describe('theme menu', () => {
    it('when a mode is chosen from the Change theme menu, ThemeService.setTheme receives it and nobody is signed out', async () => {
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
      const el = await render('collapsed', NAV_ROUTES, '/home');
      const current = el.querySelectorAll('a.rail-item[aria-current="page"]');
      expect(current.length).toBe(1);
      expect(current[0].textContent?.trim()).toBe('Home');
    });

    it('when collapsed, Change theme and Sign out are icon buttons named by their action', async () => {
      await render('collapsed');
      const theme = await loader.getHarness(MatButtonHarness.with({ selector: '.sidebar-theme-toggle' }));
      const logout = await loader.getHarness(MatButtonHarness.with({ selector: '.sidebar-logout' }));
      expect(await theme.getVariant()).toBe('icon');
      expect(await logout.getVariant()).toBe('icon');
      expect(await (await theme.host()).getAttribute('aria-label')).toBe('Change theme');
      expect(await (await theme.host()).getAttribute('aria-haspopup')).toBe('menu');
      expect(await (await logout.host()).getAttribute('aria-label')).toBe('Sign out');

      // The icon hosts are grid boxes (.sidebar-icon), so the 24px svg centres in the 40px state layer
      // instead of sitting on an inline baseline.
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

    it('when collapsed and Sign out is clicked, it signs out through MSAL and then closes the surface', async () => {
      await render('collapsed');
      const { emitted, navigate } = watchLogout();
      await (await loader.getHarness(MatButtonHarness.with({ selector: '.sidebar-logout' }))).click();
      expectMsalLogout(emitted, navigate);
    });
  });

  describe('modal form (compact bottom sheet)', () => {
    it('when modal, no destination is repeated from the navigation bar', async () => {
      const el = await render('modal');
      expect(el.querySelector('nav')).toBeNull();
      expect(el.querySelector('mat-nav-list')).toBeNull();
      expect(el.querySelectorAll('a').length).toBe(0);
    });

    it('when modal, it holds the account name, the theme choices and Sign out', async () => {
      const el = await render('modal');
      expect(el.querySelector('.sidebar-account-name')?.textContent?.trim()).toBe('Ada Lovelace');
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

    it('when modal and the focusable Sign out button is clicked, it signs out through MSAL and then closes the surface', async () => {
      const el = await render('modal');
      const { emitted, navigate } = watchLogout();
      const button = el.querySelector<HTMLButtonElement>('button.sidebar-logout')!;
      // Keyboard path: a native <button> turns Enter/Space into a click, and the handler is bound
      // to (click). jsdom does not synthesize that click from a key event, so the click is dispatched.
      expect(button.tagName).toBe('BUTTON');
      expect(button.type).toBe('button');
      button.focus();
      expect(document.activeElement).toBe(button);
      button.click();
      expectMsalLogout(emitted, navigate);
    });
  });

  describe('compact sheet names', () => {
    it('when the Entra rail names the sheet, the names cover its theme and account contents', () => {
      expect(RAIL_ACTIONS_SHEET).toEqual({
        triggerLabel: 'Open theme and account',
        sheetLabel: 'Theme and account',
        triggerIcon: 'User',
      });
    });
  });
});
