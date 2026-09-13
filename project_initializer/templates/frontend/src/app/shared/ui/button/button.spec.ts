import { ChangeDetectionStrategy, Component, signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HarnessLoader } from '@angular/cdk/testing';
import { TestbedHarnessEnvironment } from '@angular/cdk/testing/testbed';
import { MatButtonHarness } from '@angular/material/button/testing';
import { MatProgressSpinnerHarness } from '@angular/material/progress-spinner/testing';

import { ButtonComponent, ButtonSize, ButtonType, ButtonVariant } from './button';

@Component({
  imports: [ButtonComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <app-button
      [variant]="variant()"
      [size]="size()"
      [loading]="loading()"
      [loadingText]="loadingText()"
      [disabled]="disabled()"
      (clicked)="onClicked()"
    >Save changes</app-button>
  `,
})
class ButtonTestHost {
  readonly variant = signal<ButtonVariant>('primary');
  readonly size = signal<ButtonSize>('md');
  readonly loading = signal(false);
  readonly loadingText = signal('');
  readonly disabled = signal(false);
  clicks = 0;

  onClicked(): void {
    this.clicks++;
  }
}

/** An app-button inside a form, to check which buttons submit it. */
@Component({
  imports: [ButtonComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <form (submit)="onSubmit($event)">
      <input name="title" />
      <app-button class="cancel" variant="ghost">Cancel</app-button>
      <app-button class="save" [type]="saveType()" [loading]="loading()">Save changes</app-button>
    </form>
  `,
})
class ButtonFormHost {
  readonly saveType = signal<ButtonType>('submit');
  readonly loading = signal(false);
  submits = 0;

  onSubmit(event: Event): void {
    event.preventDefault();
    this.submits++;
  }
}

describe('ButtonComponent', () => {
  let fixture: ComponentFixture<ButtonTestHost>;
  let testHost: ButtonTestHost;
  let loader: HarnessLoader;

  function appButton(): HTMLElement {
    return fixture.nativeElement.querySelector('app-button');
  }

  function button(): HTMLButtonElement {
    return appButton().querySelector('button')!;
  }

  function token(name: string): string {
    return getComputedStyle(button()).getPropertyValue(name).trim();
  }

  async function set(changes: Partial<{
    variant: ButtonVariant;
    size: ButtonSize;
    loading: boolean;
    loadingText: string;
    disabled: boolean;
  }>): Promise<void> {
    if (changes.variant !== undefined) testHost.variant.set(changes.variant);
    if (changes.size !== undefined) testHost.size.set(changes.size);
    if (changes.loading !== undefined) testHost.loading.set(changes.loading);
    if (changes.loadingText !== undefined) testHost.loadingText.set(changes.loadingText);
    if (changes.disabled !== undefined) testHost.disabled.set(changes.disabled);
    fixture.detectChanges();
    await fixture.whenStable();
  }

  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [ButtonTestHost] }).compileComponents();

    fixture = TestBed.createComponent(ButtonTestHost);
    testHost = fixture.componentInstance;
    loader = TestbedHarnessEnvironment.loader(fixture);
    fixture.detectChanges();
    await fixture.whenStable();
  });

  it('when created, the component renders a Material button with the projected label', async () => {
    const harness = await loader.getHarness(MatButtonHarness);
    expect(await harness.getText()).toBe('Save changes');
    expect(await harness.getVariant()).toBe('basic');
  });

  it('when content is projected, it renders inside the Material label span', () => {
    const label = button().querySelector('.mdc-button__label');
    expect(label).toBeTruthy();
    expect(label!.textContent?.trim()).toBe('Save changes');
  });

  // --- Criterion: variant input maps to an M3 button appearance ---

  it('when variant is primary, the button uses the filled appearance', async () => {
    await set({ variant: 'primary' });
    expect(await (await loader.getHarness(MatButtonHarness)).getAppearance()).toBe('filled');
  });

  it('when variant is secondary, the button uses the outlined appearance', async () => {
    await set({ variant: 'secondary' });
    expect(await (await loader.getHarness(MatButtonHarness)).getAppearance()).toBe('outlined');
  });

  it('when variant is ghost, the button uses the text appearance', async () => {
    await set({ variant: 'ghost' });
    expect(await (await loader.getHarness(MatButtonHarness)).getAppearance()).toBe('text');
  });

  it('when variant is danger, the button uses the filled appearance', async () => {
    await set({ variant: 'danger' });
    expect(await (await loader.getHarness(MatButtonHarness)).getAppearance()).toBe('filled');
  });

  it('when variant changes at runtime, the previous appearance is replaced', async () => {
    await set({ variant: 'secondary' });
    await set({ variant: 'ghost' });
    const harness = await loader.getHarness(MatButtonHarness);
    expect(await harness.getAppearance()).toBe('text');
    expect(button().classList.contains('mat-mdc-outlined-button')).toBe(false);
  });

  it('when variant is danger, the filled container and label tokens use the error roles', async () => {
    await set({ variant: 'danger' });
    expect(token('--mat-button-filled-container-color')).toBe('var(--mat-sys-error)');
    expect(token('--mat-button-filled-label-text-color')).toBe('var(--mat-sys-on-error)');
    expect(token('--mat-button-filled-state-layer-color')).toBe('var(--mat-sys-on-error)');
  });

  it('when variant is primary, the filled tokens are left to the theme', async () => {
    await set({ variant: 'primary' });
    expect(token('--mat-button-filled-container-color')).toBe('');
  });

  // --- Criterion: size input (one M3 button height; size changes horizontal padding) ---

  it('when size is sm, the horizontal padding tokens shrink to 16px (8px on text buttons)', async () => {
    await set({ size: 'sm' });
    expect(token('--mat-button-filled-horizontal-padding')).toBe('16px');
    expect(token('--mat-button-outlined-horizontal-padding')).toBe('16px');
    expect(token('--mat-button-text-horizontal-padding')).toBe('8px');
  });

  it('when size is md, Material default padding is kept', async () => {
    await set({ size: 'md' });
    expect(token('--mat-button-filled-horizontal-padding')).toBe('');
    expect(token('--mat-button-text-horizontal-padding')).toBe('');
  });

  it('when size is lg, the horizontal padding tokens grow to 32px (16px on text buttons)', async () => {
    await set({ size: 'lg' });
    expect(token('--mat-button-filled-horizontal-padding')).toBe('32px');
    expect(token('--mat-button-outlined-horizontal-padding')).toBe('32px');
    expect(token('--mat-button-text-horizontal-padding')).toBe('16px');
  });

  it('when any size is used, the Material 48px touch target is kept and the height is not overridden', async () => {
    for (const size of ['sm', 'md', 'lg'] as const) {
      await set({ size });
      expect(button().querySelector('.mat-mdc-button-touch-target')).toBeTruthy();
      expect(token('--mat-button-filled-container-height')).toBe('');
      expect(token('--mat-button-filled-touch-target-display')).toBe('');
    }
  });

  // --- Criterion: type (an action button never submits a form by accident) ---

  it('when no type is given, the native button is type="button"', async () => {
    expect(button().getAttribute('type')).toBe('button');
    expect(await (await loader.getHarness(MatButtonHarness)).getType()).toBe('button');
  });

  // --- Criterion: loading shows a spinner + sets aria-busy ---

  it('when loading is true, an indeterminate progress spinner is rendered inside the button', async () => {
    await set({ loading: true });
    const spinner = await loader.getHarnessOrNull(MatProgressSpinnerHarness);
    expect(spinner).not.toBeNull();
    expect(await spinner!.getMode()).toBe('indeterminate');
    expect(button().contains(button().querySelector('mat-progress-spinner'))).toBe(true);
  });

  it('when loading is true, the spinner is 18px, hidden from assistive technology and sits in the leading icon slot', async () => {
    await set({ loading: true });
    const spinner = button().querySelector<HTMLElement>('mat-progress-spinner')!;
    expect(spinner.style.width).toBe('18px');
    expect(spinner.style.height).toBe('18px');
    expect(spinner.getAttribute('aria-hidden')).toBe('true');
    expect(spinner.nextElementSibling?.classList.contains('mdc-button__label')).toBe(true);
  });

  it('when loading is true, the spinner inside the button carries no tabindex attribute', async () => {
    await set({ loading: true });
    const spinner = button().querySelector<HTMLElement>('mat-progress-spinner')!;
    expect(spinner.hasAttribute('tabindex')).toBe(false);
    expect(button().querySelectorAll('[tabindex]').length).toBe(0);
  });

  it('when loading is true, the label stays visible next to the spinner', async () => {
    await set({ loading: true });
    expect(await (await loader.getHarness(MatButtonHarness)).getText()).toBe('Save changes');
  });

  it('when loading is false, no spinner is rendered', async () => {
    await set({ loading: false });
    expect(await loader.getHarnessOrNull(MatProgressSpinnerHarness)).toBeNull();
  });

  it('when loading is true, aria-busy is set on the button element only', async () => {
    await set({ loading: true });
    expect(button().getAttribute('aria-busy')).toBe('true');
    expect(appButton().hasAttribute('aria-busy')).toBe(false);
  });

  it('when loading is false, aria-busy is not set on the button element or the host', async () => {
    await set({ loading: false });
    expect(button().getAttribute('aria-busy')).toBeNull();
    expect(appButton().getAttribute('aria-busy')).toBeNull();
  });

  // --- Criterion: loadingText announces the busy state from a status region outside the button ---

  it('when loadingText is set and loading starts, a status region outside the aria-busy button announces it', async () => {
    await set({ loadingText: 'Saving changes…' });
    const status = appButton().querySelector<HTMLElement>('[role="status"]')!;
    expect(status).not.toBeNull();
    expect(status.textContent?.trim()).toBe('');
    expect(status.classList.contains('cdk-visually-hidden')).toBe(true);

    await set({ loading: true });

    // The same region stays in place, so the text added to it is read out.
    expect(appButton().querySelector('[role="status"]')).toBe(status);
    expect(status.textContent?.trim()).toBe('Saving changes…');
    expect(button().contains(status)).toBe(false);
    expect(status.closest('[aria-busy]')).toBeNull();
  });

  it('when loading ends, the status region stays and empties', async () => {
    await set({ loadingText: 'Saving changes…', loading: true });
    const status = appButton().querySelector<HTMLElement>('[role="status"]')!;

    await set({ loading: false });

    expect(appButton().querySelector('[role="status"]')).toBe(status);
    expect(status.textContent?.trim()).toBe('');
  });

  it('when no loadingText is set, no status region is rendered', async () => {
    await set({ loading: true });
    expect(appButton().querySelector('[role="status"]')).toBeNull();
  });

  // --- Criterion: disabled sets the native disabled state; loading a focusable aria-disabled one ---

  it('when disabled is true, the button element has the disabled attribute', async () => {
    await set({ disabled: true });
    expect(await (await loader.getHarness(MatButtonHarness)).isDisabled()).toBe(true);
    expect(button().disabled).toBe(true);
  });

  it('when disabled or loading, the host carries no ARIA state or disabled attribute', async () => {
    for (const state of [{ disabled: true, loading: false }, { disabled: false, loading: true }]) {
      await set(state);
      expect(appButton().hasAttribute('aria-disabled')).toBe(false);
      expect(appButton().hasAttribute('aria-busy')).toBe(false);
      expect(appButton().hasAttribute('disabled')).toBe(false);
    }
  });

  it('when disabled is false, aria-disabled is not set on the button element or the host', async () => {
    await set({ disabled: false });
    expect(button().getAttribute('aria-disabled')).toBeNull();
    expect(appButton().getAttribute('aria-disabled')).toBeNull();
    expect(appButton().hasAttribute('disabled')).toBe(false);
  });

  // --- Criterion: Emits click only when not disabled/loading ---

  it('when the button is clicked and neither disabled nor loading, clicked event is emitted', async () => {
    await (await loader.getHarness(MatButtonHarness)).click();
    expect(testHost.clicks).toBe(1);
  });

  it('when the button is clicked and disabled is true, clicked event is not emitted', async () => {
    await set({ disabled: true });
    button().dispatchEvent(new MouseEvent('click', { bubbles: true }));
    expect(testHost.clicks).toBe(0);
  });

  it('when the button is clicked and loading is true, clicked event is not emitted', async () => {
    await set({ loading: true });
    button().dispatchEvent(new MouseEvent('click', { bubbles: true }));
    expect(testHost.clicks).toBe(0);
  });

  it('when disabled is true, the native button element is disabled (DOM click blocked)', async () => {
    await set({ disabled: true });
    expect(button().disabled).toBe(true);
  });

  it('when loading is true, the button reports disabled through aria-disabled and stays in the tab order', async () => {
    await set({ loading: true });
    expect(await (await loader.getHarness(MatButtonHarness)).isDisabled()).toBe(true);
    expect(button().disabled).toBe(false);
    expect(button().hasAttribute('disabled')).toBe(false);
    expect(button().getAttribute('aria-disabled')).toBe('true');
    expect(button().hasAttribute('tabindex')).toBe(false);
  });

  it('when loading starts on the focused button, keyboard focus stays on it', async () => {
    button().focus();
    expect(document.activeElement).toBe(button());

    await set({ loading: true });

    // A native `disabled` attribute would drop focus to <body>; the busy button keeps it.
    expect(button().hasAttribute('disabled')).toBe(false);
    expect(document.activeElement).toBe(button());

    await set({ loading: false });
    expect(button().hasAttribute('aria-disabled')).toBe(false);
    expect(document.activeElement).toBe(button());
  });

  it('when loading and disabled are both true, the native disabled state wins', async () => {
    await set({ loading: true, disabled: true });
    expect(button().disabled).toBe(true);
    expect(button().hasAttribute('aria-disabled')).toBe(false);
    expect(button().getAttribute('aria-busy')).toBe('true');
  });

  // --- Keyboard: a native <button> gets Enter/Space activation and a Tab stop from the platform ---

  it('when enabled, the control is a native button that can take keyboard focus', async () => {
    const harness = await loader.getHarness(MatButtonHarness);
    expect(button().tagName).toBe('BUTTON');
    await harness.focus();
    expect(await harness.isFocused()).toBe(true);
  });

  // --- No hardcoded colours ---

  it('when rendered, no hardcoded hex colors appear in any inline element styles', async () => {
    await set({ variant: 'danger', loading: true });
    const hexPattern = /#[0-9a-fA-F]{3,8}\b/;
    const host = appButton();
    const allElements = [host, ...Array.from(host.querySelectorAll<HTMLElement>('*'))];
    for (const el of allElements) {
      expect(el.getAttribute('style') ?? '').not.toMatch(hexPattern);
    }
  });
});

