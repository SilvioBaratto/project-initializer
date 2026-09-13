import { Component, EventEmitter, signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { InteractivityChecker } from '@angular/cdk/a11y';
import { Directionality } from '@angular/cdk/bidi';
import { TestbedHarnessEnvironment } from '@angular/cdk/testing/testbed';
import { MatButtonHarness } from '@angular/material/button/testing';
import { MATERIAL_ANIMATIONS } from '@angular/material/core';
import { MatDialogHarness } from '@angular/material/dialog/testing';
import { afterEach, vi } from 'vitest';
import { ICON_PROVIDER } from '../../../icons';
import { DRAWER_PANEL_CLASS, DrawerComponent, DrawerSide } from './drawer';

@Component({
  imports: [DrawerComponent],
  template: `
    <button id="trigger" type="button">Open filters</button>
    <app-drawer
      [side]="side()"
      [open]="isOpen()"
      [drawerId]="drawerId()"
      [label]="label()"
      [ariaLabel]="ariaLabel()"
      (close)="onClose()"
    >
      <button id="btn-a" type="button">A</button>
      <button id="btn-b" type="button">B</button>
    </app-drawer>
  `,
})
class HostComponent {
  readonly side = signal<DrawerSide>('left');
  readonly isOpen = signal(false);
  readonly drawerId = signal('');
  readonly label = signal('Filters');
  readonly ariaLabel = signal('');
  closeCount = 0;
  onClose(): void {
    this.closeCount++;
  }
}

@Component({
  imports: [DrawerComponent],
  template: `<app-drawer [(open)]="isOpen" label="Filters"><p>Body</p></app-drawer>`,
})
class TwoWayHostComponent {
  readonly isOpen = signal(true);
}

const BASE_PROVIDERS = [
  ICON_PROVIDER,
  { provide: MATERIAL_ANIMATIONS, useValue: { animationsDisabled: true } },
];

function rtlDirectionality() {
  return {
    provide: Directionality,
    useValue: { value: 'rtl', valueSignal: signal('rtl'), change: new EventEmitter(), ngOnDestroy() {} },
  };
}

async function setup(providers: unknown[] = []) {
  await TestBed.configureTestingModule({
    imports: [HostComponent],
    providers: [...BASE_PROVIDERS, ...(providers as never[])],
  }).compileComponents();
  const fixture = TestBed.createComponent(HostComponent);
  const loader = TestbedHarnessEnvironment.documentRootLoader(fixture);
  await settle(fixture);
  return { fixture, host: fixture.componentInstance, loader };
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

afterEach(() => {
  vi.restoreAllMocks();
});

// ── open ────────────────────────────────────────────────────────────────────

describe('DrawerComponent — open', () => {
  it('when open is false, no side sheet is rendered', async () => {
    const { loader } = await setup();
    expect(await loader.getAllHarnesses(MatDialogHarness)).toHaveLength(0);
  });

  it('when open becomes true, one modal side sheet opens with the projected content', async () => {
    const { fixture, host, loader } = await setup();
    host.isOpen.set(true);
    await settle(fixture);

    const sheets = await loader.getAllHarnesses(MatDialogHarness);
    expect(sheets).toHaveLength(1);
    expect(await sheets[0].getRole()).toBe('dialog');
    expect(dialogs()[0].querySelector('#btn-a')).not.toBeNull();
    expect(document.querySelector('.cdk-overlay-backdrop')).not.toBeNull();
  });

  it('when the parent sets open back to false, the sheet closes without emitting close', async () => {
    const { fixture, host } = await setup();
    host.isOpen.set(true);
    await settle(fixture);

    host.isOpen.set(false);
    await settle(fixture);

    expect(dialogs()).toHaveLength(0);
    expect(host.closeCount).toBe(0);
  });

  it('when the host is destroyed while open, the sheet closes without emitting close', async () => {
    const { fixture, host } = await setup();
    host.isOpen.set(true);
    await settle(fixture);

    fixture.destroy();
    await new Promise((resolve) => setTimeout(resolve));

    expect(dialogs()).toHaveLength(0);
    expect(host.closeCount).toBe(0);
  });
});

// ── naming and ids ──────────────────────────────────────────────────────────

describe('DrawerComponent — naming', () => {
  it('uses drawerId as the dialog id so a trigger can reference it with aria-controls', async () => {
    const { fixture, host, loader } = await setup();
    host.drawerId.set('filters-sheet');
    host.isOpen.set(true);
    await settle(fixture);

    const sheet = await loader.getHarness(MatDialogHarness);
    expect(await sheet.getId()).toBe('filters-sheet');
  });

  it('the element with drawerId exists only while the sheet is open', async () => {
    const { fixture, host } = await setup();
    host.drawerId.set('filters-sheet');
    expect(document.getElementById('filters-sheet')).toBeNull();

    host.isOpen.set(true);
    await settle(fixture);
    expect(document.getElementById('filters-sheet')?.getAttribute('role')).toBe('dialog');

    host.isOpen.set(false);
    await settle(fixture);
    expect(document.getElementById('filters-sheet')).toBeNull();
  });

  it('when drawerId is empty, the dialog gets a generated Material id', async () => {
    const { fixture, host, loader } = await setup();
    host.isOpen.set(true);
    await settle(fixture);

    expect(await (await loader.getHarness(MatDialogHarness)).getId()).toMatch(/^mat-mdc-dialog-\w+$/);
  });

  it('names the sheet with its visible label headline', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const { fixture, host, loader } = await setup();
    host.isOpen.set(true);
    await settle(fixture);

    const sheet = await loader.getHarness(MatDialogHarness);
    const labelledBy = await sheet.getAriaLabelledby();
    expect(labelledBy).toBeTruthy();
    const headline = document.getElementById(labelledBy as string);
    expect(headline?.tagName).toBe('H2');
    expect(headline?.classList).toContain('mat-mdc-dialog-title');
    expect(headline?.textContent?.trim()).toBe('Filters');
    expect(await sheet.getAriaLabel()).toBeNull();
    expect(warn).not.toHaveBeenCalled();
  });

  it('a label set after the sheet opens becomes its name, and clearing it removes the name', async () => {
    vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const { fixture, host, loader } = await setup();
    host.label.set('');
    host.isOpen.set(true);
    await settle(fixture);
    const sheet = await loader.getHarness(MatDialogHarness);
    expect(await sheet.getAriaLabelledby()).toBeNull();

    host.label.set('Sort and filter');
    await settle(fixture);
    const labelledBy = await sheet.getAriaLabelledby();
    expect(document.getElementById(labelledBy as string)?.textContent?.trim()).toBe('Sort and filter');

    host.label.set('');
    await settle(fixture);
    expect(await sheet.getAriaLabelledby()).toBeNull();
    expect(dialogs()[0].querySelector('h2')).toBeNull();
  });

  it('when label is empty, ariaLabel names the sheet without a visible headline', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const { fixture, host, loader } = await setup();
    host.label.set('');
    host.ariaLabel.set('Filters');
    host.isOpen.set(true);
    await settle(fixture);

    const sheet = await loader.getHarness(MatDialogHarness);
    expect(await sheet.getAriaLabel()).toBe('Filters');
    expect(await sheet.getAriaLabelledby()).toBeNull();
    expect(dialogs()[0].querySelector('h2')).toBeNull();
    expect(warn).not.toHaveBeenCalled();
  });

  it('when both label and ariaLabel are empty, the sheet is unnamed and a dev-mode warning is logged', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const { fixture, host, loader } = await setup();
    host.label.set('');
    host.isOpen.set(true);
    await settle(fixture);

    const sheet = await loader.getHarness(MatDialogHarness);
    expect(await sheet.getAriaLabelledby()).toBeNull();
    expect(await sheet.getAriaLabel()).toBeNull();
    expect(dialogs()[0].querySelector('h2')).toBeNull();
    expect(warn).toHaveBeenCalledTimes(1);
    expect(String(warn.mock.calls[0][0])).toContain('accessible name');
  });

  it('renders a Material icon button named Close with a decorative icon', async () => {
    const { fixture, host, loader } = await setup();
    host.isOpen.set(true);
    await settle(fixture);

    const close = await loader.getHarness(MatButtonHarness.with({ selector: '.drawer-close' }));
    expect(await close.getVariant()).toBe('icon');
    expect(await (await close.host()).getAttribute('aria-label')).toBe('Close');
    const icon = dialogs()[0].querySelector('.drawer-close lucide-icon');
    expect(icon?.getAttribute('aria-hidden')).toBe('true');
  });
});

