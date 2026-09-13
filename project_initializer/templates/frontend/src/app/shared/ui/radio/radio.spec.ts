/**
 * Tests for RadioComponent (Angular Material MatRadioButton).
 * Criterion: Radio renders with an associated <label>; supports
 * checked/disabled/errorText; implements a value-based ControlValueAccessor.
 */
import { Component, signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { HarnessLoader } from '@angular/cdk/testing';
import { TestbedHarnessEnvironment } from '@angular/cdk/testing/testbed';
import { MatRadioButtonHarness } from '@angular/material/radio/testing';
import { RadioComponent } from './radio';

@Component({
  imports: [RadioComponent],
  template: `
    <app-radio
      [id]="controlId()"
      [name]="groupName()"
      [value]="value()"
      [label]="labelText()"
      [errorText]="errorText()"
      [disabled]="disabled()"
      [checked]="checked()"
    />
  `,
})
class RadioTestHost {
  readonly controlId = signal('test-radio');
  readonly groupName = signal('size');
  readonly value = signal('medium');
  readonly labelText = signal('Medium');
  readonly errorText = signal('');
  readonly disabled = signal(false);
  readonly checked = signal(false);
}

@Component({
  imports: [RadioComponent],
  template: `
    <app-radio name="size" value="small" label="Small" [checked]="true" />
    <app-radio name="size" value="large" label="Large" />
  `,
})
class RadioSetHost {}

@Component({
  imports: [RadioComponent],
  template: `
    <section>
      <app-radio value="express" label="Express delivery" />
    </section>
    <section>
      <app-radio value="wrap" label="Gift wrap" />
    </section>
    <section>
      <app-radio name="size" value="small" label="Small" [checked]="true" />
    </section>
  `,
})
class UnnamedRadiosHost {}

@Component({
  imports: [RadioComponent, ReactiveFormsModule],
  template: `
    <app-radio name="plan" value="basic" label="Basic" [formControl]="control" />
    <app-radio name="plan" value="pro" label="Pro" [formControl]="control" />
  `,
})
class RadioFormHost {
  readonly control = new FormControl('basic', { nonNullable: true });
}

function nativeInputs(fixture: ComponentFixture<unknown>): HTMLInputElement[] {
  return Array.from(fixture.nativeElement.querySelectorAll('input[type="radio"]'));
}

function radioComponents(fixture: ComponentFixture<unknown>): RadioComponent[] {
  return fixture.debugElement
    .queryAll(By.directive(RadioComponent))
    .map((el) => el.componentInstance as RadioComponent);
}

describe('RadioComponent', () => {
  let fixture: ComponentFixture<RadioTestHost>;
  let host: RadioTestHost;
  let loader: HarnessLoader;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [RadioTestHost],
    }).compileComponents();

    fixture = TestBed.createComponent(RadioTestHost);
    host = fixture.componentInstance;
    loader = TestbedHarnessEnvironment.loader(fixture);
    await fixture.whenStable();
  });

  // -- Material radio button + label association -----------------------------

  it('when rendered, a Material radio button is present', async () => {
    const radios = await loader.getAllHarnesses(MatRadioButtonHarness);
    expect(radios.length).toBe(1);
  });

  it('when rendered, a <label> element is present', () => {
    const label = fixture.nativeElement.querySelector('label');
    expect(label).not.toBeNull();
  });

  it('when rendered, the <label> is associated with the native radio input', () => {
    const label = fixture.nativeElement.querySelector('label') as HTMLLabelElement;
    const [input] = nativeInputs(fixture);
    expect(input).toBeDefined();
    expect(label.htmlFor).toBe(input.id);
  });

  it('when label text is provided, it is the radio label', async () => {
    const radio = await loader.getHarness(MatRadioButtonHarness);
    expect(await radio.getLabelText()).toBe('Medium');
  });

  it('when a label filter is used, the harness finds the radio by its label', async () => {
    const radio = await loader.getHarnessOrNull(MatRadioButtonHarness.with({ label: 'Medium' }));
    expect(radio).not.toBeNull();
  });

  it('when id is provided, it lands on the radio host and the input gets "<id>-input"', () => {
    const matRadio = fixture.nativeElement.querySelector('mat-radio-button') as HTMLElement;
    expect(matRadio.id).toBe('test-radio');
    expect(nativeInputs(fixture)[0].id).toBe('test-radio-input');
  });

  it('when no id is provided, the radio still gets a unique input id', async () => {
    host.controlId.set('');
    await fixture.whenStable();

    expect(nativeInputs(fixture)[0].id).toMatch(/^app-radio-\d+-input$/);
  });

  // -- name and value for group behaviour ------------------------------------

  it('when name is provided, the native input carries that name attribute', async () => {
    const radio = await loader.getHarness(MatRadioButtonHarness);

    expect(await radio.getName()).toBe('size');
    expect(nativeInputs(fixture)[0].name).toBe('size');
  });

  it('when value is provided, the native input carries that value', async () => {
    const radio = await loader.getHarness(MatRadioButtonHarness);
    expect(await radio.getValue()).toBe('medium');
  });

  // -- checked state ---------------------------------------------------------

  it('when writeValue matches the radio value, the radio is checked', async () => {
    radioComponents(fixture)[0].writeValue('medium');
    const radio = await loader.getHarness(MatRadioButtonHarness);

    expect(await radio.isChecked()).toBe(true);
    expect(nativeInputs(fixture)[0].checked).toBe(true);
  });

  it('when writeValue does not match the radio value, the radio is not checked', async () => {
    host.checked.set(true);
    await fixture.whenStable();
    radioComponents(fixture)[0].writeValue('large');
    const radio = await loader.getHarness(MatRadioButtonHarness);

    expect(await radio.isChecked()).toBe(false);
    expect(nativeInputs(fixture)[0].checked).toBe(false);
  });

  it('when the checked input is true, the radio is checked', async () => {
    host.checked.set(true);
    const radio = await loader.getHarness(MatRadioButtonHarness);
    expect(await radio.isChecked()).toBe(true);
  });

  it('when the user selects the radio, its checked state follows', async () => {
    const radio = await loader.getHarness(MatRadioButtonHarness);
    await radio.check();

    expect(await radio.isChecked()).toBe(true);
    expect(radioComponents(fixture)[0].isChecked()).toBe(true);
  });

  // -- disabled state --------------------------------------------------------

  it('when disabled is true, the radio and its native input are disabled', async () => {
    host.disabled.set(true);
    const radio = await loader.getHarness(MatRadioButtonHarness);

    expect(await radio.isDisabled()).toBe(true);
    expect(nativeInputs(fixture)[0].disabled).toBe(true);
  });

  it('when disabled is false, the native input is not disabled', async () => {
    const radio = await loader.getHarness(MatRadioButtonHarness);

    expect(await radio.isDisabled()).toBe(false);
    expect(nativeInputs(fixture)[0].disabled).toBe(false);
  });

  it('when disabled, a checked radio keeps its checked state', async () => {
    host.checked.set(true);
    host.disabled.set(true);
    const radio = await loader.getHarness(MatRadioButtonHarness);

    expect(await radio.isChecked()).toBe(true);
  });

  it('when disabled, selecting the radio does nothing', async () => {
    host.disabled.set(true);
    const radio = await loader.getHarness(MatRadioButtonHarness);
    await radio.check();

    expect(await radio.isChecked()).toBe(false);
  });

  // -- keyboard --------------------------------------------------------------

  it('when enabled, the native input takes keyboard focus', async () => {
    const radio = await loader.getHarness(MatRadioButtonHarness);
    await radio.focus();
    expect(await radio.isFocused()).toBe(true);
  });

  // -- error state -----------------------------------------------------------

  it('when errorText is provided, the input has aria-invalid="true"', async () => {
    host.errorText.set('Select a size');
    await fixture.whenStable();

    expect(nativeInputs(fixture)[0].getAttribute('aria-invalid')).toBe('true');
  });

  it('when no errorText is provided, aria-invalid is absent or false on the input', () => {
    const val = nativeInputs(fixture)[0].getAttribute('aria-invalid');
    expect(val === null || val === 'false').toBe(true);
  });

  it('when errorText is provided, the error message appears in the DOM as an alert', async () => {
    host.errorText.set('Select a size');
    await fixture.whenStable();

    const error = fixture.nativeElement.querySelector('[role="alert"]') as HTMLElement;
    expect(error).not.toBeNull();
    expect(error.textContent?.trim()).toBe('Select a size');
  });

  it('when errorText is provided, the input is described by the error message', async () => {
    host.errorText.set('Select a size');
    await fixture.whenStable();

    const error = fixture.nativeElement.querySelector('[role="alert"]') as HTMLElement;
    expect(error.id).toBe('test-radio-error');
    expect(nativeInputs(fixture)[0].getAttribute('aria-describedby')).toBe(error.id);
  });

  it('when errorText is cleared, the error message and its ARIA wiring are removed', async () => {
    host.errorText.set('Select a size');
    await fixture.whenStable();
    host.errorText.set('');
    await fixture.whenStable();

    const [input] = nativeInputs(fixture);
    expect(fixture.nativeElement.querySelector('[role="alert"]')).toBeNull();
    expect(input.getAttribute('aria-invalid')).toBe('false');
    expect(input.hasAttribute('aria-describedby')).toBe(false);
  });

  it('when errorText is provided, the radio switches to the error color tokens', async () => {
    const matRadio = fixture.nativeElement.querySelector('mat-radio-button') as HTMLElement;
    expect(matRadio.classList.contains('radio-invalid')).toBe(false);

    host.errorText.set('Select a size');
    await fixture.whenStable();

    expect(matRadio.classList.contains('radio-invalid')).toBe(true);
    expect(
      getComputedStyle(matRadio).getPropertyValue('--mat-radio-selected-icon-color').trim(),
    ).toBe('var(--mat-sys-error)');
  });

  // -- ControlValueAccessor --------------------------------------------------

  it('when the radio is selected, the registered change callback receives the radio value', async () => {
    let received: string | undefined;
    radioComponents(fixture)[0].registerOnChange((v: string) => {
      received = v;
    });

    const radio = await loader.getHarness(MatRadioButtonHarness);
    await radio.check();

    expect(received).toBe('medium');
  });

  it('when the radio loses focus, the registered touched callback runs', async () => {
    let touched = false;
    radioComponents(fixture)[0].registerOnTouched(() => {
      touched = true;
    });

    const radio = await loader.getHarness(MatRadioButtonHarness);
    await radio.focus();
    await radio.blur();

    expect(touched).toBe(true);
  });
});

