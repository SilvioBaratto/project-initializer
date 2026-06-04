import { provideZonelessChangeDetection, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { LucideIconConfig } from 'lucide-angular';

import { ICON_PROVIDER } from './../../icons';
import { ThemeService } from '../../services/theme.service';
import { SidebarComponent } from './sidebar';

describe('SidebarComponent', () => {
  let themeSpy: jasmine.SpyObj<Pick<ThemeService, 'toggleTheme'>> & { theme: ReturnType<typeof signal> };

  beforeEach(async () => {
    themeSpy = Object.assign(jasmine.createSpyObj('ThemeService', ['toggleTheme']), {
      theme: signal('light'),
    });

    await TestBed.configureTestingModule({
      imports: [SidebarComponent],
      providers: [
        provideZonelessChangeDetection(),
        provideRouter([]),
        ICON_PROVIDER,
        { provide: ThemeService, useValue: themeSpy },
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
    const fixture = TestBed.createComponent(SidebarComponent);
    fixture.detectChanges();
    await fixture.whenStable();
    return fixture.nativeElement;
  }

  it('when the sidebar renders, a lucide-icon element is present', async () => {
    const el = await render();
    expect(el.querySelector('lucide-icon')).toBeTruthy();
  });

  it('when the nav renders, the Home, Dashboard and Settings labels are shown', async () => {
    const el = await render();
    const navText = el.querySelector('nav')!.textContent ?? '';
    expect(navText).toContain('Home');
    expect(navText).toContain('Dashboard');
    expect(navText).toContain('Settings');
  });

  it('when the theme-toggle button is clicked, ThemeService.toggleTheme is called', async () => {
    const el = await render();
    const button = el.querySelector<HTMLButtonElement>('button[aria-label="Toggle theme"]');
    expect(button).toBeTruthy();
    button!.click();
    expect(themeSpy.toggleTheme).toHaveBeenCalled();
  });

  it('when the profile row renders, the placeholder name is shown', async () => {
    const el = await render();
    expect(el.querySelector('footer')?.textContent).toContain('User');
  });
});
