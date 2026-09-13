import { Component } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { TestbedHarnessEnvironment } from '@angular/cdk/testing/testbed';
import { MatToolbarHarness } from '@angular/material/toolbar/testing';

import { NavbarComponent } from './navbar';

@Component({
  imports: [NavbarComponent],
  template: `
    <app-navbar>
      <span navbarBrand>My App</span>
      <button navbarActions type="button" aria-label="Settings">S</button>
    </app-navbar>
  `,
})
class HostComponent {}

interface Rendered {
  fixture: ComponentFixture<HostComponent>;
  toolbar: MatToolbarHarness;
}

async function setup(): Promise<Rendered> {
  await TestBed.configureTestingModule({ imports: [HostComponent] }).compileComponents();
  const fixture = TestBed.createComponent(HostComponent);
  fixture.detectChanges();
  const toolbar = await TestbedHarnessEnvironment.loader(fixture).getHarness(MatToolbarHarness);
  return { fixture, toolbar };
}

function navbarHost(f: ComponentFixture<unknown>): HTMLElement {
  return f.nativeElement.querySelector('app-navbar')!;
}

function header(f: ComponentFixture<unknown>): HTMLElement {
  return f.nativeElement.querySelector('header')!;
}

function toolbarEl(f: ComponentFixture<unknown>): HTMLElement {
  return f.nativeElement.querySelector('mat-toolbar')!;
}

function slot(f: ComponentFixture<unknown>, name: 'brand' | 'actions'): HTMLElement {
  return header(f).querySelector(`.navbar-${name}`)!;
}

/** Text of every stylesheet containing `marker` (component styles land in <head> while the fixture lives). */
function styleTextContaining(marker: string): string {
  return Array.from(document.querySelectorAll('style'))
    .map((style) => style.textContent ?? '')
    .filter((text) => text.includes(marker))
    .join('\n');
}

/** The navbar's own stylesheet. */
function navbarStyleText(): string {
  return styleTextContaining('.navbar-brand');
}

/** Angular Material's toolbar stylesheet (unencapsulated, so it is recognisable by its class names). */
function toolbarStyleText(): string {
  return styleTextContaining('.mat-toolbar-single-row');
}

/** Declarations of the rule for `.className`, allowing the emulated-encapsulation attribute after it. */
function ruleBody(css: string, className: string): string {
  const rule = new RegExp(`\\.${className}(?:\\[[^\\]]+\\])*\\s*\\{([^}]*)\\}`).exec(css);
  if (!rule) {
    throw new Error(`No .${className} rule in the navbar stylesheet`);
  }
  return rule[1];
}

// ── safe-area insets ─────────────────────────────────────────────────────────

describe('NavbarComponent — safe-area insets', () => {
  it('when the navbar renders, its own stylesheet pads the header by the top and side safe-area insets', async () => {
    const { fixture } = await setup();
    // Component CSS, not global utility classes.
    expect(Array.from(header(fixture).classList)).toEqual(['navbar']);
    expect(ruleBody(navbarStyleText(), 'navbar')).toMatch(
      /padding:\s*env\(safe-area-inset-top\) env\(safe-area-inset-right\) 0 env\(safe-area-inset-left\)/,
    );
  });

  it('when the navbar renders, the safe-area padding sits on the header, outside the toolbar row', async () => {
    const { fixture } = await setup();
    // Padding on mat-toolbar would count inside its own row height instead of adding to it.
    expect(ruleBody(navbarStyleText(), 'navbar-toolbar')).not.toMatch(/safe-area-inset/);
    expect(header(fixture).contains(toolbarEl(fixture))).toBe(true);
  });
});

// ── header landmark ──────────────────────────────────────────────────────────

describe('NavbarComponent — header landmark', () => {
  it('when rendered, a single header element is the outermost element of the host', async () => {
    const { fixture } = await setup();
    expect(navbarHost(fixture).firstElementChild?.tagName).toBe('HEADER');
    expect(fixture.nativeElement.querySelectorAll('header').length).toBe(1);
  });

  it('when rendered, the header keeps its implicit landmark role', async () => {
    const { fixture } = await setup();
    expect(header(fixture).getAttribute('role')).toBeNull();
  });
});

// ── Material top app bar ─────────────────────────────────────────────────────

describe('NavbarComponent — Material top app bar', () => {
  it('when rendered, the bar is a single-row mat-toolbar', async () => {
    const { toolbar } = await setup();
    expect(await toolbar.hasMultipleRows()).toBe(false);
  });

  it('when rendered, the bar as a whole is not focusable and claims no widget role', async () => {
    const { fixture } = await setup();
    // States belong to the projected actions, never to the whole app bar.
    expect(toolbarEl(fixture).getAttribute('tabindex')).toBeNull();
    expect(toolbarEl(fixture).getAttribute('role')).toBeNull();
  });
});

// ── brand slot ───────────────────────────────────────────────────────────────

