import { Component, Type, signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HarnessLoader } from '@angular/cdk/testing';
import { TestbedHarnessEnvironment } from '@angular/cdk/testing/testbed';
import { MatButtonHarness } from '@angular/material/button/testing';

import { ICON_PROVIDER } from '../../../icons';
import { PaginationComponent } from './pagination';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function setup(page: number, total: number): Promise<ComponentFixture<PaginationComponent>> {
  await TestBed.configureTestingModule({
    imports: [PaginationComponent],
    providers: [ICON_PROVIDER],
  }).compileComponents();

  const f = TestBed.createComponent(PaginationComponent);
  f.componentRef.setInput('page', page);
  f.componentRef.setInput('total', total);
  f.detectChanges();
  return f;
}

function loaderFor(f: ComponentFixture<unknown>): HarnessLoader {
  return TestbedHarnessEnvironment.loader(f);
}

function button(loader: HarnessLoader, label: string): Promise<MatButtonHarness> {
  return loader.getHarness(MatButtonHarness.with({ selector: `[aria-label="${label}"]` }));
}

function nav(f: ComponentFixture<unknown>): HTMLElement {
  return f.nativeElement.querySelector('nav')!;
}

function el(f: ComponentFixture<unknown>, label: string): HTMLButtonElement {
  return f.nativeElement.querySelector(`[aria-label="${label}"]`)!;
}

function currentPageBtn(f: ComponentFixture<unknown>): HTMLButtonElement {
  return f.nativeElement.querySelector('[aria-current="page"]')!;
}

function pageButtons(f: ComponentFixture<unknown>): HTMLButtonElement[] {
  const root = f.nativeElement as HTMLElement;
  return Array.from(root.querySelectorAll<HTMLButtonElement>('button[aria-label^="Page"]'));
}

function pageNumbers(f: ComponentFixture<unknown>): number[] {
  return pageButtons(f).map((b) => Number(b.textContent?.trim()));
}

function collect(f: ComponentFixture<PaginationComponent>): number[] {
  const emitted: number[] = [];
  f.componentInstance.pageChange.subscribe((p: number) => emitted.push(p));
  return emitted;
}

/** Last value a top-level style rule matching `node` declares for `property` ('' when none). */
function declaredValue(node: Element, property: string): string {
  let value = '';
  for (const sheet of Array.from(document.styleSheets)) {
    let rules: CSSRuleList;
    try {
      rules = sheet.cssRules;
    } catch {
      continue;
    }
    for (const rule of Array.from(rules)) {
      if (!(rule instanceof CSSStyleRule)) continue;
      let matches = false;
      try {
        matches = node.matches(rule.selectorText);
      } catch {
        // Selectors jsdom can't parse (for example :dir()) don't apply to this check.
      }
      const declared = matches ? rule.style.getPropertyValue(property).trim() : '';
      if (declared) value = declared;
    }
  }
  return value;
}

// Host that feeds pageChange back into [page], like a real consumer.
@Component({
  imports: [PaginationComponent],
  template: `
    <button type="button" id="outside">Outside</button>
    <ui-pagination [page]="page()" [total]="total()" (pageChange)="page.set($event)" />
  `,
})
class HostComponent {
  readonly page = signal(1);
  readonly total = signal(5);
}

// Host that ignores pageChange: only its own code moves the page (a query param, a data reload).
@Component({
  imports: [PaginationComponent],
  template: `
    <button type="button" id="outside">Outside</button>
    <ui-pagination [page]="page()" [total]="total()" />
  `,
})
class IgnoringHostComponent {
  readonly page = signal(1);
  readonly total = signal(5);
}

async function setupHost<T extends HostComponent | IgnoringHostComponent>(
  page: number,
  total: number,
  host: Type<T> = HostComponent as Type<T>,
): Promise<ComponentFixture<T>> {
  await TestBed.configureTestingModule({
    imports: [host],
    providers: [ICON_PROVIDER],
  }).compileComponents();

  const f = TestBed.createComponent(host);
  f.componentInstance.page.set(page);
  f.componentInstance.total.set(total);
  f.detectChanges();
  await f.whenStable();
  return f;
}

