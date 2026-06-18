import { Component } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { TooltipComponent } from './tooltip';

// ---------------------------------------------------------------------------
// Host stub
// ---------------------------------------------------------------------------

@Component({
  imports: [TooltipComponent],
  template: `
    <ui-tooltip text="Save changes">
      <button id="trigger-btn">Save</button>
    </ui-tooltip>
  `,
})
class HostComponent {}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function dispatchKey(target: EventTarget, key: string): void {
  target.dispatchEvent(
    new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true }),
  );
}

function getTooltip(fixture: ComponentFixture<unknown>): TooltipComponent {
  return fixture.debugElement.children[0].componentInstance as TooltipComponent;
}

// ---------------------------------------------------------------------------
// Criterion 1 — role="tooltip", linked to the trigger via aria-describedby
// ---------------------------------------------------------------------------

describe('TooltipComponent — ARIA contract', () => {
  let fixture: ComponentFixture<HostComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [HostComponent] }).compileComponents();
    fixture = TestBed.createComponent(HostComponent);
    getTooltip(fixture).visible.set(true);
    fixture.detectChanges();
  });

  it('when tooltip is visible, an element with role="tooltip" is present', () => {
    const el = fixture.nativeElement.querySelector('[role="tooltip"]');
    expect(el).not.toBeNull();
  });

  it('when tooltip is visible, the trigger wrapper has aria-describedby matching the tooltip id', () => {
    const wrapper = fixture.nativeElement.querySelector('span[aria-describedby]');
    const tooltip = fixture.nativeElement.querySelector('[role="tooltip"]');
    expect(wrapper).not.toBeNull();
    expect(wrapper!.getAttribute('aria-describedby')).toBe(tooltip!.id);
  });

  it('when tooltip is visible, the tooltip element has a non-empty id', () => {
    const tooltip = fixture.nativeElement.querySelector('[role="tooltip"]');
    expect(tooltip?.id).toBeTruthy();
  });

  it('when tooltip is visible, it renders the text input value', () => {
    const tooltip = fixture.nativeElement.querySelector('[role="tooltip"]');
    expect(tooltip?.textContent?.trim()).toBe('Save changes');
  });
});

// ---------------------------------------------------------------------------
// Criterion 2 — Shows on hover/focus; touch fallback; Escape dismisses
// ---------------------------------------------------------------------------

