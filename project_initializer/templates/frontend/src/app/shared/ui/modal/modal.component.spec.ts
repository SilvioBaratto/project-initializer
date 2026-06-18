/**
 * Spec for issue #11: Modal overlay — WAI-ARIA contract, JS focus trap,
 * Escape/backdrop close, background inert, signal API, dark-mode tokens.
 *
 * Source-blind: authored from acceptance criteria only (Red phase of TDD).
 * These tests fail until the ModalComponent is implemented.
 *
 * Skipped criteria (oracle: NOT VERIFIABLE at unit tier):
 *   - SlideOver layout (h-dvh, edge-slide, safe-area)
 *   - "All tests pass" gate
 *   - SOLID/clean-code metrics
 */

import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Component, DebugElement, signal } from '@angular/core';
import { By } from '@angular/platform-browser';

// The component under test — does not exist yet (Red phase).
// The import will fail at build time until the component is created.
import { ModalComponent } from './modal';

// ---------------------------------------------------------------------------
// Host stub for testing signal input / output bindings
// ---------------------------------------------------------------------------

@Component({
  standalone: true,
  imports: [ModalComponent],
  template: `
    <app-modal
      [open]="isOpen()"
      (closed)="onClosed()"
    >
      <button class="focus-visible:ring-2" id="first-btn">First</button>
      <button class="focus-visible:ring-2" id="second-btn">Second</button>
    </app-modal>
  `,
})
class HostComponent {
  isOpen = signal(false);
  closedCount = 0;
  onClosed() { this.closedCount++; }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getModalPanel(fixture: ComponentFixture<unknown>): HTMLElement | null {
  return fixture.nativeElement.querySelector('[role="dialog"]');
}

function dispatchKeydown(target: EventTarget, key: string): void {
  target.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true }));
}

// ---------------------------------------------------------------------------
// Criterion A-1: role="dialog" + aria-modal
// ---------------------------------------------------------------------------

describe('ModalComponent — ARIA contract', () => {
  let fixture: ComponentFixture<HostComponent>;
  let host: HostComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [HostComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(HostComponent);
    host = fixture.componentInstance;
  });

  it('when modal is open, role="dialog" is present on the panel', () => {
    host.isOpen.set(true);
    fixture.detectChanges();

    const panel = getModalPanel(fixture);
    expect(panel).not.toBeNull();
    expect(panel?.getAttribute('role')).toBe('dialog');
  });

  it('when modal is open, aria-modal="true" is present on the panel', () => {
    host.isOpen.set(true);
    fixture.detectChanges();

    const panel = getModalPanel(fixture);
    expect(panel?.getAttribute('aria-modal')).toBe('true');
  });

  it('when modal is open, the dialog has an accessible label (aria-label or aria-labelledby)', () => {
    host.isOpen.set(true);
    fixture.detectChanges();

    const panel = getModalPanel(fixture);
    const hasLabel =
      panel?.hasAttribute('aria-label') ||
      panel?.hasAttribute('aria-labelledby');
    expect(hasLabel).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Criterion A-2: JS focus trap (Tab / Shift+Tab cycles inside the dialog)
// ---------------------------------------------------------------------------

describe('ModalComponent — focus trap', () => {
  let fixture: ComponentFixture<HostComponent>;
  let host: HostComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [HostComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(HostComponent);
    host = fixture.componentInstance;
    document.body.appendChild(fixture.nativeElement);
  });

  afterEach(() => {
    document.body.removeChild(fixture.nativeElement);
  });

  it('when modal opens, first focusable element inside receives focus', () => {
    host.isOpen.set(true);
    fixture.detectChanges();

    const first = fixture.nativeElement.querySelector('#first-btn') as HTMLElement | null;
    expect(document.activeElement).toBe(first);
  });

  it('when Tab is pressed on the last focusable element, focus wraps to the first', () => {
    host.isOpen.set(true);
    fixture.detectChanges();

    const second = fixture.nativeElement.querySelector('#second-btn') as HTMLElement;
    second.focus();
    dispatchKeydown(second, 'Tab');
    fixture.detectChanges();

    const first = fixture.nativeElement.querySelector('#first-btn') as HTMLElement;
    expect(document.activeElement).toBe(first);
  });

  it('when Shift+Tab is pressed on the first focusable element, focus wraps to the last', () => {
    host.isOpen.set(true);
    fixture.detectChanges();

    const first = fixture.nativeElement.querySelector('#first-btn') as HTMLElement;
    first.focus();
    first.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, bubbles: true, cancelable: true })
    );
    fixture.detectChanges();

    const second = fixture.nativeElement.querySelector('#second-btn') as HTMLElement;
    expect(document.activeElement).toBe(second);
  });
});