// ── side input and direction ────────────────────────────────────────────────

describe('DrawerComponent — side input', () => {
  it('when side is left, the sheet sits at the leading (left in LTR) edge', async () => {
    const { fixture, host } = await setup();
    host.isOpen.set(true);
    await settle(fixture);

    const panel = pane();
    expect(panel.classList).toContain(DRAWER_PANEL_CLASS);
    expect(panel.classList).toContain(`${DRAWER_PANEL_CLASS}--start`);
    expect(pinnedEdge(panel)).toBe('left');
  });

  it('when side is right, the sheet sits at the trailing (right in LTR) edge', async () => {
    const { fixture, host } = await setup();
    host.side.set('right');
    host.isOpen.set(true);
    await settle(fixture);

    const panel = pane();
    expect(panel.classList).toContain(`${DRAWER_PANEL_CLASS}--end`);
    expect(pinnedEdge(panel)).toBe('right');
  });

  it('when side changes while open, the sheet moves to the other edge', async () => {
    const { fixture, host } = await setup();
    host.isOpen.set(true);
    await settle(fixture);

    host.side.set('right');
    await settle(fixture);

    const panel = pane();
    expect(panel.classList).toContain(`${DRAWER_PANEL_CLASS}--end`);
    expect(panel.classList).not.toContain(`${DRAWER_PANEL_CLASS}--start`);
    expect(pinnedEdge(panel)).toBe('right');
  });

  it('in RTL, side left mirrors to the leading edge on the physical right', async () => {
    const { fixture, host } = await setup([rtlDirectionality()]);
    host.isOpen.set(true);
    await settle(fixture);

    const panel = pane();
    expect(panel.classList).toContain(`${DRAWER_PANEL_CLASS}--start`);
    expect(panel.parentElement?.getAttribute('dir')).toBe('rtl');
    expect(pinnedEdge(panel)).toBe('right');
  });
});

