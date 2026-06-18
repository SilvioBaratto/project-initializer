import { ComponentFixture, TestBed } from '@angular/core/testing';

import { AlertComponent, AlertVariant } from './alert';

describe('AlertComponent', () => {
  let fixture: ComponentFixture<AlertComponent>;
  let host: HTMLElement;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AlertComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(AlertComponent);
    host = fixture.nativeElement;
    fixture.detectChanges();
  });

  // --- Criterion: role="alert" ---

  it('when rendered, an element with role="alert" is present', () => {
    expect(host.querySelector('[role="alert"]')).not.toBeNull();
  });

  // --- Criterion: variant via tokens ---

  it('when variant is info, the info token class is applied', () => {
    fixture.componentRef.setInput('variant', 'info' as AlertVariant);
    fixture.detectChanges();

    const el = host.querySelector('[role="alert"]')!;
    expect(el.className).toContain('text-info');
  });

  it('when variant is success, the success token class is applied', () => {
    fixture.componentRef.setInput('variant', 'success' as AlertVariant);
    fixture.detectChanges();

    const el = host.querySelector('[role="alert"]')!;
    expect(el.className).toContain('text-success');
  });

  it('when variant is warning, the warning token class is applied', () => {
    fixture.componentRef.setInput('variant', 'warning' as AlertVariant);
    fixture.detectChanges();

    const el = host.querySelector('[role="alert"]')!;
    expect(el.className).toContain('text-warning');
  });

  it('when variant is danger, the danger token class is applied', () => {
    fixture.componentRef.setInput('variant', 'danger' as AlertVariant);
    fixture.detectChanges();

    const el = host.querySelector('[role="alert"]')!;
    expect(el.className).toContain('text-danger');
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
