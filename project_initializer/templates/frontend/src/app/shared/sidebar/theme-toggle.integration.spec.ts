import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { LucideIconConfig } from 'lucide-angular';

import { ICON_PROVIDER } from '../../icons';
import { ThemeService } from '../../services/theme.service';
import { SidebarComponent } from './sidebar';

/**
 * Cross-component integration: the sidebar's footer theme toggle, driven by the
 * real ThemeService, flips the `dark` class on documentElement and `isDark()`
 * across the system → light → dark cycle. OS preference is mocked to light.
 */
describe('Theme toggle (integration)', () => {
  let fixture: ComponentFixture<SidebarComponent>;
  let theme: ThemeService;
  let toggleButton: HTMLButtonElement;

  function clickToggle(): void {
    toggleButton.click();
    TestBed.tick();
  }

  beforeEach(async () => {
    localStorage.clear();
    document.documentElement.classList.remove('dark', 'theme-transitioning');
    spyOn(window, 'matchMedia').and.returnValue({
      matches: false,
      addEventListener: () => {},
      removeEventListener: () => {},
    } as unknown as MediaQueryList);

    await TestBed.configureTestingModule({
      imports: [SidebarComponent],
      providers: [
        provideZonelessChangeDetection(),
        provideRouter([]),
        ICON_PROVIDER,
        {
          provide: LucideIconConfig,
          useFactory: () => {
            const cfg = new LucideIconConfig();
            cfg.size = 16;
            return cfg;
          },
        },
      ],
    }).compileComponents();

    theme = TestBed.inject(ThemeService);
    fixture = TestBed.createComponent(SidebarComponent);
    fixture.detectChanges();
    await fixture.whenStable();
    toggleButton = fixture.nativeElement.querySelector('button[aria-label="Toggle theme"]');
  });

  afterEach(() => {
    document.documentElement.classList.remove('dark', 'theme-transitioning');
    localStorage.clear();
  });

  it('when the start theme is system and the OS prefers light, the dark class is absent', () => {
    TestBed.tick();
    expect(theme.theme()).toBe('system');
    expect(theme.isDark()).toBe(false);
    expect(document.documentElement.classList.contains('dark')).toBe(false);
  });

  it('when toggled from system, light is applied without the dark class', () => {
    clickToggle();
    expect(theme.theme()).toBe('light');
    expect(document.documentElement.classList.contains('dark')).toBe(false);
  });

  it('when toggled to dark, isDark is true and the dark class is added', () => {
    clickToggle(); // system -> light
    clickToggle(); // light -> dark
    expect(theme.theme()).toBe('dark');
    expect(theme.isDark()).toBe(true);
    expect(document.documentElement.classList.contains('dark')).toBe(true);
  });

  it('when toggled past dark, the cycle returns to system and removes the dark class', () => {
    clickToggle(); // system -> light
    clickToggle(); // light -> dark
    clickToggle(); // dark -> system
    expect(theme.theme()).toBe('system');
    expect(document.documentElement.classList.contains('dark')).toBe(false);
  });
});
