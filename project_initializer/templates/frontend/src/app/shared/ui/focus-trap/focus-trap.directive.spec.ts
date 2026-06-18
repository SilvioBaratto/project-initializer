import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Component, signal } from '@angular/core';

import { FocusTrapDirective } from './focus-trap.directive';

// ---------------------------------------------------------------------------
// Host component: trigger outside the trap (for focus-restore test) + trap
// with >=2 focusable children
// ---------------------------------------------------------------------------

@Component({
  standalone: true,
  imports: [FocusTrapDirective],
  template: `
    <button id="trigger">Open</button>
    <div appFocusTrap [active]="isActive()" (close)="onClose()">
      <button id="first-btn">First</button>
      <button id="second-btn">Second</button>
    </div>
  `,
})
class HostComponent {
  isActive = signal(false);
  closedCount = 0;
  onClose(): void { this.closedCount++; }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function dispatchKeydown(target: EventTarget, key: string, shiftKey = false): void {
  target.dispatchEvent(
    new KeyboardEvent('keydown', { key, shiftKey, bubbles: true, cancelable: true }),
  );
}

function getTrapDiv(fixture: ComponentFixture<unknown>): HTMLElement {
  return fixture.nativeElement.querySelector('[appFocusTrap]') as HTMLElement;
}

// ---------------------------------------------------------------------------
// Suite setup: append to document.body so sibling inert logic can see siblings
// ---------------------------------------------------------------------------

function createFixture(): { fixture: ComponentFixture<HostComponent>; host: HostComponent } {
  const fixture = TestBed.createComponent(HostComponent);
  const host = fixture.componentInstance;
  document.body.appendChild(fixture.nativeElement);
  fixture.detectChanges();
  return { fixture, host };
}

// ---------------------------------------------------------------------------
// Host component structure
// ---------------------------------------------------------------------------

describe('FocusTrapDirective — host setup', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [HostComponent] }).compileComponents();
  });

  it('when rendered, the [appFocusTrap] element is present with >=2 focusable children', () => {
    const { fixture } = createFixture();
    const trap = getTrapDiv(fixture);
    const focusable = trap.querySelectorAll('button,input,a[href],select,textarea,[tabindex]');
    expect(focusable.length).toBeGreaterThanOrEqual(2);
    document.body.removeChild(fixture.nativeElement);
  });
});

// ---------------------------------------------------------------------------
// Initial focus
// ---------------------------------------------------------------------------

describe('FocusTrapDirective — initial focus', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [HostComponent] }).compileComponents();
  });

  afterEach(() => {
    // guard: element may have been removed already in the test
    const node = document.body.lastChild;
    if (node && document.body.contains(node)) document.body.removeChild(node);
  });

  it('when active becomes true, the first focusable child receives focus', () => {
    const { fixture, host } = createFixture();
    host.isActive.set(true);
    fixture.detectChanges();

    const first = fixture.nativeElement.querySelector('#first-btn') as HTMLElement;
    expect(document.activeElement).toBe(first);
    document.body.removeChild(fixture.nativeElement);
  });
});

// ---------------------------------------------------------------------------
// Tab / Shift+Tab wrap
// ---------------------------------------------------------------------------

describe('FocusTrapDirective — Tab/Shift+Tab wrap', () => {
  let fixture: ComponentFixture<HostComponent>;
  let host: HostComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [HostComponent] }).compileComponents();
    ({ fixture, host } = createFixture());
    host.isActive.set(true);
    fixture.detectChanges();
  });

  afterEach(() => {
    if (document.body.contains(fixture.nativeElement)) {
      document.body.removeChild(fixture.nativeElement);
    }
  });

  it('when Tab is pressed on the last focusable element, focus wraps to the first', () => {
    const second = fixture.nativeElement.querySelector('#second-btn') as HTMLElement;
    second.focus();
    dispatchKeydown(second, 'Tab');
    fixture.detectChanges();

    const first = fixture.nativeElement.querySelector('#first-btn') as HTMLElement;
    expect(document.activeElement).toBe(first);
  });

  it('when Shift+Tab is pressed on the first focusable element, focus wraps to the last', () => {
    const first = fixture.nativeElement.querySelector('#first-btn') as HTMLElement;
    first.focus();
    dispatchKeydown(first, 'Tab', true);
    fixture.detectChanges();

    const second = fixture.nativeElement.querySelector('#second-btn') as HTMLElement;
    expect(document.activeElement).toBe(second);
  });
});

