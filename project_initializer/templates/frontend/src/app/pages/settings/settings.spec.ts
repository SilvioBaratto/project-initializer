import { provideZonelessChangeDetection, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { LucideIconConfig } from 'lucide-angular';

import { ICON_PROVIDER } from '../../icons';
import { ThemeService } from '../../services/theme.service';
import { SettingsComponent } from './settings';

describe('SettingsComponent', () => {
  let themeSpy: jasmine.SpyObj<Pick<ThemeService, 'setTheme'>> & { theme: ReturnType<typeof signal> };

  beforeEach(async () => {
    themeSpy = Object.assign(jasmine.createSpyObj('ThemeService', ['setTheme']), {
      theme: signal('system'),
    });

    await TestBed.configureTestingModule({
      imports: [SettingsComponent],
      providers: [
        provideZonelessChangeDetection(),
        ICON_PROVIDER,
        { provide: ThemeService, useValue: themeSpy },
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
  });

  async function render(): Promise<HTMLElement> {
    const fixture = TestBed.createComponent(SettingsComponent);
    fixture.detectChanges();
    await fixture.whenStable();
    return fixture.nativeElement;
  }

  it('when the settings page renders, three theme options are returned', async () => {
    const el = await render();
    expect(el.querySelectorAll('button[data-theme-option]').length).toBe(3);
  });

  it('when the Light option is clicked, setTheme is called with light', async () => {
    const el = await render();
    const light = el.querySelector<HTMLButtonElement>('button[data-theme-option="light"]');
    light!.click();
    expect(themeSpy.setTheme).toHaveBeenCalledWith('light');
  });

  it('when the stored theme is system, the System option is marked active', async () => {
    const el = await render();
    const system = el.querySelector('button[data-theme-option="system"]');
    expect(system?.className).toContain('ring-primary');
  });
});
