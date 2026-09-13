import { ComponentFixture, TestBed } from '@angular/core/testing';
import { TestbedHarnessEnvironment } from '@angular/cdk/testing/testbed';
import { MatButtonHarness } from '@angular/material/button/testing';

import { ICON_PROVIDER } from '../../../icons';
import { HamburgerComponent, HamburgerVariant } from './hamburger';

interface HamburgerInputs {
  open: boolean;
  controls: string;
  variant: HamburgerVariant;
}

interface Rendered {
  fixture: ComponentFixture<HamburgerComponent>;
  button: MatButtonHarness;
  /** The native `<button>` the harness wraps. */
  el: () => HTMLButtonElement;
}

async function setup(inputs: Partial<HamburgerInputs> = {}): Promise<Rendered> {
  await TestBed.configureTestingModule({
    imports: [HamburgerComponent],
    providers: [ICON_PROVIDER],
  }).compileComponents();
  const fixture = TestBed.createComponent(HamburgerComponent);
  for (const [name, value] of Object.entries(inputs)) {
    fixture.componentRef.setInput(name, value);
  }
  fixture.detectChanges();
  const button = await TestbedHarnessEnvironment.loader(fixture).getHarness(MatButtonHarness);
  return {
    fixture,
    button,
    el: () => fixture.nativeElement.querySelector('button') as HTMLButtonElement,
  };
}

async function attr(button: MatButtonHarness, name: string): Promise<string | null> {
  return (await button.host()).getAttribute(name);
}

// ── Material icon button ──────────────────────────────────────────────────────

describe('HamburgerComponent — Material icon button', () => {
  it('when rendered, the toggle is a matIconButton', async () => {
    const { button } = await setup();
    expect(await button.getVariant()).toBe('icon');
  });

  it('when rendered, the toggle is a native button of type "button" so Enter and Space activate it', async () => {
    const { button, el } = await setup();
    expect(el().tagName).toBe('BUTTON');
    expect(await button.getType()).toBe('button');
  });

  it('when rendered, the toggle is enabled', async () => {
    const { button } = await setup();
    expect(await button.isDisabled()).toBe(false);
  });
});

// ── aria-expanded ─────────────────────────────────────────────────────────────

describe('HamburgerComponent — aria-expanded', () => {
  it('when open is false, aria-expanded is "false"', async () => {
    const { button } = await setup({ open: false });
    expect(await attr(button, 'aria-expanded')).toBe('false');
  });

  it('when open is true, aria-expanded is "true"', async () => {
    const { button } = await setup({ open: true });
    expect(await attr(button, 'aria-expanded')).toBe('true');
  });

  it('when open changes, aria-expanded follows it', async () => {
    const { fixture, button } = await setup({ open: false });
    fixture.componentRef.setInput('open', true);
    expect(await attr(button, 'aria-expanded')).toBe('true');
  });
});

// ── aria-controls ─────────────────────────────────────────────────────────────

describe('HamburgerComponent — aria-controls', () => {
  it('when controls is set, aria-controls matches the given id', async () => {
    const { button } = await setup({ controls: 'main-drawer' });
    expect(await attr(button, 'aria-controls')).toBe('main-drawer');
  });

  it('when controls is empty, aria-controls is omitted', async () => {
    const { button } = await setup();
    expect(await attr(button, 'aria-controls')).toBeNull();
  });
});

// ── 48px touch target ─────────────────────────────────────────────────────────

describe('HamburgerComponent — 48px touch target', () => {
  it('when rendered, the button carries Material\'s 48px touch target', async () => {
    const { el } = await setup();
    expect(el().querySelector('.mat-mdc-button-touch-target')).toBeTruthy();
  });
});

// ── visible focus ─────────────────────────────────────────────────────────────

describe('HamburgerComponent — visible focus ring', () => {
  it('when rendered, the button carries Material\'s focus indicator', async () => {
    const { el } = await setup();
    expect(el().querySelector('.mat-focus-indicator')).toBeTruthy();
  });

  it('when focused, the button holds keyboard focus', async () => {
    const { button } = await setup();
    await button.focus();
    expect(await button.isFocused()).toBe(true);
  });
});

// ── toggle output ─────────────────────────────────────────────────────────────

describe('HamburgerComponent — toggle output', () => {
  it('when the button is clicked, toggle event is emitted', async () => {
    const { fixture, button } = await setup();
    let count = 0;
    fixture.componentInstance.toggle.subscribe(() => { count++; });
    await button.click();
    expect(count).toBe(1);
  });

  it('when the button is clicked twice, toggle is emitted twice', async () => {
    const { fixture, button } = await setup();
    let count = 0;
    fixture.componentInstance.toggle.subscribe(() => { count++; });
    await button.click();
    await button.click();
    expect(count).toBe(2);
  });
});