async function render(f: ComponentFixture<unknown>): Promise<void> {
  f.detectChanges();
  await f.whenStable();
}

function outsideButton(f: ComponentFixture<unknown>): HTMLButtonElement {
  return (f.nativeElement as HTMLElement).querySelector<HTMLButtonElement>('#outside')!;
}

// ===========================================================================
// Criterion — nav[aria-label] and list semantics
// ===========================================================================

describe('PaginationComponent — nav landmark', () => {
  it('when rendered, a <nav> element is present', async () => {
    const f = await setup(1, 5);
    expect(nav(f)).not.toBeNull();
    expect(nav(f).tagName.toLowerCase()).toBe('nav');
  });

  it('when no label is given, the nav is labelled "Pagination" without the role word', async () => {
    const f = await setup(1, 5);
    expect(nav(f).getAttribute('aria-label')).toBe('Pagination');
  });

  it('when a label is given, the nav uses it so two paginators on a view stay distinct', async () => {
    const f = await setup(1, 5);
    f.componentRef.setInput('label', 'Results pages below the table');
    f.detectChanges();
    expect(nav(f).getAttribute('aria-label')).toBe('Results pages below the table');
  });

  it('when rendered, the unstyled list keeps role="list"', async () => {
    const f = await setup(1, 5);
    expect(nav(f).querySelector('ul')?.getAttribute('role')).toBe('list');
  });
});

// ===========================================================================
// Criterion — aria-current="page" on the active page
// ===========================================================================

describe('PaginationComponent — aria-current="page"', () => {
  it('when page is 1, the button for page 1 has aria-current="page"', async () => {
    const f = await setup(1, 5);
    expect(currentPageBtn(f)).not.toBeNull();
    expect(currentPageBtn(f).textContent?.trim()).toBe('1');
  });

  it('when page is 3, the button for page 3 has aria-current="page"', async () => {
    const f = await setup(3, 5);
    expect(currentPageBtn(f).textContent?.trim()).toBe('3');
  });

  it('when rendered, exactly one button has aria-current="page"', async () => {
    const f = await setup(2, 5);
    const currents = f.nativeElement.querySelectorAll('[aria-current="page"]');
    expect(currents.length).toBe(1);
  });

  it('when page changes, aria-current moves to the new page button', async () => {
    const f = await setup(1, 5);
    f.componentRef.setInput('page', 4);
    f.detectChanges();
    expect(currentPageBtn(f).textContent?.trim()).toBe('4');
  });

  it('when rendered, the current page is a tonal button and other pages are text buttons', async () => {
    const f = await setup(2, 5);
    const loader = loaderFor(f);
    expect(await (await button(loader, 'Page 2')).getAppearance()).toBe('tonal');
    expect(await (await button(loader, 'Page 1')).getAppearance()).toBe('text');
    expect(await (await button(loader, 'Page 3')).getAppearance()).toBe('text');
  });

  it('when page changes, the tonal appearance follows the current page', async () => {
    const f = await setup(2, 5);
    f.componentRef.setInput('page', 3);
    f.detectChanges();
    const loader = loaderFor(f);
    expect(await (await button(loader, 'Page 3')).getAppearance()).toBe('tonal');
    expect(await (await button(loader, 'Page 2')).getAppearance()).toBe('text');
  });

  it('when rendered, the current page also gets the prominent label weight, a cue beyond its fill color', async () => {
    const f = await setup(2, 5);
    const weightToken = '--mat-button-tonal-label-text-weight';
    expect(declaredValue(currentPageBtn(f), weightToken)).toBe(
      'var(--mat-sys-label-large-weight-prominent)',
    );
    expect(declaredValue(el(f, 'Page 3'), weightToken)).toBe('');
  });

  it('when page changes, the prominent label weight follows the current page', async () => {
    const f = await setup(2, 5);
    f.componentRef.setInput('page', 3);
    f.detectChanges();
    const weightToken = '--mat-button-tonal-label-text-weight';
    expect(declaredValue(el(f, 'Page 3'), weightToken)).toBe(
      'var(--mat-sys-label-large-weight-prominent)',
    );
    expect(declaredValue(el(f, 'Page 2'), weightToken)).toBe('');
  });

  it('when the current page button is clicked, pageChange does not emit', async () => {
    const f = await setup(2, 5);
    const emitted = collect(f);
    await (await button(loaderFor(f), 'Page 2')).click();
    expect(emitted).toEqual([]);
  });
});