describe('TooltipComponent — show / hide triggers', () => {
  let fixture: ComponentFixture<HostComponent>;
  let tooltip: TooltipComponent;
  let host: HTMLElement;

  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [HostComponent] }).compileComponents();
    fixture = TestBed.createComponent(HostComponent);
    document.body.appendChild(fixture.nativeElement);
    fixture.detectChanges();
    tooltip = getTooltip(fixture);
    host = fixture.nativeElement.querySelector('ui-tooltip') as HTMLElement;
  });

  afterEach(() => {
    document.body.removeChild(fixture.nativeElement);
  });

  it('when mouseenter fires on the host, the tooltip becomes visible', () => {
    expect(tooltip.visible()).toBe(false);
    host.dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }));
    fixture.detectChanges();
    expect(tooltip.visible()).toBe(true);
  });

  it('when mouseleave fires on the host, the tooltip becomes hidden', () => {
    tooltip.show();
    fixture.detectChanges();
    host.dispatchEvent(new MouseEvent('mouseleave', { bubbles: true }));
    fixture.detectChanges();
    expect(tooltip.visible()).toBe(false);
  });

  it('when focusin fires on the host, the tooltip becomes visible', () => {
    expect(tooltip.visible()).toBe(false);
    host.dispatchEvent(new FocusEvent('focusin', { bubbles: true }));
    fixture.detectChanges();
    expect(tooltip.visible()).toBe(true);
  });

  it('when focusout fires on the host, the tooltip becomes hidden', () => {
    tooltip.show();
    fixture.detectChanges();
    host.dispatchEvent(new FocusEvent('focusout', { bubbles: true }));
    fixture.detectChanges();
    expect(tooltip.visible()).toBe(false);
  });

  it('when touchstart fires on the host, the tooltip toggles to visible', () => {
    expect(tooltip.visible()).toBe(false);
    host.dispatchEvent(new TouchEvent('touchstart', { bubbles: true, cancelable: true }));
    fixture.detectChanges();
    expect(tooltip.visible()).toBe(true);
  });

  it('when touchstart fires twice on the host, the tooltip toggles back to hidden', () => {
    host.dispatchEvent(new TouchEvent('touchstart', { bubbles: true, cancelable: true }));
    fixture.detectChanges();
    host.dispatchEvent(new TouchEvent('touchstart', { bubbles: true, cancelable: true }));
    fixture.detectChanges();
    expect(tooltip.visible()).toBe(false);
  });

  it('when Escape is pressed while tooltip is visible, it is dismissed', () => {
    tooltip.show();
    fixture.detectChanges();
    dispatchKey(document, 'Escape');
    fixture.detectChanges();
    expect(tooltip.visible()).toBe(false);
  });

  it('when Escape is pressed while tooltip is already hidden, visible stays false', () => {
    expect(tooltip.visible()).toBe(false);
    dispatchKey(document, 'Escape');
    fixture.detectChanges();
    expect(tooltip.visible()).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Escape idempotence — pressing twice keeps it hidden
// ---------------------------------------------------------------------------

describe('TooltipComponent — Escape is idempotent', () => {
  let fixture: ComponentFixture<HostComponent>;
  let tooltip: TooltipComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [HostComponent] }).compileComponents();
    fixture = TestBed.createComponent(HostComponent);
    document.body.appendChild(fixture.nativeElement);
    fixture.detectChanges();
    tooltip = getTooltip(fixture);
  });

  afterEach(() => {
    document.body.removeChild(fixture.nativeElement);
  });

  it('when Escape is pressed twice while tooltip is open, it stays hidden', () => {
    tooltip.show();
    fixture.detectChanges();
    dispatchKey(document, 'Escape');
    fixture.detectChanges();
    dispatchKey(document, 'Escape');
    fixture.detectChanges();
    expect(tooltip.visible()).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Visibility gating — tooltip DOM element present only when active
// ---------------------------------------------------------------------------

describe('TooltipComponent — visibility gating', () => {
  let fixture: ComponentFixture<HostComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [HostComponent] }).compileComponents();
    fixture = TestBed.createComponent(HostComponent);
    fixture.detectChanges();
  });

  it('when tooltip is hidden, role=tooltip element is not in the DOM', () => {
    getTooltip(fixture).visible.set(false);
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('[role="tooltip"]')).toBeNull();
  });

  it('when tooltip becomes visible, role=tooltip element appears', () => {
    getTooltip(fixture).visible.set(true);
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('[role="tooltip"]')).not.toBeNull();
  });

  it('when tooltip becomes hidden again, role=tooltip element is removed', () => {
    const t = getTooltip(fixture);
    t.visible.set(true);
    fixture.detectChanges();
    t.visible.set(false);
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('[role="tooltip"]')).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// No hardcoded hex colours
// ---------------------------------------------------------------------------

describe('TooltipComponent — token colours only', () => {
  it('when rendered, no inline hardcoded hex colour appears', async () => {
    await TestBed.configureTestingModule({ imports: [HostComponent] }).compileComponents();
    const fixture = TestBed.createComponent(HostComponent);
    getTooltip(fixture).visible.set(true);
    fixture.detectChanges();
    const hexPattern = /#[0-9a-fA-F]{3,8}\b/;
    const root = fixture.nativeElement as HTMLElement;
    const all: HTMLElement[] = [root, ...Array.from(root.querySelectorAll('*') as NodeListOf<HTMLElement>)];
    for (const el of all) {
      expect(el.getAttribute('style') ?? '').not.toMatch(hexPattern);
    }
  });
});
