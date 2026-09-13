import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HarnessLoader } from '@angular/cdk/testing';
import { TestbedHarnessEnvironment } from '@angular/cdk/testing/testbed';
import { MATERIAL_ANIMATIONS } from '@angular/material/core';
import { MatSelectionListHarness } from '@angular/material/list/testing';
import { MatMenuHarness } from '@angular/material/menu/testing';
import { provideRouter } from '@angular/router';
import { LucideIconConfig } from 'lucide-angular';

import { ICON_PROVIDER } from '../../icons';
import { ThemeService } from '../../services/theme';
import { SidebarComponent, SidebarMode } from './sidebar';

/**
 * Cross-component integration: the rail's theme choices, driven by the real ThemeService, apply
 * the chosen mode, put exactly one of `.light` / `.dark` on <html> and show the current mode as
 * the checked choice. The OS preference is mocked to light (jsdom has no window.matchMedia, so it
 * is defined).
 */
describe('Theme menu (integration)', () => {
  let fixture: ComponentFixture<SidebarComponent>;
  let loader: HarnessLoader;
  let theme: ThemeService;

  function schemeClasses(): string[] {
    return ['light', 'dark'].filter((name) => document.documentElement.classList.contains(name));
  }

  function themeMenu(): Promise<MatMenuHarness> {
    return loader.getHarness(MatMenuHarness.with({ selector: '.sidebar-theme-toggle' }));
  }

  async function chooseFromMenu(label: string): Promise<void> {
    await (await themeMenu()).clickItem({ text: label });
    TestBed.tick();
  }

  async function setup(mode: SidebarMode): Promise<void> {
    await TestBed.configureTestingModule({
      imports: [SidebarComponent],
      providers: [
        provideRouter([]),
        ICON_PROVIDER,
        LucideIconConfig,
        { provide: MATERIAL_ANIMATIONS, useValue: { animationsDisabled: true } },
      ],
    }).compileComponents();

    theme = TestBed.inject(ThemeService);
    fixture = TestBed.createComponent(SidebarComponent);
    fixture.componentRef.setInput('mode', mode);
    loader = TestbedHarnessEnvironment.loader(fixture);
    fixture.detectChanges();
    await fixture.whenStable();
  }

  beforeEach(() => {
    localStorage.clear();
    document.documentElement.classList.remove('dark', 'light', 'theme-transitioning');
    Object.defineProperty(window, 'matchMedia', {
      configurable: true,
      writable: true,
      value: (query: string) =>
        ({
          matches: false,
          media: query,
          addEventListener: () => undefined,
          removeEventListener: () => undefined,
          addListener: () => undefined,
          removeListener: () => undefined,
        }) as unknown as MediaQueryList,
    });
  });

  afterEach(() => {
    document.documentElement.classList.remove('dark', 'light', 'theme-transitioning');
    localStorage.clear();
  });

  describe('expanded rail', () => {
    beforeEach(() => setup('expanded'));

    it('when the start theme is system and the OS prefers light, the light scheme is applied', () => {
      TestBed.tick();
      expect(theme.theme()).toBe('system');
      expect(theme.isDark()).toBe(false);
      expect(schemeClasses()).toEqual(['light']);
    });

    it('when Dark is chosen, isDark is true and only the dark class is present', async () => {
      await chooseFromMenu('Dark');
      expect(theme.theme()).toBe('dark');
      expect(theme.isDark()).toBe(true);
      expect(schemeClasses()).toEqual(['dark']);
    });

    it('when Light is chosen, the choice is stored and only the light class is present', async () => {
      await chooseFromMenu('Light');
      expect(theme.theme()).toBe('light');
      expect(localStorage.getItem('app-theme')).toBe('light');
      expect(schemeClasses()).toEqual(['light']);
    });

    it('when System is chosen after Dark, the OS preference applies again', async () => {
      await chooseFromMenu('Dark');
      await chooseFromMenu('System');
      expect(theme.theme()).toBe('system');
      expect(schemeClasses()).toEqual(['light']);
    });

    it('when the menu reopens after a choice, the chosen mode is the checked item', async () => {
      await chooseFromMenu('Dark');
      await (await themeMenu()).open();
      const checked = Array.from(document.querySelectorAll('.sidebar-theme-menu [role="menuitemradio"]')).filter(
        (item) => item.getAttribute('aria-checked') === 'true',
      );
      expect(checked.map((item) => item.textContent?.trim())).toEqual(['Dark']);
    });
  });

  describe('collapsed rail', () => {
    beforeEach(() => setup('collapsed'));

    it("when Dark is chosen from the icon button's menu, the dark scheme is applied", async () => {
      await chooseFromMenu('Dark');
      expect(theme.theme()).toBe('dark');
      expect(schemeClasses()).toEqual(['dark']);
    });
  });

  describe('compact sheet', () => {
    beforeEach(() => setup('modal'));

    it('when Dark is selected in the list, the dark scheme is applied and Dark is the selected option', async () => {
      const list = await loader.getHarness(MatSelectionListHarness);
      const [, , dark] = await list.getItems();
      await dark.select();
      TestBed.tick();
      expect(theme.theme()).toBe('dark');
      expect(schemeClasses()).toEqual(['dark']);
      const options = await list.getItems();
      expect(await Promise.all(options.map((option) => option.isSelected()))).toEqual([false, false, true]);
    });
  });
});