// ===========================================================================
// Criterion — accessible first/prev/next/last controls
// ===========================================================================

describe('PaginationComponent — directional controls', () => {
  it('when rendered, first, previous, next and last page buttons are present', async () => {
    const f = await setup(2, 5);
    for (const label of ['First page', 'Previous page', 'Next page', 'Last page']) {
      expect(el(f, label)).not.toBeNull();
    }
  });

  it('when rendered, directional controls are Material icon buttons', async () => {
    const f = await setup(2, 5);
    const loader = loaderFor(f);
    for (const label of ['First page', 'Previous page', 'Next page', 'Last page']) {
      expect(await (await button(loader, label)).getVariant()).toBe('icon');
    }
  });

  it('when rendered, the chevron icons are hidden from assistive technology', async () => {
    const f = await setup(2, 5);
    const icons = Array.from((f.nativeElement as HTMLElement).querySelectorAll('lucide-icon'));
    expect(icons.length).toBe(4);
    icons.forEach((icon) => expect(icon.getAttribute('aria-hidden')).toBe('true'));
  });

  it('when prev is clicked on page 2, pageChange emits 1', async () => {
    const f = await setup(2, 5);
    const emitted = collect(f);
    await (await button(loaderFor(f), 'Previous page')).click();
    expect(emitted).toEqual([1]);
  });

  it('when next is clicked on page 2, pageChange emits 3', async () => {
    const f = await setup(2, 5);
    const emitted = collect(f);
    await (await button(loaderFor(f), 'Next page')).click();
    expect(emitted).toEqual([3]);
  });

  it('when first is clicked on page 4, pageChange emits 1', async () => {
    const f = await setup(4, 5);
    const emitted = collect(f);
    await (await button(loaderFor(f), 'First page')).click();
    expect(emitted).toEqual([1]);
  });

  it('when last is clicked on page 2, pageChange emits the total', async () => {
    const f = await setup(2, 5);
    const emitted = collect(f);
    await (await button(loaderFor(f), 'Last page')).click();
    expect(emitted).toEqual([5]);
  });

  it('when a page button is clicked, pageChange emits that page number', async () => {
    const f = await setup(1, 5);
    const emitted = collect(f);
    await (await button(loaderFor(f), 'Page 3')).click();
    expect(emitted).toEqual([3]);
  });

  it('when rendered, every control is a native <button type="button"> in the tab order (keyboard-activatable)', async () => {
    const f = await setup(2, 5);
    const controls = Array.from(nav(f).querySelectorAll<HTMLElement>('button, [role="button"], a'));
    expect(controls.length).toBe(9);
    controls.forEach((control) => {
      expect(control.tagName.toLowerCase()).toBe('button');
      expect(control.getAttribute('type')).toBe('button');
      expect(control.tabIndex).toBeGreaterThanOrEqual(0);
    });
  });
});

// ===========================================================================
// Criterion — 48px touch target
// ===========================================================================

describe('PaginationComponent — 48px touch target', () => {
  it('when rendered, every page button renders Material\'s 48px touch target', async () => {
    const f = await setup(1, 3);
    const btns = pageButtons(f);
    expect(btns.length).toBe(3);
    btns.forEach((btn) => {
      expect(btn.querySelector('.mat-mdc-button-touch-target')).not.toBeNull();
    });
  });

  it('when rendered, every directional button renders Material\'s 48px touch target', async () => {
    const f = await setup(2, 5);
    for (const label of ['First page', 'Previous page', 'Next page', 'Last page']) {
      expect(el(f, label).querySelector('.mat-mdc-button-touch-target')).not.toBeNull();
    }
  });
});

