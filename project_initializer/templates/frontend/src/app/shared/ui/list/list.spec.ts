import { Component } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';

import { ListComponent } from './list';

// ---------------------------------------------------------------------------
// Host wrapper for content projection tests
// ---------------------------------------------------------------------------

@Component({
  imports: [ListComponent],
  template: `
    <ui-list [variant]="variant">
      <li>Item A</li>
      <li>Item B</li>
      <li>Item C</li>
    </ui-list>
  `,
})
class HostComponent {
  variant: 'default' | 'divided' | 'striped' = 'default';
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function setupHost(
  variant: 'default' | 'divided' | 'striped' = 'default',
): Promise<ComponentFixture<HostComponent>> {
  await TestBed.configureTestingModule({
    imports: [HostComponent],
  }).compileComponents();

  const f = TestBed.createComponent(HostComponent);
  f.componentInstance.variant = variant;
  f.detectChanges();
  return f;
}

async function setupDirect(): Promise<ComponentFixture<ListComponent>> {
  await TestBed.configureTestingModule({
    imports: [ListComponent],
  }).compileComponents();

  const f = TestBed.createComponent(ListComponent);
  f.detectChanges();
  return f;
}

function ul(f: ComponentFixture<unknown>): HTMLElement {
  return f.nativeElement.querySelector('ul')!;
}

// ===========================================================================
// Criterion — renders as <ul> with role="list"
// ===========================================================================

describe('ListComponent — semantic element', () => {
  it('when created, the component renders without error', async () => {
    const f = await setupDirect();
    expect(f.componentInstance).toBeTruthy();
  });

  it('when rendered, a <ul> element is present', async () => {
    const f = await setupHost();
    expect(ul(f)).not.toBeNull();
    expect(ul(f).tagName.toLowerCase()).toBe('ul');
  });

  it('when rendered, the <ul> carries role="list"', async () => {
    const f = await setupHost();
    expect(ul(f).getAttribute('role')).toBe('list');
  });

  it('when content is projected, the items appear inside the list', async () => {
    const f = await setupHost();
    expect(f.nativeElement.textContent).toContain('Item A');
    expect(f.nativeElement.textContent).toContain('Item B');
    expect(f.nativeElement.textContent).toContain('Item C');
  });
});

// ===========================================================================
// Criterion — divided variant via token (border-border)
// ===========================================================================

describe('ListComponent — divided variant', () => {
  it('when variant is divided, the list carries a divide-y class', async () => {
    const f = await setupHost('divided');
    expect(ul(f).className).toContain('divide-y');
  });

  it('when variant is divided, the divider colour uses the border token class', async () => {
    const f = await setupHost('divided');
    // The border token class is `divide-border` — maps to --color-border
    expect(ul(f).className).toContain('divide-border');
  });

  it('when variant is default, no divide-y class is applied', async () => {
    const f = await setupHost('default');
    expect(ul(f).className).not.toContain('divide-y');
  });
});

// ===========================================================================
// Criterion — striped variant via token (surface-inset)
// ===========================================================================

describe('ListComponent — striped variant', () => {
  it('when variant is striped, the list carries a class referencing bg-surface-inset', async () => {
    const f = await setupHost('striped');
    // The striped pattern applies bg-surface-inset to odd rows via a variant class.
    // We accept either a direct class or a CSS-nth-child selector class on the <ul>.
    expect(ul(f).className).toContain('surface-inset');
  });

  it('when variant is default, no surface-inset stripe class is applied', async () => {
    const f = await setupHost('default');
    // Only the base border-on-raised is present; no inset stripe
    const hasStripe = ul(f).className.includes('surface-inset')
      && ul(f).className.includes('odd');
    expect(hasStripe).toBe(false);
  });
});

// ===========================================================================
// Criterion — Signal input reactivity
// ===========================================================================

describe('ListComponent — signal input reactivity', () => {
  it('when variant input changes from default to divided, the divided classes are applied', async () => {
    await TestBed.configureTestingModule({ imports: [ListComponent] }).compileComponents();
    const f = TestBed.createComponent(ListComponent);
    f.detectChanges();

    const listEl: HTMLElement = f.nativeElement.querySelector('ul')!;
    expect(listEl.className).not.toContain('divide-y');

    f.componentRef.setInput('variant', 'divided');
    f.detectChanges();
    expect(listEl.className).toContain('divide-y');
  });
});

// ===========================================================================
// Criterion — Dark-mode tokens; no hardcoded hex
// ===========================================================================

describe('ListComponent — token colours only', () => {
  it('when rendered with divided variant, no hardcoded hex colours appear in inline styles', async () => {
    const f = await setupHost('divided');
    const hexPattern = /#[0-9a-fA-F]{3,8}\b/;
    const root = f.nativeElement as HTMLElement;
    const all: HTMLElement[] = [root, ...Array.from(root.querySelectorAll<HTMLElement>('*'))];
    for (const el of all) {
      expect(el.getAttribute('style') ?? '').not.toMatch(hexPattern);
    }
  });

  it('when rendered with striped variant, no hardcoded hex colours appear in inline styles', async () => {
    const f = await setupHost('striped');
    const hexPattern = /#[0-9a-fA-F]{3,8}\b/;
    const root = f.nativeElement as HTMLElement;
    const all: HTMLElement[] = [root, ...Array.from(root.querySelectorAll<HTMLElement>('*'))];
    for (const el of all) {
      expect(el.getAttribute('style') ?? '').not.toMatch(hexPattern);
    }
  });
});
