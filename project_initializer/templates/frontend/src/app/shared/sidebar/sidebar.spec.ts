import { Component, signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HarnessLoader } from '@angular/cdk/testing';
import { TestbedHarnessEnvironment } from '@angular/cdk/testing/testbed';
import { MatButtonHarness } from '@angular/material/button/testing';
import { MatActionListHarness, MatNavListHarness, MatSelectionListHarness } from '@angular/material/list/testing';
import { MatMenuHarness } from '@angular/material/menu/testing';
import { MATERIAL_ANIMATIONS } from '@angular/material/core';
import { Router, Routes, provideRouter } from '@angular/router';
import { vi } from 'vitest';
import { LucideIconConfig } from 'lucide-angular';

import { ICON_PROVIDER } from '../../icons';
import { ThemeMode, ThemeService } from '../../services/theme';
import { NAV_ITEMS } from '../nav-item';
import { RAIL_ACTIONS_SHEET, SidebarComponent, SidebarMode } from './sidebar';

@Component({ selector: 'app-route-stub', template: '' })
class RouteStubComponent {}

const NAV_ROUTES: Routes = NAV_ITEMS.map((item) => ({ path: item.route.slice(1), component: RouteStubComponent }));

/** The sidebar's own stylesheet (component styles land in <head> while the fixture lives). */
function sidebarStyleText(): string {
  return Array.from(document.querySelectorAll('style'))
    .map((style) => style.textContent ?? '')
    .filter((text) => text.includes('.sidebar-footer'))
    .join('\n');
}

/** Radio items of the open theme menu, rendered in the body-level overlay container. */
function themeMenuItems(): HTMLElement[] {
  return Array.from(document.querySelectorAll<HTMLElement>('.sidebar-theme-menu [role="menuitemradio"]'));
}

