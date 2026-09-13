import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
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
      // Component-less routes: enough for RouterLink to resolve and navigate.
      provideRouter([
        { path: 'settings', children: [] },
        { path: '', children: [] },
      ]),
      ICON_PROVIDER,
      {
        provide: LucideIconConfig,
        useFactory: () => {
          const cfg = new LucideIconConfig();
          cfg.size = 24;
          cfg.strokeWidth = 2;
          return cfg;
        },
      },
    ],
  }).compileComponents();

  const f = TestBed.createComponent(BreadcrumbsComponent);
  f.componentRef.setInput('items', items);
  f.detectChanges();
  await f.whenStable();
  return f;
}

function nav(f: ComponentFixture<unknown>): HTMLElement {
  return f.nativeElement.querySelector('nav')!;
}

function ol(f: ComponentFixture<unknown>): HTMLElement {
  return f.nativeElement.querySelector('ol')!;
}

function links(f: ComponentFixture<unknown>): HTMLAnchorElement[] {
  return Array.from(f.nativeElement.querySelectorAll('a'));
}

function crumbs(f: ComponentFixture<unknown>): HTMLLIElement[] {
  return Array.from(f.nativeElement.querySelectorAll('li'));
}

/** The emulated-encapsulation stylesheet Angular injected for this component. */
function componentStylesheet(): string {
  const sheets = Array.from(document.head.querySelectorAll('style')).map((s) => s.textContent ?? '');
  return sheets.find((css) => css.includes('.crumb-link')) ?? '';
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

  it('when a label is given, the nav uses it as its distinct accessible name', async () => {
    const f = await setup(THREE_CRUMBS);
    f.componentRef.setInput('label', 'Dark preview breadcrumb');
    f.detectChanges();
    expect(nav(f).getAttribute('aria-label')).toBe('Dark preview breadcrumb');
  });

  it('when breadcrumbs render, the landmark label sits on the nav, not the host', async () => {
    const f = await setup(THREE_CRUMBS);
    expect((f.nativeElement as HTMLElement).hasAttribute('aria-label')).toBe(false);
  });

  it('when breadcrumbs render, the list is an ordered list (<ol>)', async () => {
    const f = await setup(THREE_CRUMBS);
    expect(ol(f)).not.toBeNull();
    expect(ol(f).tagName.toLowerCase()).toBe('ol');
  });

  it('when breadcrumbs render, the unstyled list keeps list semantics with role="list"', async () => {
    const f = await setup(THREE_CRUMBS);
    expect(ol(f).getAttribute('role')).toBe('list');
  });

  it('when three crumbs are provided, three <li> elements are rendered', async () => {
    const f = await setup(THREE_CRUMBS);
    expect(crumbs(f).length).toBe(3);
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

  it('when breadcrumbs render, the aria-current element is inside the last <li>', async () => {
    const f = await setup(THREE_CRUMBS);
    const lis = crumbs(f);
    expect(lis[lis.length - 1].querySelector('[aria-current="page"]')).not.toBeNull();
  });
});

describe('BreadcrumbsComponent — last crumb is not a link', () => {
  it('when breadcrumbs render, the aria-current element is not an <a>', async () => {
    const f = await setup(THREE_CRUMBS);
    const current = f.nativeElement.querySelector('[aria-current="page"]')!;
    expect(current.tagName.toLowerCase()).not.toBe('a');
  });

  it('when breadcrumbs render, the current crumb is not focusable', async () => {
    const f = await setup(THREE_CRUMBS);
    const current = f.nativeElement.querySelector('[aria-current="page"]') as HTMLElement;
    expect(current.hasAttribute('tabindex')).toBe(false);
    expect(current.hasAttribute('href')).toBe(false);
  });

  it('when breadcrumbs render, non-last crumbs are anchor elements', async () => {
    const f = await setup(THREE_CRUMBS);
    // Three crumbs → first two are links (2 anchors)
    expect(links(f).length).toBe(2);
  });
});

describe('BreadcrumbsComponent — ancestor links', () => {
  it('when breadcrumbs render, each link carries an href to its route (native keyboard activation)', async () => {
    const f = await setup(THREE_CRUMBS);
    expect(links(f).map((a) => a.getAttribute('href'))).toEqual(['/', '/settings']);
  });

  it('when breadcrumbs render, each link is named by its visible label only', async () => {
    const f = await setup(THREE_CRUMBS);
    const [home, settings] = links(f);
    expect(home.textContent?.trim()).toBe('Home');
    expect(settings.textContent?.trim()).toBe('Settings');
    expect(home.hasAttribute('aria-label')).toBe(false);
  });

  it('when an ancestor link is clicked, the router navigates to its route', async () => {
    const f = await setup(THREE_CRUMBS);
    const router = TestBed.inject(Router);

    links(f)[1].click();
    await f.whenStable();

    expect(router.url).toBe('/settings');
  });

  it('when two crumbs share a label, every crumb still renders', async () => {
    const f = await setup([
      { label: 'Docs', routerLink: '/' },
      { label: 'Docs', routerLink: '/settings' },
      { label: 'Docs' },
    ]);
    expect(crumbs(f).length).toBe(3);
  });
});

describe('BreadcrumbsComponent — ancestor without a route', () => {
  const NO_ROUTE: CrumbItem[] = [
    { label: 'Home', routerLink: '/' },
    { label: 'Archive' },
    { label: 'Profile' },
  ];

  it('when a middle crumb has no routerLink, it renders as text, not a link to the current page', async () => {
    const f = await setup(NO_ROUTE);
    const middle = crumbs(f)[1];
    expect(middle.querySelector('a')).toBeNull();
    expect(middle.querySelector('[href]')).toBeNull();
    expect(middle.textContent?.trim()).toBe('Archive');
    expect(links(f).map((a) => a.getAttribute('href'))).toEqual(['/']);
  });

  it('when a middle crumb has no routerLink, it is not marked as the current page', async () => {
    const f = await setup(NO_ROUTE);
    expect(crumbs(f)[1].querySelector('[aria-current]')).toBeNull();
    expect(f.nativeElement.querySelectorAll('[aria-current="page"]').length).toBe(1);
  });

  it('when a middle crumb has no routerLink, a separator still follows it', async () => {
    const f = await setup(NO_ROUTE);
    expect(crumbs(f)[1].querySelector('lucide-icon[aria-hidden="true"]')).not.toBeNull();
    expect(f.nativeElement.querySelectorAll('lucide-icon[aria-hidden="true"]').length).toBe(2);
  });
});

describe('BreadcrumbsComponent — pressed ripple', () => {
  it('when breadcrumbs render, each link hosts a ripple layer and the current crumb has none', async () => {
    const f = await setup(THREE_CRUMBS);
    for (const a of links(f)) {
      expect(a.querySelector('.crumb-ripple.mat-ripple')).not.toBeNull();
    }
    expect(f.nativeElement.querySelector('[aria-current="page"] .mat-ripple')).toBeNull();
  });

  it('when a link is pressed with a pointer, a ripple fades in inside the link', async () => {
    const f = await setup(THREE_CRUMBS);
    const [home] = links(f);
    home.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, buttons: 1, detail: 1 }));
    expect(home.querySelectorAll('.crumb-ripple .mat-ripple-element').length).toBe(1);
  });

  it('when a screen reader sends a fake mousedown, no ripple appears', async () => {
    const f = await setup(THREE_CRUMBS);
    const [home] = links(f);
    home.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, buttons: 0, detail: 0 }));
    expect(home.querySelectorAll('.mat-ripple-element').length).toBe(0);
  });

  it('when rendered, the ripple uses the content color at the pressed state-layer opacity', async () => {
    await setup(THREE_CRUMBS);
    expect(componentStylesheet()).toMatch(
      /--mat-ripple-color:[^;]*var\(--mat-sys-on-surface-variant\)[^;]*var\(--mat-sys-pressed-state-layer-opacity\)/,
    );
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

  it('when breadcrumbs render, separators follow their link inside the same <li>', async () => {
    const f = await setup(THREE_CRUMBS);
    const firstLi: HTMLElement = f.nativeElement.querySelector('li');
    const anchor = firstLi.querySelector('a')!;
    expect(anchor.nextElementSibling?.tagName.toLowerCase()).toBe('lucide-icon');
  });

  it('when breadcrumbs render, separator chevrons render at 18px', async () => {
    const f = await setup(THREE_CRUMBS);
    const svg = f.nativeElement.querySelector('lucide-icon svg') as SVGElement | null;
    expect(svg).not.toBeNull();
    expect(svg!.getAttribute('width')).toBe('18');
    expect(svg!.getAttribute('height')).toBe('18');
  });
});

