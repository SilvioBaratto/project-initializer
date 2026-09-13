import { Component, Type, signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HarnessLoader } from '@angular/cdk/testing';
import { TestbedHarnessEnvironment } from '@angular/cdk/testing/testbed';
import { MatAutocompleteModule } from '@angular/material/autocomplete';
import { MatAutocompleteHarness } from '@angular/material/autocomplete/testing';
import { MATERIAL_ANIMATIONS } from '@angular/material/core';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatSelectHarness } from '@angular/material/select/testing';
import { vi } from 'vitest';

import { FocusTrapDirective } from './focus-trap.directive';

// ---------------------------------------------------------------------------
// Host components
// ---------------------------------------------------------------------------

/** Trigger and background siblings around a trap with >=2 focusable children. */
@Component({
  imports: [FocusTrapDirective],
  template: `
    <button id="trigger" type="button">Open</button>
    <p id="note" aria-hidden="true">Decorative note</p>
    @if (rendered()) {
      <div appFocusTrap [active]="isActive()" (close)="onClose()">
        <button id="first-btn" type="button">First</button>
        <button id="second-btn" type="button">Second</button>
      </div>
    }
    <button id="after" type="button">After</button>
  `,
})
class HostComponent {
  readonly isActive = signal(false);
  readonly rendered = signal(true);
  closedCount = 0;
  onClose(): void {
    this.closedCount++;
  }
}

/** A trap whose preferred initial focus target is marked with cdkFocusInitial. */
@Component({
  imports: [FocusTrapDirective],
  template: `
    <div appFocusTrap [active]="true">
      <button id="plain" type="button">Plain</button>
      <input id="preferred" cdkFocusInitial aria-label="Name" />
    </div>
  `,
})
class InitialFocusHostComponent {}

/** A text-only dialog: nothing inside the trap can take focus. */
@Component({
  imports: [FocusTrapDirective],
  template: `
    <button id="text-trigger" type="button">Show details</button>
    <div id="text-dialog" role="dialog" aria-label="Details" appFocusTrap [active]="isActive()">
      <p>Your changes are saved on this device only</p>
    </div>
    <button id="text-after" type="button">After</button>
  `,
})
class TextOnlyHostComponent {
  readonly isActive = signal(false);
}

/** An inner trap (for example a dialog) opened from inside an outer trap (for example a drawer). */
@Component({
  imports: [FocusTrapDirective],
  template: `
    <div id="outer" appFocusTrap [active]="outerActive()" (close)="onOuterClose()">
      <button id="outer-btn" type="button">Outer</button>
      <section>
        <div id="inner" appFocusTrap [active]="innerActive()" (close)="onInnerClose()">
          <button id="inner-first" type="button">Inner first</button>
          <button id="inner-last" type="button">Inner last</button>
        </div>
      </section>
    </div>
  `,
})
class NestedHostComponent {
  readonly outerActive = signal(false);
  readonly innerActive = signal(false);
  outerClosed = 0;
  innerClosed = 0;
  onOuterClose(): void {
    this.outerClosed++;
  }
  onInnerClose(): void {
    this.innerClosed++;
  }
}

/** A trap nested inside page structure, as a panel inside main, beside a header and navigation. */
@Component({
  imports: [FocusTrapDirective],
  template: `
    <header id="page-header"><button id="menu" type="button">Menu</button></header>
    <nav id="page-nav" aria-label="Main"><a href="/home">Home</a></nav>
    <main id="page-main">
      <h1 id="page-title">Orders</h1>
      <section id="panel">
        <div appFocusTrap [active]="isActive()">
          <button type="button">Save order</button>
        </div>
      </section>
    </main>
    <div id="page-live" aria-live="polite"></div>
    <div id="page-backdrop" class="cdk-overlay-backdrop"></div>
  `,
})
class NestedPageHostComponent {
  readonly isActive = signal(false);
}

