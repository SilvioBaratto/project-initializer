import { ComponentFixture, TestBed } from '@angular/core/testing';

import { SkeletonComponent } from './skeleton';

describe('SkeletonComponent', () => {
  let fixture: ComponentFixture<SkeletonComponent>;
  let host: HTMLElement;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SkeletonComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(SkeletonComponent);
    host = fixture.nativeElement;
    fixture.detectChanges();
  });

  // --- Criterion: uses .animate-shimmer ---

  it('when rendered, the skeleton element carries the animate-shimmer class', () => {
    const el = host.querySelector('div');
    expect(el?.className).toContain('animate-shimmer');
  });

  // --- Criterion: no layout shift — explicit dimensions ---

  it('when rendered, the skeleton element carries a width class', () => {
    const el = host.querySelector('div');
    expect(el?.className).toMatch(/\bw-/);
  });

  it('when rendered, the skeleton element carries a height class', () => {
    const el = host.querySelector('div');
    expect(el?.className).toMatch(/\bh-/);
  });

  it('when width input is changed, the new width class is applied', () => {
    fixture.componentRef.setInput('width', 'w-32');
    fixture.detectChanges();

    const el = host.querySelector('div');
    expect(el?.className).toContain('w-32');
  });

  it('when height input is changed, the new height class is applied', () => {
    fixture.componentRef.setInput('height', 'h-12');
    fixture.detectChanges();

    const el = host.querySelector('div');
    expect(el?.className).toContain('h-12');
  });

  // --- Criterion: shape variants ---

  it('when shape is avatar, the skeleton element has rounded-full', () => {
    fixture.componentRef.setInput('shape', 'avatar');
    fixture.detectChanges();

    const el = host.querySelector('div');
    expect(el?.className).toContain('rounded-full');
  });

  it('when shape is line (default), the skeleton element has the rounded class', () => {
    const el = host.querySelector('div');
    expect(el?.className).toContain('rounded');
  });

  // --- aria-hidden so screen readers skip placeholder ---

  it('when rendered, the skeleton element has aria-hidden="true" so screen readers skip it', () => {
    const el = host.querySelector('div');
    expect(el?.getAttribute('aria-hidden')).toBe('true');
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