describe('ButtonComponent inside a form', () => {
  let fixture: ComponentFixture<ButtonFormHost>;

  const buttonIn = (selector: string): HTMLButtonElement =>
    fixture.nativeElement.querySelector(`app-button${selector} button`);

  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [ButtonFormHost] }).compileComponents();
    fixture = TestBed.createComponent(ButtonFormHost);
    fixture.detectChanges();
    await fixture.whenStable();
  });

  async function render(): Promise<void> {
    fixture.detectChanges();
    await fixture.whenStable();
  }

  it('when an app-button without a type is clicked, the form is not submitted', () => {
    buttonIn('.cancel').click();
    expect(buttonIn('.cancel').type).toBe('button');
    expect(fixture.componentInstance.submits).toBe(0);
  });

  it('when type is submit, clicking the button submits the form', () => {
    expect(buttonIn('.save').type).toBe('submit');
    buttonIn('.save').click();
    expect(fixture.componentInstance.submits).toBe(1);
  });

  it('when type is reset, the native button is type="reset"', async () => {
    fixture.componentInstance.saveType.set('reset');
    await render();
    expect(buttonIn('.save').getAttribute('type')).toBe('reset');
  });

  it('when a submit button is loading, a click on it does not submit the form again', async () => {
    fixture.componentInstance.loading.set(true);
    await render();

    // Focusable while busy, so the click reaches the button; its default action is cancelled.
    expect(buttonIn('.save').hasAttribute('disabled')).toBe(false);
    buttonIn('.save').click();
    expect(fixture.componentInstance.submits).toBe(0);
  });
});