describe('RadioComponent in a set sharing one name', () => {
  let fixture: ComponentFixture<RadioSetHost>;
  let loader: HarnessLoader;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [RadioSetHost],
    }).compileComponents();

    fixture = TestBed.createComponent(RadioSetHost);
    loader = TestbedHarnessEnvironment.loader(fixture);
    await fixture.whenStable();
  });

  it('when rendered, every native input carries the shared name, so the browser groups them', () => {
    const names = nativeInputs(fixture).map((input) => input.name);
    expect(names).toEqual(['size', 'size']);
  });

  it('when the user selects another radio, the previously checked radio is unchecked', async () => {
    const small = await loader.getHarness(MatRadioButtonHarness.with({ label: 'Small' }));
    const large = await loader.getHarness(MatRadioButtonHarness.with({ label: 'Large' }));
    expect(await small.isChecked()).toBe(true);

    await large.check();

    expect(await large.isChecked()).toBe(true);
    expect(await small.isChecked()).toBe(false);
    expect(radioComponents(fixture).map((radio) => radio.isChecked())).toEqual([false, true]);
  });

  it('when a value is written after another radio was selected, the matching radio is checked again', async () => {
    const small = await loader.getHarness(MatRadioButtonHarness.with({ label: 'Small' }));
    const large = await loader.getHarness(MatRadioButtonHarness.with({ label: 'Large' }));
    await large.check();

    radioComponents(fixture).forEach((radio) => radio.writeValue('small'));

    expect(await small.isChecked()).toBe(true);
    expect(await large.isChecked()).toBe(false);
  });
});