describe('SidebarComponent', () => {
  let themeSpy: { setTheme: ReturnType<typeof vi.fn>; theme: ReturnType<typeof signal<ThemeMode>> };
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

  beforeEach(() => {
    themeSpy = { setTheme: vi.fn(), theme: signal<ThemeMode>('light') };
  });

  describe('expanded rail (default mode)', () => {
    it('when the rail renders, destinations sit in a mat-nav-list labelled Primary', async () => {
      const el = await render();
      const list = el.querySelector('mat-nav-list');
      expect(list?.getAttribute('role')).toBe('navigation');
      // The same name as the compact navigation bar: one primary navigation, whatever its form.
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

    it('when a destination is clicked, closeSidebar is emitted', async () => {
      await render('expanded', NAV_ROUTES);
      const emitted = vi.fn();
      fixture.componentInstance.closeSidebar.subscribe(emitted);
      const [home] = await (await loader.getHarness(MatNavListHarness)).getItems();
      await home.click();
      expect(emitted).toHaveBeenCalledTimes(1);
    });

    it('when the actions render, Change theme is the only one: with no session there is no account row and no Sign out', async () => {
      const el = await render();
      const actions = await (await loader.getHarness(MatActionListHarness)).getItems();
      expect(await Promise.all(actions.map((a) => a.getTitle()))).toEqual(['Change theme']);
      expect(fixture.componentInstance.accountName()).toBeNull();
      expect(fixture.componentInstance.canSignOut()).toBe(false);
      expect(el.querySelector('.sidebar-account')).toBeNull();
      expect(el.querySelector('.sidebar-logout')).toBeNull();
      expect(el.textContent).not.toContain('User');
      expect(el.textContent).not.toContain('Sign out');
    });
  });

  describe('theme menu', () => {
    it('when the expanded rail renders, Change theme is a one-line item that opens a menu, not a destination', async () => {
      const el = await render();
      const button = el.querySelector<HTMLButtonElement>('button.sidebar-theme-toggle')!;
      expect(button.closest('nav, mat-nav-list')).toBeNull();
      expect(button.getAttribute('aria-haspopup')).toBe('menu');
      // Named by its visible text. No supporting line: the menu shows the current mode.
      expect(button.hasAttribute('aria-label')).toBe(false);
      expect(button.querySelector('.mat-mdc-list-item-line')).toBeNull();
      expect(button.classList.contains('mdc-list-item--with-two-lines')).toBe(false);
    });

    it('when the menu opens, it offers System, Light and Dark as radio items with the current mode checked', async () => {
      await render();
      const menu = await themeMenu();
      await menu.open();
      const items = await menu.getItems();
      expect(await Promise.all(items.map((i) => i.getText()))).toEqual(['System', 'Light', 'Dark']);
      expect(themeMenuItems().map((i) => i.getAttribute('aria-checked'))).toEqual(['false', 'true', 'false']);
    });

    it('when a mode is chosen from the menu, ThemeService.setTheme receives it', async () => {
      await render();
      await (await themeMenu()).clickItem({ text: 'Dark' });
      expect(themeSpy.setTheme).toHaveBeenCalledTimes(1);
      expect(themeSpy.setTheme).toHaveBeenCalledWith('dark');
    });

    it('when the theme changes, the checked item follows it', async () => {
      await render();
      themeSpy.theme.set('dark');
      fixture.detectChanges();
      await fixture.whenStable();
      await (await themeMenu()).open();
      expect(themeMenuItems().map((i) => i.getAttribute('aria-checked'))).toEqual(['false', 'false', 'true']);
    });

    it('when a list item is clicked, it shows no focus state layer: that overlay is for keyboard focus only', async () => {
      await render();
      expect(sidebarStyleText()).toMatch(
        /\.mat-mdc-list-item(?:\[[^\]]+\])*:not\(:focus-visible\)[^{}]*\{[^}]*--mat-list-list-item-focus-state-layer-opacity:\s*0/,
      );
    });
  });

  describe('enlarged text', () => {
    it('when text is enlarged, the wider rails wrap their list text and grow instead of truncating it', async () => {
      await render();
      const css = sidebarStyleText();
      expect(css).toMatch(/--mat-list-list-item-one-line-container-height:\s*auto/);
      expect(css).toMatch(/\.mat-mdc-list-item(?:\[[^\]]+\])*\s*\{[^}]*min-block-size:\s*56px/);
      expect(css).toMatch(/\.mat-mdc-list-item-title[^{}]*\{[^}]*white-space:\s*normal/);
    });

    it('when text is enlarged, collapsed rail labels never break inside a word (the shell widens the rail instead)', async () => {
      await render('collapsed');
      const css = sidebarStyleText();
      expect(css).toMatch(/\.rail-label(?:\[[^\]]+\])*\s*\{[^}]*overflow-wrap:\s*normal/);
      expect(css).toMatch(/\.rail-label(?:\[[^\]]+\])*\s*\{[^}]*hyphens:\s*manual/);
      expect(css).not.toMatch(/\.rail-label(?:\[[^\]]+\])*\s*\{[^}]*(?:overflow-wrap:\s*anywhere|word-break:\s*break-all|hyphens:\s*auto)/);
    });
  });

  describe('current destination cue', () => {
    it('when a destination is current in the expanded rail, its label turns bold, not only its fill color', async () => {
      await render('expanded', NAV_ROUTES, '/settings');
      expect(sidebarStyleText()).toMatch(
        /\.mdc-list-item--activated[^{}]*\{[^}]*--mat-list-list-item-label-text-weight:\s*var\(--mat-sys-label-large-weight-prominent\)/,
      );
      // The rule's selector matches the rendered current item (the harness waits for routerLinkActive).
      await (await loader.getHarness(MatNavListHarness)).getItems();
      const current = fixture.nativeElement.querySelector('a[aria-current="page"]');
      expect(current?.classList.contains('mdc-list-item--activated')).toBe(true);
    });
  });

  describe('right-to-left', () => {
    it('when the layout is RTL, directional rail icons (Sign out) mirror', async () => {
      await render('collapsed');
      expect(sidebarStyleText()).toMatch(
        /\[dir=['"]?rtl['"]?\][^{}]*\.sidebar-icon-directional[^{}]*\{[^}]*transform:\s*scaleX\(-1\)/,
      );
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

    it('when collapsed, Change theme is the only action, an icon button named by its action that opens the theme menu', async () => {
      const el = await render('collapsed');
      const theme = await loader.getHarness(MatButtonHarness.with({ selector: '.sidebar-theme-toggle' }));
      expect(await theme.getVariant()).toBe('icon');
      const host = await theme.host();
      expect(await host.getAttribute('aria-label')).toBe('Change theme');
      expect(await host.getAttribute('aria-haspopup')).toBe('menu');
      expect(el.querySelector('.sidebar-logout')).toBeNull();

      // The icon host is a grid box (.sidebar-icon), so the 24px svg centres in the 40px state layer
      // instead of sitting on an inline baseline.
      const icon = el.querySelector('button.sidebar-theme-toggle lucide-icon');
      expect(icon?.classList.contains('sidebar-icon')).toBe(true);
      expect(icon?.getAttribute('aria-hidden')).toBe('true');

      // The icon stands for the action, so it stays the same whatever the current mode.
      const markup = icon?.innerHTML;
      themeSpy.theme.set('dark');
      fixture.detectChanges();
      await fixture.whenStable();
      expect(el.querySelector('button.sidebar-theme-toggle lucide-icon')?.innerHTML).toBe(markup);

      await (await themeMenu()).clickItem({ text: 'System' });
      expect(themeSpy.setTheme).toHaveBeenCalledWith('system');
    });
  });

  describe('modal form (compact bottom sheet)', () => {
    it('when modal, no destination is repeated from the navigation bar', async () => {
      const el = await render('modal');
      expect(el.querySelector('nav')).toBeNull();
      expect(el.querySelector('mat-nav-list')).toBeNull();
      expect(el.querySelectorAll('a').length).toBe(0);
    });

    it('when modal, it holds only the theme choices, a single-selection list under a Theme heading: no menu, account row or Sign out', async () => {
      const el = await render('modal');
      expect(el.querySelector('.sidebar-account')).toBeNull();
      expect(el.querySelector('mat-action-list')).toBeNull();
      expect(el.querySelector('.sidebar-theme-toggle')).toBeNull();

      const options = await (await loader.getHarness(MatSelectionListHarness)).getItems();
      expect(await Promise.all(options.map((o) => o.getTitle()))).toEqual(['System', 'Light', 'Dark']);
      expect(await Promise.all(options.map((o) => o.isSelected()))).toEqual([false, true, false]);
      const list = el.querySelector('mat-selection-list')!;
      expect(list.getAttribute('aria-multiselectable')).toBe('false');
      expect(el.querySelector(`#${list.getAttribute('aria-labelledby')}`)?.textContent?.trim()).toBe('Theme');
    });

    it('when a mode is selected in the sheet, ThemeService.setTheme receives it', async () => {
      await render('modal');
      const [, , dark] = await (await loader.getHarness(MatSelectionListHarness)).getItems();
      await dark.select();
      expect(themeSpy.setTheme).toHaveBeenCalledWith('dark');
    });
  });

  describe('compact sheet names', () => {
    it('when the base scaffold names the sheet, the names describe its theme-only contents', () => {
      expect(RAIL_ACTIONS_SHEET).toEqual({
        triggerLabel: 'Open theme settings',
        sheetLabel: 'Theme settings',
        triggerIcon: 'Settings2',
      });
    });
  });
});