// ---------------------------------------------------------------------------
// Criterion A-3: Escape key closes the modal
// ---------------------------------------------------------------------------

describe('ModalComponent — Escape key closes', () => {
  let fixture: ComponentFixture<HostComponent>;
  let host: HostComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [HostComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(HostComponent);
    host = fixture.componentInstance;
    document.body.appendChild(fixture.nativeElement);
  });

  afterEach(() => {
    document.body.removeChild(fixture.nativeElement);
  });

  it('when Escape is pressed while modal is open, the closed output fires', () => {
    host.isOpen.set(true);
    fixture.detectChanges();

    dispatchKeydown(document, 'Escape');
    fixture.detectChanges();

    expect(host.closedCount).toBe(1);
  });
});

// ---------------------------------------------------------------------------
// Criterion A-4: Backdrop click closes the modal
// ---------------------------------------------------------------------------

describe('ModalComponent — backdrop click closes', () => {
  let fixture: ComponentFixture<HostComponent>;
  let host: HostComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [HostComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(HostComponent);
    host = fixture.componentInstance;
    document.body.appendChild(fixture.nativeElement);
  });

  afterEach(() => {
    document.body.removeChild(fixture.nativeElement);
  });

  it('when backdrop is clicked, the closed output fires', () => {
    host.isOpen.set(true);
    fixture.detectChanges();

    // The backdrop is a sibling/ancestor of the dialog panel with a (click) binding.
    // Query for an element that is NOT the dialog panel itself.
    const backdrop = fixture.nativeElement.querySelector('[data-testid="modal-backdrop"]') as HTMLElement | null;
    expect(backdrop).not.toBeNull();
    backdrop!.click();
    fixture.detectChanges();

    expect(host.closedCount).toBe(1);
  });

  it('when the dialog panel itself is clicked, the closed output does NOT fire', () => {
    host.isOpen.set(true);
    fixture.detectChanges();

    const panel = getModalPanel(fixture) as HTMLElement;
    panel.click();
    fixture.detectChanges();

    expect(host.closedCount).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// Criterion A-5: Background is inerted in code when modal is open
// ---------------------------------------------------------------------------

describe('ModalComponent — background inert', () => {
  let fixture: ComponentFixture<HostComponent>;
  let host: HostComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [HostComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(HostComponent);
    host = fixture.componentInstance;
    document.body.appendChild(fixture.nativeElement);
  });

  afterEach(() => {
    document.body.removeChild(fixture.nativeElement);
  });

  it('when modal is open, the main page content carries the inert attribute', () => {
    /**
     * Choice (criterion is ambiguous about which element): we expect a sibling
     * element with [data-testid="main-content"] or <main> to receive inert.
     * The implementation may use any selector; test targets the observable DOM
     * attribute on the main content region.
     */
    const main = document.createElement('main');
    main.id = 'main-content';
    document.body.insertBefore(main, fixture.nativeElement);

    host.isOpen.set(true);
    fixture.detectChanges();

    expect(main.hasAttribute('inert')).toBe(true);

    document.body.removeChild(main);
  });

  it('when modal is closed, the inert attribute is removed from the main content', () => {
    const main = document.createElement('main');
    main.id = 'main-content';
    document.body.insertBefore(main, fixture.nativeElement);

    host.isOpen.set(true);
    fixture.detectChanges();

    host.isOpen.set(false);
    fixture.detectChanges();

    expect(main.hasAttribute('inert')).toBe(false);

    document.body.removeChild(main);
  });
});

// ---------------------------------------------------------------------------
// Criterion B-1: Open/close driven by signal input() / output()
// ---------------------------------------------------------------------------

describe('ModalComponent — signal input/output API', () => {
  let fixture: ComponentFixture<HostComponent>;
  let host: HostComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [HostComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(HostComponent);
    host = fixture.componentInstance;
  });

  it('when open input is false, the dialog panel is not present in the DOM', () => {
    host.isOpen.set(false);
    fixture.detectChanges();

    const panel = getModalPanel(fixture);
    expect(panel).toBeNull();
  });

  it('when open input changes from false to true, the dialog panel appears', () => {
    host.isOpen.set(false);
    fixture.detectChanges();

    host.isOpen.set(true);
    fixture.detectChanges();

    const panel = getModalPanel(fixture);
    expect(panel).not.toBeNull();
  });

  it('when open input changes from true to false, the dialog panel disappears', () => {
    host.isOpen.set(true);
    fixture.detectChanges();

    host.isOpen.set(false);
    fixture.detectChanges();

    const panel = getModalPanel(fixture);
    expect(panel).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Criterion B-2: Visible focus — focus-visible ring not suppressed
// ---------------------------------------------------------------------------

describe('ModalComponent — visible focus (focus-visible ring)', () => {
  it('when modal renders, no interactive child has outline suppressed without focus-visible replacement', async () => {
    /**
     * Choice: we assert that the ModalComponent template does not include
     * the bare class "outline-none" without a companion "focus-visible:*" class
     * on the same element.  We inspect the rendered DOM rather than the source.
     */
    await TestBed.configureTestingModule({
      imports: [HostComponent],
    }).compileComponents();

    const fixture = TestBed.createComponent(HostComponent);
    (fixture.componentInstance as HostComponent).isOpen.set(true);
    fixture.detectChanges();

    const allElements: NodeListOf<Element> = fixture.nativeElement.querySelectorAll('*');
    allElements.forEach((el) => {
      const classes = Array.from(el.classList);
      const suppressesOutline = classes.includes('outline-none');
      const hasFocusVisible = classes.some((c) => c.startsWith('focus-visible:'));
      if (suppressesOutline) {
        expect(hasFocusVisible).toBe(true);
      }
    });
  });
});

// ---------------------------------------------------------------------------
// Criterion B-3: Dark-mode tokens — dark: variant classes present
// ---------------------------------------------------------------------------

describe('ModalComponent — dark-mode tokens', () => {
  it('when modal renders, at least one dark: Tailwind class is present on an element', async () => {
    await TestBed.configureTestingModule({
      imports: [HostComponent],
    }).compileComponents();

    const fixture = TestBed.createComponent(HostComponent);
    (fixture.componentInstance as HostComponent).isOpen.set(true);
    fixture.detectChanges();

    const allElements: NodeListOf<Element> = fixture.nativeElement.querySelectorAll('*');
    let hasDarkClass = false;
    allElements.forEach((el) => {
      if (Array.from(el.classList).some((c) => c.startsWith('dark:'))) {
        hasDarkClass = true;
      }
    });
    expect(hasDarkClass).toBe(true);
  });

  it('when modal renders, no inline hardcoded hex colour is present', async () => {
    await TestBed.configureTestingModule({
      imports: [HostComponent],
    }).compileComponents();

    const fixture = TestBed.createComponent(HostComponent);
    (fixture.componentInstance as HostComponent).isOpen.set(true);
    fixture.detectChanges();

    const allElements: NodeListOf<Element> = fixture.nativeElement.querySelectorAll('[style]');
    allElements.forEach((el) => {
      const style = (el as HTMLElement).style.cssText;
      expect(style).not.toMatch(/#[0-9a-fA-F]{3,6}/);
    });
  });
});