// ===========================================================================
// Criterion — bounds-aware disabled state
// ===========================================================================

describe('PaginationComponent — disabled state at bounds', () => {
  it('when page is 1, the first and prev buttons are disabled', async () => {
    const f = await setup(1, 5);
    const loader = loaderFor(f);
    expect(await (await button(loader, 'First page')).isDisabled()).toBe(true);
    expect(await (await button(loader, 'Previous page')).isDisabled()).toBe(true);
    expect(el(f, 'Previous page').disabled).toBe(true);
  });

  it('when page is the last page, the next and last buttons are disabled', async () => {
    const f = await setup(5, 5);
    const loader = loaderFor(f);
    expect(await (await button(loader, 'Next page')).isDisabled()).toBe(true);
    expect(await (await button(loader, 'Last page')).isDisabled()).toBe(true);
    expect(el(f, 'Next page').disabled).toBe(true);
  });

  it('when page is interior, no directional button is disabled', async () => {
    const f = await setup(3, 5);
    const loader = loaderFor(f);
    for (const label of ['First page', 'Previous page', 'Next page', 'Last page']) {
      expect(await (await button(loader, label)).isDisabled()).toBe(false);
    }
  });

  it('when on the first page, prev and first do not emit pageChange', async () => {
    const f = await setup(1, 5);
    const emitted = collect(f);
    f.componentInstance.onPrev();
    f.componentInstance.onFirst();
    expect(emitted).toEqual([]);
  });

  it('when on the last page, next and last do not emit pageChange', async () => {
    const f = await setup(5, 5);
    const emitted = collect(f);
    f.componentInstance.onNext();
    f.componentInstance.onLast();
    expect(emitted).toEqual([]);
  });
});

// ===========================================================================
// Criterion — focus never falls off a button that disables at a bound
// ===========================================================================

describe('PaginationComponent — focus at bounds', () => {
  it('when next reaches the last page, focus moves to the previous page button', async () => {
    const f = await setupHost(4, 5);
    const next = el(f, 'Next page');
    next.focus();
    next.click();
    await render(f);
    expect(f.componentInstance.page()).toBe(5);
    expect(document.activeElement).toBe(el(f, 'Previous page'));
  });

  it('when last is activated, focus moves to the previous page button', async () => {
    const f = await setupHost(2, 5);
    const last = el(f, 'Last page');
    last.focus();
    last.click();
    await render(f);
    expect(f.componentInstance.page()).toBe(5);
    expect(document.activeElement).toBe(el(f, 'Previous page'));
  });

  it('when prev reaches the first page, focus moves to the next page button', async () => {
    const f = await setupHost(2, 5);
    const prev = el(f, 'Previous page');
    prev.focus();
    prev.click();
    await render(f);
    expect(f.componentInstance.page()).toBe(1);
    expect(document.activeElement).toBe(el(f, 'Next page'));
  });

  it('when next stays inside the range, focus stays on the next page button', async () => {
    const f = await setupHost(2, 5);
    const next = el(f, 'Next page');
    next.focus();
    next.click();
    await render(f);
    expect(f.componentInstance.page()).toBe(3);
    expect(document.activeElement).toBe(next);
  });

  it('when a page button is clicked, focus stays on that (now current) page button', async () => {
    const f = await setupHost(1, 5);
    const page3 = el(f, 'Page 3');
    page3.focus();
    page3.click();
    await render(f);
    expect(currentPageBtn(f)).toBe(page3);
    expect(document.activeElement).toBe(page3);
  });

  it('when focus has moved elsewhere before the page updates, focus is not taken back', async () => {
    const f = await setupHost(2, 5);
    const last = el(f, 'Last page');
    last.focus();
    last.click();
    const outside = outsideButton(f);
    outside.focus();
    await render(f);
    expect(f.componentInstance.page()).toBe(5);
    expect(document.activeElement).toBe(outside);
  });

  it('when the consumer ignores pageChange and later moves to the last page with focus on body, focus stays on body', async () => {
    const f = await setupHost(4, 5, IgnoringHostComponent);
    const next = el(f, 'Next page');
    next.focus();
    next.click();
    await render(f);
    expect(f.componentInstance.page()).toBe(4);
    next.blur();
    expect(document.activeElement).toBe(document.body);

    f.componentInstance.page.set(5);
    await render(f);
    expect(document.activeElement).toBe(document.body);
  });

  it('when the consumer ignores pageChange and focus visits another control first, a later move to the last page leaves focus alone', async () => {
    const f = await setupHost(4, 5, IgnoringHostComponent);
    const next = el(f, 'Next page');
    next.focus();
    next.click();
    await render(f);
    const outside = outsideButton(f);
    outside.focus();
    outside.blur();

    f.componentInstance.page.set(5);
    await render(f);
    expect(document.activeElement).toBe(document.body);
  });

  it('when the edge is requested from code while focus is outside the paginator, reaching it never moves focus', async () => {
    const f = await setupHost(4, 5, IgnoringHostComponent);
    const pagination = f.debugElement.children
      .find((d) => d.name === 'ui-pagination')!.componentInstance as PaginationComponent;
    expect(document.activeElement).toBe(document.body);
    pagination.onNext();
    await render(f);

    f.componentInstance.page.set(5);
    await render(f);
    expect(document.activeElement).toBe(document.body);
  });

  it('when the consumer answers with a different page, a later move to the edge leaves focus alone', async () => {
    const f = await setupHost(4, 5, IgnoringHostComponent);
    const next = el(f, 'Next page');
    next.focus();
    next.click();
    f.componentInstance.page.set(3);
    await render(f);
    next.blur();

    f.componentInstance.page.set(5);
    await render(f);
    expect(document.activeElement).toBe(document.body);
  });
});

