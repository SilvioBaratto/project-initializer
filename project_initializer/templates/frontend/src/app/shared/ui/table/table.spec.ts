import { Component, signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HarnessLoader } from '@angular/cdk/testing';
import { TestbedHarnessEnvironment } from '@angular/cdk/testing/testbed';
import { MatTableHarness } from '@angular/material/table/testing';

import { TableComponent, TableColumn } from './table';

const COLS: TableColumn[] = [
  { key: 'name', header: 'Name' },
  { key: 'role', header: 'Role' },
];

const ROWS = [
  { name: 'Alice', role: 'Admin' },
  { name: 'Bob', role: 'User' },
];

const LABEL = 'Team members';

// ---------------------------------------------------------------------------
// Host wrapper: consumer-style bindings, including a page-specific label
// ---------------------------------------------------------------------------

@Component({
  imports: [TableComponent],
  template: `<ui-table [columns]="cols()" [rows]="rows()" [label]="label()" />`,
})
class HostComponent {
  readonly cols = signal(COLS);
  readonly rows = signal<Record<string, unknown>[]>(ROWS);
  readonly label = signal<string | undefined>(LABEL);
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

interface Rendered {
  f: ComponentFixture<TableComponent>;
  el: HTMLElement;
  loader: HarnessLoader;
}

/** Renders the table with the shared columns and rows; pass `label: null` to leave the label unset. */
async function setup({ label = LABEL }: { label?: string | null } = {}): Promise<Rendered> {
  await TestBed.configureTestingModule({
    imports: [TableComponent],
  }).compileComponents();

  const f = TestBed.createComponent(TableComponent);
  f.componentRef.setInput('columns', COLS);
  f.componentRef.setInput('rows', ROWS);
  if (label !== null) {
    f.componentRef.setInput('label', label);
  }
  f.detectChanges();
  await f.whenStable();
  return { f, el: f.nativeElement as HTMLElement, loader: TestbedHarnessEnvironment.loader(f) };
}

async function setInput(f: ComponentFixture<TableComponent>, name: string, value: unknown): Promise<void> {
  f.componentRef.setInput(name, value);
  f.detectChanges();
  await f.whenStable();
}

/** The scroll wrapper, found by its own class so the unnamed (non-landmark) case is reachable too. */
function scroller(el: HTMLElement): HTMLElement {
  return el.querySelector<HTMLElement>('.table-region')!;
}

/** The component's own stylesheet, as injected into the document (emulated encapsulation keeps class names). */
function componentStyles(): string {
  return Array.from(document.querySelectorAll('style'))
    .map((style) => style.textContent ?? '')
    .filter((css) => css.includes('.table-region'))
    .join('\n');
}

/** Body of the `@media (min-width: 600px)` block, matched by brace depth so nested rules stay inside. */
function mediumQueryBody(css: string): string {
  const start = css.search(/@media\s*\(min-width:\s*600px\)\s*\{/);
  if (start < 0) {
    return '';
  }
  const open = css.indexOf('{', start);
  let depth = 0;
  for (let i = open; i < css.length; i++) {
    if (css[i] === '{') depth++;
    if (css[i] === '}' && --depth === 0) {
      return css.slice(open + 1, i);
    }
  }
  return '';
}

/**
 * Declarations of the rule for `className` inside a CSS chunk. Emulated encapsulation may append an
 * attribute selector (`.table-data[_ngcontent-abc]`), so anything up to the brace is allowed.
 */
function ruleFor(css: string, className: string): string {
  const match = css.match(new RegExp(`\\.${className}(?![\\w-])[^{},]*\\{([^}]*)\\}`));
  return match?.[1] ?? '';
}

/** Makes every element report content wider than its box, as a table wider than its region does. */
function overflowing(): void {
  vi.spyOn(Element.prototype, 'scrollWidth', 'get').mockReturnValue(900);
  vi.spyOn(Element.prototype, 'clientWidth', 'get').mockReturnValue(400);
}

async function render(f: ComponentFixture<unknown>): Promise<void> {
  f.detectChanges();
  await f.whenStable();
}

/** Stand-in for ResizeObserver, which jsdom lacks, so a test can fire the resize callback itself. */
class FakeResizeObserver {
  static instances: FakeResizeObserver[] = [];
  readonly observed: Element[] = [];
  disconnected = false;

  constructor(private readonly callback: ResizeObserverCallback) {
    FakeResizeObserver.instances.push(this);
  }

  observe(target: Element): void {
    this.observed.push(target);
  }

  unobserve(): void {
    // Not used by the component.
  }

  disconnect(): void {
    this.disconnected = true;
  }

  fire(): void {
    this.callback([], this as unknown as ResizeObserver);
  }
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  FakeResizeObserver.instances = [];
});

// ===========================================================================
// Criterion — Semantic Material data table (medium and wider)
// ===========================================================================

describe('TableComponent — semantic mat-table', () => {
  it('when rendered, a native <table> carrying mat-table is present', async () => {
    const { el } = await setup();
    const table = el.querySelector('table');
    expect(table).not.toBeNull();
    expect(table!.classList).toContain('mat-mdc-table');
  });

  it('when rendered, a <thead> element is present for column headers', async () => {
    const { el } = await setup();
    expect(el.querySelector('table thead')).not.toBeNull();
  });

  it('when rendered, a <tbody> element is present for data rows', async () => {
    const { el } = await setup();
    expect(el.querySelector('table tbody')).not.toBeNull();
  });

  it('when columns are provided, the header row shows each column header in order', async () => {
    const { loader } = await setup();
    const table = await loader.getHarness(MatTableHarness);
    const [headerRow] = await table.getHeaderRows();
    const cells = await headerRow.getCells();
    const headers = await Promise.all(cells.map((cell) => cell.getText()));
    expect(headers).toEqual(['Name', 'Role']);
  });

  it('when columns are provided, each column definition is named after its key', async () => {
    const { loader } = await setup();
    const table = await loader.getHarness(MatTableHarness);
    const [headerRow] = await table.getHeaderRows();
    const cells = await headerRow.getCells();
    const names = await Promise.all(cells.map((cell) => cell.getColumnName()));
    expect(names).toEqual(['name', 'role']);
  });

  it('when columns are provided, header cells have scope="col"', async () => {
    const { el } = await setup();
    const ths = Array.from(el.querySelectorAll<HTMLElement>('th'));
    expect(ths.length).toBe(COLS.length);
    ths.forEach((th) => expect(th.getAttribute('scope')).toBe('col'));
  });

  it('when a label is set, the table takes it as its accessible name', async () => {
    const { el } = await setup();
    expect(el.querySelector('table')!.getAttribute('aria-label')).toBe(LABEL);
  });
});

// ===========================================================================
// Criterion — Row data rendering
// ===========================================================================

describe('TableComponent — row data', () => {
  it('when rows are provided, each cell shows the value for its column key', async () => {
    const { loader } = await setup();
    const table = await loader.getHarness(MatTableHarness);
    const byColumn = await table.getCellTextByColumnName();
    expect(byColumn['name'].text).toEqual(['Alice', 'Bob']);
    expect(byColumn['role'].text).toEqual(['Admin', 'User']);
  });

  it('when rows input changes, the new values are rendered', async () => {
    const { f, el, loader } = await setup();
    await setInput(f, 'rows', [{ name: 'Carol', role: 'Editor' }]);
    const table = await loader.getHarness(MatTableHarness);
    expect(await table.getCellTextByIndex()).toEqual([['Carol', 'Editor']]);
    expect(el.textContent).not.toContain('Alice');
  });

  it('when rows is empty, no data rows appear in the table or the stacked cards', async () => {
    const { f, el, loader } = await setup();
    await setInput(f, 'rows', []);
    const table = await loader.getHarness(MatTableHarness);
    expect((await table.getRows()).length).toBe(0);
    expect(el.querySelectorAll('tbody tr').length).toBe(0);
    expect(el.querySelectorAll('ul li').length).toBe(0);
  });
});

// ===========================================================================
// Criterion — Stacked card layout at M3 compact (below 600px)
// ===========================================================================

describe('TableComponent — stacked cards below 600px', () => {
  it('when rendered, a <ul role="list"> named by the label provides the compact card layout', async () => {
    const { el } = await setup();
    const ul = el.querySelector('ul');
    expect(ul).not.toBeNull();
    expect(ul!.getAttribute('role')).toBe('list');
    expect(ul!.getAttribute('aria-label')).toBe(LABEL);
  });

  it('when rendered, each row produces a card <li> in the compact list', async () => {
    const { el } = await setup();
    expect(el.querySelectorAll('ul li').length).toBe(ROWS.length);
  });

  it('when rendered, every card shows one header / value pair per column', async () => {
    const { el } = await setup();
    const cards = Array.from(el.querySelectorAll('ul li'));
    cards.forEach((card, index) => {
      const labels = Array.from(card.querySelectorAll('dl dt')).map((dt) => dt.textContent?.trim());
      const values = Array.from(card.querySelectorAll('dl dd')).map((dd) => dd.textContent?.trim());
      expect(labels).toEqual(['Name', 'Role']);
      expect(values).toEqual([ROWS[index].name, ROWS[index].role]);
    });
  });

  it('when rendered in a window without media query support (compact baseline), only the cards are displayed', async () => {
    // jsdom does not evaluate `(min-width: 600px)`, so it computes the mobile-first baseline.
    const { el } = await setup();
    expect(getComputedStyle(el.querySelector('table')!).display).toBe('none');
    expect(getComputedStyle(el.querySelector('ul')!).display).not.toBe('none');
  });

  it('when the stylesheet is loaded, the layout switches at the M3 600px breakpoint, never 768px', async () => {
    await setup();
    const css = componentStyles();
    expect(css).toMatch(/min-width:\s*600px/);
    expect(css).not.toMatch(/768px/);
  });

  it('when the window is 600px or wider, the stylesheet shows the table and hides the cards', async () => {
    // jsdom never applies the media query, so read what the 600px block declares.
    await setup();
    const medium = mediumQueryBody(componentStyles());
    expect(medium).not.toBe('');
    expect(ruleFor(medium, 'table-data')).toMatch(/display:\s*table\s*(;|$)/);
    expect(ruleFor(medium, 'table-cards')).toMatch(/display:\s*none\s*(;|$)/);
  });
});

// ===========================================================================
// Criterion — Horizontal-scroll region with overscroll containment
// ===========================================================================

describe('TableComponent — horizontal-scroll region', () => {
  it('when rendered, a single scroll wrapper encloses both the table and the cards', async () => {
    const { el } = await setup();
    expect(el.querySelectorAll('.table-region').length).toBe(1);
    expect(scroller(el)).toBe(el.firstElementChild);
    expect(scroller(el).contains(el.querySelector('table'))).toBe(true);
    expect(scroller(el).contains(el.querySelector('ul'))).toBe(true);
  });

  it('when rendered, the scroll region scrolls horizontally and contains overscroll', async () => {
    const { el } = await setup();
    const css = componentStyles();
    expect(getComputedStyle(scroller(el)).overflowX).toBe('auto');
    expect(css).toMatch(/overscroll-behavior:\s*contain/);
  });

  it('when the content fits the region, the wrapper is neither a tab stop nor a landmark, and the table and list keep the label', async () => {
    // jsdom lays nothing out, so scrollWidth equals clientWidth (0): nothing overflows.
    const { el } = await setup();
    const wrapper = scroller(el);
    expect(wrapper.hasAttribute('tabindex')).toBe(false);
    expect(wrapper.hasAttribute('role')).toBe(false);
    expect(wrapper.hasAttribute('aria-label')).toBe(false);
    expect(el.querySelector('table')!.getAttribute('aria-label')).toBe(LABEL);
    expect(el.querySelector('ul')!.getAttribute('aria-label')).toBe(LABEL);
  });

  it('when the content overflows the region, the wrapper is a tab stop so keyboard users can focus and scroll it', async () => {
    overflowing();
    const { el } = await setup();
    const wrapper = scroller(el);
    expect(wrapper.getAttribute('tabindex')).toBe('0');
    wrapper.focus();
    expect(document.activeElement).toBe(wrapper);
  });

  it('when a label is set and the content overflows, the wrapper is a single region landmark named by it without a role word', async () => {
    overflowing();
    const { el } = await setup();
    const regions = el.querySelectorAll('[role="region"]');
    expect(regions.length).toBe(1);
    expect(regions[0]).toBe(scroller(el));
    const name = scroller(el).getAttribute('aria-label') ?? '';
    expect(name).toBe(LABEL);
    expect(name).not.toMatch(/region|table/i);
  });

  it('when no label is set, no unnamed region landmark renders, an overflowing wrapper stays keyboard-scrollable, and dev mode warns once', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    overflowing();
    const { f, el } = await setup({ label: null });
    await setInput(f, 'rows', [{ name: 'Carol', role: 'Editor' }]);
    expect(el.querySelector('[role="region"]')).toBeNull();
    for (const node of [scroller(el), el.querySelector('table')!, el.querySelector('ul')!]) {
      expect(node.hasAttribute('aria-label')).toBe(false);
    }
    expect(scroller(el).getAttribute('tabindex')).toBe('0');
    expect(el.querySelector('ul')!.getAttribute('role')).toBe('list');
    expect(warn).toHaveBeenCalledTimes(1);
    expect(String(warn.mock.calls[0][0])).toContain('label');
  });

  it('when the label is blank, it is treated as missing: no landmark renders and dev mode warns', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    overflowing();
    const { el } = await setup({ label: '   ' });
    expect(el.querySelector('[role="region"]')).toBeNull();
    expect(scroller(el).hasAttribute('aria-label')).toBe(false);
    expect(warn).toHaveBeenCalledTimes(1);
  });