describe('ButtonComponent.handleClick', () => {
  let fixture: ComponentFixture<ButtonComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [ButtonComponent] }).compileComponents();
    fixture = TestBed.createComponent(ButtonComponent);
    fixture.detectChanges();
  });

  function emitsWhen(inputs: { disabled?: boolean; loading?: boolean }, event?: Event): boolean {
    for (const [name, value] of Object.entries(inputs)) {
      fixture.componentRef.setInput(name, value);
    }
    fixture.detectChanges();
    let emitted = false;
    fixture.componentInstance.clicked.subscribe(() => {
      emitted = true;
    });
    fixture.componentInstance.handleClick(event);
    return emitted;
  }

  it('when neither disabled nor loading, clicked event is emitted', () => {
    expect(emitsWhen({ disabled: false, loading: false })).toBe(true);
  });

  it('when disabled is true, clicked event is not emitted', () => {
    expect(emitsWhen({ disabled: true })).toBe(false);
  });

  it('when loading is true, clicked event is not emitted', () => {
    expect(emitsWhen({ loading: true })).toBe(false);
  });

  it('when loading is true, the click event default action is cancelled', () => {
    const event = new MouseEvent('click', { cancelable: true });
    expect(emitsWhen({ loading: true }, event)).toBe(false);
    expect(event.defaultPrevented).toBe(true);
  });

  it('when neither disabled nor loading, the click event default action is kept', () => {
    const event = new MouseEvent('click', { cancelable: true });
    expect(emitsWhen({ disabled: false, loading: false }, event)).toBe(true);
    expect(event.defaultPrevented).toBe(false);
  });

  it('when variant changes, appearance maps primary/secondary/ghost/danger to filled/outlined/text/filled', () => {
    const expected: Record<ButtonVariant, string> = {
      primary: 'filled',
      secondary: 'outlined',
      ghost: 'text',
      danger: 'filled',
    };
    for (const [variant, appearance] of Object.entries(expected)) {
      fixture.componentRef.setInput('variant', variant);
      expect(fixture.componentInstance.appearance()).toBe(appearance);
    }
  });
});