// ===========================================================================
// Criterion — page window for long ranges
// ===========================================================================

describe('PaginationComponent — page window', () => {
  it('when there are seven pages or fewer, every page has a button and there is no gap', async () => {
    const f = await setup(4, 7);
    expect(pageNumbers(f)).toEqual([1, 2, 3, 4, 5, 6, 7]);
    expect(f.nativeElement.querySelectorAll('.gap').length).toBe(0);
  });

  it('when the current page is near the start of a long range, the window hugs the start', async () => {
    const f = await setup(1, 20);
    expect(pageNumbers(f)).toEqual([1, 2, 3, 4, 5, 20]);
    expect(f.nativeElement.querySelectorAll('.gap').length).toBe(1);
  });

  it('when the current page is in the middle of a long range, gaps surround its neighbours', async () => {
    const f = await setup(10, 20);
    expect(pageNumbers(f)).toEqual([1, 9, 10, 11, 20]);
    expect(f.nativeElement.querySelectorAll('.gap').length).toBe(2);
    expect(currentPageBtn(f).textContent?.trim()).toBe('10');
  });

  it('when the current page is near the end of a long range, the window hugs the end', async () => {
    const f = await setup(20, 20);
    expect(pageNumbers(f)).toEqual([1, 16, 17, 18, 19, 20]);
  });

  it('when rendered, gaps are hidden from assistive technology', async () => {
    const f = await setup(10, 20);
    const gaps = Array.from((f.nativeElement as HTMLElement).querySelectorAll('.gap'));
    gaps.forEach((gap) => expect(gap.getAttribute('aria-hidden')).toBe('true'));
  });

  it('when rendered, the pages signal exposes the visible page numbers', async () => {
    const f = await setup(10, 20);
    expect(f.componentInstance.pages()).toEqual([1, 9, 10, 11, 20]);
  });
});

// ===========================================================================
// Criterion — status for narrow paginators and screen readers
// ===========================================================================

