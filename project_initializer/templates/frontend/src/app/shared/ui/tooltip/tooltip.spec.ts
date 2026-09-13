import { Component, Type, signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { HarnessLoader } from '@angular/cdk/testing';
import { TestbedHarnessEnvironment } from '@angular/cdk/testing/testbed';
import { MatButton } from '@angular/material/button';
import { MATERIAL_ANIMATIONS } from '@angular/material/core';
import {
  MAT_TOOLTIP_DEFAULT_OPTIONS,
  MatTooltip,
  MatTooltipDefaultOptions,
  TooltipPosition,
} from '@angular/material/tooltip';
import { MatTooltipHarness } from '@angular/material/tooltip/testing';
import { vi } from 'vitest';
import { ButtonComponent } from '../button/button';
import { TooltipComponent } from './tooltip';
import { TooltipDirective } from './tooltip.directive';

// ---------------------------------------------------------------------------
// Host stubs
// ---------------------------------------------------------------------------

@Component({
  imports: [TooltipComponent],
  template: `
    <ui-tooltip [text]="text()" [position]="position()">
      <button id="trigger-btn" type="button">Save</button>
    </ui-tooltip>
    <button id="outside-btn" type="button">Elsewhere</button>
  `,
})
class WrapperHostComponent {
  readonly text = signal('Save changes');
  readonly position = signal<TooltipPosition>('below');
}

/** The real consumer shape: the focusable <button> lives inside <app-button>'s own view. */
@Component({
  imports: [TooltipComponent, ButtonComponent],
  template: `
    <ui-tooltip text="Save changes">
      <app-button variant="ghost" size="sm">Save</app-button>
    </ui-tooltip>
    <button id="outside-btn" type="button">Elsewhere</button>
  `,
})
class AppButtonHostComponent {}

/** Two focusable elements inside one wrapper, to pin the subtree focus rules. */
@Component({
  imports: [TooltipComponent],
  template: `
    <ui-tooltip text="Save changes">
      <button id="trigger-btn" type="button">Save</button>
      <button id="second-btn" type="button">Save as</button>
    </ui-tooltip>
  `,
})
class TwoFocusablesHostComponent {}

/** Only a natively disabled control inside the wrapper: nothing a keyboard can reach. */
@Component({
  imports: [TooltipComponent],
  template: `
    <ui-tooltip text="Publishing is paused">
      <button id="trigger-btn" type="button" disabled>Publish</button>
    </ui-tooltip>
  `,
})
class DisabledTriggerHostComponent {}

/** A disabled control before a focusable link, and a disabledInteractive Material button. */
@Component({
  imports: [TooltipComponent, MatButton],
  template: `
    <ui-tooltip text="Publishing is paused">
      <button id="trigger-btn" type="button" disabled>Publish</button>
      <a id="help-link" href="/help">Learn why</a>
    </ui-tooltip>
    <ui-tooltip text="Add a title to publish">
      <button id="interactive-btn" matButton="filled" type="button" disabled disabledInteractive>
        Publish
      </button>
    </ui-tooltip>
  `,
})
class UnavailableTriggersHostComponent {}

@Component({
  imports: [TooltipDirective],
  template: `
    <button
      id="trigger-btn"
      type="button"
      [uiTooltip]="text()"
      [uiTooltipDisabled]="disabled()"
      uiTooltipPosition="above"
    >
      Delete
    </button>
    <button id="outside-btn" type="button">Elsewhere</button>
  `,
})
class DirectiveHostComponent {
  readonly text = signal('Delete draft');
  readonly disabled = signal(false);
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

interface Setup<T> {
  fixture: ComponentFixture<T>;
  loader: HarnessLoader;
}

async function setup<T>(
  host: Type<T>,
  options?: Partial<MatTooltipDefaultOptions>,
): Promise<Setup<T>> {
  TestBed.configureTestingModule({
    imports: [host],
    providers: [
      { provide: MATERIAL_ANIMATIONS, useValue: { animationsDisabled: true } },
      ...(options
        ? [
            {
              provide: MAT_TOOLTIP_DEFAULT_OPTIONS,
              useValue: { showDelay: 0, hideDelay: 0, touchendHideDelay: 0, ...options },
            },
          ]
        : []),
    ],
  });
  const fixture = TestBed.createComponent(host);
  await settle(fixture);
  return { fixture, loader: TestbedHarnessEnvironment.loader(fixture) };
}

/**
 * Flushes change detection, afterNextRender hooks and MatTooltip's 0ms show/hide
 * timers. The harness reports a tooltip open as soon as its panel is attached,
 * but MatTooltip only treats it as visible (and only then accepts Escape) once
 * that timer has run.
 */
async function settle(fixture: ComponentFixture<unknown>, ms = 0): Promise<void> {
  await fixture.whenStable();
  await new Promise((resolve) => setTimeout(resolve, ms));
  await fixture.whenStable();
}

function trigger(fixture: ComponentFixture<unknown>): HTMLButtonElement {
  return fixture.nativeElement.querySelector('#trigger-btn');
}

function outside(fixture: ComponentFixture<unknown>): HTMLButtonElement {
  return fixture.nativeElement.querySelector('#outside-btn');
}

function matTooltipOn(fixture: ComponentFixture<unknown>, selector: string): MatTooltip {
  return fixture.debugElement.query(By.css(selector)).injector.get(MatTooltip);
}

function descriptionIds(el: Element): string[] {
  return (el.getAttribute('aria-describedby') ?? '').split(/\s+/).filter(Boolean);
}

function describedText(el: Element): string {
  return descriptionIds(el)
    .map((id) => document.getElementById(id)?.textContent ?? '')
    .join(' ')
    .trim();
}

function tooltipPanel(): HTMLElement | null {
  return document.querySelector('.mat-mdc-tooltip');
}

function pressKey(target: EventTarget, key: string, keyCode: number): void {
  const event = new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true });
  Object.defineProperty(event, 'keyCode', { get: () => keyCode });
  target.dispatchEvent(event);
}