// ---------------------------------------------------------------------------
// Escape → close output
// ---------------------------------------------------------------------------

describe('FocusTrapDirective — Escape emits close', () => {
  let fixture: ComponentFixture<HostComponent>;
  let host: HostComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [HostComponent] }).compileComponents();
    ({ fixture, host } = createFixture());
  });

  afterEach(() => {
    if (document.body.contains(fixture.nativeElement)) {
      document.body.removeChild(fixture.nativeElement);
    }
  });

  it('when Escape is pressed while active, the close output fires once', () => {
    host.isActive.set(true);
    fixture.detectChanges();

    const trap = getTrapDiv(fixture);
    dispatchKeydown(trap, 'Escape');
    fixture.detectChanges();

    expect(host.closedCount).toBe(1);
  });

  it('when Escape is pressed while inactive, the close output does not fire', () => {
    host.isActive.set(false);
    fixture.detectChanges();

    const trap = getTrapDiv(fixture);
    dispatchKeydown(trap, 'Escape');
    fixture.detectChanges();

    expect(host.closedCount).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// Sibling inert + aria-hidden
// ---------------------------------------------------------------------------

describe('FocusTrapDirective — sibling inert/aria-hidden', () => {
  let fixture: ComponentFixture<HostComponent>;
  let host: HostComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [HostComponent] }).compileComponents();
    ({ fixture, host } = createFixture());
  });

  afterEach(() => {
    if (document.body.contains(fixture.nativeElement)) {
      document.body.removeChild(fixture.nativeElement);
    }
  });

  it('when active, sibling elements of the trap receive the inert attribute', () => {
    host.isActive.set(true);
    fixture.detectChanges();

    const trigger = fixture.nativeElement.querySelector('#trigger') as HTMLElement;
    // The trigger lives in the host element which is a sibling of the trap div inside
    // the fixture nativeElement. We need to check the trigger's parent (the wrapper
    // that contains both the trigger button and the trap div).
    const trapDiv = getTrapDiv(fixture);
    const parent = trapDiv.parentElement!;
    const siblings = Array.from(parent.children).filter(c => c !== trapDiv);

    expect(siblings.length).toBeGreaterThan(0);
    siblings.forEach(sibling => {
      expect(sibling.hasAttribute('inert')).toBe(true);
      expect(sibling.getAttribute('aria-hidden')).toBe('true');
    });
  });

  it('when deactivated, inert and aria-hidden are removed from sibling elements', () => {
    host.isActive.set(true);
    fixture.detectChanges();

    host.isActive.set(false);
    fixture.detectChanges();

    const trapDiv = getTrapDiv(fixture);
    const parent = trapDiv.parentElement!;
    const siblings = Array.from(parent.children).filter(c => c !== trapDiv);

    siblings.forEach(sibling => {
      expect(sibling.hasAttribute('inert')).toBe(false);
      expect(sibling.hasAttribute('aria-hidden')).toBe(false);
    });
  });
});

// ---------------------------------------------------------------------------
// Focus restoration
// ---------------------------------------------------------------------------

describe('FocusTrapDirective — focus restoration', () => {
  let fixture: ComponentFixture<HostComponent>;
  let host: HostComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [HostComponent] }).compileComponents();
    ({ fixture, host } = createFixture());
  });

  afterEach(() => {
    if (document.body.contains(fixture.nativeElement)) {
      document.body.removeChild(fixture.nativeElement);
    }
  });

  it('when deactivated, focus returns to the element focused before activation', () => {
    const trigger = fixture.nativeElement.querySelector('#trigger') as HTMLElement;
    trigger.focus();
    expect(document.activeElement).toBe(trigger);

    host.isActive.set(true);
    fixture.detectChanges();

    host.isActive.set(false);
    fixture.detectChanges();

    expect(document.activeElement).toBe(trigger);
  });
});
