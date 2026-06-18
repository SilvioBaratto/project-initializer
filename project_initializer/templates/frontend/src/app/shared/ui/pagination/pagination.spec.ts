import { Component } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { LucideIconConfig } from 'lucide-angular';

import { ICON_PROVIDER } from '../../../icons';
import { PaginationComponent } from './pagination';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function setup(page: number, total: number): Promise<ComponentFixture<PaginationComponent>> {
  await TestBed.configureTestingModule({
    imports: [PaginationComponent],
    providers: [
      ICON_PROVIDER,
      {
        provide: LucideIconConfig,
        useFactory: () => {
          const cfg = new LucideIconConfig();
          cfg.size = 16;
          cfg.strokeWidth = 1.5;
          return cfg;
        },
      },
    ],
  }).compileComponents();

  const f = TestBed.createComponent(PaginationComponent);
  f.componentRef.setInput('page', page);
  f.componentRef.setInput('total', total);
  f.detectChanges();
  return f;
}

function nav(f: ComponentFixture<unknown>): HTMLElement {
  return f.nativeElement.querySelector('nav')!;
}

function prevBtn(f: ComponentFixture<unknown>): HTMLButtonElement {
  return f.nativeElement.querySelector('[aria-label="Previous page"]')!;
}

function nextBtn(f: ComponentFixture<unknown>): HTMLButtonElement {
  return f.nativeElement.querySelector('[aria-label="Next page"]')!;
}

function currentPageBtn(f: ComponentFixture<unknown>): HTMLButtonElement {
  return f.nativeElement.querySelector('[aria-current="page"]')!;
}

function pageButtons(f: ComponentFixture<unknown>): HTMLButtonElement[] {
  const root = f.nativeElement as HTMLElement;
  return Array.from(root.querySelectorAll<HTMLButtonElement>('button[aria-label^="Page"]'));
}

// ===========================================================================
// Criterion — nav[aria-label]
// ===========================================================================

describe('PaginationComponent — nav landmark', () => {
  it('when rendered, a <nav> element is present', async () => {
    const f = await setup(1, 5);
    expect(nav(f)).not.toBeNull();
    expect(nav(f).tagName.toLowerCase()).toBe('nav');
  });

  it('when rendered, the nav carries an aria-label attribute', async () => {
    const f = await setup(1, 5);
    expect(nav(f).getAttribute('aria-label')).toBeTruthy();
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
});

// ===========================================================================
// Criterion — accessible prev/next controls
// ===========================================================================

describe('PaginationComponent — prev/next controls', () => {
  it('when rendered, a "Previous page" button is present', async () => {
    const f = await setup(2, 5);
    expect(prevBtn(f)).not.toBeNull();
  });

  it('when rendered, a "Next page" button is present', async () => {
    const f = await setup(2, 5);
    expect(nextBtn(f)).not.toBeNull();
  });

  it('when prev is clicked on page 2, pageChange emits 1', async () => {
    const f = await setup(2, 5);
    const emitted: number[] = [];
    f.componentInstance.pageChange.subscribe((p: number) => emitted.push(p));
    prevBtn(f).click();
    expect(emitted).toEqual([1]);
  });

  it('when next is clicked on page 2, pageChange emits 3', async () => {
    const f = await setup(2, 5);
    const emitted: number[] = [];
    f.componentInstance.pageChange.subscribe((p: number) => emitted.push(p));
    nextBtn(f).click();
    expect(emitted).toEqual([3]);
  });

  it('when a page button is clicked, pageChange emits that page number', async () => {
    const f = await setup(1, 5);
    const emitted: number[] = [];
    f.componentInstance.pageChange.subscribe((p: number) => emitted.push(p));
    pageButtons(f)[2].click(); // page 3
    expect(emitted).toContain(3);
  });
});

// ===========================================================================
// Criterion — ≥44px touch target
// ===========================================================================

describe('PaginationComponent — ≥44px touch target', () => {
  it('when rendered, page buttons carry a min-h-11 class', async () => {
    const f = await setup(1, 3);
    const btns = pageButtons(f);
    expect(btns.length).toBeGreaterThan(0);
    btns.forEach((btn) => {
      expect(btn.className).toContain('min-h-11');
    });
  });

  it('when rendered, prev button carries a min-h-11 class', async () => {
    const f = await setup(2, 5);
    expect(prevBtn(f).className).toContain('min-h-11');
  });

  it('when rendered, next button carries a min-h-11 class', async () => {
    const f = await setup(2, 5);
    expect(nextBtn(f).className).toContain('min-h-11');
  });
});

// ===========================================================================
// Criterion — bounds-aware disabled state
// ===========================================================================

describe('PaginationComponent — disabled state at bounds', () => {
  it('when page is 1, the prev button is disabled', async () => {
    const f = await setup(1, 5);
    expect(prevBtn(f).disabled).toBe(true);
  });

  it('when page is the last page, the next button is disabled', async () => {
    const f = await setup(5, 5);
    expect(nextBtn(f).disabled).toBe(true);
  });

  it('when page is interior, neither prev nor next is disabled', async () => {
    const f = await setup(3, 5);
    expect(prevBtn(f).disabled).toBe(false);
    expect(nextBtn(f).disabled).toBe(false);
  });

  it('when on the first page, clicking prev does not emit pageChange', async () => {
    const f = await setup(1, 5);
    const emitted: number[] = [];
    f.componentInstance.pageChange.subscribe((p: number) => emitted.push(p));
    f.componentInstance.onPrev();
    expect(emitted).toEqual([]);
  });

  it('when on the last page, clicking next does not emit pageChange', async () => {
    const f = await setup(5, 5);
    const emitted: number[] = [];
    f.componentInstance.pageChange.subscribe((p: number) => emitted.push(p));
    f.componentInstance.onNext();
    expect(emitted).toEqual([]);
  });
});

// ===========================================================================
// Criterion — dark-mode tokens; no hardcoded hex
// ===========================================================================

describe('PaginationComponent — token colours only', () => {
  it('when rendered, no hardcoded hex colours appear in inline element styles', async () => {
    const f = await setup(2, 5);
    const hexPattern = /#[0-9a-fA-F]{3,8}\b/;
    const root = f.nativeElement as HTMLElement;
    const all: HTMLElement[] = [root, ...Array.from(root.querySelectorAll<HTMLElement>('*'))];
    for (const el of all) {
      expect(el.getAttribute('style') ?? '').not.toMatch(hexPattern);
    }
  });
});