  it('when a label is set, dev mode logs no warning', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    await setup();
    expect(warn).not.toHaveBeenCalled();
  });

  it('when rows change so the content overflows, the region re-measures without a resize', async () => {
    const { f, el } = await setup();
    expect(scroller(el).hasAttribute('tabindex')).toBe(false);

    overflowing();
    await setInput(f, 'rows', [...ROWS, { name: 'Carol', role: 'Editor' }]);
    expect(scroller(el).getAttribute('tabindex')).toBe('0');
    expect(scroller(el).getAttribute('role')).toBe('region');
  });

  it('when rendered, a resize observer watches the region and the table', async () => {
    vi.stubGlobal('ResizeObserver', FakeResizeObserver);
    const { el } = await setup();
    // Material's table may create observers of its own: take the one watching the scroll region.
    const observer = FakeResizeObserver.instances.find((o) =>
      o.observed.some((target) => target.classList.contains('table-region')),
    )!;
    expect(observer).toBeDefined();
    expect(observer.observed).toContain(scroller(el));
    expect(observer.observed).toContain(el.querySelector('table'));
  });

  it('when the region resizes so its content overflows, it becomes a named tab stop, and loses both when the overflow ends', async () => {
    vi.stubGlobal('ResizeObserver', FakeResizeObserver);
    const { f, el } = await setup();
    // Material's table may create observers of its own: take the one watching the scroll region.
    const observer = FakeResizeObserver.instances.find((o) =>
      o.observed.some((target) => target.classList.contains('table-region')),
    )!;

    overflowing();
    observer.fire();
    await render(f);
    expect(scroller(el).getAttribute('tabindex')).toBe('0');
    expect(scroller(el).getAttribute('role')).toBe('region');
    expect(scroller(el).getAttribute('aria-label')).toBe(LABEL);

    vi.restoreAllMocks();
    observer.fire();
    await render(f);
    expect(scroller(el).hasAttribute('tabindex')).toBe(false);
    expect(scroller(el).hasAttribute('role')).toBe(false);
    expect(scroller(el).hasAttribute('aria-label')).toBe(false);
  });

  it('when the focused region stops overflowing, it keeps its tab stop until focus leaves, so focus never drops to the page', async () => {
    vi.stubGlobal('ResizeObserver', FakeResizeObserver);
    overflowing();
    const { f, el } = await setup();
    // Material's table may create observers of its own: take the one watching the scroll region.
    const observer = FakeResizeObserver.instances.find((o) =>
      o.observed.some((target) => target.classList.contains('table-region')),
    )!;
    const wrapper = scroller(el);
    wrapper.focus();

    vi.restoreAllMocks();
    observer.fire();
    await render(f);
    expect(wrapper.getAttribute('tabindex')).toBe('0');
    expect(document.activeElement).toBe(wrapper);

    wrapper.blur();
    await render(f);
    expect(wrapper.hasAttribute('tabindex')).toBe(false);
  });

  it('when the component is destroyed, the resize observer disconnects', async () => {
    vi.stubGlobal('ResizeObserver', FakeResizeObserver);
    const { f } = await setup();
    // Material's table may create observers of its own: take the one watching the scroll region.
    const observer = FakeResizeObserver.instances.find((o) =>
      o.observed.some((target) => target.classList.contains('table-region')),
    )!;
    f.destroy();
    expect(observer.disconnected).toBe(true);
  });

  it('when a consumer passes a label, the region, table and list all use it', async () => {
    overflowing();
    await TestBed.configureTestingModule({ imports: [HostComponent] }).compileComponents();
    const host = TestBed.createComponent(HostComponent);
    host.detectChanges();
    await host.whenStable();
    const el = host.nativeElement as HTMLElement;

    expect(el.querySelector('[role="region"]')!.getAttribute('aria-label')).toBe(LABEL);
    expect(el.querySelector('table')!.getAttribute('aria-label')).toBe(LABEL);
    expect(el.querySelector('ul')!.getAttribute('aria-label')).toBe(LABEL);
  });

  it('when a consumer clears the label, the landmark and names are removed', async () => {
    vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    overflowing();
    await TestBed.configureTestingModule({ imports: [HostComponent] }).compileComponents();
    const host = TestBed.createComponent(HostComponent);
    host.detectChanges();
    await host.whenStable();

    host.componentInstance.label.set(undefined);
    host.detectChanges();
    await host.whenStable();
    const el = host.nativeElement as HTMLElement;

    expect(el.querySelector('[role="region"]')).toBeNull();
    expect(el.querySelector('table')!.hasAttribute('aria-label')).toBe(false);
  });

  it('when two tables on one page get different labels, their region landmarks have distinct names', async () => {
    @Component({
      imports: [TableComponent],
      template: `
        <ui-table [columns]="cols" [rows]="rows" label="Team members" />
        <ui-table [columns]="cols" [rows]="rows" label="Pending invites" />
      `,
    })
    class TwoTablesHost {
      readonly cols = COLS;
      readonly rows = ROWS;
    }

    overflowing();
    await TestBed.configureTestingModule({ imports: [TwoTablesHost] }).compileComponents();
    const host = TestBed.createComponent(TwoTablesHost);
    host.detectChanges();
    await host.whenStable();

    const names = Array.from((host.nativeElement as HTMLElement).querySelectorAll('[role="region"]')).map((region) =>
      region.getAttribute('aria-label'),
    );
    expect(names).toEqual(['Team members', 'Pending invites']);
    expect(new Set(names).size).toBe(names.length);
  });
});

