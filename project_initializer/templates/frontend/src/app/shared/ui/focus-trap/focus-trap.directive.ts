import { ConfigurableFocusTrap, ConfigurableFocusTrapFactory } from '@angular/cdk/a11y';
import { hasModifierKey } from '@angular/cdk/keycodes';
import { Platform } from '@angular/cdk/platform';
import {
  DOCUMENT,
  Directive,
  ElementRef,
  Injector,
  OnDestroy,
  afterNextRender,
  effect,
  inject,
  input,
  output,
  untracked,
} from '@angular/core';

/** Class the CDK puts on the two focus anchors it inserts around the trapped host. */
const FOCUS_TRAP_ANCHOR_CLASS = 'cdk-focus-trap-anchor';

/** Body-level container of CDK overlays: select, autocomplete and menu panels opened from inside the host. */
const OVERLAY_CONTAINER_CLASS = 'cdk-overlay-container';

/** Scrim of a CDK overlay. Inert would swallow the click that dismisses an overlay hosting the trap. */
const OVERLAY_BACKDROP_CLASS = 'cdk-overlay-backdrop';

/** Escape presses a focus trap already turned into `close`, so an enclosing trap leaves them alone. */
const escapeHandledByTrap = new WeakSet<Event>();

/** A background sibling's own attribute values, kept so deactivation puts back exactly what was there. */
interface SavedBackgroundState {
  readonly inert: string | null;
  readonly ariaHidden: string | null;
}

/**
 * Turns its host into a modal focus region while `active` is true.
 *
 * - Tab and Shift+Tab stay inside the host. A CDK a11y `ConfigurableFocusTrap` puts focus anchors
 *   before and after the host, so focus wraps from the last tabbable element to the first and back.
 *   Traps stack through the CDK `FocusTrapManager`: only the innermost active trap wraps.
 * - Focus that leaves the host by pointer or script is pulled back by the CDK inert strategy.
 * - Once rendered, focus moves to the `[cdkFocusInitial]` element, or else the first tabbable child.
 *   With nothing tabbable inside, the host itself takes focus (with `tabindex="-1"` if it has none),
 *   and Tab keeps it there.
 * - Everything outside the host gets `inert` and `aria-hidden="true"`: the siblings of the host and
 *   of each of its ancestors up to `<body>`. A host nested in the page (a panel inside `<main>`)
 *   still hides the header and navigation, and screen readers do not depend on `aria-modal` alone.
 *   Like CDK Dialog, it leaves live regions, popovers, scripts and styles alone, and so the CDK
 *   overlay container (panels opened from inside the host) and overlay backdrops. Their own values
 *   come back on deactivation.
 * - Escape emits `close`, except while an expanded combobox (`mat-select`, `matAutocomplete`) is
 *   the target, because Escape then closes only its panel. In nested traps only the innermost closes.
 * - On deactivation or destroy, focus returns to the element that had it before activation.
 */
@Directive({
  selector: '[appFocusTrap]',
  host: {
    '(keydown)': 'onKeydown($event)',
  },
})
export class FocusTrapDirective implements OnDestroy {
  readonly active = input(false);
  readonly close = output<void>();

  private readonly host: HTMLElement = inject(ElementRef).nativeElement;
  private readonly document = inject(DOCUMENT);
  private readonly injector = inject(Injector);
  private readonly isBrowser = inject(Platform).isBrowser;
  private readonly focusTrapFactory = inject(ConfigurableFocusTrapFactory);

  private focusTrap: ConfigurableFocusTrap | null = null;
  private previousElement: HTMLElement | null = null;
  private anchors: Element[] = [];
  private addedTabindex = false;
  private readonly savedBackground = new Map<Element, SavedBackgroundState>();

  constructor() {
    effect(() => {
      const active = this.active();
      untracked(() => (active ? this.activate() : this.deactivate()));
    });
  }

  ngOnDestroy(): void {
    this.deactivate();
  }

  onKeydown(event: KeyboardEvent): void {
    if (!this.active() || event.key !== 'Escape' || hasModifierKey(event) || escapeHandledByTrap.has(event)) {
      return;
    }
    const combobox = event.target instanceof Element ? event.target.closest('[role="combobox"]') : null;
    // An expanded combobox closes its own panel from the CDK overlay keyboard dispatcher on <body>,
    // which runs after this listener. The surface stays open.
    if (combobox?.getAttribute('aria-expanded') === 'true') return;
    // Another widget that consumed Escape keeps it. A collapsed combobox is not such a widget:
    // matAutocomplete calls preventDefault on every Escape, even with its panel closed.
    if (event.defaultPrevented && !combobox) return;
    event.preventDefault();
    escapeHandledByTrap.add(event);
    this.close.emit();
  }

