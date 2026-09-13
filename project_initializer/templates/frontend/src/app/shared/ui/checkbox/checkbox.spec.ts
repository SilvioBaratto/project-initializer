/**
 * Tests for CheckboxComponent (Angular Material MatCheckbox).
 * Criterion: Checkbox renders with an associated <label>; supports
 * checked/disabled/indeterminate/errorText; implements ControlValueAccessor.
 */
import { Component, signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { HarnessLoader } from '@angular/cdk/testing';
import { TestbedHarnessEnvironment } from '@angular/cdk/testing/testbed';
import { MatCheckboxHarness } from '@angular/material/checkbox/testing';
import { CheckboxComponent } from './checkbox';

@Component({
  imports: [CheckboxComponent],
  template: `
    <app-checkbox
      [id]="controlId()"
      [label]="labelText()"
      [errorText]="errorText()"
      [disabled]="disabled()"
      [checked]="checked()"
      [(indeterminate)]="indeterminate"
    />
  `,
})
class CheckboxTestHost {
  readonly controlId = signal('test-checkbox');
  readonly labelText = signal('Accept terms');
  readonly errorText = signal('');
  readonly disabled = signal(false);
  readonly checked = signal(false);
  readonly indeterminate = signal(false);
}

@Component({
  imports: [CheckboxComponent, ReactiveFormsModule],
  template: `<app-checkbox label="Subscribe to updates" [formControl]="control" />`,
})
class CheckboxFormHost {
  readonly control = new FormControl(false, { nonNullable: true });
}

function nativeInput(fixture: ComponentFixture<unknown>): HTMLInputElement {
  return fixture.nativeElement.querySelector('input[type="checkbox"]') as HTMLInputElement;
}

function checkboxComponent(fixture: ComponentFixture<unknown>): CheckboxComponent {
  return fixture.debugElement.query((el) => el.componentInstance instanceof CheckboxComponent)
    ?.componentInstance as CheckboxComponent;
}

/**
 * The value that style rules matching `el` declare for a custom property, as
 * authored (for example "var(--mat-sys-error)"); the last matching rule in
 * document order wins. CSSOM rule declarations keep var() references in jsdom
 * and in real browsers alike, whereas getComputedStyle substitutes them in a
 * real browser, so this stays valid under either test environment.
 */
function declaredValue(el: Element, property: string): string {
  let value = '';
  for (const sheet of Array.from(document.styleSheets)) {
    let rules: CSSRule[];
    try {
      rules = Array.from(sheet.cssRules);
    } catch {
      continue; // cross-origin sheet
    }
    for (const rule of rules) {
      if (!(rule instanceof CSSStyleRule)) continue;
      try {
        if (!el.matches(rule.selectorText)) continue;
      } catch {
        continue; // selector this engine cannot evaluate
      }
      value = rule.style.getPropertyValue(property).trim() || value;
    }
  }
  return value;
}

describe('CheckboxComponent', () => {
  let fixture: ComponentFixture<CheckboxTestHost>;
  let host: CheckboxTestHost;
  let loader: HarnessLoader;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [CheckboxTestHost, CheckboxFormHost],
    }).compileComponents();

    fixture = TestBed.createComponent(CheckboxTestHost);
    host = fixture.componentInstance;
    loader = TestbedHarnessEnvironment.loader(fixture);
    await fixture.whenStable();
  });

  // -- Material checkbox + label association ---------------------------------

  it('when rendered, a Material checkbox is present', async () => {
    const checkboxes = await loader.getAllHarnesses(MatCheckboxHarness);
    expect(checkboxes.length).toBe(1);
  });

  it('when rendered, a <label> element is present', () => {
    const label = fixture.nativeElement.querySelector('label');
    expect(label).not.toBeNull();
  });

  it('when rendered, the <label> is associated with the native checkbox input', () => {
    const label = fixture.nativeElement.querySelector('label') as HTMLLabelElement;
    const input = nativeInput(fixture);
    expect(input).not.toBeNull();
    expect(label.htmlFor).toBe(input.id);
  });

  it('when label text is provided, it is the checkbox label', async () => {
    const checkbox = await loader.getHarness(MatCheckboxHarness);
    expect(await checkbox.getLabelText()).toBe('Accept terms');
  });

  it('when a label filter is used, the harness finds the checkbox by its label', async () => {
    const checkbox = await loader.getHarnessOrNull(
      MatCheckboxHarness.with({ label: 'Accept terms' }),
    );
    expect(checkbox).not.toBeNull();
  });

  it('when id is provided, it lands on the checkbox host and the input gets "<id>-input"', () => {
    const matCheckbox = fixture.nativeElement.querySelector('mat-checkbox') as HTMLElement;
    expect(matCheckbox.id).toBe('test-checkbox');
    expect(nativeInput(fixture).id).toBe('test-checkbox-input');
  });

  it('when no id is provided, each checkbox still gets a unique input id', async () => {
    host.controlId.set('');
    await fixture.whenStable();

    const input = nativeInput(fixture);
    expect(input.id).toMatch(/^app-checkbox-\d+-input$/);
  });

  // -- checked state ---------------------------------------------------------

  it('when writeValue is called with true, the checkbox is checked', async () => {
    checkboxComponent(fixture).writeValue(true);
    const checkbox = await loader.getHarness(MatCheckboxHarness);

    expect(await checkbox.isChecked()).toBe(true);
    expect(nativeInput(fixture).checked).toBe(true);
  });

  it('when writeValue is called with false, the checkbox is not checked', async () => {
    host.checked.set(true);
    await fixture.whenStable();
    checkboxComponent(fixture).writeValue(false);
    const checkbox = await loader.getHarness(MatCheckboxHarness);

    expect(await checkbox.isChecked()).toBe(false);
    expect(nativeInput(fixture).checked).toBe(false);
  });

  it('when the checked input is true, the checkbox is checked', async () => {
    host.checked.set(true);
    const checkbox = await loader.getHarness(MatCheckboxHarness);
    expect(await checkbox.isChecked()).toBe(true);
  });

  it('when the user toggles the checkbox, its checked state follows', async () => {
    const checkbox = await loader.getHarness(MatCheckboxHarness);
    await checkbox.toggle();
    expect(await checkbox.isChecked()).toBe(true);
    expect(checkboxComponent(fixture).isChecked()).toBe(true);
  });

  // -- indeterminate state ---------------------------------------------------

  it('when indeterminate is true, the checkbox reports the mixed state', async () => {
    host.indeterminate.set(true);
    const checkbox = await loader.getHarness(MatCheckboxHarness);

    expect(await checkbox.isIndeterminate()).toBe(true);
    expect(nativeInput(fixture).getAttribute('aria-checked')).toBe('mixed');
  });

  it('when the user checks an indeterminate checkbox, the indeterminate model syncs back to false', async () => {
    host.indeterminate.set(true);
    const checkbox = await loader.getHarness(MatCheckboxHarness);

    await checkbox.check();

    expect(await checkbox.isIndeterminate()).toBe(false);
    expect(host.indeterminate()).toBe(false);
  });

  // -- disabled state --------------------------------------------------------

  it('when disabled is true, the checkbox and its native input are disabled', async () => {
    host.disabled.set(true);
    const checkbox = await loader.getHarness(MatCheckboxHarness);

    expect(await checkbox.isDisabled()).toBe(true);
    expect(nativeInput(fixture).disabled).toBe(true);
  });

  it('when disabled is false, the native input is not disabled', async () => {
    const checkbox = await loader.getHarness(MatCheckboxHarness);

    expect(await checkbox.isDisabled()).toBe(false);
    expect(nativeInput(fixture).disabled).toBe(false);
  });

  it('when disabled, a checked checkbox keeps its checked state', async () => {
    host.checked.set(true);
    host.disabled.set(true);
    const checkbox = await loader.getHarness(MatCheckboxHarness);

    expect(await checkbox.isChecked()).toBe(true);
  });

  // -- keyboard --------------------------------------------------------------

  it('when enabled, the native input takes keyboard focus', async () => {
    const checkbox = await loader.getHarness(MatCheckboxHarness);
    await checkbox.focus();
    expect(await checkbox.isFocused()).toBe(true);
  });

  // -- error state -----------------------------------------------------------

  it('when errorText is provided, the input has aria-invalid="true"', async () => {
    host.errorText.set('Accept the terms to continue');
    await fixture.whenStable();

    expect(nativeInput(fixture).getAttribute('aria-invalid')).toBe('true');
  });

  it('when no errorText is provided, aria-invalid is absent on the input', () => {
    const val = nativeInput(fixture).getAttribute('aria-invalid');
    expect(val === null || val === 'false').toBe(true);
  });

  it('when errorText is provided, the error message appears in the DOM as an alert', async () => {
    host.errorText.set('Accept the terms to continue');
    await fixture.whenStable();

    const error = fixture.nativeElement.querySelector('[role="alert"]') as HTMLElement;
    expect(error).not.toBeNull();
    expect(error.textContent?.trim()).toBe('Accept the terms to continue');
  });

  it('when errorText is provided, the input is described by the error message', async () => {
    host.errorText.set('Accept the terms to continue');
    await fixture.whenStable();

    const error = fixture.nativeElement.querySelector('[role="alert"]') as HTMLElement;
    expect(error.id).toBe('test-checkbox-error');
    expect(nativeInput(fixture).getAttribute('aria-describedby')).toBe(error.id);
  });

  it('when errorText is cleared, the error message and its ARIA wiring are removed', async () => {
    host.errorText.set('Accept the terms to continue');
    await fixture.whenStable();
    host.errorText.set('');
    await fixture.whenStable();

    const input = nativeInput(fixture);
    expect(fixture.nativeElement.querySelector('[role="alert"]')).toBeNull();
    expect(input.hasAttribute('aria-invalid')).toBe(false);
    expect(input.hasAttribute('aria-describedby')).toBe(false);
  });

  it('when errorText is provided, the checkbox switches to the error color tokens', async () => {
    const matCheckbox = fixture.nativeElement.querySelector('mat-checkbox') as HTMLElement;
    expect(matCheckbox.classList.contains('checkbox-invalid')).toBe(false);
    expect(declaredValue(matCheckbox, '--mat-checkbox-selected-icon-color')).toBe('');

    host.errorText.set('Accept the terms to continue');
    await fixture.whenStable();

    expect(matCheckbox.classList.contains('checkbox-invalid')).toBe(true);
    expect(declaredValue(matCheckbox, '--mat-checkbox-selected-icon-color')).toBe(
      'var(--mat-sys-error)',
    );
    expect(declaredValue(matCheckbox, '--mat-checkbox-selected-checkmark-color')).toBe(
      'var(--mat-sys-on-error)',
    );
  });

  // -- ControlValueAccessor --------------------------------------------------

  it('when the user checks the checkbox, the registered change callback receives true', async () => {
    let received: boolean | undefined;
    checkboxComponent(fixture).registerOnChange((v: boolean) => {
      received = v;
    });

    const checkbox = await loader.getHarness(MatCheckboxHarness);
    await checkbox.check();

    expect(received).toBe(true);
  });
});

