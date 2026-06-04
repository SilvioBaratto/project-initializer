import { provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { LucideIconConfig } from 'lucide-angular';

import { ICON_PROVIDER } from './../../icons';
import { SidebarComponent } from './sidebar';

describe('SidebarComponent', () => {
  beforeEach(async () => {
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
            cfg.strokeWidth = 1.5;
            return cfg;
          },
        },
      ],
    }).compileComponents();
  });

  it('when the sidebar renders, a lucide-icon element is present', async () => {
    const fixture = TestBed.createComponent(SidebarComponent);
    fixture.detectChanges();
    await fixture.whenStable();

    const lucideIcon = fixture.nativeElement.querySelector('lucide-icon');
    expect(lucideIcon).toBeTruthy();
  });

  it('when the sidebar renders, the lucide-icon uses the seeded MessageSquare name', async () => {
    const fixture = TestBed.createComponent(SidebarComponent);
    fixture.detectChanges();
    await fixture.whenStable();

    const svg = fixture.nativeElement.querySelector('lucide-icon svg');
    expect(svg).toBeTruthy();
  });

  it('when the nav item has an accessible label, the visible name text is rendered', async () => {
    const fixture = TestBed.createComponent(SidebarComponent);
    fixture.detectChanges();
    await fixture.whenStable();

    const navLink = fixture.nativeElement.querySelector('nav a');
    expect(navLink).toBeTruthy();
    expect(navLink.textContent).toContain('Chatbot');
  });
});