// ── aria-label reflects state ─────────────────────────────────────────────────

describe('HamburgerComponent — aria-label', () => {
  it('when open is false, aria-label is "Open navigation"', async () => {
    const { button } = await setup({ open: false });
    expect(await attr(button, 'aria-label')).toBe('Open navigation');
  });

  it('when open is true, aria-label is "Close navigation"', async () => {
    const { button } = await setup({ open: true });
    expect(await attr(button, 'aria-label')).toBe('Close navigation');
  });

  it('when the rail variant is collapsed, aria-label is "Expand navigation"', async () => {
    const { button } = await setup({ variant: 'rail', open: false });
    expect(await attr(button, 'aria-label')).toBe('Expand navigation');
  });

  it('when the rail variant is expanded, aria-label is "Collapse navigation"', async () => {
    const { button } = await setup({ variant: 'rail', open: true });
    expect(await attr(button, 'aria-label')).toBe('Collapse navigation');
  });

  it('when open changes, aria-label follows it', async () => {
    const { fixture, button } = await setup({ open: false });
    fixture.componentRef.setInput('open', true);
    expect(await attr(button, 'aria-label')).toBe('Close navigation');
  });

  it('for every state, the label names the action without role words or a trailing period', async () => {
    const { fixture } = await setup();
    for (const variant of ['modal', 'rail'] as const) {
      for (const open of [false, true]) {
        fixture.componentRef.setInput('variant', variant);
        fixture.componentRef.setInput('open', open);
        const label = fixture.componentInstance.label();
        expect(label).not.toMatch(/\b(button|menu|icon)\b/i);
        expect(label).not.toMatch(/\.$/);
      }
    }
  });
});

// ── icon switches with open state ─────────────────────────────────────────────

describe('HamburgerComponent — icon', () => {
  function svg(r: Rendered): SVGElement | null {
    r.fixture.detectChanges();
    return r.el().querySelector('lucide-icon svg');
  }

  it('when open is false, the Menu icon is rendered', async () => {
    const r = await setup({ open: false });
    expect(svg(r)?.classList).toContain('lucide-Menu');
  });

  it('when open is true, the X icon is rendered', async () => {
    const r = await setup({ open: true });
    expect(svg(r)?.classList).toContain('lucide-X');
  });

  it('when open changes, the icon swaps from Menu to X', async () => {
    const r = await setup({ open: false });
    r.fixture.componentRef.setInput('open', true);
    expect(svg(r)?.classList).toContain('lucide-X');
    expect(svg(r)?.classList).not.toContain('lucide-Menu');
  });

  it('when the rail variant is collapsed, the Menu icon is rendered', async () => {
    const r = await setup({ variant: 'rail', open: false });
    expect(svg(r)?.classList).toContain('lucide-Menu');
  });

  it('when the rail variant is expanded, the PanelLeftClose icon is rendered', async () => {
    const r = await setup({ variant: 'rail', open: true });
    expect(svg(r)?.classList).toContain('lucide-PanelLeftClose');
  });

  it('when the rail variant expands, the icon swaps from Menu to PanelLeftClose', async () => {
    const r = await setup({ variant: 'rail', open: false });
    r.fixture.componentRef.setInput('open', true);
    expect(svg(r)?.classList).toContain('lucide-PanelLeftClose');
    expect(svg(r)?.classList).not.toContain('lucide-Menu');
  });

  it('when the rail variant is expanded, its directional PanelLeftClose icon is marked to mirror in RTL', async () => {
    const r = await setup({ variant: 'rail', open: true });
    r.fixture.detectChanges();
    expect(r.el().querySelector('lucide-icon')?.classList).toContain('hamburger-icon-directional');
  });

  it('when the rail variant is collapsed, its symmetric Menu icon is not marked to mirror', async () => {
    const r = await setup({ variant: 'rail', open: false });
    r.fixture.detectChanges();
    expect(r.el().querySelector('lucide-icon')?.classList).not.toContain('hamburger-icon-directional');
  });

  it('when the modal variant renders, its symmetric icons are not marked to mirror', async () => {
    const r = await setup({ variant: 'modal' });
    for (const open of [false, true]) {
      r.fixture.componentRef.setInput('open', open);
      r.fixture.detectChanges();
      expect(r.el().querySelector('lucide-icon')?.classList).not.toContain('hamburger-icon-directional');
    }
  });

  it('when rendered, the icon is hidden from assistive technology', async () => {
    const r = await setup();
    expect(r.el().querySelector('lucide-icon')?.getAttribute('aria-hidden')).toBe('true');
  });
});
