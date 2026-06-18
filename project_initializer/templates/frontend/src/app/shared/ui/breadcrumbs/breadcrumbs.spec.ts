import { Component } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { LucideIconConfig } from 'lucide-angular';

import { ICON_PROVIDER } from '../../../icons';
import { BreadcrumbsComponent, CrumbItem } from './breadcrumbs';

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

async function setup(items: CrumbItem[] = []): Promise<ComponentFixture<BreadcrumbsComponent>> {
  await TestBed.configureTestingModule({
    imports: [BreadcrumbsComponent],
    providers: [
      provideRouter([]),
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

  const f = TestBed.createComponent(BreadcrumbsComponent);
  f.componentRef.setInput('items', items);
  f.detectChanges();
  return f;
}

function nav(f: ComponentFixture<unknown>): HTMLElement {
  return f.nativeElement.querySelector('nav')!;
}

function ol(f: ComponentFixture<unknown>): HTMLElement {
  return f.nativeElement.querySelector('ol')!;
}

const THREE_CRUMBS: CrumbItem[] = [
  { label: 'Home', routerLink: '/' },
  { label: 'Settings', routerLink: '/settings' },
  { label: 'Profile' },
];

// ===========================================================================
// Criterion 1 — nav[aria-label="Breadcrumb"] wrapping an ordered list
// ===========================================================================

describe('BreadcrumbsComponent — nav landmark', () => {
  it('when breadcrumbs render, a <nav> element is present', async () => {
    const f = await setup(THREE_CRUMBS);
    expect(nav(f)).not.toBeNull();
  });

  it('when breadcrumbs render, the nav has aria-label="Breadcrumb"', async () => {
    const f = await setup(THREE_CRUMBS);
    expect(nav(f).getAttribute('aria-label')).toBe('Breadcrumb');
  });

  it('when breadcrumbs render, the list is an ordered list (<ol>)', async () => {
    const f = await setup(THREE_CRUMBS);
    expect(ol(f)).not.toBeNull();
    expect(ol(f).tagName.toLowerCase()).toBe('ol');
  });

  it('when three crumbs are provided, three <li> elements are rendered', async () => {
    const f = await setup(THREE_CRUMBS);
    const items = f.nativeElement.querySelectorAll('li');
    expect(items.length).toBe(3);
  });
});

// ===========================================================================
// Criterion 2 — Last crumb: aria-current="page"; not a link; separators hidden
// ===========================================================================

describe('BreadcrumbsComponent — aria-current="page" on last crumb', () => {
  it('when breadcrumbs render, an element with aria-current="page" is present', async () => {
    const f = await setup(THREE_CRUMBS);
    const current = f.nativeElement.querySelector('[aria-current="page"]');
    expect(current).not.toBeNull();
  });

  it('when breadcrumbs render, only the last crumb has aria-current="page"', async () => {
    const f = await setup(THREE_CRUMBS);
    const currents = f.nativeElement.querySelectorAll('[aria-current="page"]');
    expect(currents.length).toBe(1);
  });

  it('when breadcrumbs render, the last crumb label appears inside the aria-current element', async () => {
    const f = await setup(THREE_CRUMBS);
    const current = f.nativeElement.querySelector('[aria-current="page"]')!;
    expect(current.textContent?.trim()).toBe('Profile');
  });
});

describe('BreadcrumbsComponent — last crumb is not a link', () => {
  it('when breadcrumbs render, the aria-current element is not an <a>', async () => {
    const f = await setup(THREE_CRUMBS);
    const current = f.nativeElement.querySelector('[aria-current="page"]')!;
    expect(current.tagName.toLowerCase()).not.toBe('a');
  });

  it('when breadcrumbs render, non-last crumbs are anchor elements', async () => {
    const f = await setup(THREE_CRUMBS);
    const anchors: NodeListOf<HTMLAnchorElement> = f.nativeElement.querySelectorAll('a');
    // Three crumbs → first two are links (2 anchors)
    expect(anchors.length).toBe(2);
  });
});

describe('BreadcrumbsComponent — separators are aria-hidden', () => {
  it('when breadcrumbs render, separator icons carry aria-hidden="true"', async () => {
    const f = await setup(THREE_CRUMBS);
    const hiddenEls = f.nativeElement.querySelectorAll('[aria-hidden="true"]');
    expect(hiddenEls.length).toBeGreaterThan(0);
  });

  it('when three crumbs render, two separators are present', async () => {
    const f = await setup(THREE_CRUMBS);
    // Two separators between 3 crumbs — each is a lucide-icon with aria-hidden
    const separators = f.nativeElement.querySelectorAll('lucide-icon[aria-hidden="true"]');
    expect(separators.length).toBe(2);
  });

  it('when one crumb renders, no separator is present', async () => {
    const f = await setup([{ label: 'Home' }]);
    const separators = f.nativeElement.querySelectorAll('lucide-icon[aria-hidden="true"]');
    expect(separators.length).toBe(0);
  });
});

// ===========================================================================
// Criterion 3 — Signal input; dark-mode tokens
// ===========================================================================

describe('BreadcrumbsComponent — signal input', () => {
  it('when items input changes, the rendered crumbs update', async () => {
    const f = await setup([{ label: 'Alpha' }, { label: 'Beta' }]);
    expect(f.nativeElement.textContent).toContain('Alpha');
    expect(f.nativeElement.textContent).toContain('Beta');

    f.componentRef.setInput('items', [{ label: 'Gamma' }, { label: 'Delta' }]);
    f.detectChanges();

    expect(f.nativeElement.textContent).toContain('Gamma');
    expect(f.nativeElement.textContent).toContain('Delta');
    expect(f.nativeElement.textContent).not.toContain('Alpha');
  });

  it('when items is empty, no list items are rendered', async () => {
    const f = await setup([]);
    const lis = f.nativeElement.querySelectorAll('li');
    expect(lis.length).toBe(0);
  });
});

describe('BreadcrumbsComponent — dark-mode tokens', () => {
  it('when rendered, no hardcoded hex colours appear in inline element styles', async () => {
    const f = await setup(THREE_CRUMBS);
    const hexPattern = /#[0-9a-fA-F]{3,8}\b/;
    const root = f.nativeElement as HTMLElement;
    const all: HTMLElement[] = [root, ...Array.from(root.querySelectorAll<HTMLElement>('*'))];
    for (const el of all) {
      expect(el.getAttribute('style') ?? '').not.toMatch(hexPattern);
    }
  });

  it('when rendered, the ordered list carries a text-text-secondary token class', async () => {
    const f = await setup(THREE_CRUMBS);
    expect(ol(f).className).toContain('text-text-secondary');
  });

  it('when rendered, the current crumb carries a text-text token class', async () => {
    const f = await setup(THREE_CRUMBS);
    const current = f.nativeElement.querySelector('[aria-current="page"]')!;
    expect(current.className).toContain('text-text');
  });
});
