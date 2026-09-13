import { Component, signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HarnessLoader } from '@angular/cdk/testing';
import { TestbedHarnessEnvironment } from '@angular/cdk/testing/testbed';
import { MatButtonHarness } from '@angular/material/button/testing';
import { MatActionListHarness, MatNavListHarness, MatSelectionListHarness } from '@angular/material/list/testing';
import { MatMenuHarness } from '@angular/material/menu/testing';
import { MatProgressSpinnerHarness } from '@angular/material/progress-spinner/testing';
import { MATERIAL_ANIMATIONS } from '@angular/material/core';
import { Router, Routes, provideRouter } from '@angular/router';
import type { User } from '@supabase/supabase-js';
import { vi } from 'vitest';
import { LucideIconConfig } from 'lucide-angular';

import { appConfig } from '../../app.config';
import { routes as appRoutes } from '../../app.routes';
import { ICON_PROVIDER } from '../../icons';
import { AuthService } from '../../services/auth';
import { ThemeMode, ThemeService } from '../../services/theme';
import { NAV_ITEMS } from '../nav-item';
import { SidebarComponent, SidebarMode } from './sidebar';

/**
 * Supabase overlay: replaces the base sidebar.spec.ts. Same rail contract as the base
 * (destinations, theme menu, modes), plus the account area this overlay changes:
 * the signed-in email and Sign out through AuthService, then /login. The last block
 * checks the scaffold wiring the rail depends on (icon providers and routes).
 */
@Component({ selector: 'app-route-stub', template: '' })
class RouteStubComponent {}

const LOGIN_ROUTE = { path: 'login', component: RouteStubComponent };
const NAV_ROUTES: Routes = NAV_ITEMS.map((item) => ({ path: item.route.slice(1), component: RouteStubComponent }));

