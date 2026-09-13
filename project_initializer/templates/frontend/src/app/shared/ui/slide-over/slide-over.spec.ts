import { Component, signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { InteractivityChecker } from '@angular/cdk/a11y';
import { TestbedHarnessEnvironment } from '@angular/cdk/testing/testbed';
import { MatButtonHarness } from '@angular/material/button/testing';
import { MATERIAL_ANIMATIONS } from '@angular/material/core';
import { MatDialogHarness } from '@angular/material/dialog/testing';
import { afterEach, vi } from 'vitest';
import { ICON_PROVIDER } from '../../../icons';
import { DRAWER_PANEL_CLASS } from '../drawer/drawer';
import { SlideOverComponent, SlideOverSide } from './slide-over';

@Component({
  imports: [SlideOverComponent],
  template: `
    <button id="trigger" type="button">Open details</button>
    <app-slide-over [open]="isOpen()" [side]="side()" [label]="label()" (closed)="onClosed()">
      <button id="first-btn" type="button">First</button>
      <button id="second-btn" type="button">Second</button>
    </app-slide-over>
  `,
})
class HostComponent {
  readonly isOpen = signal(false);
  readonly side = signal<SlideOverSide>('right');
  readonly label = signal('Order details');
  closedCount = 0;
  onClosed(): void {
    this.closedCount++;
  }
}

@Component({
  imports: [SlideOverComponent],
  template: `<app-slide-over [(open)]="isOpen" label="Order details"><p>Body</p></app-slide-over>`,
})
class TwoWayHostComponent {
  readonly isOpen = signal(true);
}

const BASE_PROVIDERS = [
  ICON_PROVIDER,
  { provide: MATERIAL_ANIMATIONS, useValue: { animationsDisabled: true } },
];

async function setup() {
  await TestBed.configureTestingModule({
    imports: [HostComponent],
    providers: BASE_PROVIDERS,
  }).compileComponents();
  const fixture = TestBed.createComponent(HostComponent);
  const loader = TestbedHarnessEnvironment.documentRootLoader(fixture);
  await settle(fixture);
  return { fixture, host: fixture.componentInstance, loader };
}

async function openSheet() {
  const ctx = await setup();
  ctx.host.isOpen.set(true);
  await settle(ctx.fixture);
  return ctx;
}

/** Runs change detection and lets MatDialog's microtask/afterRender work finish. */
async function settle(fixture: ComponentFixture<unknown>): Promise<void> {
  fixture.detectChanges();
  await fixture.whenStable();
  await new Promise((resolve) => setTimeout(resolve));
  await fixture.whenStable();
}

function dialogs(): HTMLElement[] {
  return Array.from(document.querySelectorAll<HTMLElement>('.mat-mdc-dialog-container'));
}

function pane(): HTMLElement {
  const el = document.querySelector<HTMLElement>(`.cdk-overlay-pane.${DRAWER_PANEL_CLASS}`);
  expect(el).not.toBeNull();
  return el as HTMLElement;
}

/** MatDialog positions are physical: the pane gets a zero margin on the edge it is pinned to. */
function pinnedEdge(panel: HTMLElement): 'left' | 'right' | null {
  if (/^0(px)?$/.test(panel.style.marginLeft)) return 'left';
  if (/^0(px)?$/.test(panel.style.marginRight)) return 'right';
  return null;
}

const CLOSE_BUTTON = MatButtonHarness.with({ selector: '.drawer-close' });

afterEach(() => {
  vi.restoreAllMocks();
});

// ── ARIA contract ───────────────────────────────────────────────────────────

describe('SlideOverComponent — ARIA contract', () => {
  it('when open, the panel is a Material dialog with role="dialog"', async () => {
    const { loader } = await openSheet();
    const sheets = await loader.getAllHarnesses(MatDialogHarness);
    expect(sheets).toHaveLength(1);
    expect(await sheets[0].getRole()).toBe('dialog');
  });

  it('when open, the panel is named by its h2 headline showing label', async () => {
    const { loader } = await openSheet();
    const sheet = await loader.getHarness(MatDialogHarness);
    const labelledBy = await sheet.getAriaLabelledby();
    expect(labelledBy).toBeTruthy();
    const headline = document.getElementById(labelledBy as string);
    expect(headline?.tagName).toBe('H2');
    expect(headline?.textContent?.trim()).toBe('Order details');
  });

  it('with the required label, the panel is named without a missing-name warning', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const { loader } = await openSheet();

    const sheet = await loader.getHarness(MatDialogHarness);
    expect(await sheet.getAriaLabel()).toBeNull();
    const labelledBy = await sheet.getAriaLabelledby();
    expect(document.getElementById(labelledBy as string)?.textContent?.trim()).toBe('Order details');
    expect(warn).not.toHaveBeenCalled();
  });

  it('when label changes while open, the visible headline and the panel name follow it', async () => {
    const { fixture, host, loader } = await openSheet();
    host.label.set('Shipping details');
    await settle(fixture);

    const labelledBy = await (await loader.getHarness(MatDialogHarness)).getAriaLabelledby();
    const headline = document.getElementById(labelledBy as string);
    expect(headline?.tagName).toBe('H2');
    expect(headline?.textContent?.trim()).toBe('Shipping details');
  });

  it('while open, the page outside the panel is hidden from assistive technology and restored on close', async () => {
    const { fixture, host } = await openSheet();
    const pageRoot = fixture.nativeElement.closest('body > *') as HTMLElement;
    expect(pageRoot).not.toBeNull();
    expect(pageRoot.getAttribute('aria-hidden')).toBe('true');
    expect(document.querySelector('.cdk-overlay-backdrop')).not.toBeNull();

    host.isOpen.set(false);
    await settle(fixture);
    expect(pageRoot.hasAttribute('aria-hidden')).toBe(false);
  });

  it('the header close control is a Material icon button named "Close panel" with a decorative icon', async () => {
    const { loader } = await openSheet();
    const close = await loader.getHarness(CLOSE_BUTTON);
    expect(await close.getVariant()).toBe('icon');
    expect(await (await close.host()).getAttribute('aria-label')).toBe('Close panel');
    expect(dialogs()[0].querySelector('.drawer-close lucide-icon')?.getAttribute('aria-hidden')).toBe('true');
  });
});

