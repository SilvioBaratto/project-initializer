import { Component } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { MediaMatcher } from '@angular/cdk/layout';
import { HarnessLoader } from '@angular/cdk/testing';
import { TestbedHarnessEnvironment } from '@angular/cdk/testing/testbed';
import { MatButtonHarness } from '@angular/material/button/testing';
import { MATERIAL_ANIMATIONS } from '@angular/material/core';
import { MatSnackBar, MatSnackBarConfig } from '@angular/material/snack-bar';
import { MatSnackBarHarness } from '@angular/material/snack-bar/testing';
import { vi } from 'vitest';

import { ICON_PROVIDER } from '../../../icons';
import { WINDOW_SIZE_QUERIES, WindowSizeClass } from '../../../services/window-size-class';
import { ToastComponent } from './toast';
import { ToastData, ToastService, ToastVariant } from './toast.service';

/** A page with a control that owns focus before a toast opens. */
@Component({
  template: '<button type="button" class="trigger">Save changes</button>',
})
class PageHost {}

/** jsdom has no matchMedia: answer the M3 window size queries for one size class. */
function mediaMatcherFor(active: WindowSizeClass): Partial<MediaMatcher> {
  return {
    matchMedia: (query: string) =>
      ({
        matches: query === WINDOW_SIZE_QUERIES[active],
        media: query,
        addListener: () => undefined,
        removeListener: () => undefined,
        addEventListener: () => undefined,
        removeEventListener: () => undefined,
      }) as unknown as MediaQueryList,
  };
}

/** Concatenated text of every stylesheet Angular attached to the document. */
function documentStyles(): string {
  return Array.from(document.querySelectorAll('style'))
    .map((style) => style.textContent ?? '')
    .join('\n');
}

/** Snackbar containers that are open (not exiting). They render in the overlay container, not the fixture. */
function openContainers(): HTMLElement[] {
  return Array.from(
    document.querySelectorAll<HTMLElement>('.mat-mdc-snack-bar-container:not([mat-exit])'),
  );
}

/** Lets MatSnackBar finish opening or closing (animations are disabled in these specs). */
async function settle(fixture: ComponentFixture<unknown>, waitMs = 0): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, waitMs));
  await fixture.whenStable();
  await new Promise((resolve) => setTimeout(resolve));
  await fixture.whenStable();
}

interface Setup {
  fixture: ComponentFixture<PageHost>;
  loader: HarnessLoader;
  service: ToastService;
  snackBar: MatSnackBar;
}

function setUp(sizeClass: WindowSizeClass = 'expanded'): Setup {
  TestBed.configureTestingModule({
    imports: [PageHost],
    providers: [
      ICON_PROVIDER,
      { provide: MediaMatcher, useValue: mediaMatcherFor(sizeClass) },
      { provide: MATERIAL_ANIMATIONS, useValue: { animationsDisabled: true } },
    ],
  });
  const fixture = TestBed.createComponent(PageHost);
  fixture.detectChanges();
  return {
    fixture,
    loader: TestbedHarnessEnvironment.documentRootLoader(fixture),
    service: TestBed.inject(ToastService),
    snackBar: TestBed.inject(MatSnackBar),
  };
}

/** Spies on MatSnackBar.openFromComponent (calling through) and returns the config of each call. */
function spyOnOpen(snackBar: MatSnackBar): () => MatSnackBarConfig<ToastData>[] {
  const open = vi.spyOn(snackBar, 'openFromComponent');
  return () => open.mock.calls.map(([, config]) => config as MatSnackBarConfig<ToastData>);
}

