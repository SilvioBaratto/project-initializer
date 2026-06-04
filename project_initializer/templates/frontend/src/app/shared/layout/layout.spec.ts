import { provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { LucideIconConfig } from 'lucide-angular';

import { ICON_PROVIDER } from '../../icons';
import { LayoutComponent } from './layout';

describe('LayoutComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [LayoutComponent],
      providers: [
        provideZonelessChangeDetection(),
        provideRouter([]),
        ICON_PROVIDER,
        {
          provide: LucideIconConfig,
          useFactory: () => {
            const cfg = new LucideIconConfig();
            cfg.size = 16;
            cfg.strokeWidth = 1.5;
            return cfg;
          },
        },
      ],
    }).compileComponents();
  });

  async function render(): Promise<HTMLElement> {
    const fixture = TestBed.createComponent(LayoutComponent);
    fixture.detectChanges();
    await fixture.whenStable();
    return fixture.nativeElement;
  }

  it('when the shell renders, the sidebar is present', async () => {
    const el = await render();
    expect(el.querySelector('app-sidebar')).toBeTruthy();
  });

  it('when the shell renders, the bottom-tab-bar is present', async () => {
    const el = await render();
    expect(el.querySelector('app-bottom-tab-bar')).toBeTruthy();
  });

  it('when the shell renders, main is the skip-link target with a11y attributes', async () => {
    const el = await render();
    const main = el.querySelector('main');
    expect(main?.id).toBe('main-content');
    expect(main?.getAttribute('tabindex')).toBe('-1');
    expect(main?.getAttribute('aria-label')).toBeTruthy();
  });

  it('when the shell renders, an aria-live route announcer is present', async () => {
    const el = await render();
    expect(el.querySelector('.sr-only[aria-live="polite"]')).toBeTruthy();
  });

  it('when the shell renders, an inert toast outlet is present', async () => {
    const el = await render();
    expect(el.querySelector('#toast-outlet')).toBeTruthy();
  });

  it('when the mobile header renders, the hamburger uses a lucide-icon', async () => {
    const el = await render();
    expect(el.querySelector('header lucide-icon')).toBeTruthy();
  });

  it('when toggleSidebar is called, the open state flips', () => {
    const fixture = TestBed.createComponent(LayoutComponent);
    const component = fixture.componentInstance;
    expect(component.isSidebarOpen()).toBe(false);
    component.toggleSidebar();
    expect(component.isSidebarOpen()).toBe(true);
  });
});