describe('CheckboxComponent with reactive forms', () => {
  let fixture: ComponentFixture<CheckboxFormHost>;
  let loader: HarnessLoader;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [CheckboxFormHost],
    }).compileComponents();

    fixture = TestBed.createComponent(CheckboxFormHost);
    loader = TestbedHarnessEnvironment.loader(fixture);
    await fixture.whenStable();
  });

  it('when the control value is set, the checkbox reflects it', async () => {
    fixture.componentInstance.control.setValue(true);
    const checkbox = await loader.getHarness(MatCheckboxHarness);
    expect(await checkbox.isChecked()).toBe(true);
  });

  it('when the user checks the checkbox, the control value and dirty flag update', async () => {
    const checkbox = await loader.getHarness(MatCheckboxHarness);
    await checkbox.check();

    const control = fixture.componentInstance.control;
    expect(control.value).toBe(true);
    expect(control.dirty).toBe(true);
  });

  it('when the checkbox loses focus, the control is marked touched', async () => {
    const checkbox = await loader.getHarness(MatCheckboxHarness);
    await checkbox.focus();
    await checkbox.blur();

    expect(fixture.componentInstance.control.touched).toBe(true);
  });

  it('when the control is disabled, the checkbox is disabled', async () => {
    fixture.componentInstance.control.disable();
    const checkbox = await loader.getHarness(MatCheckboxHarness);
    expect(await checkbox.isDisabled()).toBe(true);
  });
});