describe('ToastService', () => {
  let t: Setup;

  beforeEach(() => {
    t = setUp();
  });

  // --- signal state ---

  it('when created, no toast is on screen', () => {
    expect(t.service.toasts()).toEqual([]);
    expect(openContainers()).toHaveLength(0);
  });

  // --- show ---

  it('when show is called, it returns an id and opens one snackbar with the message', async () => {
    const id = t.service.show('success', 'Profile saved');
    await settle(t.fixture);

    expect(typeof id).toBe('number');
    expect(t.service.toasts()).toEqual([{ id, variant: 'success', message: 'Profile saved' }]);
    const snackBars = await t.loader.getAllHarnesses(MatSnackBarHarness);
    expect(snackBars).toHaveLength(1);
    expect(await snackBars[0].getMessage()).toContain('Profile saved');
  });

  it('when show is called, ToastComponent is the snackbar content', () => {
    const open = vi.spyOn(t.snackBar, 'openFromComponent');
    t.service.show('info', 'Link copied');
    expect(open.mock.calls[0][0]).toBe(ToastComponent);
  });

  it('when show is called with variant error, the variant is preserved', () => {
    t.service.show('error', "Couldn't save changes");
    expect(t.service.toasts()[0].variant).toBe('error');
  });

  it('when a second toast is shown, it replaces the first so one snackbar is on screen', async () => {
    t.service.show('info', 'Draft saved');
    const second = t.service.show('success', 'Post published');
    await settle(t.fixture);

    expect(t.service.toasts().map((toast) => toast.id)).toEqual([second]);
    const snackBars = await t.loader.getAllHarnesses(MatSnackBarHarness);
    expect(snackBars).toHaveLength(1);
    expect(await snackBars[0].getMessage()).toContain('Post published');
  });

  // --- dismiss ---

  it('when dismiss is called with the id on screen, the toast is removed and its snackbar closes', async () => {
    const id = t.service.show('warning', 'Storage almost full');
    await settle(t.fixture);

    t.service.dismiss(id);
    expect(t.service.toasts()).toEqual([]);
    await settle(t.fixture);
    expect(openContainers()).toHaveLength(0);
  });

  it('when dismiss is called with a replaced id, the toast on screen is preserved', async () => {
    const first = t.service.show('info', 'Draft saved');
    const second = t.service.show('success', 'Post published');
    t.service.dismiss(first);
    await settle(t.fixture);

    expect(t.service.toasts().map((toast) => toast.id)).toEqual([second]);
    expect(await t.loader.getAllHarnesses(MatSnackBarHarness)).toHaveLength(1);
  });

  it('when dismiss is called twice with the same id, nothing else changes', async () => {
    const id = t.service.show('info', 'Link copied');
    t.service.dismiss(id);
    t.service.dismiss(id);
    await settle(t.fixture);

    expect(t.service.toasts()).toEqual([]);
    expect(openContainers()).toHaveLength(0);
  });

  it('when ngOnDestroy runs, the snackbar on screen closes', async () => {
    t.service.show('error', "Couldn't save changes");
    await settle(t.fixture);

    t.service.ngOnDestroy();
    await settle(t.fixture);
    expect(t.service.toasts()).toEqual([]);
    expect(openContainers()).toHaveLength(0);
  });

  // --- duration vs. action (never both) ---

  it('when a toast has a duration, its snackbar closes after that duration', async () => {
    t.service.show('info', 'Link copied', 50);
    await settle(t.fixture);
    expect(t.service.toasts()).toHaveLength(1);

    await settle(t.fixture, 150);
    expect(t.service.toasts()).toEqual([]);
    expect(openContainers()).toHaveLength(0);
  });

  const durationCases: {
    name: string;
    variant: ToastVariant;
    duration?: number;
    expected: number;
    dismissible: boolean;
  }[] = [
    { name: 'a success toast without a duration', variant: 'success', expected: 5000, dismissible: false },
    { name: 'an error without a duration', variant: 'error', expected: 0, dismissible: true },
    { name: 'an info toast with a duration of 0', variant: 'info', duration: 0, expected: 0, dismissible: true },
    { name: 'an error with a duration', variant: 'error', duration: 8000, expected: 8000, dismissible: false },
  ];

  durationCases.forEach(({ name, variant, duration, expected, dismissible }) => {
    it(`when ${name} is shown, the snackbar duration is ${expected} and dismissible is ${dismissible}`, () => {
      const configs = spyOnOpen(t.snackBar);
      t.service.show(variant, 'Message', duration);

      const [config] = configs();
      expect(config.duration).toBe(expected);
      expect(config.data?.dismissible).toBe(dismissible);
    });
  });

  // --- live region politeness: assertive only for errors ---

  it('when an error toast opens, its live region is assertive', async () => {
    t.service.show('error', "Couldn't save changes");
    await settle(t.fixture);

    const snackBar = await t.loader.getHarness(MatSnackBarHarness);
    expect(await snackBar.getAriaLive()).toBe('assertive');
  });

  (['info', 'success', 'warning'] as const).forEach((variant) => {
    it(`when a ${variant} toast opens, its live region is polite`, async () => {
      t.service.show(variant, 'Settings updated');
      await settle(t.fixture);

      const snackBar = await t.loader.getHarness(MatSnackBarHarness);
      expect(await snackBar.getAriaLive()).toBe('polite');
    });
  });

  // --- placement ---

  it('when the window is expanded, the snackbar sits bottom center with the app-toast panel class', async () => {
    const configs = spyOnOpen(t.snackBar);
    t.service.show('info', 'Link copied');
    await settle(t.fixture);

    const [config] = configs();
    expect(config.verticalPosition).toBe('bottom');
    expect(config.horizontalPosition).toBe('center');
    expect(config.panelClass).toBe('app-toast');
    const [container] = openContainers();
    expect(container.classList).toContain('app-toast');
  });
});