/** A child widget that consumes Escape itself (for example a search field clearing its query). */
@Component({
  imports: [FocusTrapDirective],
  template: `
    <div appFocusTrap [active]="true" (close)="onClose()">
      <button id="consumes-escape" type="button" (keydown.escape)="$event.preventDefault()">Clear search</button>
      <button type="button">Done</button>
    </div>
  `,
})
class EscapeConsumerHostComponent {
  closedCount = 0;
  onClose(): void {
    this.closedCount++;
  }
}

/** Material comboboxes inside an active trap. */
@Component({
  imports: [FocusTrapDirective, MatFormFieldModule, MatInputModule, MatSelectModule, MatAutocompleteModule],
  template: `
    <button id="combobox-trigger" type="button">Edit address</button>
    <div appFocusTrap [active]="true" (close)="onClose()">
      <mat-form-field>
        <mat-label>Country</mat-label>
        <mat-select id="country">
          <mat-option value="it">Italy</mat-option>
          <mat-option value="fr">France</mat-option>
        </mat-select>
      </mat-form-field>
      <mat-form-field>
        <mat-label>City</mat-label>
        <input id="city" matInput [matAutocomplete]="cities" />
        <mat-autocomplete #cities="matAutocomplete">
          <mat-option value="Rome">Rome</mat-option>
          <mat-option value="Milan">Milan</mat-option>
        </mat-autocomplete>
      </mat-form-field>
    </div>
  `,
})
class ComboboxHostComponent {
  closedCount = 0;
  onClose(): void {
    this.closedCount++;
  }
}

/** A collapsed autocomplete inside an inner trap nested in an outer trap. */
@Component({
  imports: [FocusTrapDirective, MatFormFieldModule, MatInputModule, MatAutocompleteModule],
  template: `
    <div appFocusTrap [active]="true" (close)="onOuterClose()">
      <button type="button">Outer</button>
      <section>
        <div appFocusTrap [active]="true" (close)="onInnerClose()">
          <button type="button">Inner</button>
          <mat-form-field>
            <mat-label>City</mat-label>
            <input id="nested-city" matInput [matAutocomplete]="nestedCities" />
            <mat-autocomplete #nestedCities="matAutocomplete">
              <mat-option value="Rome">Rome</mat-option>
            </mat-autocomplete>
          </mat-form-field>
        </div>
      </section>
    </div>
  `,
})
class NestedComboboxHostComponent {
  outerClosed = 0;
  innerClosed = 0;
  onOuterClose(): void {
    this.outerClosed++;
  }
  onInnerClose(): void {
    this.innerClosed++;
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const ANCHOR_SELECTOR = '.cdk-focus-trap-anchor';
const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]';

/** Material and the CDK still read the legacy keyCode, which a constructed KeyboardEvent leaves at 0. */
const KEY_CODES: Record<string, number> = { Tab: 9, Enter: 13, Escape: 27 };

const mounted: ComponentFixture<unknown>[] = [];

/** Appends the host to document.body so sibling inert/aria-hidden logic sees real DOM siblings. */
function mount<T>(type: Type<T>): ComponentFixture<T> {
  const fixture = TestBed.createComponent(type);
  document.body.appendChild(fixture.nativeElement);
  mounted.push(fixture);
  return fixture;
}

async function settle(fixture: ComponentFixture<unknown>): Promise<void> {
  fixture.detectChanges();
  await fixture.whenStable();
}

function byId(id: string): HTMLElement {
  const element = document.getElementById(id);
  if (!element) throw new Error(`#${id} is not rendered`);
  return element;
}

function dispatchKeydown(target: EventTarget, key: string, init: KeyboardEventInit = {}): KeyboardEvent {
  const event = new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true, ...init });
  Object.defineProperty(event, 'keyCode', { get: () => KEY_CODES[key] ?? 0 });
  target.dispatchEvent(event);
  return event;
}

/**
 * Presses Tab the way a browser does. jsdom dispatches the keydown but has no sequential focus
 * navigation, so move focus to the next (or previous) tabbable element in document order, skipping
 * anything inside an inert subtree. The start point may itself be out of the tab order (a
 * tabindex="-1" host). The CDK focus anchors take part like any tabbable element.
 */