/** Tab keydown, then focus, so InputModalityDetector reports a keyboard origin. */
function focusWithKeyboard(el: HTMLElement): void {
  pressKey(el, 'Tab', 9);
  el.focus();
}

/** A real (non screen-reader) mousedown, then focus, so the origin is a pointer. */
function focusWithPointer(el: HTMLElement): void {
  el.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, buttons: 1, detail: 1 }));
  el.focus();
}

function touch(el: HTMLElement, type: 'touchstart' | 'touchend'): void {
  el.dispatchEvent(new TouchEvent(type, { bubbles: true, cancelable: true }));
}

async function openWithHover(
  fixture: ComponentFixture<unknown>,
  loader: HarnessLoader,
): Promise<MatTooltipHarness> {
  const tooltip = await loader.getHarness(MatTooltipHarness);
  await tooltip.show();
  await settle(fixture);
  return tooltip;
}

// ---------------------------------------------------------------------------
// <ui-tooltip> — ARIA: the focusable trigger is described, not the wrapper
// ---------------------------------------------------------------------------

describe('TooltipComponent — ARIA contract', () => {
  it('describes the focusable projected trigger with the tooltip text', async () => {
    const { fixture } = await setup(WrapperHostComponent);
    expect(describedText(trigger(fixture))).toBe('Save changes');
  });

  it('does not put aria-describedby on the non-focusable wrapper', async () => {
    const { fixture } = await setup(WrapperHostComponent);
    const wrapper = fixture.nativeElement.querySelector('ui-tooltip') as HTMLElement;
    expect(wrapper.hasAttribute('aria-describedby')).toBe(false);
  });

  it('links aria-describedby to an element with role="tooltip" and a unique id', async () => {
    const { fixture } = await setup(WrapperHostComponent);
    const [id] = descriptionIds(trigger(fixture));
    expect(id).toBeTruthy();
    const message = document.getElementById(id);
    expect(message?.getAttribute('role')).toBe('tooltip');
    expect(document.querySelectorAll(`[id="${id}"]`)).toHaveLength(1);
  });

  it('updates the description when the text changes', async () => {
    const { fixture } = await setup(WrapperHostComponent);
    fixture.componentInstance.text.set('Discard changes');
    await settle(fixture);
    expect(describedText(trigger(fixture))).toBe('Discard changes');
  });

  it('removes the description when the text is cleared', async () => {
    const { fixture } = await setup(WrapperHostComponent);
    fixture.componentInstance.text.set('');
    await settle(fixture);
    expect(descriptionIds(trigger(fixture))).toHaveLength(0);
  });

  it('removes the description element when destroyed', async () => {
    const { fixture } = await setup(WrapperHostComponent);
    const [id] = descriptionIds(trigger(fixture));
    fixture.destroy();
    expect(document.getElementById(id)).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// <ui-tooltip> — unavailable triggers: only focusable elements are described
// ---------------------------------------------------------------------------

describe('TooltipComponent — unavailable triggers', () => {
  it('describes nothing and warns in dev mode when the only control inside is disabled', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    try {
      const { fixture } = await setup(DisabledTriggerHostComponent);
      const wrapper = fixture.nativeElement.querySelector('ui-tooltip') as HTMLElement;

      expect(descriptionIds(trigger(fixture))).toHaveLength(0);
      expect(wrapper.hasAttribute('aria-describedby')).toBe(false);
      expect(warn).toHaveBeenCalledWith(expect.stringContaining('ui-tooltip: nothing inside can take focus'));

      // Teardown has no description to remove and must not throw.
      expect(() => fixture.destroy()).not.toThrow();
    } finally {
      warn.mockRestore();
    }
  });

  it('skips a disabled control and describes the next focusable element', async () => {
    const { fixture } = await setup(UnavailableTriggersHostComponent);

    expect(descriptionIds(trigger(fixture))).toHaveLength(0);
    expect(describedText(fixture.nativeElement.querySelector('#help-link'))).toBe('Publishing is paused');
  });

  it('describes a disabledInteractive button, which stays focusable', async () => {
    const { fixture } = await setup(UnavailableTriggersHostComponent);
    const button = fixture.nativeElement.querySelector('#interactive-btn') as HTMLButtonElement;

    expect(button.hasAttribute('disabled')).toBe(false);
    expect(button.getAttribute('aria-disabled')).toBe('true');
    expect(describedText(button)).toBe('Add a title to publish');
  });
});

// ---------------------------------------------------------------------------
// <ui-tooltip> — show / hide triggers
// ---------------------------------------------------------------------------

describe('TooltipComponent — show / hide triggers', () => {
  it('shows the text on hover and hides when the pointer leaves', async () => {
    const { fixture, loader } = await setup(WrapperHostComponent);
    const tooltip = await loader.getHarness(MatTooltipHarness);
    expect(await tooltip.isOpen()).toBe(false);

    await tooltip.show();
    await settle(fixture);
    expect(await tooltip.isOpen()).toBe(true);
    expect(await tooltip.getTooltipText()).toBe('Save changes');

    await tooltip.hide();
    await settle(fixture);
    expect(await tooltip.isOpen()).toBe(false);
  });

  it('shows when the projected trigger receives keyboard focus', async () => {
    const { fixture } = await setup(WrapperHostComponent);
    focusWithKeyboard(trigger(fixture));
    await settle(fixture);
    expect(tooltipPanel()?.textContent?.trim()).toBe('Save changes');
  });

  it('does not show when focus comes from a pointer click', async () => {
    const { fixture } = await setup(WrapperHostComponent);
    focusWithPointer(trigger(fixture));
    await settle(fixture);
    expect(tooltipPanel()).toBeNull();
  });

  it('hides when keyboard focus leaves the wrapper', async () => {
    const { fixture } = await setup(WrapperHostComponent);
    focusWithKeyboard(trigger(fixture));
    await settle(fixture);
    expect(tooltipPanel()).not.toBeNull();

    focusWithKeyboard(outside(fixture));
    await settle(fixture);
    expect(tooltipPanel()).toBeNull();
  });

  it('does not show when focus is moved from code after earlier keyboard use', async () => {
    const { fixture } = await setup(WrapperHostComponent);
    // The last input was a key press, but focus() runs later (after render, a
    // route change): FocusMonitor reports a 'program' origin, so matTooltip stays closed.
    pressKey(outside(fixture), 'Tab', 9);
    await settle(fixture, 20);
    trigger(fixture).focus();
    await settle(fixture);
    expect(document.activeElement).toBe(trigger(fixture));
    expect(tooltipPanel()).toBeNull();
  });

  it('stays open while keyboard focus moves between elements inside the wrapper', async () => {
    const { fixture } = await setup(TwoFocusablesHostComponent);
    focusWithKeyboard(trigger(fixture));
    await settle(fixture);
    expect(tooltipPanel()).not.toBeNull();

    focusWithKeyboard(fixture.nativeElement.querySelector('#second-btn'));
    await settle(fixture);
    expect(tooltipPanel()?.textContent?.trim()).toBe('Save changes');
  });

  it('show() and hide() open and close the tooltip', async () => {
    const { fixture } = await setup(WrapperHostComponent);
    const component = fixture.debugElement.query(By.directive(TooltipComponent))
      .componentInstance as TooltipComponent;

    component.show();
    await settle(fixture);
    expect(tooltipPanel()).not.toBeNull();

    component.hide();
    await settle(fixture);
    expect(tooltipPanel()).toBeNull();
  });

  it('stays closed when the text is empty', async () => {
    const { fixture, loader } = await setup(WrapperHostComponent);
    fixture.componentInstance.text.set('');
    await settle(fixture);
    const tooltip = await openWithHover(fixture, loader);
    expect(await tooltip.isOpen()).toBe(false);
  });

  it('maps the position input onto MatTooltip', async () => {
    const { fixture } = await setup(WrapperHostComponent);
    expect(matTooltipOn(fixture, 'ui-tooltip').position).toBe('below');

    fixture.componentInstance.position.set('above');
    await settle(fixture);
    expect(matTooltipOn(fixture, 'ui-tooltip').position).toBe('above');
  });
});

// ---------------------------------------------------------------------------
// <ui-tooltip> — touch & hold on touch-only devices (M3 touch & hold tooltips)
// ---------------------------------------------------------------------------

describe('TooltipComponent — touch & hold', () => {
  const touchOnly: Partial<MatTooltipDefaultOptions> = {
    detectHoverCapability: () => false,
    touchLongPressShowDelay: 40,
  };

  it('shows after a touch & hold on the projected trigger', async () => {
    const { fixture } = await setup(WrapperHostComponent, touchOnly);
    touch(trigger(fixture), 'touchstart');
    await settle(fixture, 80);
    expect(tooltipPanel()?.textContent?.trim()).toBe('Save changes');
  });

  it('does not show for a short tap', async () => {
    const { fixture } = await setup(WrapperHostComponent, touchOnly);
    touch(trigger(fixture), 'touchstart');
    touch(trigger(fixture), 'touchend');
    await settle(fixture, 80);
    expect(tooltipPanel()).toBeNull();
  });

  it('hides when the touch ends', async () => {
    const { fixture } = await setup(WrapperHostComponent, touchOnly);
    touch(trigger(fixture), 'touchstart');
    await settle(fixture, 80);
    expect(tooltipPanel()).not.toBeNull();

    touch(trigger(fixture), 'touchend');
    await settle(fixture);
    expect(tooltipPanel()).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// <ui-tooltip> — Escape dismisses (idempotent)
// ---------------------------------------------------------------------------

describe('TooltipComponent — Escape', () => {
  it('dismisses the open tooltip', async () => {
    const { fixture, loader } = await setup(WrapperHostComponent);
    const tooltip = await openWithHover(fixture, loader);
    expect(await tooltip.isOpen()).toBe(true);

    pressKey(trigger(fixture), 'Escape', 27);
    await settle(fixture);
    expect(await tooltip.isOpen()).toBe(false);
  });

  it('keeps the tooltip hidden when pressed twice', async () => {
    const { fixture, loader } = await setup(WrapperHostComponent);
    const tooltip = await openWithHover(fixture, loader);

    pressKey(trigger(fixture), 'Escape', 27);
    await settle(fixture);
    expect(await tooltip.isOpen()).toBe(false);
    pressKey(trigger(fixture), 'Escape', 27);
    await settle(fixture);
    expect(await tooltip.isOpen()).toBe(false);
  });

  it('leaves a hidden tooltip hidden', async () => {
    const { fixture, loader } = await setup(WrapperHostComponent);
    pressKey(trigger(fixture), 'Escape', 27);
    await settle(fixture);
    expect(await (await loader.getHarness(MatTooltipHarness)).isOpen()).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// No hardcoded hex colours
// ---------------------------------------------------------------------------

describe('TooltipComponent — token colours only', () => {
  it('renders no inline hex colour on the wrapper, trigger or tooltip panel', async () => {
    const { fixture, loader } = await setup(WrapperHostComponent);
    await openWithHover(fixture, loader);
    const hexPattern = /#[0-9a-fA-F]{3,8}\b/;
    const root = fixture.nativeElement as HTMLElement;
    const overlay = document.querySelector('.cdk-overlay-container') as HTMLElement | null;
    const all = [root, ...Array.from(root.querySelectorAll<HTMLElement>('*'))];
    if (overlay) {
      all.push(overlay, ...Array.from(overlay.querySelectorAll<HTMLElement>('*')));
    }
    for (const el of all) {
      expect(el.getAttribute('style') ?? '').not.toMatch(hexPattern);
    }
  });
});

// ---------------------------------------------------------------------------
// [uiTooltip] — MatTooltip directly on the focusable trigger
// ---------------------------------------------------------------------------

describe('TooltipDirective — [uiTooltip]', () => {
  it('puts aria-describedby on the element that carries uiTooltip', async () => {
    const { fixture } = await setup(DirectiveHostComponent);
    expect(describedText(trigger(fixture))).toBe('Delete draft');
  });

  it('shows the text on hover', async () => {
    const { fixture, loader } = await setup(DirectiveHostComponent);
    const tooltip = await openWithHover(fixture, loader);
    expect(await tooltip.isOpen()).toBe(true);
    expect(await tooltip.getTooltipText()).toBe('Delete draft');
  });

  it('shows on keyboard focus and hides on blur', async () => {
    const { fixture } = await setup(DirectiveHostComponent);
    focusWithKeyboard(trigger(fixture));
    await settle(fixture);
    expect(tooltipPanel()?.textContent?.trim()).toBe('Delete draft');

    focusWithKeyboard(outside(fixture));
    await settle(fixture);
    expect(tooltipPanel()).toBeNull();
  });

  it('maps uiTooltipPosition onto MatTooltip', async () => {
    const { fixture } = await setup(DirectiveHostComponent);
    expect(matTooltipOn(fixture, '#trigger-btn').position).toBe('above');
  });

  it('dismisses on Escape', async () => {
    const { fixture, loader } = await setup(DirectiveHostComponent);
    const tooltip = await openWithHover(fixture, loader);
    pressKey(trigger(fixture), 'Escape', 27);
    await settle(fixture);
    expect(await tooltip.isOpen()).toBe(false);
  });

  it('uiTooltipDisabled keeps it closed and drops the description', async () => {
    const { fixture, loader } = await setup(DirectiveHostComponent);
    fixture.componentInstance.disabled.set(true);
    await settle(fixture);
    const tooltip = await loader.getHarness(MatTooltipHarness);
    expect(await tooltip.isDisabled()).toBe(true);
    await tooltip.show();
    await settle(fixture);
    expect(await tooltip.isOpen()).toBe(false);
    expect(descriptionIds(trigger(fixture))).toHaveLength(0);
  });

  it('does not show when focus is moved from code after earlier keyboard use', async () => {
    const { fixture } = await setup(DirectiveHostComponent);
    pressKey(outside(fixture), 'Tab', 9);
    await settle(fixture, 20);
    trigger(fixture).focus();
    await settle(fixture);
    expect(document.activeElement).toBe(trigger(fixture));
    expect(tooltipPanel()).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// <ui-tooltip> around <app-button> — the trigger sits in a child component view
// ---------------------------------------------------------------------------

describe('TooltipComponent — wrapping <app-button>', () => {
  function innerButton(fixture: ComponentFixture<unknown>): HTMLButtonElement {
    return fixture.nativeElement.querySelector('ui-tooltip app-button button');
  }

  it('describes the button rendered inside <app-button>', async () => {
    const { fixture } = await setup(AppButtonHostComponent);
    expect(innerButton(fixture)).not.toBeNull();
    expect(describedText(innerButton(fixture))).toBe('Save changes');
    expect(fixture.nativeElement.querySelector('app-button').hasAttribute('aria-describedby')).toBe(
      false,
    );
  });

  it('opens on hover', async () => {
    const { fixture, loader } = await setup(AppButtonHostComponent);
    const tooltip = await openWithHover(fixture, loader);
    expect(await tooltip.isOpen()).toBe(true);
    expect(await tooltip.getTooltipText()).toBe('Save changes');
  });

  it('shows on keyboard focus of the inner button and hides when focus leaves', async () => {
    const { fixture } = await setup(AppButtonHostComponent);
    focusWithKeyboard(innerButton(fixture));
    await settle(fixture);
    expect(tooltipPanel()?.textContent?.trim()).toBe('Save changes');

    focusWithKeyboard(outside(fixture));
    await settle(fixture);
    expect(tooltipPanel()).toBeNull();
  });
});