// ===========================================================================
// Criterion — Signal inputs (Angular 21)
// ===========================================================================

describe('TableComponent — signal inputs', () => {
  it('when columns input is set, the component reflects the change reactively', async () => {
    const { f, el } = await setup();
    await setInput(f, 'columns', [{ key: 'email', header: 'Email' }]);
    expect(el.textContent).toContain('Email');
    expect(el.textContent).not.toContain('Name');
  });

  it('when a consumer updates bound signals, the table re-renders', async () => {
    await TestBed.configureTestingModule({ imports: [HostComponent] }).compileComponents();
    const host = TestBed.createComponent(HostComponent);
    host.detectChanges();
    await host.whenStable();

    host.componentInstance.rows.set([{ name: 'Dana', role: 'Owner' }]);
    host.detectChanges();
    await host.whenStable();

    const table = await TestbedHarnessEnvironment.loader(host).getHarness(MatTableHarness);
    expect(await table.getCellTextByIndex()).toEqual([['Dana', 'Owner']]);
  });
});

// ===========================================================================
// Criterion — Material 3 tokens only; no color literals
// ===========================================================================

describe('TableComponent — M3 tokens only', () => {
  it('when rendered, no hardcoded hex colours appear in inline element styles', async () => {
    const { el } = await setup();
    const hexPattern = /#[0-9a-fA-F]{3,8}\b/;
    const all: HTMLElement[] = [el, ...Array.from(el.querySelectorAll<HTMLElement>('*'))];
    for (const node of all) {
      expect(node.getAttribute('style') ?? '').not.toMatch(hexPattern);
    }
  });

  it('when the stylesheet is loaded, colors come from --mat-sys-* roles and no literals', async () => {
    await setup();
    const css = componentStyles();
    expect(css).toContain('var(--mat-sys-surface)');
    expect(css).toContain('var(--mat-sys-outline-variant)');
    expect(css).toContain('var(--mat-sys-secondary)');
    expect(css).not.toMatch(/#[0-9a-fA-F]{3,8}\b|\b(?:rgba?|hsla?)\(/);
  });
});