describe('RadioComponent without a name', () => {
  let fixture: ComponentFixture<UnnamedRadiosHost>;
  let loader: HarnessLoader;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [UnnamedRadiosHost],
    }).compileComponents();

    fixture = TestBed.createComponent(UnnamedRadiosHost);
    loader = TestbedHarnessEnvironment.loader(fixture);
    await fixture.whenStable();
  });

  it('when rendered, each unnamed radio gets its own non-empty name, so the browser does not group them', () => {
    const [express, wrap, small] = nativeInputs(fixture).map((input) => input.name);

    expect(express).not.toBe('');
    expect(wrap).not.toBe('');
    expect(express).not.toBe(wrap);
    expect(small).toBe('size');
  });

  it('when the user selects one unnamed radio and then another, the first stays checked', async () => {
    const express = await loader.getHarness(
      MatRadioButtonHarness.with({ label: 'Express delivery' }),
    );
    const wrap = await loader.getHarness(MatRadioButtonHarness.with({ label: 'Gift wrap' }));

    await express.check();
    await wrap.check();

    expect(await express.isChecked()).toBe(true);
    expect(await wrap.isChecked()).toBe(true);
    expect(radioComponents(fixture).map((radio) => radio.isChecked())).toEqual([
      true,
      true,
      true,
    ]);
  });

  it('when the user selects an unnamed radio, a named set elsewhere keeps its selection', async () => {
    const express = await loader.getHarness(
      MatRadioButtonHarness.with({ label: 'Express delivery' }),
    );
    const small = await loader.getHarness(MatRadioButtonHarness.with({ label: 'Small' }));

    await express.check();

    expect(await small.isChecked()).toBe(true);
  });
});

