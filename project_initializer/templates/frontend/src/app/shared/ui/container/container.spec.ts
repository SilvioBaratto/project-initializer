import { ComponentFixture, TestBed } from '@angular/core/testing';

import { ContainerComponent } from './container';

describe('ContainerComponent', () => {
  let fixture: ComponentFixture<ContainerComponent>;
  let host: HTMLElement;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ContainerComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(ContainerComponent);
    host = fixture.nativeElement;
    fixture.detectChanges();
  });

  it('when created, the component renders without error', () => {
    expect(fixture.componentInstance).toBeTruthy();
  });

  it('when rendered, the px-safe class is applied to the container element', () => {
    // px-safe may be applied via host:{class:} on the host element or on an inner wrapper.
    const hasPxSafe =
      host.classList.contains('px-safe') ||
      host.querySelector('.px-safe') !== null;
    expect(hasPxSafe).toBe(true);
  });

  it('when rendered, no hardcoded hex colors appear in any inline element styles', () => {
    // Proxy for the @theme-tokens criterion: @theme utilities arrive via CSS classes, not inline
    // styles. An inline style containing a hex literal would indicate a hardcoded colour.
    const hexPattern = /#[0-9a-fA-F]{3,8}\b/;
    const allElements = [host, ...Array.from(host.querySelectorAll<HTMLElement>('*'))];
    for (const el of allElements) {
      const inlineStyle = el.getAttribute('style') ?? '';
      expect(inlineStyle).not.toMatch(hexPattern);
    }
  });

  it('when a size input is provided, the component re-renders without error', () => {
    fixture.componentRef.setInput('size', 'lg');
    expect(() => fixture.detectChanges()).not.toThrow();
  });
});