// ── open input ──────────────────────────────────────────────────────────────

describe('SlideOverComponent — open input', () => {
  it('when open is false, no panel is rendered', async () => {
    const { loader } = await setup();
    expect(await loader.getAllHarnesses(MatDialogHarness)).toHaveLength(0);
  });

  it('nothing renders in place; the panel and its projected content live in the overlay container', async () => {
    const { fixture } = await openSheet();
    const hostEl = fixture.nativeElement.querySelector('app-slide-over') as HTMLElement;
    expect(hostEl.querySelector('[role="dialog"]')).toBeNull();
    expect(hostEl.querySelector('#first-btn')).toBeNull();

    const sheet = dialogs()[0];
    expect(sheet.closest('.cdk-overlay-container')).not.toBeNull();
    expect(sheet.querySelector('#first-btn')).not.toBeNull();
    expect(sheet.querySelector('#second-btn')).not.toBeNull();
  });

  it('when the parent sets open back to false, the panel closes without emitting closed', async () => {
    const { fixture, host } = await openSheet();
    host.isOpen.set(false);
    await settle(fixture);

    expect(dialogs()).toHaveLength(0);
    expect(host.closedCount).toBe(0);
  });

  it('when the host is destroyed while open, the panel closes without emitting closed', async () => {
    const { fixture, host } = await openSheet();
    fixture.destroy();
    await new Promise((resolve) => setTimeout(resolve));

    expect(dialogs()).toHaveLength(0);
    expect(host.closedCount).toBe(0);
  });
});

// ── side input ──────────────────────────────────────────────────────────────

describe('SlideOverComponent — side input', () => {
  it('by default, the panel sits at the trailing (right in LTR) edge', async () => {
    await openSheet();
    const panel = pane();
    expect(panel.classList).toContain(`${DRAWER_PANEL_CLASS}--end`);
    expect(pinnedEdge(panel)).toBe('right');
  });

  it('when side is left, the panel sits at the leading (left in LTR) edge', async () => {
    const { fixture, host } = await setup();
    host.side.set('left');
    host.isOpen.set(true);
    await settle(fixture);

    const panel = pane();
    expect(panel.classList).toContain(`${DRAWER_PANEL_CLASS}--start`);
    expect(pinnedEdge(panel)).toBe('left');
  });
});