describe('RadioComponent with reactive forms', () => {
  let fixture: ComponentFixture<RadioFormHost>;
  let loader: HarnessLoader;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [RadioFormHost],
    }).compileComponents();

    fixture = TestBed.createComponent(RadioFormHost);
    loader = TestbedHarnessEnvironment.loader(fixture);
    await fixture.whenStable();
  });

  it('when the form initializes, the radio matching the control value is checked', async () => {
    const basic = await loader.getHarness(MatRadioButtonHarness.with({ label: 'Basic' }));
    const pro = await loader.getHarness(MatRadioButtonHarness.with({ label: 'Pro' }));

    expect(await basic.isChecked()).toBe(true);
    expect(await pro.isChecked()).toBe(false);
  });

  it('when the control value is set, the matching radio is checked and the other is not', async () => {
    fixture.componentInstance.control.setValue('pro');
    const basic = await loader.getHarness(MatRadioButtonHarness.with({ label: 'Basic' }));
    const pro = await loader.getHarness(MatRadioButtonHarness.with({ label: 'Pro' }));

    expect(await pro.isChecked()).toBe(true);
    expect(await basic.isChecked()).toBe(false);
  });

  it('when the user selects a radio, the control value and dirty flag update', async () => {
    const pro = await loader.getHarness(MatRadioButtonHarness.with({ label: 'Pro' }));
    await pro.check();

    const control = fixture.componentInstance.control;
    expect(control.value).toBe('pro');
    expect(control.dirty).toBe(true);
  });

  it('when the user selects a radio and the form is reset, the initial radio is checked again', async () => {
    const basic = await loader.getHarness(MatRadioButtonHarness.with({ label: 'Basic' }));
    const pro = await loader.getHarness(MatRadioButtonHarness.with({ label: 'Pro' }));
    await pro.check();

    fixture.componentInstance.control.reset();

    expect(await basic.isChecked()).toBe(true);
    expect(await pro.isChecked()).toBe(false);
  });

  it('when a radio loses focus, the control is marked touched', async () => {
    const basic = await loader.getHarness(MatRadioButtonHarness.with({ label: 'Basic' }));
    await basic.focus();
    await basic.blur();

    expect(fixture.componentInstance.control.touched).toBe(true);
  });

  it('when the control is disabled, every radio is disabled', async () => {
    fixture.componentInstance.control.disable();
    const radios = await loader.getAllHarnesses(MatRadioButtonHarness);

    expect(radios.length).toBe(2);
    for (const radio of radios) {
      expect(await radio.isDisabled()).toBe(true);
    }
  });
});
