import { ChangeDetectionStrategy, Component, signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';

import { GRID_GAP_STEP_PX, GridComponent } from './grid';

/** Minimal CSSOM shapes shared by jsdom's style, media and container rules. */
interface CssRuleLike {
  readonly selectorText?: string;
  readonly conditionText?: string;
  readonly media?: { readonly mediaText: string };
  readonly style?: CSSStyleDeclaration;
  readonly cssRules?: ArrayLike<CssRuleLike>;
}

interface FoundRule {
  readonly rule: CssRuleLike;
  /** Condition of the enclosing `@media` / `@container` rule, or `''` at top level. */
  readonly condition: string;
  readonly atRule: 'media' | 'container' | '';
}

/** Flattens every style rule of the document's style sheets with its enclosing condition. */
function collectStyleRules(): FoundRule[] {
  const found: FoundRule[] = [];
  const walk = (rules: ArrayLike<CssRuleLike>, condition: string, atRule: FoundRule['atRule']) => {
    for (const rule of Array.from(rules)) {
      if (rule.selectorText !== undefined && rule.style) {
        found.push({ rule, condition, atRule });
      } else if (rule.cssRules) {
        const isMedia = rule.media !== undefined;
        const text = isMedia ? rule.media!.mediaText : (rule.conditionText ?? '');
        walk(rule.cssRules, text, isMedia ? 'media' : 'container');
      }
    }
  };
  for (const sheet of Array.from(document.styleSheets)) {
    walk(sheet.cssRules as unknown as ArrayLike<CssRuleLike>, '', '');
  }
  return found;
}

function normalize(text: string): string {
  return text.replace(/\s+/g, ' ').trim();
}

/** Rules for `selector` inside the given condition (`''` = top level). */
function rulesFor(selector: string, atRule: FoundRule['atRule'], condition = ''): CSSStyleDeclaration[] {
  return collectStyleRules()
    .filter(
      (r) =>
        normalize(r.rule.selectorText!) === selector &&
        r.atRule === atRule &&
        normalize(r.condition) === condition,
    )
    .map((r) => r.rule.style!);
}

const CELLS = '.app-grid > .app-grid__cells';
/** Zero-specificity default span rule for every projected cell. */
const CELL_DEFAULT = ':where(.app-grid > .app-grid__cells) > *';
const WINDOW_CELLS = '.app-grid:not(.app-grid--container-query) > .app-grid__cells';
const CONTAINER_CELLS = '.app-grid.app-grid--container-query > .app-grid__cells';

describe('GridComponent', () => {
  let fixture: ComponentFixture<GridComponent>;
  let host: HTMLElement;

  const cells = () => host.querySelector<HTMLElement>('.app-grid__cells')!;

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

  it('when rendered, the host carries the app-grid class and wraps a single cells element', () => {
    expect(host.classList.contains('app-grid')).toBe(true);
    expect(host.querySelectorAll('.app-grid__cells').length).toBe(1);
  });

  it('when rendered, the grid is purely structural: no role, landmark or label', () => {
    for (const el of [host, cells()]) {
      expect(el.getAttribute('role')).toBeNull();
      expect(el.getAttribute('aria-label')).toBeNull();
    }
  });

  describe('M3 column grid: 4 / 8 / 12 columns', () => {
    it('below 600px, the cells lay out on 4 columns with a 16px gutter', () => {
      const [base] = rulesFor(CELLS, '');
      expect(base).toBeDefined();
      expect(base.getPropertyValue('display')).toBe('grid');
      expect(base.getPropertyValue('--app-grid-columns').trim()).toBe('4');
      expect(normalize(base.getPropertyValue('grid-template-columns'))).toBe(
        'repeat(var(--app-grid-columns), minmax(0, 1fr))',
      );
      expect(base.getPropertyValue('gap')).toBe('16px');
    });

    it('every projected cell spans 4 columns, giving 1 / 2 / 3 cells per row', () => {
      const [base] = rulesFor(CELLS, '');
      const [cell] = rulesFor(CELL_DEFAULT, '');
      expect(base.getPropertyValue('--app-grid-cell-span').trim()).toBe('4');
      expect(cell).toBeDefined();
      expect(normalize(cell.getPropertyValue('grid-column'))).toBe('span var(--app-grid-cell-span)');
    });

    it('the default cell span has zero specificity, so a consumer grid-column rule always wins', () => {
      const spanRules = collectStyleRules().filter(
        (r) => r.rule.selectorText!.includes('app-grid') && r.rule.style!.getPropertyValue('grid-column') !== '',
      );
      expect(spanRules.map((r) => normalize(r.rule.selectorText!))).toEqual([CELL_DEFAULT]);
      expect(spanRules[0].condition).toBe('');
    });

    it('only the cells container sets --app-grid-cell-span, so a value set on a cell is never overridden', () => {
      const setters = collectStyleRules()
        .filter(
          (r) =>
            r.rule.selectorText!.includes('app-grid') &&
            r.rule.style!.getPropertyValue('--app-grid-cell-span') !== '',
        )
        .map((r) => normalize(r.rule.selectorText!));
      expect(setters).toEqual([CELLS]);
    });

    it('from a 600px window, the cells use 8 columns and a 24px gutter', () => {
      const [medium] = rulesFor(WINDOW_CELLS, 'media', '(min-width: 600px)');
      expect(medium).toBeDefined();
      expect(medium.getPropertyValue('--app-grid-columns').trim()).toBe('8');
      expect(medium.getPropertyValue('gap')).toBe('24px');
    });

    it('from a 1200px window, the cells use 12 columns', () => {
      const [large] = rulesFor(WINDOW_CELLS, 'media', '(min-width: 1200px)');
      expect(large).toBeDefined();
      expect(large.getPropertyValue('--app-grid-columns').trim()).toBe('12');
    });

    it('changes columns only at the M3 medium (600px) and large (1200px) window breakpoints', () => {
      const conditions = collectStyleRules()
        .filter((r) => r.rule.selectorText!.includes('app-grid') && r.condition !== '')
        .map((r) => normalize(r.condition));
      expect(conditions.length).toBeGreaterThan(0);
      for (const condition of conditions) {
        expect(['(min-width: 600px)', '(min-width: 1200px)']).toContain(condition);
      }
    });
  });

  describe('gap input', () => {
    it('when gap is unset, no inline gap overrides the M3 gutter', () => {
      expect(fixture.componentInstance.gapOverride()).toBeNull();
      expect(cells().style.gap).toBe('');
    });

    it('when a gap is provided, the gutter is that many 4px steps at every width', () => {
      fixture.componentRef.setInput('gap', 3);
      fixture.detectChanges();
      expect(GRID_GAP_STEP_PX).toBe(4);
      expect(cells().style.gap).toBe('12px');
    });

    it('when gap is 0, the gutter collapses to 0px', () => {
      fixture.componentRef.setInput('gap', 0);
      fixture.detectChanges();
      expect(cells().style.gap).toBe('0px');
    });

    it('when gap is negative or not finite, the M3 gutter is kept', () => {
      fixture.componentRef.setInput('gap', -2);
      fixture.detectChanges();
      expect(cells().style.gap).toBe('');

      fixture.componentRef.setInput('gap', Number.NaN);
      fixture.detectChanges();
      expect(cells().style.gap).toBe('');
    });

    it('when gap goes back to unset, the inline gap is removed', () => {
      fixture.componentRef.setInput('gap', 2);
      fixture.detectChanges();
      expect(cells().style.gap).toBe('8px');

      fixture.componentRef.setInput('gap', undefined);
      fixture.detectChanges();
      expect(cells().style.gap).toBe('');
    });
  });

  describe('containerQuery input', () => {
    it('when containerQuery is true, the host becomes an inline-size query container', () => {
      fixture.componentRef.setInput('containerQuery', true);
      fixture.detectChanges();
      expect(host.classList.contains('app-grid--container-query')).toBe(true);

      const [container] = rulesFor('.app-grid.app-grid--container-query', '');
      expect(container.getPropertyValue('container-type')).toBe('inline-size');

      // A custom element is inline by default, and inline-size containment has no effect on an inline box.
      const [hostRule] = rulesFor('.app-grid', '');
      expect(hostRule).toBeDefined();
      expect(hostRule.getPropertyValue('display')).toBe('block');
    });

    it('when containerQuery is given as a bare attribute, it is coerced to true', () => {
      fixture.componentRef.setInput('containerQuery', '');
      fixture.detectChanges();
      expect(host.classList.contains('app-grid--container-query')).toBe(true);
    });

    it('when containerQuery is false, the host is not a query container', () => {
      fixture.componentRef.setInput('containerQuery', false);
      fixture.detectChanges();
      expect(host.classList.contains('app-grid--container-query')).toBe(false);
    });

    it('in container mode, the columns follow the grid width at the same 600px / 1200px literals', () => {
      const [medium] = rulesFor(CONTAINER_CELLS, 'container', '(min-width: 600px)');
      const [large] = rulesFor(CONTAINER_CELLS, 'container', '(min-width: 1200px)');
      expect(medium.getPropertyValue('--app-grid-columns').trim()).toBe('8');
      expect(medium.getPropertyValue('gap')).toBe('24px');
      expect(large.getPropertyValue('--app-grid-columns').trim()).toBe('12');
    });
  });

  it('when rendered, no hardcoded hex colors appear in any inline element styles', () => {
    fixture.componentRef.setInput('gap', 5);
    fixture.detectChanges();
    const hexPattern = /#[0-9a-fA-F]{3,8}\b/;
    const allElements = [host, ...Array.from(host.querySelectorAll<HTMLElement>('*'))];
    for (const el of allElements) {
      expect(el.getAttribute('style') ?? '').not.toMatch(hexPattern);
    }
  });
});

@Component({
  imports: [GridComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <app-grid [gap]="gap()">
      @for (label of labels(); track label) {
        <div class="cell">{{ label }}</div>
      }
    </app-grid>
  `,
})
class GridHostComponent {
  readonly labels = signal(['Col 1', 'Col 2', 'Col 3']);
  readonly gap = signal<number | undefined>(undefined);
}

describe('GridComponent content projection', () => {
  let fixture: ComponentFixture<GridHostComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [GridHostComponent] }).compileComponents();
    fixture = TestBed.createComponent(GridHostComponent);
    fixture.detectChanges();
  });

  it('projects each child as a direct cell of the grid, in order', () => {
    const gridCells = fixture.nativeElement.querySelector('.app-grid__cells') as HTMLElement;
    const children = Array.from(gridCells.children);
    expect(children.map((el) => el.textContent?.trim())).toEqual(['Col 1', 'Col 2', 'Col 3']);
    expect(children.every((el) => el.classList.contains('cell'))).toBe(true);
  });

  it('keeps cells direct children when the projected list changes', () => {
    fixture.componentInstance.labels.set(['A', 'B', 'C', 'D']);
    fixture.detectChanges();
    const gridCells = fixture.nativeElement.querySelector('.app-grid__cells') as HTMLElement;
    expect(Array.from(gridCells.children).map((el) => el.textContent?.trim())).toEqual(['A', 'B', 'C', 'D']);
  });

  it('applies a consumer-bound gap to the cells', () => {
    fixture.componentInstance.gap.set(6);
    fixture.detectChanges();
    const gridCells = fixture.nativeElement.querySelector('.app-grid__cells') as HTMLElement;
    expect(gridCells.style.gap).toBe('24px');
  });
});

@Component({
  imports: [GridComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <app-grid>
      <div class="cell">Narrow</div>
      <div class="cell wide" [style.--app-grid-cell-span]="wideSpan()">Wide</div>
    </app-grid>
  `,
})
class WideCellHostComponent {
  readonly wideSpan = signal<number | null>(8);
}

describe('GridComponent per-cell span hook', () => {
  let fixture: ComponentFixture<WideCellHostComponent>;

  const cellsOf = () =>
    Array.from((fixture.nativeElement as HTMLElement).querySelectorAll<HTMLElement>('.app-grid__cells > .cell'));

  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [WideCellHostComponent] }).compileComponents();
    fixture = TestBed.createComponent(WideCellHostComponent);
    fixture.detectChanges();
  });

  it('every projected cell is matched by the default span rule, which resolves the span on the cell itself', () => {
    for (const cell of cellsOf()) {
      expect(cell.matches(CELL_DEFAULT)).toBe(true);
      expect(normalize(getComputedStyle(cell).getPropertyValue('grid-column'))).toBe(
        'span var(--app-grid-cell-span)',
      );
    }
  });

  it('when a cell sets --app-grid-cell-span, that cell carries its own span and its siblings do not', () => {
    const [narrow, wide] = cellsOf();
    expect(wide.style.getPropertyValue('--app-grid-cell-span')).toBe('8');
    expect(narrow.style.getPropertyValue('--app-grid-cell-span')).toBe('');
  });

  it('when the per-cell span is cleared, the cell falls back to the inherited 4-column span', () => {
    const [, wide] = cellsOf();
    fixture.componentInstance.wideSpan.set(null);
    fixture.detectChanges();
    expect(wide.style.getPropertyValue('--app-grid-cell-span')).toBe('');
    expect(wide.matches(CELL_DEFAULT)).toBe(true);
  });
});