function pressTab(shiftKey = false): void {
  const from = document.activeElement as HTMLElement;
  const notCancelled = from.dispatchEvent(
    new KeyboardEvent('keydown', { key: 'Tab', shiftKey, bubbles: true, cancelable: true }),
  );
  if (!notCancelled) return;
  const order = Array.from(document.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
    (element) => element !== from && element.tabIndex >= 0 && !element.closest('[inert]'),
  );
  const follows = (element: HTMLElement) =>
    (from.compareDocumentPosition(element) & Node.DOCUMENT_POSITION_FOLLOWING) !== 0;
  const next = shiftKey ? order.filter((element) => !follows(element)).at(-1) : order.find(follows);
  next?.focus();
}

function trapOf(fixture: ComponentFixture<unknown>): HTMLElement {
  return fixture.nativeElement.querySelector('[appFocusTrap]') as HTMLElement;
}

/** Sibling elements of the trap host, without the CDK focus anchors. */
function backgroundSiblings(trap: HTMLElement): Element[] {
  return Array.from(trap.parentElement!.children).filter(
    (child) => child !== trap && !child.matches(ANCHOR_SELECTOR),
  );
}

async function nextMacrotask(): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve));
}

describe('FocusTrapDirective', () => {
  beforeEach(() => {
    // jsdom has no layout: every element reports no client rects, so the CDK InteractivityChecker
    // would treat all of them as hidden and untabbable. Give elements geometry so tabbability
    // is decided by the DOM alone, as in a browser.
    vi.spyOn(Element.prototype, 'getClientRects').mockReturnValue([
      { width: 100, height: 40 },
    ] as unknown as DOMRectList);
  });

  afterEach(() => {
    for (const fixture of mounted.splice(0)) {
      fixture.destroy();
      (fixture.nativeElement as HTMLElement).remove();
    }
    vi.restoreAllMocks();
  });

  // -------------------------------------------------------------------------
  // Host component structure
  // -------------------------------------------------------------------------

  describe('host setup', () => {
    it('when rendered, the [appFocusTrap] element is present with >=2 focusable children', async () => {
      const fixture = mount(HostComponent);
      await settle(fixture);

      const focusable = trapOf(fixture).querySelectorAll(FOCUSABLE);
      expect(focusable.length).toBeGreaterThanOrEqual(2);
    });

    it('when inactive, no CDK focus anchors are attached and siblings are untouched', async () => {
      const fixture = mount(HostComponent);
      await settle(fixture);

      expect(document.querySelectorAll(ANCHOR_SELECTOR).length).toBe(0);
      expect(byId('trigger').hasAttribute('inert')).toBe(false);
      expect(byId('trigger').hasAttribute('aria-hidden')).toBe(false);
    });
  });

  // -------------------------------------------------------------------------
  // Initial focus
  // -------------------------------------------------------------------------

  describe('initial focus', () => {
    it('when active becomes true, the first focusable child receives focus', async () => {
      const fixture = mount(HostComponent);
      await settle(fixture);

      fixture.componentInstance.isActive.set(true);
      await settle(fixture);

      expect(document.activeElement).toBe(byId('first-btn'));
    });

    it('when a child is marked cdkFocusInitial, that child receives focus instead', async () => {
      const fixture = mount(InitialFocusHostComponent);
      await settle(fixture);

      expect(document.activeElement).toBe(byId('preferred'));
    });
  });

  // -------------------------------------------------------------------------
  // Host without tabbable content (text-only dialog)
  // -------------------------------------------------------------------------

  describe('host without tabbable content', () => {
    let fixture: ComponentFixture<TextOnlyHostComponent>;

    beforeEach(async () => {
      fixture = mount(TextOnlyHostComponent);
      await settle(fixture);
      byId('text-trigger').focus();
      fixture.componentInstance.isActive.set(true);
      await settle(fixture);
    });

    it('when activated, the host itself receives focus through tabindex="-1"', () => {
      const dialog = byId('text-dialog');
      expect(document.activeElement).toBe(dialog);
      expect(dialog.getAttribute('tabindex')).toBe('-1');
    });

    it('when Tab or Shift+Tab is pressed, focus stays on the host instead of a hidden anchor', () => {
      const dialog = byId('text-dialog');

      pressTab();
      expect(document.activeElement).toBe(dialog);

      pressTab(true);
      expect(document.activeElement).toBe(dialog);
    });

    it('when deactivated, the added tabindex is removed and focus returns to the trigger', async () => {
      fixture.componentInstance.isActive.set(false);
      await settle(fixture);

      expect(byId('text-dialog').hasAttribute('tabindex')).toBe(false);
      expect(document.activeElement).toBe(byId('text-trigger'));
    });
  });

  // -------------------------------------------------------------------------
  // Tab / Shift+Tab wrap (CDK focus anchors)
  // -------------------------------------------------------------------------

  describe('Tab/Shift+Tab wrap', () => {
    let fixture: ComponentFixture<HostComponent>;

    beforeEach(async () => {
      fixture = mount(HostComponent);
      fixture.componentInstance.isActive.set(true);
      await settle(fixture);
    });

    it('when active, a tabbable CDK focus anchor sits on each side of the host', () => {
      const trap = trapOf(fixture);
      expect(trap.previousElementSibling?.matches(ANCHOR_SELECTOR)).toBe(true);
      expect(trap.nextElementSibling?.matches(ANCHOR_SELECTOR)).toBe(true);
      trap.parentElement!.querySelectorAll(ANCHOR_SELECTOR).forEach((anchor) => {
        expect(anchor.getAttribute('tabindex')).toBe('0');
        expect(anchor.getAttribute('aria-hidden')).toBe('true');
        expect(anchor.hasAttribute('inert')).toBe(false);
      });
    });

    it('when a host has tabbable children, it gets no tabindex of its own', () => {
      expect(trapOf(fixture).hasAttribute('tabindex')).toBe(false);
    });

    it('when Tab is pressed on the last focusable element, focus wraps to the first', () => {
      byId('second-btn').focus();
      pressTab();

      expect(document.activeElement).toBe(byId('first-btn'));
    });

    it('when Shift+Tab is pressed on the first focusable element, focus wraps to the last', () => {
      byId('first-btn').focus();
      pressTab(true);

      expect(document.activeElement).toBe(byId('second-btn'));
    });

    it('when Tab is pressed between children, focus moves to the next child', () => {
      byId('first-btn').focus();
      pressTab();

      expect(document.activeElement).toBe(byId('second-btn'));
    });

    it('when focus is moved outside the host while active, focus is pulled back inside', async () => {
      const outside = document.createElement('button');
      outside.type = 'button';
      document.body.appendChild(outside);

      outside.focus();
      await nextMacrotask();

      expect(document.activeElement).toBe(byId('first-btn'));
      outside.remove();
    });

    it('when deactivated, the CDK focus anchors are removed and Tab leaves the host', async () => {
      fixture.componentInstance.isActive.set(false);
      await settle(fixture);

      expect(document.querySelectorAll(ANCHOR_SELECTOR).length).toBe(0);
      byId('second-btn').focus();
      pressTab();
      expect(document.activeElement).toBe(byId('after'));
    });
  });

  // -------------------------------------------------------------------------
  // Escape -> close output
  // -------------------------------------------------------------------------

  describe('Escape emits close', () => {
    let fixture: ComponentFixture<HostComponent>;

    beforeEach(async () => {
      fixture = mount(HostComponent);
      await settle(fixture);
    });

    it('when Escape is pressed while active, the close output fires once', async () => {
      fixture.componentInstance.isActive.set(true);
      await settle(fixture);

      const event = dispatchKeydown(byId('first-btn'), 'Escape');

      expect(fixture.componentInstance.closedCount).toBe(1);
      expect(event.defaultPrevented).toBe(true);
    });

    it('when Escape is pressed while inactive, the close output does not fire', async () => {
      fixture.componentInstance.isActive.set(false);
      await settle(fixture);

      dispatchKeydown(trapOf(fixture), 'Escape');

      expect(fixture.componentInstance.closedCount).toBe(0);
    });

    it('when Escape is pressed with a modifier key, the close output does not fire', async () => {
      fixture.componentInstance.isActive.set(true);
      await settle(fixture);

      dispatchKeydown(byId('first-btn'), 'Escape', { altKey: true });

      expect(fixture.componentInstance.closedCount).toBe(0);
    });

    it('when another key is pressed while active, the close output does not fire', async () => {
      fixture.componentInstance.isActive.set(true);
      await settle(fixture);

      dispatchKeydown(byId('first-btn'), 'Enter');

      expect(fixture.componentInstance.closedCount).toBe(0);
    });

    it('when a child widget consumes Escape with preventDefault, the close output does not fire', async () => {
      const consumer = mount(EscapeConsumerHostComponent);
      await settle(consumer);

      dispatchKeydown(byId('consumes-escape'), 'Escape');

      expect(consumer.componentInstance.closedCount).toBe(0);
    });
  });

  // -------------------------------------------------------------------------
  // Escape with Material comboboxes (mat-select, matAutocomplete)
  // -------------------------------------------------------------------------

  describe('Escape with Material comboboxes', () => {
    let fixture: ComponentFixture<ComboboxHostComponent>;
    let loader: HarnessLoader;

    beforeEach(async () => {
      TestBed.configureTestingModule({
        providers: [{ provide: MATERIAL_ANIMATIONS, useValue: { animationsDisabled: true } }],
      });
      fixture = mount(ComboboxHostComponent);
      await settle(fixture);
      loader = TestbedHarnessEnvironment.loader(fixture);
    });

    it('when Escape is pressed on an open mat-select, only the select panel closes', async () => {
      const select = await loader.getHarness(MatSelectHarness);
      await select.open();
      const country = byId('country');
      expect(country.getAttribute('aria-expanded')).toBe('true');

      dispatchKeydown(country, 'Escape');
      await settle(fixture);

      expect(country.getAttribute('aria-expanded')).toBe('false');
      expect(fixture.componentInstance.closedCount).toBe(0);
    });

    it('when Escape is pressed again after the mat-select panel closed, the close output fires', async () => {
      const select = await loader.getHarness(MatSelectHarness);
      await select.open();
      const country = byId('country');
      dispatchKeydown(country, 'Escape');
      await settle(fixture);

      dispatchKeydown(country, 'Escape');

      expect(fixture.componentInstance.closedCount).toBe(1);
    });

    it('when Escape is pressed on an open autocomplete, only the autocomplete panel closes', async () => {
      const autocomplete = await loader.getHarness(MatAutocompleteHarness);
      await autocomplete.focus();
      expect(await autocomplete.isOpen()).toBe(true);
      expect(byId('city').getAttribute('aria-expanded')).toBe('true');

      dispatchKeydown(byId('city'), 'Escape');
      await settle(fixture);

      expect(await autocomplete.isOpen()).toBe(false);
      expect(fixture.componentInstance.closedCount).toBe(0);
    });

    it('when Escape is pressed on a collapsed autocomplete, the close output fires', async () => {
      const city = byId('city');
      expect(city.getAttribute('aria-expanded')).toBe('false');

      // matAutocomplete calls preventDefault on every Escape, even with its panel closed.
      const event = dispatchKeydown(city, 'Escape');

      expect(event.defaultPrevented).toBe(true);
      expect(fixture.componentInstance.closedCount).toBe(1);
    });
  });

  // -------------------------------------------------------------------------
  // Sibling inert + aria-hidden
  // -------------------------------------------------------------------------

  describe('sibling inert/aria-hidden', () => {
    let fixture: ComponentFixture<HostComponent>;

    beforeEach(async () => {
      fixture = mount(HostComponent);
      await settle(fixture);
    });

    it('when active, sibling elements of the trap receive the inert and aria-hidden attributes', async () => {
      fixture.componentInstance.isActive.set(true);
      await settle(fixture);

      const siblings = backgroundSiblings(trapOf(fixture));
      expect(siblings.length).toBeGreaterThan(0);
      siblings.forEach((sibling) => {
        expect(sibling.hasAttribute('inert')).toBe(true);
        expect(sibling.getAttribute('aria-hidden')).toBe('true');
      });
    });

    it('when deactivated, inert and aria-hidden are removed from sibling elements', async () => {
      fixture.componentInstance.isActive.set(true);
      await settle(fixture);
      fixture.componentInstance.isActive.set(false);
      await settle(fixture);

      for (const id of ['trigger', 'after']) {
        expect(byId(id).hasAttribute('inert')).toBe(false);
        expect(byId(id).hasAttribute('aria-hidden')).toBe(false);
      }
    });

    it('when deactivated, a sibling keeps the aria-hidden value it had before activation', async () => {
      fixture.componentInstance.isActive.set(true);
      await settle(fixture);
      fixture.componentInstance.isActive.set(false);
      await settle(fixture);

      expect(byId('note').getAttribute('aria-hidden')).toBe('true');
      expect(byId('note').hasAttribute('inert')).toBe(false);
    });
  });

  // -------------------------------------------------------------------------
  // Background of a nested host: every ancestor level up to body
  // -------------------------------------------------------------------------

  describe('background outside a nested host', () => {
    let fixture: ComponentFixture<NestedPageHostComponent>;
    const addedToBody: HTMLElement[] = [];

    function addToBody(configure: (element: HTMLElement) => void): HTMLElement {
      const element = document.createElement('div');
      configure(element);
      document.body.appendChild(element);
      addedToBody.push(element);
      return element;
    }

    function expectHidden(element: Element): void {
      expect(element.hasAttribute('inert')).toBe(true);
      expect(element.getAttribute('aria-hidden')).toBe('true');
    }

    function expectUntouched(element: Element): void {
      expect(element.hasAttribute('inert')).toBe(false);
      expect(element.hasAttribute('aria-hidden')).toBe(false);
    }

    beforeEach(async () => {
      fixture = mount(NestedPageHostComponent);
      await settle(fixture);
    });

    afterEach(() => {
      addedToBody.splice(0).forEach((element) => element.remove());
    });

    it('when active, the siblings of every ancestor up to body are hidden, and the ancestors are not', async () => {
      const bodySibling = addToBody(() => undefined);
      fixture.componentInstance.isActive.set(true);
      await settle(fixture);

      [byId('page-title'), byId('page-header'), byId('page-nav'), bodySibling].forEach(expectHidden);
      [byId('panel'), byId('page-main'), fixture.nativeElement as HTMLElement].forEach(expectUntouched);
    });

    it('when active, the overlay container, overlay backdrops and live regions stay reachable', async () => {
      const overlayContainer = addToBody((element) => element.classList.add('cdk-overlay-container'));
      fixture.componentInstance.isActive.set(true);
      await settle(fixture);

      [overlayContainer, byId('page-backdrop'), byId('page-live')].forEach(expectUntouched);
    });

    it('when deactivated, every level gets back the attributes it had before activation', async () => {
      const bodySibling = addToBody((element) => element.setAttribute('aria-hidden', 'true'));
      fixture.componentInstance.isActive.set(true);
      await settle(fixture);
      fixture.componentInstance.isActive.set(false);
      await settle(fixture);

      [byId('page-title'), byId('page-header'), byId('page-nav')].forEach(expectUntouched);
      expect(bodySibling.getAttribute('aria-hidden')).toBe('true');
      expect(bodySibling.hasAttribute('inert')).toBe(false);
    });
  });

  // -------------------------------------------------------------------------
  // Focus restoration
  // -------------------------------------------------------------------------

  describe('focus restoration', () => {
    let fixture: ComponentFixture<HostComponent>;

    beforeEach(async () => {
      fixture = mount(HostComponent);
      await settle(fixture);
      byId('trigger').focus();
    });

    it('when deactivated, focus returns to the element focused before activation', async () => {
      expect(document.activeElement).toBe(byId('trigger'));

      fixture.componentInstance.isActive.set(true);
      await settle(fixture);
      expect(document.activeElement).toBe(byId('first-btn'));

      fixture.componentInstance.isActive.set(false);
      await settle(fixture);

      expect(document.activeElement).toBe(byId('trigger'));
    });

    it('when the host is destroyed while active, focus returns and siblings are restored', async () => {
      fixture.componentInstance.isActive.set(true);
      await settle(fixture);

      fixture.componentInstance.rendered.set(false);
      await settle(fixture);

      expect(document.activeElement).toBe(byId('trigger'));
      expect(byId('trigger').hasAttribute('inert')).toBe(false);
      expect(document.querySelectorAll(ANCHOR_SELECTOR).length).toBe(0);
    });

    it('when the consumer moves focus elsewhere just before deactivating, focus stays there', async () => {
      fixture.componentInstance.isActive.set(true);
      await settle(fixture);
      const elsewhere = document.createElement('button');
      elsewhere.type = 'button';
      document.body.appendChild(elsewhere);

      // The CDK inert strategy schedules a refocus for this move; deactivating in the same task cancels it.
      elsewhere.focus();
      fixture.componentInstance.isActive.set(false);
      await settle(fixture);
      await nextMacrotask();

      expect(document.activeElement).toBe(elsewhere);
      elsewhere.remove();
    });
  });

  // -------------------------------------------------------------------------
  // Nested traps
  // -------------------------------------------------------------------------

  describe('nested traps', () => {
    let fixture: ComponentFixture<NestedHostComponent>;

    beforeEach(async () => {
      fixture = mount(NestedHostComponent);
      fixture.componentInstance.outerActive.set(true);
      await settle(fixture);
      fixture.componentInstance.innerActive.set(true);
      await settle(fixture);
    });

    it('when the inner trap activates, it takes focus and only its anchors stay tabbable', () => {
      expect(document.activeElement).toBe(byId('inner-first'));
      const outer = byId('outer');
      expect(outer.previousElementSibling?.hasAttribute('tabindex')).toBe(false);
      expect(outer.nextElementSibling?.hasAttribute('tabindex')).toBe(false);
    });

    it('when Tab is pressed on the last inner element, focus wraps inside the inner trap', () => {
      byId('inner-last').focus();
      pressTab();

      expect(document.activeElement).toBe(byId('inner-first'));
    });

    it('when Escape is pressed inside the inner trap, only the inner close output fires', () => {
      dispatchKeydown(byId('inner-first'), 'Escape');

      expect(fixture.componentInstance.innerClosed).toBe(1);
      expect(fixture.componentInstance.outerClosed).toBe(0);
    });

    it('when the inner trap deactivates, focus returns to the outer trap and it wraps again', async () => {
      fixture.componentInstance.innerActive.set(false);
      await settle(fixture);

      expect(document.activeElement).toBe(byId('outer-btn'));
      const outer = byId('outer');
      expect(outer.nextElementSibling?.getAttribute('tabindex')).toBe('0');
    });

    it('when Escape is pressed on a collapsed autocomplete in the inner trap, only the inner close output fires', async () => {
      const combobox = mount(NestedComboboxHostComponent);
      await settle(combobox);
      expect(byId('nested-city').getAttribute('aria-expanded')).toBe('false');

      dispatchKeydown(byId('nested-city'), 'Escape');

      expect(combobox.componentInstance.innerClosed).toBe(1);
      expect(combobox.componentInstance.outerClosed).toBe(0);
    });
  });
});