// ===========================================================================
// Criterion 3 — Signal input; Material 3 tokens
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
    expect(crumbs(f).length).toBe(0);
  });
});

describe('BreadcrumbsComponent — Material 3 tokens', () => {
  it('when rendered, no hardcoded hex colours appear in inline element styles', async () => {
    const f = await setup(THREE_CRUMBS);
    const hexPattern = /#[0-9a-fA-F]{3,8}\b/;
    const root = f.nativeElement as HTMLElement;
    const all: HTMLElement[] = [root, ...Array.from(root.querySelectorAll<HTMLElement>('*'))];
    for (const el of all) {
      expect(el.getAttribute('style') ?? '').not.toMatch(hexPattern);
    }
  });

  it('when rendered, the stylesheet paints from --mat-sys-* roles with no color literals', async () => {
    await setup(THREE_CRUMBS);
    const css = componentStylesheet();
    expect(css).not.toBe('');
    expect(css).toContain('var(--mat-sys-on-surface-variant)');
    expect(css).toContain('var(--mat-sys-on-surface)');
    expect(css).toContain('var(--mat-sys-body-medium)');
    expect(css).not.toMatch(/#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(/);
  });

  it('when rendered, the link state layer uses the Material state-layer opacity tokens', async () => {
    await setup(THREE_CRUMBS);
    const css = componentStylesheet();
    expect(css).toContain('var(--mat-sys-hover-state-layer-opacity)');
    expect(css).toContain('var(--mat-sys-focus-state-layer-opacity)');
    expect(css).toContain('var(--mat-sys-pressed-state-layer-opacity)');
    expect(css).toMatch(/outline-offset:\s*2px/);
  });

  it('when rendered, crumb rows reserve a 48px target', async () => {
    await setup(THREE_CRUMBS);
    expect(componentStylesheet()).toMatch(/min-block-size:\s*48px/);
  });

  it('when rendered, the separator chevron mirrors in right-to-left layouts', async () => {
    await setup(THREE_CRUMBS);
    expect(componentStylesheet()).toMatch(/:dir\(rtl\)[^{]*\{[^}]*scaleX\(-1\)/);
  });
});
