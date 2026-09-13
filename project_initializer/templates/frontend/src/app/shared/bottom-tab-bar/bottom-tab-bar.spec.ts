import { Component } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Router, Routes, provideRouter } from '@angular/router';
import { vi } from 'vitest';
import { LucideIconConfig } from 'lucide-angular';

import { ICON_PROVIDER } from '../../icons';
import { NAV_ITEMS } from '../nav-item';
import { BottomTabBarComponent, NAV_BAR_BLOCK_SIZE_PROPERTY } from './bottom-tab-bar';

@Component({ selector: 'app-route-stub', template: '' })
class RouteStubComponent {}

/** The bar's own stylesheet (component styles land in <head> while the fixture lives). */
function barStyleText(): string {
  return Array.from(document.querySelectorAll('style'))
    .map((style) => style.textContent ?? '')
    .filter((text) => text.includes('.nav-bar-indicator'))
    .join('\n');
}

describe('BottomTabBarComponent', () => {
  async function setup(routes: Routes = [], url?: string): Promise<ComponentFixture<BottomTabBarComponent>> {
    await TestBed.configureTestingModule({
      imports: [BottomTabBarComponent],
      providers: [provideRouter(routes), ICON_PROVIDER, LucideIconConfig],
    }).compileComponents();

    if (url) {
      await TestBed.inject(Router).navigateByUrl(url);
    }
    const fixture = TestBed.createComponent(BottomTabBarComponent);
    fixture.detectChanges();
    await fixture.whenStable();
    return fixture;
  }

  function tabsOf(fixture: ComponentFixture<BottomTabBarComponent>): HTMLAnchorElement[] {
    return Array.from(fixture.nativeElement.querySelectorAll('nav a'));
  }

  it('when the bar renders, one tab per navigation destination is shown, within the M3 3–5', async () => {
    const tabs = tabsOf(await setup());
    expect(tabs.length).toBe(NAV_ITEMS.length);
    expect(tabs.length).toBe(4);
  });

  it('when the bar renders, it pads by the safe-area insets from its own stylesheet, with no utility classes', async () => {
    const fixture = await setup();
    const nav: HTMLElement = fixture.nativeElement.querySelector('nav');
    expect(Array.from(nav.classList)).toEqual(['nav-bar']);
    const rule = /\.nav-bar(?:\[[^\]]+\])*\s*\{([^}]*)\}/.exec(barStyleText());
    expect(rule?.[1]).toMatch(
      /padding:\s*0 env\(safe-area-inset-right\) env\(safe-area-inset-bottom\) env\(safe-area-inset-left\)/,
    );
    // The minimum block size, which is also the toast unit's fallback offset: 64px plus the bottom inset.
    expect(rule?.[1]).toMatch(/min-block-size:\s*calc\(64px \+ env\(safe-area-inset-bottom\)\)/);
  });

  it('when text is enlarged, tab labels hyphenate before breaking mid-word', async () => {
    await setup();
    expect(barStyleText()).toMatch(/\.nav-bar-label(?:\[[^\]]+\])*\s*\{[^}]*hyphens:\s*auto/);
  });

  it('when the bar renders, it is a navigation landmark labelled Primary', async () => {
    const fixture = await setup();
    const nav = fixture.nativeElement.querySelector('nav');
    expect(nav.getAttribute('aria-label')).toBe('Primary');
  });

  it('when each tab renders, its accessible name is its always-visible label', async () => {
    const tabs = tabsOf(await setup());
    tabs.forEach((tab, i) => {
      // Visible text names the link; an aria-label would duplicate it.
      expect(tab.hasAttribute('aria-label')).toBe(false);
      expect(tab.textContent?.trim()).toBe(NAV_ITEMS[i].name);
    });
  });

  it('when each tab renders, a decorative lucide-icon sits in the active indicator', async () => {
    const tabs = tabsOf(await setup());
    for (const tab of tabs) {
      const icon = tab.querySelector('.nav-bar-indicator lucide-icon');
      expect(icon).toBeTruthy();
      expect(icon?.getAttribute('aria-hidden')).toBe('true');
    }
  });

  it('when the tabs render, the Home, Dashboard, Chat and Settings labels are shown', async () => {
    const text = tabsOf(await setup())
      .map((t) => t.textContent)
      .join(' ');
    expect(text).toContain('Home');
    expect(text).toContain('Dashboard');
    expect(text).toContain('Chat');
    expect(text).toContain('Settings');
  });

  it('when each tab renders, it links to its destination route', async () => {
    const tabs = tabsOf(await setup());
    expect(tabs.map((t) => t.getAttribute('href'))).toEqual(NAV_ITEMS.map((i) => i.route));
  });

  it('when a tab is active, only that anchor exposes aria-current="page"', async () => {
    const routes = NAV_ITEMS.map((item) => ({ path: item.route.slice(1), component: RouteStubComponent }));
    const fixture = await setup(routes, '/dashboard');

    const current = fixture.nativeElement.querySelectorAll('nav a[aria-current="page"]');
    expect(current.length).toBe(1);
    expect(current[0].textContent.trim()).toBe('Dashboard');
    expect(current[0].classList.contains('nav-bar-item-active')).toBe(true);
  });

  it('when no destination matches the URL, no tab is marked current', async () => {
    const fixture = await setup();
    expect(fixture.nativeElement.querySelector('nav a[aria-current]')).toBeNull();
  });

  describe('block size published for the toast unit', () => {
    let resize: ResizeObserverCallback | undefined;
    const observe = vi.fn();
    const disconnect = vi.fn();

    beforeEach(() => {
      resize = undefined;
      observe.mockClear();
      disconnect.mockClear();
      // jsdom has no ResizeObserver: capture the bar's callback to drive it by hand.
      vi.stubGlobal(
        'ResizeObserver',
        class {
          constructor(callback: ResizeObserverCallback) {
            resize = callback;
          }
          observe = observe;
          unobserve = vi.fn();
          disconnect = disconnect;
        },
      );
    });

    afterEach(() => {
      vi.unstubAllGlobals();
      document.documentElement.style.removeProperty(NAV_BAR_BLOCK_SIZE_PROPERTY);
    });

    it('when the bar is measured, <html> carries its rendered block size, which follows a resize', async () => {
      const fixture = await setup();
      TestBed.tick();
      expect(NAV_BAR_BLOCK_SIZE_PROPERTY).toBe('--app-nav-bar-block-size');
      expect(observe).toHaveBeenCalledWith(fixture.nativeElement);

      // Enlarged text wraps a label and the bar grows past its 64px minimum.
      resize!([{ borderBoxSize: [{ blockSize: 80, inlineSize: 390 }] } as unknown as ResizeObserverEntry], {} as ResizeObserver);
      expect(document.documentElement.style.getPropertyValue(NAV_BAR_BLOCK_SIZE_PROPERTY)).toBe('80px');

      resize!([{ borderBoxSize: [{ blockSize: 64, inlineSize: 390 }] } as unknown as ResizeObserverEntry], {} as ResizeObserver);
      expect(document.documentElement.style.getPropertyValue(NAV_BAR_BLOCK_SIZE_PROPERTY)).toBe('64px');
    });

    it('when the bar is destroyed (the window reaches 600px), it stops observing and removes the property', async () => {
      const fixture = await setup();
      TestBed.tick();
      resize!([{ borderBoxSize: [{ blockSize: 72, inlineSize: 390 }] } as unknown as ResizeObserverEntry], {} as ResizeObserver);
      expect(document.documentElement.style.getPropertyValue(NAV_BAR_BLOCK_SIZE_PROPERTY)).toBe('72px');

      fixture.destroy();
      expect(disconnect).toHaveBeenCalledTimes(1);
      expect(document.documentElement.style.getPropertyValue(NAV_BAR_BLOCK_SIZE_PROPERTY)).toBe('');
    });
  });
});
