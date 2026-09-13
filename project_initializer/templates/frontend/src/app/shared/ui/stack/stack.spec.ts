import { ChangeDetectionStrategy, Component } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';

import {
  STACK_DEFAULT_GAP,
  STACK_GAP_STEP_PX,
  StackAlign,
  StackComponent,
  StackJustify,
} from './stack';

@Component({
  imports: [StackComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <app-stack direction="row" [gap]="2" align="center">
      <span class="item">One</span>
      <span class="item">Two</span>
    </app-stack>
  `,
})
class StackHostComponent {}

describe('StackComponent', () => {
  let fixture: ComponentFixture<StackComponent>;
  let host: HTMLElement;

  const setInput = (name: string, value: unknown) => {
    fixture.componentRef.setInput(name, value);
    fixture.detectChanges();
  };

  /** Resolved value of a layout property on the host, as cascaded from stack.css. */
  const layout = (property: string) => getComputedStyle(host).getPropertyValue(property);

  const gapValue = () => host.style.getPropertyValue('--app-stack-gap');

  /**
   * The gap stack.css actually applies to the host. A browser substitutes var() in computed values
   * (`8px`); jsdom returns the declared `var(--name, fallback)` text, so resolve that reference against
   * the host's own custom property. Either way the result is the applied px value, so the assertion
   * holds in both runners and fails if the stylesheet stops reading the bound property.
   */
  const appliedGap = () => {
    const declared = layout('gap').trim();
    const reference = /^var\(\s*(--[\w-]+)\s*(?:,\s*(.+))?\)$/.exec(declared);
    if (!reference) return declared;
    const [, name, fallback = ''] = reference;
    const bound = getComputedStyle(host).getPropertyValue(name).trim() || host.style.getPropertyValue(name).trim();
    return bound || fallback.trim();
  };

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

  it('when rendered with default inputs, the host is a column that stretches items without wrapping', () => {
    expect(host.dataset['direction']).toBe('col');
    expect(host.dataset['wrap']).toBe('nowrap');
    expect(host.dataset['align']).toBe('stretch');
    expect(host.dataset['justify']).toBe('start');

    expect(layout('display')).toBe('flex');
    expect(layout('flex-direction')).toBe('column');
    expect(layout('flex-wrap')).toBe('nowrap');
    expect(layout('align-items')).toBe('stretch');
    expect(layout('justify-content')).toBe('start');
  });

  it('when direction is set to row, the host lays items out in a row', () => {
    setInput('direction', 'row');

    expect(host.dataset['direction']).toBe('row');
    expect(layout('flex-direction')).toBe('row');
  });

  it('when direction changes from row back to col, the host stacks items in a column again', () => {
    setInput('direction', 'row');
    setInput('direction', 'col');

    expect(host.dataset['direction']).toBe('col');
    expect(layout('flex-direction')).toBe('column');
  });

  it('when direction is not a known value, the host falls back to a column', () => {
    setInput('direction', 'diagonal');

    expect(host.dataset['direction']).toBe('col');
    expect(layout('flex-direction')).toBe('column');
  });

  it('when wrap is set to true, items wrap onto new lines', () => {
    setInput('wrap', true);

    expect(host.dataset['wrap']).toBe('wrap');
    expect(layout('flex-wrap')).toBe('wrap');
  });

  it('when wrap is given as a bare attribute, it is coerced to true and items wrap', () => {
    setInput('wrap', '');

    expect(host.dataset['wrap']).toBe('wrap');
    expect(layout('flex-wrap')).toBe('wrap');
  });

  it('when wrap is set back to false, items stay on one line', () => {
    setInput('wrap', true);
    setInput('wrap', false);

    expect(host.dataset['wrap']).toBe('nowrap');
    expect(layout('flex-wrap')).toBe('nowrap');
  });

  it('when gap is left at its default, items are 16px apart', () => {
    expect(STACK_GAP_STEP_PX).toBe(4);
    expect(STACK_DEFAULT_GAP * STACK_GAP_STEP_PX).toBe(16);
    expect(gapValue()).toBe('16px');
  });

  it.each([
    [0, '0px'],
    [1, '4px'],
    [2, '8px'],
    [3, '12px'],
    [6, '24px'],
  ] as const)('when gap is %d, items are %s apart on the 4px grid', (steps, px) => {
    setInput('gap', steps);

    expect(gapValue()).toBe(px);
  });

  it('when gap is fractional, it rounds to the nearest whole 4px step', () => {
    setInput('gap', 2.4);
    expect(gapValue()).toBe('8px');

    setInput('gap', 2.6);
    expect(gapValue()).toBe('12px');
  });

  it.each([-1, Number.NaN, Number.POSITIVE_INFINITY])('when gap is %s, the default 16px gap applies', (steps) => {
    setInput('gap', steps);

    expect(gapValue()).toBe('16px');
  });

  it('when gap is bound, the stylesheet applies the bound gap between items', () => {
    expect(appliedGap()).toBe('16px');

    setInput('gap', 2);
    expect(appliedGap()).toBe('8px');

    setInput('gap', 0);
    expect(appliedGap()).toBe('0px');
  });

  it.each<StackAlign>(['start', 'center', 'end', 'stretch', 'baseline'])(
    'when align is %s, items align to %s on the cross axis',
    (align) => {
      setInput('align', align);

      expect(host.dataset['align']).toBe(align);
      expect(layout('align-items')).toBe(align);
    },
  );

  it('when align is not a known value, items stretch on the cross axis', () => {
    setInput('align', 'middle');

    expect(host.dataset['align']).toBe('stretch');
    expect(layout('align-items')).toBe('stretch');
  });

  it.each<StackJustify>(['start', 'center', 'end', 'space-between', 'space-around', 'space-evenly'])(
    'when justify is %s, items are distributed with %s on the main axis',
    (justify) => {
      setInput('justify', justify);

      expect(host.dataset['justify']).toBe(justify);
      expect(layout('justify-content')).toBe(justify);
    },
  );

  it('when justify is not a known value, items pack to the start of the main axis', () => {
    setInput('justify', 'between');

    expect(host.dataset['justify']).toBe('start');
    expect(layout('justify-content')).toBe('start');
  });

  it('when items are projected, they are direct children of the stack with no wrapper element', () => {
    const hostFixture = TestBed.createComponent(StackHostComponent);
    hostFixture.detectChanges();

    const stack = (hostFixture.nativeElement as HTMLElement).querySelector<HTMLElement>('app-stack')!;
    const items = Array.from(stack.children);

    expect(items.map((item) => item.textContent)).toEqual(['One', 'Two']);
    expect(items.every((item) => item.classList.contains('item'))).toBe(true);
    expect(stack.dataset['direction']).toBe('row');
    expect(stack.dataset['align']).toBe('center');
    expect(stack.style.getPropertyValue('--app-stack-gap')).toBe('8px');
  });

  it('when rendered, the stack adds no role or landmark of its own', () => {
    expect(host.hasAttribute('role')).toBe(false);
    expect(host.querySelector('[role]')).toBeNull();
  });

  it('when rendered, no class attribute is added to the host', () => {
    expect(host.getAttribute('class') ?? '').toBe('');
  });

  it('when rendered, no hardcoded hex colors appear in any inline element styles', () => {
    const hexPattern = /#[0-9a-fA-F]{3,8}\b/;
    const allElements = [host, ...Array.from(host.querySelectorAll<HTMLElement>('*'))];
    for (const el of allElements) {
      expect(el.getAttribute('style') ?? '').not.toMatch(hexPattern);
    }
  });
});