function deferred(): { promise: Promise<void>; resolve: () => void; reject: (reason: unknown) => void } {
  let resolve!: () => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<void>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

/** Radio items of the open theme menu, rendered in the body-level overlay container. */
function themeMenuItems(): HTMLElement[] {
  return Array.from(document.querySelectorAll<HTMLElement>('.sidebar-theme-menu [role="menuitemradio"]'));
}

describe('SidebarComponent (supabase)', () => {
  let themeSpy: { setTheme: ReturnType<typeof vi.fn>; theme: ReturnType<typeof signal<ThemeMode>> };
  let authSpy: { logout: ReturnType<typeof vi.fn>; currentUser: ReturnType<typeof signal<Partial<User> | null>> };
  let fixture: ComponentFixture<SidebarComponent>;
  let loader: HarnessLoader;

  async function render(mode?: SidebarMode, routes: Routes = [], url?: string): Promise<HTMLElement> {
    await TestBed.configureTestingModule({
      imports: [SidebarComponent],
      providers: [
        provideRouter([...routes, LOGIN_ROUTE]),
        ICON_PROVIDER,
        LucideIconConfig,
        { provide: ThemeService, useValue: themeSpy },
        { provide: AuthService, useValue: authSpy },
        { provide: MATERIAL_ANIMATIONS, useValue: { animationsDisabled: true } },
      ],
    }).compileComponents();

    return create(mode, url);
  }

  async function create(mode?: SidebarMode, url?: string): Promise<HTMLElement> {
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

  beforeEach(() => {
    themeSpy = { setTheme: vi.fn(), theme: signal<ThemeMode>('light') };
    authSpy = { logout: vi.fn().mockResolvedValue(undefined), currentUser: signal<Partial<User> | null>(null) };
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

    it('when the rail renders, each item carries a decorative lucide-icon and no inline svg markup', async () => {
      const el = await render();
      const icons = el.querySelectorAll('mat-nav-list lucide-icon');
      expect(icons.length).toBe(NAV_ITEMS.length);
      icons.forEach((icon) => expect(icon.getAttribute('aria-hidden')).toBe('true'));
      // Every svg comes from a lucide-icon host; the template ships no hand-written svg.
      el.querySelectorAll('svg').forEach((svg) => expect(svg.closest('lucide-icon')).not.toBeNull());
    });

    it('when a destination is clicked, closeSidebar is emitted', async () => {
      await render('expanded', NAV_ROUTES);
      const emitted = vi.fn();
      fixture.componentInstance.closeSidebar.subscribe(emitted);
      const [home] = await (await loader.getHarness(MatNavListHarness)).getItems();
      await home.click();
      expect(emitted).toHaveBeenCalledTimes(1);
    });

    it('when the actions render, Change theme and sign out are list items with the account name above', async () => {
      authSpy.currentUser.set({ email: 'ada@example.com' });
      const el = await render();
      const actions = await (await loader.getHarness(MatActionListHarness)).getItems();
      expect(await Promise.all(actions.map((a) => a.getTitle()))).toEqual(['Change theme', 'Sign out']);
      expect(el.querySelector('.sidebar-account')?.textContent?.trim()).toBe('ada@example.com');
      // LogOut's arrow points toward the inline end, so the icon is marked to mirror in RTL.
      const signOutIcon = el.querySelector('button.sidebar-logout lucide-icon');
      expect(signOutIcon?.classList.contains('sidebar-icon-directional')).toBe(true);
    });
  });

  describe('account', () => {
    it('when a user is signed in, the account row shows their email', async () => {
      authSpy.currentUser.set({ email: 'ada@example.com' });
      const el = await render();
      expect(el.querySelector('.sidebar-account-name')?.textContent?.trim()).toBe('ada@example.com');
    });

    it('when the session changes, the account row follows it and is omitted, not a placeholder, without a user', async () => {
      const el = await render('modal');
      expect(fixture.componentInstance.accountName()).toBeNull();
      expect(el.querySelector('.sidebar-account')).toBeNull();

      authSpy.currentUser.set({ email: 'grace@example.com' });
      fixture.detectChanges();
      await fixture.whenStable();
      expect(el.querySelector('.sidebar-account-name')?.textContent?.trim()).toBe('grace@example.com');

      authSpy.currentUser.set(null);
      fixture.detectChanges();
      await fixture.whenStable();
      expect(el.querySelector('.sidebar-account')).toBeNull();
      expect(el.textContent).not.toContain('User');
    });

    it('when sign out is clicked, it signs out first, then replaces the entry with /login and closes the rail', async () => {
      const signOut = deferred();
      authSpy.logout.mockReturnValue(signOut.promise);
      await render('expanded', NAV_ROUTES, '/home');
      const router = TestBed.inject(Router);
      const navigate = vi.spyOn(router, 'navigate');
      const emitted = vi.fn();
      fixture.componentInstance.closeSidebar.subscribe(emitted);

      const [, signOutItem] = await (await loader.getHarness(MatActionListHarness)).getItems();
      await signOutItem.click();

      // Still signing out: guestGuard would bounce a navigation to /login back to '/'.
      expect(authSpy.logout).toHaveBeenCalledTimes(1);
      expect(navigate).not.toHaveBeenCalled();
      expect(emitted).not.toHaveBeenCalled();

      signOut.resolve();
      // onLogout resumes in a microtask; once it has navigated, whenStable covers the navigation.
      await vi.waitFor(() => expect(navigate).toHaveBeenCalled());
      await fixture.whenStable();

      expect(navigate).toHaveBeenCalledWith(['/login'], { replaceUrl: true });
      expect(emitted).toHaveBeenCalledTimes(1);
      expect(router.url).toBe('/login');
    });

    it('when signing out fails, the user still reaches /login, the rail closes and the error propagates', async () => {
      authSpy.logout.mockRejectedValue(new Error('network down'));
      await render('modal');
      const emitted = vi.fn();
      fixture.componentInstance.closeSidebar.subscribe(emitted);

      await expect(fixture.componentInstance.onLogout()).rejects.toThrow('network down');
      await fixture.whenStable();

      expect(emitted).toHaveBeenCalledTimes(1);
      expect(TestBed.inject(Router).url).toBe('/login');
      expect(fixture.componentInstance.signingOut()).toBe(false);
    });
  });

  describe('sign out in progress', () => {
    it('when sign out is activated twice while signing out, Supabase and navigation run once', async () => {
      const signOut = deferred();
      authSpy.logout.mockReturnValue(signOut.promise);
      const el = await render('modal');
      const navigate = vi.spyOn(TestBed.inject(Router), 'navigate');
      const emitted = vi.fn();
      fixture.componentInstance.closeSidebar.subscribe(emitted);
      const button = el.querySelector<HTMLButtonElement>('button.sidebar-logout')!;

      button.click();
      button.click();
      fixture.detectChanges();
      expect(authSpy.logout).toHaveBeenCalledTimes(1);

      signOut.resolve();
      await vi.waitFor(() => expect(navigate).toHaveBeenCalled());
      await fixture.whenStable();

      expect(authSpy.logout).toHaveBeenCalledTimes(1);
      expect(navigate).toHaveBeenCalledTimes(1);
      expect(emitted).toHaveBeenCalledTimes(1);
    });

    it('when signing out in the wider rails, the item is busy, shows progress and stays focusable', async () => {
      const signOut = deferred();
      authSpy.logout.mockReturnValue(signOut.promise);
      const el = await render('expanded', NAV_ROUTES, '/home');
      const button = el.querySelector<HTMLButtonElement>('button.sidebar-logout')!;
      expect(button.hasAttribute('aria-busy')).toBe(false);
      expect(await loader.getAllHarnesses(MatProgressSpinnerHarness)).toHaveLength(0);

      button.focus();
      button.click();
      fixture.detectChanges();
      await fixture.whenStable();

      expect(button.getAttribute('aria-busy')).toBe('true');
      expect(button.disabled).toBe(false);
      expect(document.activeElement).toBe(button);
      // The progress indicator replaces the LogOut icon; the label does not change.
      const spinner = await loader.getHarness(MatProgressSpinnerHarness.with({ selector: '.sidebar-logout .sidebar-progress' }));
      expect(await spinner.getMode()).toBe('indeterminate');
      expect(el.querySelector('button.sidebar-logout lucide-icon')).toBeNull();
      expect(el.querySelector('button.sidebar-logout mat-progress-spinner')?.getAttribute('aria-hidden')).toBe('true');
      const [, signOutItem] = await (await loader.getHarness(MatActionListHarness)).getItems();
      expect(await signOutItem.getTitle()).toBe('Sign out');

      signOut.resolve();
      await vi.waitFor(() => expect(TestBed.inject(Router).url).toBe('/login'));
      await vi.waitFor(() => expect(fixture.componentInstance.signingOut()).toBe(false));
      fixture.detectChanges();
      await fixture.whenStable();

      expect(button.hasAttribute('aria-busy')).toBe(false);
      expect(el.querySelector('button.sidebar-logout lucide-icon')).not.toBeNull();
    });

    it('when signing out in the collapsed rail, the icon button is busy and shows progress', async () => {
      const signOut = deferred();
      authSpy.logout.mockReturnValue(signOut.promise);
      const el = await render('collapsed');
      const signOutButton = await loader.getHarness(MatButtonHarness.with({ selector: '.sidebar-logout' }));

      await signOutButton.click();

      const host = await signOutButton.host();
      expect(await host.getAttribute('aria-busy')).toBe('true');
      expect(await signOutButton.isDisabled()).toBe(false);
      expect(await host.getAttribute('aria-label')).toBe('Sign out');
      expect(el.querySelector('button.sidebar-logout mat-progress-spinner')).not.toBeNull();
      expect(el.querySelector('button.sidebar-logout lucide-icon')).toBeNull();

      signOut.resolve();
      await vi.waitFor(() => expect(fixture.componentInstance.signingOut()).toBe(false));
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
      expect(el.querySelector('.sidebar-account')).toBeNull();
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

    it('when collapsed, Change theme and sign out are icon buttons named by their action', async () => {
      await render('collapsed');
      const theme = await loader.getHarness(MatButtonHarness.with({ selector: '.sidebar-theme-toggle' }));
      const signOutButton = await loader.getHarness(MatButtonHarness.with({ selector: '.sidebar-logout' }));
      expect(await theme.getVariant()).toBe('icon');
      expect(await signOutButton.getVariant()).toBe('icon');
      expect(await (await theme.host()).getAttribute('aria-label')).toBe('Change theme');
      expect(await (await theme.host()).getAttribute('aria-haspopup')).toBe('menu');
      expect(await (await signOutButton.host()).getAttribute('aria-label')).toBe('Sign out');

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

    it('when collapsed and sign out is clicked, it signs out, goes to /login and emits closeSidebar', async () => {
      await render('collapsed');
      const emitted = vi.fn();
      fixture.componentInstance.closeSidebar.subscribe(emitted);
      await (await loader.getHarness(MatButtonHarness.with({ selector: '.sidebar-logout' }))).click();
      await fixture.whenStable();

      expect(authSpy.logout).toHaveBeenCalledTimes(1);
      expect(emitted).toHaveBeenCalledTimes(1);
      expect(TestBed.inject(Router).url).toBe('/login');
    });
  });

  describe('modal rail (compact)', () => {
    it('when modal, no destination is repeated from the navigation bar', async () => {
      const el = await render('modal');
      expect(el.querySelector('nav')).toBeNull();
      expect(el.querySelector('mat-nav-list')).toBeNull();
      expect(el.querySelectorAll('a').length).toBe(0);
    });

    it('when modal, it holds the account name, the theme choices and sign out', async () => {
      authSpy.currentUser.set({ email: 'ada@example.com' });
      const el = await render('modal');
      expect(el.querySelector('.sidebar-account')?.textContent?.trim()).toBe('ada@example.com');
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

    it('when modal and sign out is activated from the keyboard, it signs out and emits closeSidebar', async () => {
      const el = await render('modal');
      const emitted = vi.fn();
      fixture.componentInstance.closeSidebar.subscribe(emitted);
      const button = el.querySelector<HTMLButtonElement>('button.sidebar-logout')!;
      // A native <button>: Enter and Space activate it through a click event.
      expect(button.tagName).toBe('BUTTON');
      expect(button.getAttribute('type')).toBe('button');
      button.focus();
      expect(document.activeElement).toBe(button);
      button.click();
      await fixture.whenStable();

      expect(authSpy.logout).toHaveBeenCalledTimes(1);
      expect(emitted).toHaveBeenCalledTimes(1);
      expect(TestBed.inject(Router).url).toBe('/login');
    });
  });

  describe('scaffold wiring (supabase app.config.ts and app.routes.ts)', () => {
    it('with the providers from the supabase app.config, every rail icon renders', async () => {
      // No hand-picked ICON_PROVIDER / LucideIconConfig here: lucide-angular throws
      // 'The "Home" icon has not been provided…' when app.config forgets the providers.
      await TestBed.configureTestingModule({
        imports: [SidebarComponent],
        providers: [
          ...appConfig.providers,
          { provide: ThemeService, useValue: themeSpy },
          { provide: AuthService, useValue: authSpy },
          { provide: MATERIAL_ANIMATIONS, useValue: { animationsDisabled: true } },
        ],
      }).compileComponents();

      for (const mode of ['expanded', 'collapsed'] as const) {
        const el = await create(mode);
        const icons = Array.from(el.querySelectorAll('lucide-icon'));
        expect(icons.length).toBeGreaterThan(0);
        expect(icons.filter((icon) => !icon.querySelector('svg')).length).toBe(0);
        fixture.destroy();
      }
    });

    it('every rail destination is a page under the signed-in shell route', () => {
      // The rail and the navigation bar both render NAV_ITEMS, and the specs above stub their
      // routes. Here the real routes must hold each destination, or '**' redirects it away
      // and no item can ever be current.
      const shell = appRoutes.find((route) => route.path === '' && route.children);
      const pages = (shell?.children ?? [])
        .filter((child) => !child.redirectTo && child.path)
        .map((child) => `/${child.path}`);
      for (const item of NAV_ITEMS) {
        expect(pages, `${item.name} (${item.route})`).toContain(item.route);
      }
    });
  });
});