// ── dismissal ───────────────────────────────────────────────────────────────

describe('DrawerComponent — close output', () => {
  it('when the scrim is clicked, close fires once and the sheet closes', async () => {
    const { fixture, host } = await setup();
    host.isOpen.set(true);
    await settle(fixture);

    (document.querySelector('.cdk-overlay-backdrop') as HTMLElement).click();
    await settle(fixture);

    expect(host.closeCount).toBe(1);
    expect(dialogs()).toHaveLength(0);
  });

  it('when Escape is pressed while open, close fires once and the sheet closes', async () => {
    const { fixture, host, loader } = await setup();
    host.isOpen.set(true);
    await settle(fixture);

    await (await loader.getHarness(MatDialogHarness)).close(); // sends Escape
    await settle(fixture);

    expect(host.closeCount).toBe(1);
    expect(dialogs()).toHaveLength(0);
  });

  it('when the close button is activated, close fires once and the sheet closes', async () => {
    const { fixture, host, loader } = await setup();
    host.isOpen.set(true);
    await settle(fixture);

    await (await loader.getHarness(MatButtonHarness.with({ selector: '.drawer-close' }))).click();
    await settle(fixture);

    expect(host.closeCount).toBe(1);
    expect(dialogs()).toHaveLength(0);
  });

  it('when Escape is pressed while closed, close does not fire', async () => {
    const { fixture, host } = await setup();
    document.body.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }),
    );
    await settle(fixture);
    expect(host.closeCount).toBe(0);
  });

  it('after a user dismissal, open can reopen the sheet', async () => {
    const { fixture, host, loader } = await setup();
    host.isOpen.set(true);
    await settle(fixture);
    await (await loader.getHarness(MatDialogHarness)).close();
    await settle(fixture);

    host.isOpen.set(false); // parent clears its state from (close)
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

describe('DrawerComponent — focus', () => {
  it('when the sheet opens, focus moves into it (first tabbable element)', async () => {
    // jsdom has no layout, so the CDK would treat every element as invisible and untabbable.
    vi.spyOn(InteractivityChecker.prototype, 'isVisible').mockReturnValue(true);
    const { fixture, host } = await setup();
    host.isOpen.set(true);
    await settle(fixture);

    const sheet = dialogs()[0];
    expect(sheet.contains(document.activeElement)).toBe(true);
    expect(document.activeElement).toBe(sheet.querySelector('.drawer-close'));
  });

  it('when the sheet closes, focus returns to the element that opened it', async () => {
    vi.spyOn(InteractivityChecker.prototype, 'isVisible').mockReturnValue(true);
    const { fixture, host, loader } = await setup();
    document.body.appendChild(fixture.nativeElement);
    const trigger = fixture.nativeElement.querySelector('#trigger') as HTMLElement;
    trigger.focus();
    expect(document.activeElement).toBe(trigger);

    host.isOpen.set(true);
    await settle(fixture);
    expect(document.activeElement).not.toBe(trigger);

    await (await loader.getHarness(MatDialogHarness)).close();
    await settle(fixture);

    expect(document.activeElement).toBe(trigger);
    fixture.nativeElement.remove();
  });
});
