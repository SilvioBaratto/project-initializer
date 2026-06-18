import { ComponentFixture, TestBed } from '@angular/core/testing';
import { LucideIconConfig } from 'lucide-angular';

import { ICON_PROVIDER } from '../../../icons';
import { SpinnerComponent } from './spinner';

describe('SpinnerComponent', () => {
  let fixture: ComponentFixture<SpinnerComponent>;
  let host: HTMLElement;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SpinnerComponent],
      providers: [
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

    fixture = TestBed.createComponent(SpinnerComponent);
    host = fixture.nativeElement;
    fixture.detectChanges();
  });

  // --- Criterion: role="status" ---

  it('when rendered, the host contains an element with role="status"', () => {
    expect(host.querySelector('[role="status"]')).not.toBeNull();
  });

  // --- Criterion: sr-only label ---

  it('when rendered, a sr-only text element is present inside the status region', () => {
    const srEl = host.querySelector('[role="status"] .sr-only');
    expect(srEl).not.toBeNull();
  });

  it('when label input is provided, the sr-only text reflects it', () => {
    fixture.componentRef.setInput('label', 'Saving changes…');
    fixture.detectChanges();

    const srEl = host.querySelector('.sr-only');
    expect(srEl?.textContent?.trim()).toBe('Saving changes…');
  });

  it('when no label input is provided, the sr-only text defaults to a non-empty string', () => {
    const srEl = host.querySelector('.sr-only');
    expect(srEl?.textContent?.trim().length).toBeGreaterThan(0);
  });

  // --- Criterion: reduced-motion safe (motion-safe:animate-spin) ---

  it('when rendered, the spinning icon uses motion-safe:animate-spin so the animation halts under prefers-reduced-motion', async () => {
    fixture.detectChanges();
    await fixture.whenStable();

    const icon = host.querySelector('lucide-icon');
    expect(icon?.className).toContain('motion-safe:animate-spin');
  });

  // --- No hardcoded hex colours ---

  it('when rendered, no hardcoded hex colors appear in any inline element styles', () => {
    const hexPattern = /#[0-9a-fA-F]{3,8}\b/;
    const allElements = [host, ...Array.from(host.querySelectorAll<HTMLElement>('*'))];
    for (const el of allElements) {
      expect(el.getAttribute('style') ?? '').not.toMatch(hexPattern);
    }
  });
});