  private activate(): void {
    if (this.focusTrap || !this.isBrowser) return;
    this.previousElement = this.document.activeElement as HTMLElement | null;
    this.inertBackground();
    // create() attaches the anchors and registers this trap as the innermost active one.
    const trap = this.focusTrapFactory.create(this.host);
    this.focusTrap = trap;
    this.watchAnchors();
    // Content under @if inside the host may render later in this pass, so wait for the render.
    afterNextRender(
      () => {
        if (this.focusTrap === trap && !trap.focusInitialElement()) this.focusHost();
      },
      { injector: this.injector },
    );
  }

  private deactivate(): void {
    const trap = this.focusTrap;
    if (!trap) return;
    this.focusTrap = null;
    // Disabling first also cancels the CDK inert strategy's pending refocus, then destroy removes the anchors.
    trap.enabled = false;
    this.anchors.forEach((anchor) => anchor.removeEventListener('focus', this.onAnchorFocus));
    this.anchors = [];
    trap.destroy();
    this.restoreBackground();
    this.restoreFocus();
    if (this.addedTabindex) {
      this.host.removeAttribute('tabindex');
      this.addedTabindex = false;
    }
  }

  /** Listens on the CDK anchors, which sit directly before and after the host once the trap is created. */
  private watchAnchors(): void {
    this.anchors = [this.host.previousElementSibling, this.host.nextElementSibling].filter(
      (sibling): sibling is Element => !!sibling?.classList.contains(FOCUS_TRAP_ANCHOR_CLASS),
    );
    this.anchors.forEach((anchor) => anchor.addEventListener('focus', this.onAnchorFocus));
  }

  /** Runs after the CDK anchor listener. Focus still on the anchor means the host has nothing tabbable. */
  private readonly onAnchorFocus = (event: Event): void => {
    if (this.focusTrap && this.document.activeElement === event.target) this.focusHost();
  };

  private focusHost(): void {
    if (!this.host.hasAttribute('tabindex')) {
      this.host.setAttribute('tabindex', '-1');
      this.addedTabindex = true;
    }
    this.host.focus();
  }

  private restoreFocus(): void {
    const previous = this.previousElement;
    this.previousElement = null;
    const current = this.document.activeElement;
    // Leave focus alone when the user or the consumer already moved it somewhere else.
    const focusStillHere = !current || current === this.document.body || this.host.contains(current);
    if (previous && focusStillHere) previous.focus();
  }

  /** Walks from the host up to `<body>`, hiding the siblings met at each level. Ancestors stay untouched. */
  private inertBackground(): void {
    let node: Element = this.host;
    let parent = node.parentElement;
    while (parent && node !== this.document.body) {
      for (const sibling of Array.from(parent.children)) {
        if (sibling === node || staysReachable(sibling)) continue;
        this.savedBackground.set(sibling, {
          inert: sibling.getAttribute('inert'),
          ariaHidden: sibling.getAttribute('aria-hidden'),
        });
        sibling.setAttribute('inert', '');
        sibling.setAttribute('aria-hidden', 'true');
      }
      node = parent;
      parent = node.parentElement;
    }
  }

  private restoreBackground(): void {
    this.savedBackground.forEach((saved, sibling) => {
      restoreAttribute(sibling, 'inert', saved.inert);
      restoreAttribute(sibling, 'aria-hidden', saved.ariaHidden);
    });
    this.savedBackground.clear();
  }
}

/**
 * Outside elements the trap never hides. CDK Dialog skips the same ones (overlay container, live
 * regions, popovers, scripts, styles); the focus anchors and overlay backdrops must stay usable too.
 */
function staysReachable(element: Element): boolean {
  return (
    element.classList.contains(FOCUS_TRAP_ANCHOR_CLASS) ||
    element.classList.contains(OVERLAY_CONTAINER_CLASS) ||
    element.classList.contains(OVERLAY_BACKDROP_CLASS) ||
    element.hasAttribute('aria-live') ||
    element.hasAttribute('popover') ||
    element.nodeName === 'SCRIPT' ||
    element.nodeName === 'STYLE'
  );
}

function restoreAttribute(element: Element, name: string, value: string | null): void {
  if (value === null) {
    element.removeAttribute(name);
  } else {
    element.setAttribute(name, value);
  }
}
