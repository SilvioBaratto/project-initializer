import { Component } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';

import { TableComponent, TableColumn } from './table';

const COLS: TableColumn[] = [
  { key: 'name', header: 'Name' },
  { key: 'role', header: 'Role' },
];

const ROWS = [
  { name: 'Alice', role: 'Admin' },
  { name: 'Bob',   role: 'User'  },
];

// ---------------------------------------------------------------------------
// Host wrapper for slot projection tests
// ---------------------------------------------------------------------------

@Component({
  imports: [TableComponent],
  template: `<ui-table [columns]="cols" [rows]="rows" />`,
})
class HostComponent {
  cols = COLS;
  rows = ROWS;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function setup(): Promise<ComponentFixture<TableComponent>> {
  await TestBed.configureTestingModule({
    imports: [TableComponent],
  }).compileComponents();

  const f = TestBed.createComponent(TableComponent);
  f.componentRef.setInput('columns', COLS);
  f.componentRef.setInput('rows', ROWS);
  f.detectChanges();
  return f;
}

// ===========================================================================
// Criterion — Semantic table at ≥md
// ===========================================================================

describe('TableComponent — semantic table element', () => {
  it('when rendered, a <table> element is present in the DOM', async () => {
    const f = await setup();
    expect(f.nativeElement.querySelector('table')).not.toBeNull();
  });

  it('when rendered, a <thead> element is present for column headers', async () => {
    const f = await setup();
    expect(f.nativeElement.querySelector('thead')).not.toBeNull();
  });

  it('when rendered, a <tbody> element is present for data rows', async () => {
    const f = await setup();
    expect(f.nativeElement.querySelector('tbody')).not.toBeNull();
  });

  it('when columns are provided, header cells carry the column header text', async () => {
    const f = await setup();
    const ths: NodeListOf<HTMLElement> = f.nativeElement.querySelectorAll('th');
    const headers = Array.from(ths).map(th => th.textContent?.trim());
    expect(headers).toContain('Name');
    expect(headers).toContain('Role');
  });

  it('when columns are provided, header cells have scope="col"', async () => {
    const f = await setup();
    const ths: NodeListOf<HTMLElement> = f.nativeElement.querySelectorAll('th');
    expect(ths.length).toBeGreaterThan(0);
    Array.from(ths).forEach(th => {
      expect(th.getAttribute('scope')).toBe('col');
    });
  });

  it('when the table is hidden on mobile, the table element carries the md: breakpoint show class', async () => {
    const f = await setup();
    const table: HTMLElement = f.nativeElement.querySelector('table');
    // "hidden md:table" — the `hidden` class hides below md; `md:table` restores display at md+
    expect(table.className).toContain('md:table');
  });

  it('when the table element is styled for mobile hide, it carries the hidden class', async () => {
    const f = await setup();
    const table: HTMLElement = f.nativeElement.querySelector('table');
    expect(table.className).toContain('hidden');
  });
});

// ===========================================================================
// Criterion — Row data rendering
// ===========================================================================

describe('TableComponent — row data', () => {
  it('when rows are provided, their cell values appear in the table body', async () => {
    const f = await setup();
    const text = f.nativeElement.textContent ?? '';
    expect(text).toContain('Alice');
    expect(text).toContain('Bob');
    expect(text).toContain('Admin');
    expect(text).toContain('User');
  });

  it('when rows input changes, the new values are rendered', async () => {
    const f = await setup();
    f.componentRef.setInput('rows', [{ name: 'Carol', role: 'Editor' }]);
    f.detectChanges();
    expect(f.nativeElement.textContent).toContain('Carol');
    expect(f.nativeElement.textContent).not.toContain('Alice');
  });

  it('when rows is empty, no <tr> elements appear in tbody', async () => {
    const f = await setup();
    f.componentRef.setInput('rows', []);
    f.detectChanges();
    const trs = f.nativeElement.querySelectorAll('tbody tr');
    expect(trs.length).toBe(0);
  });
});

// ===========================================================================
// Criterion — Card/stacked layout below md
// ===========================================================================

describe('TableComponent — card/stacked layout below md', () => {
  it('when rendered, a <ul> element provides the mobile card layout', async () => {
    const f = await setup();
    expect(f.nativeElement.querySelector('ul')).not.toBeNull();
  });

  it('when rendered, the mobile <ul> carries md:hidden to collapse at ≥md', async () => {
    const f = await setup();
    const ul: HTMLElement = f.nativeElement.querySelector('ul')!;
    expect(ul.className).toContain('md:hidden');
  });

  it('when rendered, each row produces a card <li> in the mobile list', async () => {
    const f = await setup();
    const lis = f.nativeElement.querySelectorAll('ul li');
    expect(lis.length).toBe(ROWS.length);
  });

  it('when rendered, the mobile card shows column header labels as field labels', async () => {
    const f = await setup();
    const ul: HTMLElement = f.nativeElement.querySelector('ul')!;
    expect(ul.textContent).toContain('Name');
    expect(ul.textContent).toContain('Role');
  });
});

// ===========================================================================
// Criterion — Horizontal-scroll fallback with overscroll-contain
// ===========================================================================

describe('TableComponent — horizontal-scroll fallback', () => {
  it('when rendered, the scroll wrapper carries overflow-x-auto', async () => {
    const f = await setup();
    const wrapper: HTMLElement = f.nativeElement.firstElementChild as HTMLElement;
    expect(wrapper.className).toContain('overflow-x-auto');
  });

  it('when rendered, the scroll wrapper carries overscroll-contain', async () => {
    const f = await setup();
    const wrapper: HTMLElement = f.nativeElement.firstElementChild as HTMLElement;
    expect(wrapper.className).toContain('overscroll-contain');
  });

  it('when rendered, the scroll region has tabindex=0 for keyboard accessibility', async () => {
    const f = await setup();
    const wrapper: HTMLElement = f.nativeElement.firstElementChild as HTMLElement;
    expect(wrapper.getAttribute('tabindex')).toBe('0');
  });

  it('when rendered, the scroll region has role="region" for landmark navigation', async () => {
    const f = await setup();
    const wrapper: HTMLElement = f.nativeElement.firstElementChild as HTMLElement;
    expect(wrapper.getAttribute('role')).toBe('region');
  });
});

// ===========================================================================
// Criterion — Signal inputs (Angular 21)
// ===========================================================================

describe('TableComponent — signal inputs', () => {
  it('when columns input is set, the component reflects the change reactively', async () => {
    const f = await setup();
    f.componentRef.setInput('columns', [{ key: 'email', header: 'Email' }]);
    f.detectChanges();
    expect(f.nativeElement.textContent).toContain('Email');
    expect(f.nativeElement.textContent).not.toContain('Name');
  });
});

// ===========================================================================
// Criterion — Dark-mode tokens; no hardcoded hex
// ===========================================================================

describe('TableComponent — token colours only', () => {
  it('when rendered, no hardcoded hex colours appear in inline element styles', async () => {
    const f = await setup();
    const hexPattern = /#[0-9a-fA-F]{3,8}\b/;
    const root = f.nativeElement as HTMLElement;
    const all: HTMLElement[] = [root, ...Array.from(root.querySelectorAll<HTMLElement>('*'))];
    for (const el of all) {
      expect(el.getAttribute('style') ?? '').not.toMatch(hexPattern);
    }
  });
});
