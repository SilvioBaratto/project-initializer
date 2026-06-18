import { ComponentFixture, TestBed } from '@angular/core/testing';

import { BadgeComponent, BadgeVariant } from './badge';

describe('BadgeComponent', () => {
  let fixture: ComponentFixture<BadgeComponent>;
  let host: HTMLElement;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [BadgeComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(BadgeComponent);
    host = fixture.nativeElement;
    fixture.detectChanges();
  });

  // --- Structural ---

  it('when created, the component renders without error', () => {
    expect(fixture.componentInstance).toBeTruthy();
  });

  // --- Criterion: variant via tokens ---

  it('when variant is default, the surface-inset token class is applied', () => {
    fixture.componentRef.setInput('variant', 'default' as BadgeVariant);
    fixture.detectChanges();

    const el = host.querySelector('span')!;
    expect(el.className).toContain('bg-surface-inset');
  });

  it('when variant is primary, the primary token class is applied', () => {
    fixture.componentRef.setInput('variant', 'primary' as BadgeVariant);
    fixture.detectChanges();

    const el = host.querySelector('span')!;
    expect(el.className).toContain('text-primary');
  });

  it('when variant is info, the info token class is applied', () => {
    fixture.componentRef.setInput('variant', 'info' as BadgeVariant);
    fixture.detectChanges();

    const el = host.querySelector('span')!;
    expect(el.className).toContain('text-info');
  });

  it('when variant is success, the success token class is applied', () => {
    fixture.componentRef.setInput('variant', 'success' as BadgeVariant);
    fixture.detectChanges();

    const el = host.querySelector('span')!;
    expect(el.className).toContain('text-success');
  });

  it('when variant is warning, the warning token class is applied', () => {
    fixture.componentRef.setInput('variant', 'warning' as BadgeVariant);
    fixture.detectChanges();

    const el = host.querySelector('span')!;
    expect(el.className).toContain('text-warning');
  });

  it('when variant is danger, the danger token class is applied', () => {
    fixture.componentRef.setInput('variant', 'danger' as BadgeVariant);
    fixture.detectChanges();

    const el = host.querySelector('span')!;
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
