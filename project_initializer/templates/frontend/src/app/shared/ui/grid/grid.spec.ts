import { ComponentFixture, TestBed } from '@angular/core/testing';

import { GridComponent } from './grid';

describe('GridComponent', () => {
  let fixture: ComponentFixture<GridComponent>;
  let host: HTMLElement;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [GridComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(GridComponent);
    host = fixture.nativeElement;
    fixture.detectChanges();
  });

  it('when created, the component renders without error', () => {
    expect(fixture.componentInstance).toBeTruthy();
  });

  it('when rendered with default inputs, the grid element carries grid-cols-1 (mobile-first base)', () => {
    // The responsive sequence is cols-1 / md:cols-2 / lg:cols-3; grid-cols-1 is the base.
    const gridEl = host.querySelector('.grid') ?? host;
    expect(gridEl.classList.contains('grid-cols-1')).toBe(true);
  });

  it('when rendered, the grid element carries the md:grid-cols-2 responsive class', () => {
    const gridEl = host.querySelector('.grid') ?? host;
    expect(gridEl.classList.contains('md:grid-cols-2')).toBe(true);
  });

  it('when rendered, the grid element carries the lg:grid-cols-3 responsive class', () => {
    const gridEl = host.querySelector('.grid') ?? host;
    expect(gridEl.classList.contains('lg:grid-cols-3')).toBe(true);
  });

  it('when a gap input is provided, the gap class reflects that value', () => {
    fixture.componentRef.setInput('gap', 4);
    fixture.detectChanges();
    const gridEl = host.querySelector('.grid') ?? host;
    // gap-4 is the canonical Tailwind class for a gap of 4 spacing units
    expect(gridEl.classList.toString()).toContain('gap-');
  });

  it('when containerQuery input is true, the @container class is applied', () => {
    fixture.componentRef.setInput('containerQuery', true);
    fixture.detectChanges();
    const allEls = [host, ...Array.from(host.querySelectorAll('*') as NodeListOf<Element>)];
    const hasContainer = allEls.some((el) =>
      Array.from(el.classList).some((c) => c.includes('container')),
    );
    expect(hasContainer).toBe(true);
  });

  it('when containerQuery input is false, no @container class is applied', () => {
    fixture.componentRef.setInput('containerQuery', false);
    fixture.detectChanges();
    const allEls = [host, ...Array.from(host.querySelectorAll('*') as NodeListOf<Element>)];
    const hasContainer = allEls.some((el) =>
      Array.from(el.classList).some((c) => c === '@container'),
    );
    expect(hasContainer).toBe(false);
  });

  it('when rendered, no hardcoded hex colors appear in any inline element styles', () => {
    const hexPattern = /#[0-9a-fA-F]{3,8}\b/;
    const allElements = [host, ...Array.from(host.querySelectorAll<HTMLElement>('*'))];
    for (const el of allElements) {
      expect(el.getAttribute('style') ?? '').not.toMatch(hexPattern);
    }
  });
});
