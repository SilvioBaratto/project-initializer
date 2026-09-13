import { Component, Injectable, signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { InteractivityChecker } from '@angular/cdk/a11y';
import { TestbedHarnessEnvironment } from '@angular/cdk/testing/testbed';
import { MatButtonHarness } from '@angular/material/button/testing';
import { vi } from 'vitest';

import { ICON_PROVIDER } from '../../../icons';
import { AlertComponent, AlertVariant } from './alert';

@Component({
  imports: [AlertComponent],
  template: `
    <a #helpLink class="help-link" href="#payment-help">Read payment help</a>
    <p #note class="note">Card ending 4242</p>
    <app-alert
      [variant]="variant()"
      [dismissible]="dismissible()"
      [dismissLabel]="dismissLabel()"
      [restoreFocusTo]="restoreTarget() === 'help' ? helpLink : restoreTarget() === 'note' ? note : null"
      [(open)]="open"
      (dismissed)="onDismissed()"
    >
      Payment failed
    </app-alert>
    @if (showRetry()) {
      <button type="button" class="retry">Retry payment</button>
    }
  `,
})
class HostComponent {
  readonly variant = signal<AlertVariant>('danger');
  readonly dismissible = signal(false);
  readonly dismissLabel = signal('Dismiss message');
  readonly open = signal(true);
  readonly restoreTarget = signal<'help' | 'note' | null>(null);
  readonly showRetry = signal(true);
  readonly onDismissed = vi.fn();
}

/** jsdom has no layout, so the real checker sees every element as invisible and untabbable. */
@Injectable()
class LayoutFreeInteractivityChecker extends InteractivityChecker {
  override isVisible(): boolean {
    return true;
  }
}

/** Concatenated text of every stylesheet Angular attached to the document. */
function documentStyles(): string {
  return Array.from(document.querySelectorAll('style'))
    .map((style) => style.textContent ?? '')
    .join('\n');
}

describe('AlertComponent', () => {
  let fixture: ComponentFixture<AlertComponent>;
  let host: HTMLElement;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AlertComponent],
      providers: [ICON_PROVIDER],
    }).compileComponents();

    fixture = TestBed.createComponent(AlertComponent);
    host = fixture.nativeElement;
    fixture.detectChanges();
  });

  function setVariant(variant: AlertVariant): void {
    fixture.componentRef.setInput('variant', variant);
    fixture.detectChanges();
  }

  // --- Live region role: assertive only for errors ---

  it('when rendered with the default variant, the message is a polite role="status" region', () => {
    expect(host.classList).toContain('alert-info');
    expect(host.querySelector('[role="status"]')).not.toBeNull();
    expect(host.querySelector('[role="alert"]')).toBeNull();
  });

  it('when variant is danger, the message is an assertive role="alert" region', () => {
    setVariant('danger');

    expect(host.querySelector('[role="alert"]')).not.toBeNull();
    expect(host.querySelector('[role="status"]')).toBeNull();
  });

  it.each<[AlertVariant, 'alert' | 'status']>([
    ['info', 'status'],
    ['success', 'status'],
    ['warning', 'status'],
    ['danger', 'alert'],
  ])('when variant is %s, exactly one live region with role="%s" is rendered', (variant, role) => {
    setVariant(variant);

    const regions = host.querySelectorAll('[role="alert"], [role="status"]');
    expect(regions.length).toBe(1);
    expect(regions[0].getAttribute('role')).toBe(role);
  });

  // --- Variant via tokens: host class selects the token set, icon + label back up color ---

  it.each<[AlertVariant, string, string]>([
    ['info', 'lucide-Info', 'Information'],
    ['success', 'lucide-CircleCheckBig', 'Success'],
    ['warning', 'lucide-TriangleAlert', 'Warning'],
    ['danger', 'lucide-CircleAlert', 'Error'],
  ])('when variant is %s, the variant class, a distinct %s icon and the "%s" label are rendered', (variant, iconClass, label) => {
    setVariant(variant);

    expect(host.classList).toContain(`alert-${variant}`);
    for (const other of ['info', 'success', 'warning', 'danger'].filter((v) => v !== variant)) {
      expect(host.classList).not.toContain(`alert-${other}`);
    }

    const icon = host.querySelector('.alert-icon svg');
    expect(icon?.classList).toContain(iconClass);

    const hiddenLabel = host.querySelector('.alert-message .cdk-visually-hidden');
    expect(hiddenLabel?.textContent?.trim()).toBe(`${label}:`);
  });

  it('when rendered, the status icon is decorative and precedes the message', () => {
    const icon = host.querySelector('.alert-icon')!;
    const message = host.querySelector('.alert-message')!;

    expect(icon.getAttribute('aria-hidden')).toBe('true');
    expect(icon.compareDocumentPosition(message) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(message.contains(icon)).toBe(false);
  });

  it('when rendered, the stylesheet maps every variant to its container and on-container roles', () => {
    const css = documentStyles();

    for (const status of ['info', 'success', 'warning']) {
      expect(css).toContain(`var(--app-${status}-container)`);
      expect(css).toContain(`var(--app-on-${status}-container)`);
    }
    expect(css).toContain('var(--mat-sys-error-container)');
    expect(css).toContain('var(--mat-sys-on-error-container)');
    expect(css).toContain('var(--mat-sys-corner-medium)');
    expect(css).toContain('var(--mat-sys-body-medium)');
  });

  // --- No hardcoded hex colours ---

  it('when rendered, no hardcoded hex colors appear in any inline element styles', () => {
    const hexPattern = /#[0-9a-fA-F]{3,8}\b/;
    const allElements = [host, ...Array.from(host.querySelectorAll<HTMLElement>('*'))];
    for (const el of allElements) {
      expect(el.getAttribute('style') ?? '').not.toMatch(hexPattern);
    }
  });

  // --- Visibility is the open model ---

  it('when open is toggled, the host is hidden and shown again', () => {
    expect(host.hidden).toBe(false);

    fixture.componentRef.setInput('open', false);
    fixture.detectChanges();
    expect(host.hidden).toBe(true);

    fixture.componentRef.setInput('open', true);
    fixture.detectChanges();
    expect(host.hidden).toBe(false);
    expect(host.querySelector('[role="status"]')).not.toBeNull();
  });

  // --- Dismiss is opt-in ---

  it('when dismissible is not set, no dismiss button is rendered', async () => {
    const loader = TestbedHarnessEnvironment.loader(fixture);

    expect(await loader.getAllHarnesses(MatButtonHarness)).toHaveLength(0);
    expect(host.classList).not.toContain('alert-dismissible');
  });
});

