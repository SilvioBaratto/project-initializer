import { getDebugNode } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { MatBottomSheet, MatBottomSheetRef } from '@angular/material/bottom-sheet';
import { MATERIAL_ANIMATIONS } from '@angular/material/core';
import { provideRouter } from '@angular/router';
import { vi } from 'vitest';
import { LucideIconConfig } from 'lucide-angular';

import { ICON_PROVIDER } from '../../icons';
import { SidebarComponent } from '../sidebar/sidebar';
import { ShellActionsSheetComponent } from './shell-actions-sheet';

/** Lets the bottom sheet finish opening or closing (animations are simulated in a later task). */
async function settle(): Promise<void> {
  for (let round = 0; round < 2; round++) {
    await new Promise((resolve) => setTimeout(resolve));
  }
}

describe('ShellActionsSheetComponent', () => {
  let ref: MatBottomSheetRef<ShellActionsSheetComponent>;

  beforeEach(async () => {
    // jsdom has no matchMedia. ThemeService (rendered by the rail contents) reads it directly, and
    // the bottom sheet container observes breakpoints through MediaMatcher's legacy listener API.
    Object.defineProperty(window, 'matchMedia', {
      configurable: true,
      writable: true,
      value: (query: string) =>
        ({
          matches: false,
          media: query,
          addListener: () => undefined,
          removeListener: () => undefined,
          addEventListener: () => undefined,
          removeEventListener: () => undefined,
        }) as unknown as MediaQueryList,
    });
    await TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        ICON_PROVIDER,
        LucideIconConfig,
        { provide: MATERIAL_ANIMATIONS, useValue: { animationsDisabled: true } },
      ],
    }).compileComponents();

    ref = TestBed.inject(MatBottomSheet).open(ShellActionsSheetComponent);
    await settle();
  });

  afterEach(() => {
    document.documentElement.classList.remove('dark', 'light', 'theme-transitioning');
    localStorage.clear();
  });

  function sidebarElement(): HTMLElement {
    return document.querySelector<HTMLElement>('.mat-bottom-sheet-container app-shell-actions-sheet app-sidebar')!;
  }

  it('when opened, the sheet renders the rail actions in their modal form and no destinations', () => {
    const sidebar = getDebugNode(sidebarElement())!.componentInstance as SidebarComponent;
    expect(sidebar.mode()).toBe('modal');
    expect(sidebarElement().querySelector('mat-selection-list.sidebar-theme-options')).toBeTruthy();
    expect(sidebarElement().querySelectorAll('a').length).toBe(0);
  });

  it('when the rail contents ask to close (after Sign out), the sheet dismisses', async () => {
    const dismissed = vi.fn();
    ref.afterDismissed().subscribe(dismissed);

    const sidebar = getDebugNode(sidebarElement())!.componentInstance as SidebarComponent;
    sidebar.closeSidebar.emit();
    await settle();

    expect(dismissed).toHaveBeenCalledTimes(1);
    expect(document.querySelector('app-shell-actions-sheet')).toBeNull();
  });

  it('when opened, the sheet content pads by the safe-area insets so the last action clears the home indicator', () => {
    const css = Array.from(document.querySelectorAll('style'))
      .map((style) => style.textContent ?? '')
      .filter((text) => text.includes('safe-area-inset-bottom'))
      .join('\n');
    expect(css).toMatch(
      /\[_nghost-[^\]]+\]\s*\{[^}]*padding:\s*0 env\(safe-area-inset-right\) env\(safe-area-inset-bottom\) env\(safe-area-inset-left\)/,
    );
  });
});
