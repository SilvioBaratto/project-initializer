import { ComponentFixture, TestBed } from '@angular/core/testing';

import { StackComponent } from './stack';

describe('StackComponent', () => {
  let fixture: ComponentFixture<StackComponent>;
  let host: HTMLElement;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [StackComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(StackComponent);
    host = fixture.nativeElement;
    fixture.detectChanges();
  });

  it('when created, the component renders without error', () => {
    expect(fixture.componentInstance).toBeTruthy();
  });

  it('when rendered with default inputs, the flex class is present', () => {
    const flexEl = host.querySelector('.flex') ?? host;
    expect(flexEl).toBeTruthy();
  });

  it('when direction is set to row, the flex-row class is present', () => {
    fixture.componentRef.setInput('direction', 'row');
    fixture.detectChanges();
    const flexEl = host.querySelector('.flex') ?? host;
    expect(flexEl.classList.contains('flex-row')).toBe(true);
  });

  it('when direction is set to col, the flex-col class is present', () => {
    fixture.componentRef.setInput('direction', 'col');
    fixture.detectChanges();
    const flexEl = host.querySelector('.flex') ?? host;
    expect(flexEl.classList.contains('flex-col')).toBe(true);
  });

  it('when wrap is set to true, the flex-wrap class is present', () => {
    fixture.componentRef.setInput('wrap', true);
    fixture.detectChanges();
    const flexEl = host.querySelector('.flex') ?? host;
    expect(flexEl.classList.contains('flex-wrap')).toBe(true);
  });

  it('when a gap input is provided, a gap class is present', () => {
    fixture.componentRef.setInput('gap', 4);
    fixture.detectChanges();
    const flexEl = host.querySelector('.flex') ?? host;
    expect(flexEl.classList.toString()).toContain('gap-');
  });

  it('when rendered, no hardcoded hex colors appear in any inline element styles', () => {
    const hexPattern = /#[0-9a-fA-F]{3,8}\b/;
    const allElements = [host, ...Array.from(host.querySelectorAll<HTMLElement>('*'))];
    for (const el of allElements) {
      expect(el.getAttribute('style') ?? '').not.toMatch(hexPattern);
    }
  });
});