describe('AlertComponent with projected content', () => {
  let fixture: ComponentFixture<HostComponent>;
  let hostComponent: HostComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [HostComponent],
      providers: [
        ICON_PROVIDER,
        { provide: InteractivityChecker, useClass: LayoutFreeInteractivityChecker },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(HostComponent);
    hostComponent = fixture.componentInstance;
    fixture.detectChanges();
  });

  function alertHost(): HTMLElement {
    return fixture.nativeElement.querySelector('app-alert');
  }

  function element(selector: string): HTMLElement {
    return fixture.nativeElement.querySelector(selector);
  }

  /** Renders the dismiss button, focuses it like a keyboard user, then activates it. */
  async function dismissWithFocusedButton(): Promise<void> {
    hostComponent.dismissible.set(true);
    fixture.detectChanges();
    const button = await TestbedHarnessEnvironment.loader(fixture).getHarness(MatButtonHarness);
    const dismiss = element('.alert-dismiss');
    dismiss.focus();
    expect(document.activeElement).toBe(dismiss);

    await button.click();
  }

  it('when content is projected, the live region announces the status label then the message', () => {
    const region = alertHost().querySelector('[role="alert"]')!;

    expect(region.textContent?.replace(/\s+/g, ' ').trim()).toBe('Error: Payment failed');
  });

  it('when dismissible, a native icon button with the dismiss label is rendered outside the live region', async () => {
    hostComponent.dismissible.set(true);
    fixture.detectChanges();
    const loader = TestbedHarnessEnvironment.loader(fixture);

    const button = await loader.getHarness(
      MatButtonHarness.with({ selector: '[aria-label="Dismiss message"]' }),
    );
    expect(await button.getVariant()).toBe('icon');

    const dismiss = alertHost().querySelector<HTMLButtonElement>('.alert-dismiss')!;
    // A native <button type="button"> gives Enter and Space for free.
    expect(dismiss.tagName).toBe('BUTTON');
    expect(dismiss.type).toBe('button');
    expect(alertHost().querySelector('[role="alert"]')!.contains(dismiss)).toBe(false);
    expect(dismiss.querySelector('svg')?.classList).toContain('lucide-X');
    expect(alertHost().classList).toContain('alert-dismissible');

    dismiss.focus();
    expect(document.activeElement).toBe(dismiss);
  });

  it('when dismissLabel is set, the dismiss button uses it as its accessible name', async () => {
    hostComponent.dismissible.set(true);
    hostComponent.dismissLabel.set('Dismiss payment error');
    fixture.detectChanges();
    const loader = TestbedHarnessEnvironment.loader(fixture);

    const buttons = await loader.getAllHarnesses(
      MatButtonHarness.with({ selector: '[aria-label="Dismiss payment error"]' }),
    );
    expect(buttons).toHaveLength(1);
  });

  it('when the dismiss button is clicked, dismissed is emitted once, open becomes false and the alert is hidden', async () => {
    hostComponent.dismissible.set(true);
    fixture.detectChanges();
    const button = await TestbedHarnessEnvironment.loader(fixture).getHarness(MatButtonHarness);

    expect(alertHost().hidden).toBe(false);

    await button.click();

    expect(hostComponent.onDismissed).toHaveBeenCalledTimes(1);
    expect(hostComponent.open()).toBe(false);
    expect(alertHost().hidden).toBe(true);
  });

  it('when a dismissed alert is opened again, it is visible with its live region and can be dismissed again', async () => {
    await dismissWithFocusedButton();
    expect(alertHost().hidden).toBe(true);

    hostComponent.open.set(true);
    fixture.detectChanges();

    expect(alertHost().hidden).toBe(false);
    const region = alertHost().querySelector('[role="alert"]');
    expect(region?.textContent?.replace(/\s+/g, ' ').trim()).toBe('Error: Payment failed');

    await (await TestbedHarnessEnvironment.loader(fixture).getHarness(MatButtonHarness)).click();
    expect(hostComponent.onDismissed).toHaveBeenCalledTimes(2);
    expect(alertHost().hidden).toBe(true);
  });

  // --- Focus never drops to <body> when the focused dismiss button hides itself ---

  it('when the focused dismiss button is activated and restoreFocusTo is set, focus moves to that element', async () => {
    hostComponent.restoreTarget.set('help');

    await dismissWithFocusedButton();

    expect(document.activeElement).not.toBe(document.body);
    expect(document.activeElement).toBe(element('.help-link'));
    expect(alertHost().hidden).toBe(true);
  });

  it('when the focused dismiss button is activated without restoreFocusTo, focus moves to the next tabbable control', async () => {
    await dismissWithFocusedButton();

    expect(document.activeElement).not.toBe(document.body);
    expect(document.activeElement).toBe(element('.retry'));
  });

  it('when no tabbable control follows the alert, focus moves to the previous tabbable control', async () => {
    hostComponent.showRetry.set(false);

    await dismissWithFocusedButton();

    expect(document.activeElement).toBe(element('.help-link'));
  });

  it('when restoreFocusTo cannot take focus, focus falls back to the nearest tabbable control', async () => {
    hostComponent.restoreTarget.set('note');

    await dismissWithFocusedButton();

    expect(document.activeElement).toBe(element('.retry'));
  });

  it('when focus is outside the alert, dismissing leaves focus where it is', () => {
    hostComponent.dismissible.set(true);
    fixture.detectChanges();
    const helpLink = element('.help-link');
    helpLink.focus();

    fixture.debugElement.query(By.directive(AlertComponent)).componentInstance.dismiss();
    fixture.detectChanges();

    expect(document.activeElement).toBe(helpLink);
    expect(alertHost().hidden).toBe(true);
  });
});