describe('PaginationComponent — page status', () => {
  it('when rendered, the status reads "Page 2 of 5" in a polite live region', async () => {
    const f = await setup(2, 5);
    const status = (f.nativeElement as HTMLElement).querySelector('.status')!;
    expect(status.textContent?.trim()).toBe('Page 2 of 5');
    expect(status.getAttribute('aria-live')).toBe('polite');
  });

  it('when page changes, the status follows it', async () => {
    const f = await setup(2, 5);
    f.componentRef.setInput('page', 3);
    f.detectChanges();
    const status = (f.nativeElement as HTMLElement).querySelector('.status')!;
    expect(status.textContent?.trim()).toBe('Page 3 of 5');
  });

  it('when rendered, every page button is named "Page N" after its own number', async () => {
    const f = await setup(10, 20);
    expect(pageButtons(f).map((b) => b.getAttribute('aria-label'))).toEqual([
      'Page 1',
      'Page 9',
      'Page 10',
      'Page 11',
      'Page 20',
    ]);
  });
});

// ===========================================================================
// Criterion — the row adapts to the paginator's own width, not the window's
// ===========================================================================

/** The component's own stylesheet, as injected into the document. */
function paginationStyles(): string {
  return Array.from(document.querySelectorAll('style'))
    .map((style) => style.textContent ?? '')
    .filter((css) => css.includes('.page-slot'))
    .join('\n');
}

/** Body of the at-rule whose prelude matches `prelude`, matched by brace depth so nested rules stay inside. */
function atRuleBody(css: string, prelude: RegExp): string {
  const start = css.search(prelude);
  if (start < 0) return '';
  const open = css.indexOf('{', start);
  let depth = 0;
  for (let i = open; i < css.length; i++) {
    if (css[i] === '{') depth++;
    if (css[i] === '}' && --depth === 0) return css.slice(open + 1, i);
  }
  return '';
}

describe('PaginationComponent — width-driven layout', () => {
  it('when every page fits, the row holds 11 slots, the widest row the 528px query budgets for (11 × 48px)', async () => {
    const f = await setup(4, 7);
    expect((f.nativeElement as HTMLElement).querySelectorAll('.slot').length).toBe(11);
  });

  it('when the stylesheet is loaded, the host is an inline-size query container named pagination', async () => {
    await setup(2, 5);
    expect(paginationStyles()).toMatch(/container:\s*pagination\s*\/\s*inline-size/);
  });

  it('when the paginator is narrower than its widest row, page numbers and gaps step aside for the status', async () => {
    await setup(2, 5);
    const narrow = atRuleBody(paginationStyles(), /@container\s+pagination\s*\(max-width:\s*527\.98px\)/);
    expect(narrow).toMatch(/\.page-slot[^{]*,\s*\.gap[^{]*\{\s*display:\s*none/);
  });

  it('when the paginator has room for the whole row, the status is only visually hidden', async () => {
    await setup(2, 5);
    const wide = atRuleBody(paginationStyles(), /@container\s+pagination\s*\(min-width:\s*528px\)/);
    expect(wide).toMatch(/\.status[^{]*\{[^}]*clip-path:\s*inset\(50%\)/);
    expect(wide).not.toMatch(/display:\s*none/);
  });

  it('when the stylesheet is loaded, no window media query decides the layout', async () => {
    await setup(2, 5);
    const css = paginationStyles();
    expect(css).not.toBe('');
    expect(css).not.toMatch(/@media[^{]*width/);
  });
});

// ===========================================================================
// Criterion — token colours only
// ===========================================================================

describe('PaginationComponent — token colours only', () => {
  it('when rendered, no hardcoded hex colours appear in inline element styles', async () => {
    const f = await setup(2, 5);
    const hexPattern = /#[0-9a-fA-F]{3,8}\b/;
    const root = f.nativeElement as HTMLElement;
    const all: HTMLElement[] = [root, ...Array.from(root.querySelectorAll<HTMLElement>('*'))];
    for (const node of all) {
      expect(node.getAttribute('style') ?? '').not.toMatch(hexPattern);
    }
  });
});