describe('NavbarComponent — brand projection', () => {
  it('when brand content is projected, it appears inside the header', async () => {
    const { fixture } = await setup();
    expect(header(fixture).textContent).toContain('My App');
  });

  it('when brand content is projected, it renders in the toolbar leading slot', async () => {
    const { fixture, toolbar } = await setup();
    const [rowText] = await toolbar.getRowsAsText();
    expect(rowText).toContain('My App');
    expect(slot(fixture, 'brand').textContent).toContain('My App');
  });

  it('when rendered, the brand slot precedes the actions slot in DOM order', async () => {
    const { fixture } = await setup();
    const position = slot(fixture, 'brand').compareDocumentPosition(slot(fixture, 'actions'));
    expect(position & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });
});

// ── actions slot ─────────────────────────────────────────────────────────────

describe('NavbarComponent — actions projection', () => {
  it('when actions content is projected, it appears inside the header', async () => {
    const { fixture } = await setup();
    const btn = header(fixture).querySelector('button[aria-label="Settings"]');
    expect(btn).not.toBeNull();
  });

  it('when actions content is projected, it renders in the trailing slot, not the brand slot', async () => {
    const { fixture } = await setup();
    expect(slot(fixture, 'actions').querySelector('button[aria-label="Settings"]')).not.toBeNull();
    expect(slot(fixture, 'brand').querySelector('button')).toBeNull();
  });
});

// ── M3 tokens ────────────────────────────────────────────────────────────────

describe('NavbarComponent — M3 tokens', () => {
  it('when rendered, no hardcoded hex colours appear in inline element styles', async () => {
    const { fixture } = await setup();
    const hexPattern = /#[0-9a-fA-F]{3,8}\b/;
    const root = navbarHost(fixture);
    const els: HTMLElement[] = [root, ...Array.from(root.querySelectorAll<HTMLElement>('*'))];
    for (const el of els) {
      expect(el.getAttribute('style') ?? '').not.toMatch(hexPattern);
    }
  });

  it("when rendered, Material's toolbar defaults its container to the surface and on-surface roles", async () => {
    await setup();
    const css = toolbarStyleText();
    expect(css).toMatch(
      /background:\s*var\(--mat-toolbar-container-background-color,\s*var\(--mat-sys-surface\)\)/,
    );
    expect(css).toMatch(
      /(?:^|[;{\s])color:\s*var\(--mat-toolbar-container-text-color,\s*var\(--mat-sys-on-surface\)\)/,
    );
  });

  it('when rendered, the navbar leaves the toolbar colour tokens undeclared so theme overrides reach the bar', async () => {
    await setup();
    expect(navbarStyleText()).not.toMatch(/--mat-toolbar-container-(?:background|text)-color\s*:/);
  });

  it('when rendered, the header behind the safe-area inset follows the same toolbar tokens', async () => {
    await setup();
    const css = ruleBody(navbarStyleText(), 'navbar');
    expect(css).toMatch(
      /background-color:\s*var\(--mat-toolbar-container-background-color,\s*var\(--mat-sys-surface\)\)/,
    );
    expect(css).toMatch(
      /(?:^|[;{\s])color:\s*var\(--mat-toolbar-container-text-color,\s*var\(--mat-sys-on-surface\)\)/,
    );
  });

  it('when rendered, the brand inherits the title-large role from the toolbar title tokens', async () => {
    const { fixture } = await setup();
    expect(toolbarEl(fixture).classList).toContain('mat-toolbar');
    const toolbarCss = toolbarStyleText();
    expect(toolbarCss).toMatch(
      /font-size:\s*var\(--mat-toolbar-title-text-size,\s*var\(--mat-sys-title-large-size\)\)/,
    );
    expect(toolbarCss).toMatch(
      /letter-spacing:\s*var\(--mat-toolbar-title-text-tracking,\s*var\(--mat-sys-title-large-tracking\)\)/,
    );
    // No type declarations of its own, so a toolbar typography override reaches the brand too.
    expect(navbarStyleText()).not.toMatch(
      /(?:^|[;{\s])(?:font|font-family|font-size|font-weight|line-height|letter-spacing)\s*:/,
    );
  });

  it('when rendered, the stylesheet carries no colour literals', async () => {
    await setup();
    const css = navbarStyleText();
    expect(css).not.toBe('');
    expect(css).not.toMatch(/#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(/);
  });
});

// ── layout: height, wrapping, targets ────────────────────────────────────────

describe('NavbarComponent — layout', () => {
  it('when rendered, the bar keeps the 64px M3 minimum at every width and grows with its content', async () => {
    await setup();
    const css = ruleBody(navbarStyleText(), 'navbar-toolbar');
    expect(css).toMatch(/min-block-size:\s*var\(--mat-toolbar-standard-height,\s*64px\)/);
    expect(css).toMatch(/(?:^|[;{\s])block-size:\s*auto/);
  });

  it('when rendered, the brand slot can shrink and wraps a long title instead of overflowing', async () => {
    await setup();
    const css = ruleBody(navbarStyleText(), 'navbar-brand');
    expect(css).toMatch(/min-inline-size:\s*0/);
    expect(css).toMatch(/white-space:\s*normal/);
    expect(css).toMatch(/overflow-wrap:\s*anywhere/);
    // Max-content columns would hold the title at its full one-line width.
    expect(css).not.toMatch(/max-content/);
  });

  it('when rendered, the brand slot does not clip, so a projected toggle keeps its touch target and focus ring', async () => {
    await setup();
    expect(ruleBody(navbarStyleText(), 'navbar-brand')).not.toMatch(/overflow\s*:\s*(?:hidden|clip|scroll|auto)/);
  });

  it('when rendered, the actions keep their size at the inline end', async () => {
    await setup();
    const css = ruleBody(navbarStyleText(), 'navbar-actions');
    expect(css).toMatch(/grid-auto-columns:\s*max-content/);
    expect(css).toMatch(/margin-inline-start:\s*auto/);
  });
});