describe('ToastService at the compact window size', () => {
  // The offset above the navigation bar lives in src/styles/overlays/_toast.scss, keyed to the
  // bar being on screen: MatSnackBar applies panelClass once, so a class picked from the window
  // size would go stale on resize and would also lift toasts on pages without the bar (login).
  it('when a toast opens, it gets the same panel class as at wider sizes', async () => {
    const t = setUp('compact');
    const configs = spyOnOpen(t.snackBar);
    t.service.show('info', 'Link copied');
    await settle(t.fixture);

    expect(configs()[0].panelClass).toBe('app-toast');
    const [container] = openContainers();
    expect(Array.from(container.classList).filter((c) => c.startsWith('app-toast'))).toEqual(['app-toast']);
  });
});

describe('ToastComponent', () => {
  let t: Setup;

  beforeEach(() => {
    t = setUp();
  });

  function toastHost(): HTMLElement {
    return document.querySelector<HTMLElement>('app-toast')!;
  }

  // --- variants: message, status prefix and icon ---

  const variants: { variant: ToastVariant; status: string; icon: string }[] = [
    { variant: 'info', status: 'Information', icon: 'Info' },
    { variant: 'success', status: 'Success', icon: 'CircleCheckBig' },
    { variant: 'warning', status: 'Warning', icon: 'TriangleAlert' },
    { variant: 'error', status: 'Error', icon: 'CircleAlert' },
  ];

  variants.forEach(({ variant, status, icon }) => {
    it(`when variant is ${variant}, the label shows the message after a hidden "${status}" prefix and a decorative ${icon} icon`, async () => {
      t.service.show(variant, `${variant}-msg`);
      await settle(t.fixture);

      const host = toastHost();
      expect(host.classList).toContain(`toast-${variant}`);
      const label = host.querySelector('.mdc-snackbar__label')!;
      expect(label.textContent).toContain(`${variant}-msg`);
      expect(label.querySelector('.cdk-visually-hidden')?.textContent).toContain(`${status}:`);
      const iconHost = label.querySelector('lucide-icon.toast-icon')!;
      expect(iconHost.getAttribute('aria-hidden')).toBe('true');
      expect(iconHost.querySelector(`svg.lucide-${icon}`)).toBeTruthy();
    });
  });

  // --- action ---

  it('when a toast auto-dismisses, it renders no action', async () => {
    t.service.show('success', 'Profile saved');
    await settle(t.fixture);

    expect(toastHost().querySelector('button')).toBeNull();
    expect(toastHost().querySelector('.mat-mdc-snack-bar-actions')).toBeNull();
  });

  it('when a toast waits for the user, its one action is a labelled Material icon button', async () => {
    t.service.show('error', "Couldn't save changes");
    await settle(t.fixture);

    const buttons = await t.loader.getAllHarnesses(
      MatButtonHarness.with({ ancestor: '.mat-mdc-snack-bar-container' }),
    );
    expect(buttons).toHaveLength(1);
    const button = await buttons[0].host();
    expect(await button.getAttribute('aria-label')).toBe('Dismiss notification');
    expect(await button.hasClass('mat-mdc-icon-button')).toBe(true);
    expect(await button.hasClass('mat-mdc-snack-bar-action')).toBe(true);
  });

  it('when the dismiss button is clicked, the toast is removed and the snackbar closes', async () => {
    t.service.show('error', "Couldn't save changes");
    await settle(t.fixture);

    const button = await t.loader.getHarness(
      MatButtonHarness.with({ selector: '[aria-label="Dismiss notification"]' }),
    );
    await button.click();
    await settle(t.fixture);

    expect(t.service.toasts()).toEqual([]);
    expect(openContainers()).toHaveLength(0);
  });

  // --- keyboard and focus ---

  it('when Escape is pressed inside the toast, the snackbar closes', async () => {
    t.service.show('error', "Couldn't save changes");
    await settle(t.fixture);

    const button = toastHost().querySelector<HTMLButtonElement>('button')!;
    button.focus();
    button.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    await settle(t.fixture);

    expect(t.service.toasts()).toEqual([]);
    expect(openContainers()).toHaveLength(0);
  });

  it('when the dismiss button closes the toast, focus returns to the element it came from', async () => {
    const trigger = (t.fixture.nativeElement as HTMLElement).querySelector<HTMLButtonElement>('.trigger')!;
    trigger.focus();
    t.service.show('error', "Couldn't save changes");
    await settle(t.fixture);

    const button = toastHost().querySelector<HTMLButtonElement>('button')!;
    button.focus();
    button.dispatchEvent(new FocusEvent('focusin', { bubbles: true, relatedTarget: trigger }));
    button.click();

    expect(document.activeElement).toBe(trigger);
  });

  function pageTrigger(): HTMLButtonElement {
    return (t.fixture.nativeElement as HTMLElement).querySelector<HTMLButtonElement>('.trigger')!;
  }

  /** Moves focus from `origin` onto the toast's dismiss button, as Tab would. */
  function focusDismissButtonFrom(origin: HTMLElement): HTMLButtonElement {
    const button = toastHost().querySelector<HTMLButtonElement>('button')!;
    button.focus();
    button.dispatchEvent(new FocusEvent('focusin', { bubbles: true, relatedTarget: origin }));
    return button;
  }

  it('when a new toast replaces one that holds focus, focus returns to the element it came from', async () => {
    const trigger = pageTrigger();
    trigger.focus();
    t.service.show('error', "Couldn't save changes");
    await settle(t.fixture);
    const button = focusDismissButtonFrom(trigger);

    t.service.show('success', 'Changes saved');
    await settle(t.fixture);

    expect(button.isConnected).toBe(false);
    expect(document.activeElement).toBe(trigger);
  });

  it('when dismiss(id) closes a toast that holds focus, focus returns to the element it came from', async () => {
    const trigger = pageTrigger();
    trigger.focus();
    const id = t.service.show('error', "Couldn't save changes");
    await settle(t.fixture);
    const button = focusDismissButtonFrom(trigger);

    t.service.dismiss(id);
    await settle(t.fixture);

    expect(button.isConnected).toBe(false);
    expect(document.activeElement).toBe(trigger);
  });

  it('when a toast is replaced while focus is back on the page, focus stays where it is', async () => {
    const trigger = pageTrigger();
    trigger.focus();
    t.service.show('error', "Couldn't save changes");
    await settle(t.fixture);
    focusDismissButtonFrom(trigger);
    const other = document.createElement('button');
    other.type = 'button';
    other.textContent = 'Edit profile';
    (t.fixture.nativeElement as HTMLElement).appendChild(other);
    other.focus();

    t.service.show('success', 'Changes saved');
    await settle(t.fixture);

    expect(document.activeElement).toBe(other);
  });

  // --- tokens ---

  it('when rendered, the stylesheet tints status icons with container roles over the inverse surface', async () => {
    t.service.show('info', 'Link copied');
    await settle(t.fixture);

    const css = documentStyles();
    for (const status of ['info', 'success', 'warning']) {
      expect(css).toContain(`var(--app-${status}-container)`);
    }
    expect(css).toContain('var(--mat-sys-error-container)');
  });

  it('when rendered, no hardcoded hex colors appear in inline element styles', async () => {
    t.service.show('error', "Couldn't save changes");
    await settle(t.fixture);

    const hexPattern = /#[0-9a-fA-F]{3,8}\b/;
    const [container] = openContainers();
    const all: HTMLElement[] = [container, ...Array.from(container.querySelectorAll<HTMLElement>('*'))];
    for (const el of all) {
      expect(el.getAttribute('style') ?? '').not.toMatch(hexPattern);
    }
  });
});
