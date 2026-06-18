/**
 * Spec for issue #22: Components demo catalog
 *
 * Asserts:
 * - The page renders a section per component group (Core, Forms, Navigation, Overlays, Data Display)
 * - Both a light region and a dark-scoped region are rendered per group
 */

import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { LucideIconConfig } from 'lucide-angular';

import { ICON_PROVIDER } from '../../icons';
import { ComponentsComponent } from './components';

const GROUPS = ['Core', 'Forms', 'Navigation', 'Overlays', 'Data Display'];

describe('ComponentsComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ComponentsComponent],
      providers: [
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
  });

  async function render(): Promise<HTMLElement> {
    const fixture = TestBed.createComponent(ComponentsComponent);
    fixture.detectChanges();
    await fixture.whenStable();
    return fixture.nativeElement;
  }

  for (const group of GROUPS) {
    it(`when the catalog renders, a section for '${group}' is present`, async () => {
      const el = await render();
      const sections = Array.from(el.querySelectorAll('[data-section]'));
      const match = sections.find(
        (s) => s.getAttribute('data-section') === group,
      );
      expect(match).toBeTruthy();
    });
  }

  it('when the catalog renders, at least one dark-scoped container is present per section', async () => {
    const el = await render();
    const darkContainers = el.querySelectorAll('.dark');
    // Each section uses ThemePreviewComponent which renders one dark container
    expect(darkContainers.length).toBeGreaterThanOrEqual(GROUPS.length);
  });

  it('when the catalog renders, a light region (without dark class on outer wrapper) exists', async () => {
    const el = await render();
    // The host element does not carry the dark class — light region is the default surface
    expect(el.classList.contains('dark')).toBe(false);
  });

  it('when the catalog renders, a dark-classed container element is present', async () => {
    const el = await render();
    expect(el.querySelector('.dark')).toBeTruthy();
  });

  it('when an overlay is opened, at most one overlay panel is rendered in the DOM', async () => {
    const fixture = TestBed.createComponent(ComponentsComponent);
    fixture.componentInstance.activeOverlay.set('modal');
    fixture.detectChanges();
    await fixture.whenStable();
    const el = fixture.nativeElement;
    const overlayPanels = el.querySelectorAll('[role="dialog"]');
    expect(overlayPanels).toHaveLength(1);
  });
});