// ── closed output ───────────────────────────────────────────────────────────

describe('SlideOverComponent — closed output', () => {
  it('when Escape is pressed while open, closed fires once and the panel closes', async () => {
    const { fixture, host, loader } = await openSheet();
    await (await loader.getHarness(MatDialogHarness)).close(); // sends Escape
    await settle(fixture);

    expect(host.closedCount).toBe(1);
    expect(dialogs()).toHaveLength(0);
  });

  it('when the scrim is clicked, closed fires once and the panel closes', async () => {
    const { fixture, host } = await openSheet();
    (document.querySelector('.cdk-overlay-backdrop') as HTMLElement).click();
    await settle(fixture);

    expect(host.closedCount).toBe(1);
    expect(dialogs()).toHaveLength(0);
  });

  it('when the close button is activated, closed fires once and the panel closes', async () => {
    const { fixture, host, loader } = await openSheet();
    await (await loader.getHarness(CLOSE_BUTTON)).click();
    await settle(fixture);

    expect(host.closedCount).toBe(1);
    expect(dialogs()).toHaveLength(0);
  });

  it('handleClose() dismisses the panel as the user would and emits closed once', async () => {
    const { fixture, host } = await openSheet();
    const slideOver = fixture.debugElement.children
      .map((child) => child.componentInstance)
      .find((instance): instance is SlideOverComponent => instance instanceof SlideOverComponent);
    expect(slideOver).toBeDefined();

    slideOver?.handleClose();
    await settle(fixture);

    expect(host.closedCount).toBe(1);
    expect(dialogs()).toHaveLength(0);
  });

  it('when Escape is pressed while closed, closed does not fire', async () => {
    const { fixture, host } = await setup();
    document.body.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }));
    await settle(fixture);
    expect(host.closedCount).toBe(0);
  });

  it('after a user dismissal, open can reopen the panel', async () => {
    const { fixture, host, loader } = await openSheet();
    await (await loader.getHarness(MatDialogHarness)).close();
    await settle(fixture);

    host.isOpen.set(false); // parent clears its state from (closed)
    await settle(fixture);
    host.isOpen.set(true);
    await settle(fixture);

    expect(dialogs()).toHaveLength(1);
  });

  it('with [(open)], a user dismissal writes false back to the parent', async () => {
    await TestBed.configureTestingModule({
      imports: [TwoWayHostComponent],
      providers: BASE_PROVIDERS,
    }).compileComponents();
    const fixture = TestBed.createComponent(TwoWayHostComponent);
    const loader = TestbedHarnessEnvironment.documentRootLoader(fixture);
    await settle(fixture);
    expect(dialogs()).toHaveLength(1);

    await (await loader.getHarness(MatDialogHarness)).close();
    await settle(fixture);

    expect(fixture.componentInstance.isOpen()).toBe(false);
    expect(dialogs()).toHaveLength(0);
  });
});

// ── focus ───────────────────────────────────────────────────────────────────

describe('SlideOverComponent — focus', () => {
  it('when the panel opens, focus moves into it (the close button comes first)', async () => {
    // jsdom has no layout, so the CDK would treat every element as invisible and untabbable.
    vi.spyOn(InteractivityChecker.prototype, 'isVisible').mockReturnValue(true);
    await openSheet();

    const sheet = dialogs()[0];
    expect(sheet.contains(document.activeElement)).toBe(true);
    expect(document.activeElement).toBe(sheet.querySelector('.drawer-close'));
  });

  it('when the panel closes, focus returns to the element that opened it', async () => {
    vi.spyOn(InteractivityChecker.prototype, 'isVisible').mockReturnValue(true);
    const { fixture, host, loader } = await setup();
    const trigger = fixture.nativeElement.querySelector('#trigger') as HTMLElement;
    trigger.focus();
    expect(document.activeElement).toBe(trigger);

    host.isOpen.set(true);
    await settle(fixture);
    expect(document.activeElement).not.toBe(trigger);

    await (await loader.getHarness(MatDialogHarness)).close();
    await settle(fixture);

    expect(document.activeElement).toBe(trigger);
  });
});
