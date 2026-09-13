/**
 * Tests for InputComponent (Angular Material outlined form field + matInput).
 * Criteria: the native input carries `id` so a label associates with it; errorText
 * drives the error state (mat-error, aria-invalid, aria-describedby), including an
 * errorText already set on the first render; disabled and
 * ControlValueAccessor work; inside a FORM_FIELD_CONTEXT the field renders the
 * context's label, hint and error with the context's ids.
 */
import { Component, forwardRef, signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { FormControl, ReactiveFormsModule, Validators } from '@angular/forms';
import { HarnessLoader } from '@angular/cdk/testing';
import { TestbedHarnessEnvironment } from '@angular/cdk/testing/testbed';
import { MatFormFieldHarness } from '@angular/material/form-field/testing';
import { MatInputHarness } from '@angular/material/input/testing';
import { FORM_FIELD_CONTEXT, FormFieldContext } from '../form-field/form-field-context';
import { InputComponent } from './input';

// ---------------------------------------------------------------------------
// Hosts
// ---------------------------------------------------------------------------

@Component({
  imports: [InputComponent],
  template: `
    <label [attr.for]="controlId()">{{ labelText() }}</label>
    <app-input [id]="controlId()" [errorText]="errorText()" [disabled]="disabled()" />
  `,
})
class InputTestHost {
  readonly controlId = signal('test-input');
  readonly labelText = signal('Username');
  readonly errorText = signal('');
  readonly disabled = signal(false);
}

@Component({
  imports: [InputComponent, ReactiveFormsModule],
  template: `<app-input id="search" aria-label="Search" [formControl]="control" />`,
})
class InputFormHost {
  readonly control = new FormControl('', { nonNullable: true, validators: Validators.required });
}

/** Stands in for <app-form-field>: provides the context the input renders from. */
@Component({
  imports: [InputComponent],
  providers: [{ provide: FORM_FIELD_CONTEXT, useExisting: forwardRef(() => InputContextHost) }],
  template: `<app-input [id]="ownId()" [errorText]="ownErrorText()" />`,
})
class InputContextHost implements FormFieldContext {
  readonly label = signal('Email');
  readonly helpText = signal('');
  readonly errorText = signal('');
  readonly controlId = 'ctx-control';
  readonly helpId = 'ctx-help';
  readonly errorId = 'ctx-error';

  readonly ownId = signal('');
  readonly ownErrorText = signal('');
}

/** errorText is already set when the field first renders (server or pre-filled validation error). */
@Component({
  imports: [InputComponent],
  template: `<app-input aria-label="Name" errorText="Enter your name" />`,
})
class InputInitialErrorHost {}

/** A context whose help and error text are both set before the field first renders. */
@Component({
  imports: [InputComponent],
  providers: [
    { provide: FORM_FIELD_CONTEXT, useExisting: forwardRef(() => InputContextInitialErrorHost) },
  ],
  template: `<app-input />`,
})
class InputContextInitialErrorHost implements FormFieldContext {
  readonly label = signal('Email');
  readonly helpText = signal('Use the address you sign in with');
  readonly errorText = signal('Enter a valid email');
  readonly controlId = 'ctx-control';
  readonly helpId = 'ctx-help';
  readonly errorId = 'ctx-error';
}

function nativeInput(fixture: ComponentFixture<unknown>): HTMLInputElement {
  return fixture.nativeElement.querySelector('input') as HTMLInputElement;
}

/** Element the input's aria-describedby points at (first id), or null. */
function describedBy(fixture: ComponentFixture<unknown>): HTMLElement | null {
  const ids = nativeInput(fixture).getAttribute('aria-describedby');
  if (!ids) return null;
  return fixture.nativeElement.querySelector(`#${ids.split(/\s+/)[0]}`);
}

describe('InputComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [
        InputTestHost,
        InputFormHost,
        InputContextHost,
        InputInitialErrorHost,
        InputContextInitialErrorHost,
      ],
    }).compileComponents();
  });

  // =========================================================================
  // Standalone (no form field context)
  // =========================================================================

  describe('without a form field context', () => {
    let fixture: ComponentFixture<InputTestHost>;
    let host: InputTestHost;
    let loader: HarnessLoader;

    beforeEach(async () => {
      fixture = TestBed.createComponent(InputTestHost);
      host = fixture.componentInstance;
      loader = TestbedHarnessEnvironment.loader(fixture);
      await fixture.whenStable();
    });

    // -- Material structure --------------------------------------------------

    it('renders an outlined Material form field around a matInput', async () => {
      const field = await loader.getHarness(MatFormFieldHarness);
      expect(await field.getAppearance()).toBe('outline');
      expect(await field.getControl(MatInputHarness)).not.toBeNull();
      expect(nativeInput(fixture).classList).toContain('mat-mdc-input-element');
    });

    it('renders no floating label of its own', async () => {
      const field = await loader.getHarness(MatFormFieldHarness);
      expect(await field.hasLabel()).toBe(false);
    });

    // -- label association via id -------------------------------------------

    it('when id is provided, the native input has that id so a <label for> association works', async () => {
      const input = await loader.getHarness(MatInputHarness);
      expect(await input.getId()).toBe('test-input');
    });

    it('when id matches the for attribute of a sibling label, the label references the input', () => {
      const label = fixture.nativeElement.querySelector('label') as HTMLLabelElement;
      expect(label.htmlFor).toBe(nativeInput(fixture).id);
    });

    // -- error state ----------------------------------------------------------

    it('when errorText is provided, the input has aria-invalid="true"', async () => {
      host.errorText.set('Username is required');
      await fixture.whenStable();

      expect(nativeInput(fixture).getAttribute('aria-invalid')).toBe('true');
    });

    it('when no errorText is provided, the input does not have aria-invalid="true"', () => {
      const val = nativeInput(fixture).getAttribute('aria-invalid');
      expect(val === null || val === 'false').toBe(true);
    });

    it('when errorText is provided, the field shows it in a mat-error that aria-describedby references', async () => {
      host.errorText.set('Username is required');
      await fixture.whenStable();

      const field = await loader.getHarness(MatFormFieldHarness);
      expect(await field.hasErrors()).toBe(true);
      expect(await field.getTextErrors()).toEqual(['Username is required']);
      expect(describedBy(fixture)?.textContent).toContain('Username is required');
    });

    it('when errorText is cleared, the error state, message and aria-describedby are removed', async () => {
      host.errorText.set('Username is required');
      await fixture.whenStable();
      host.errorText.set('');
      await fixture.whenStable();

      const field = await loader.getHarness(MatFormFieldHarness);
      expect(await field.hasErrors()).toBe(false);
      expect(nativeInput(fixture).getAttribute('aria-invalid')).toBe('false');
      expect(nativeInput(fixture).getAttribute('aria-describedby')).toBeNull();
    });

    // -- disabled state -------------------------------------------------------

    it('when disabled is true, the input element and the form field are disabled', async () => {
      host.disabled.set(true);
      await fixture.whenStable();

      const field = await loader.getHarness(MatFormFieldHarness);
      const input = await loader.getHarness(MatInputHarness);
      expect(nativeInput(fixture).disabled).toBe(true);
      expect(await input.isDisabled()).toBe(true);
      expect(await field.isDisabled()).toBe(true);
    });

    it('when disabled is false, the input element is not disabled', async () => {
      const input = await loader.getHarness(MatInputHarness);
      expect(nativeInput(fixture).disabled).toBe(false);
      expect(await input.isDisabled()).toBe(false);
    });
  });

  // =========================================================================
  // Forms API, static attributes and aria-label passthrough
  // =========================================================================

  describe('with a FormControl', () => {
    let fixture: ComponentFixture<InputFormHost>;
    let host: InputFormHost;
    let loader: HarnessLoader;

    beforeEach(async () => {
      fixture = TestBed.createComponent(InputFormHost);
      host = fixture.componentInstance;
      loader = TestbedHarnessEnvironment.loader(fixture);
      await fixture.whenStable();
    });

    it('moves a static id from the host element onto the native input', () => {
      const appInput = fixture.nativeElement.querySelector('app-input') as HTMLElement;
      const matches = fixture.nativeElement.querySelectorAll('#search');

      expect(appInput.hasAttribute('id')).toBe(false);
      expect(matches.length).toBe(1);
      expect(matches[0]).toBe(nativeInput(fixture));
    });

    it('passes aria-label through to the native input and keeps it off the host', () => {
      const appInput = fixture.nativeElement.querySelector('app-input') as HTMLElement;

      expect(nativeInput(fixture).getAttribute('aria-label')).toBe('Search');
      expect(appInput.hasAttribute('aria-label')).toBe(false);
    });

    it('writes the control value into the native input', async () => {
      host.control.setValue('Ada');
      await fixture.whenStable();

      const input = await loader.getHarness(MatInputHarness);
      expect(await input.getValue()).toBe('Ada');
    });

    it('reports typed text back to the control', async () => {
      const input = await loader.getHarness(MatInputHarness);
      await input.setValue('Grace');

      expect(host.control.value).toBe('Grace');
      expect(host.control.dirty).toBe(true);
    });

    it('marks the control touched when the input loses focus', async () => {
      const input = await loader.getHarness(MatInputHarness);
      await input.focus();
      await input.blur();

      expect(host.control.touched).toBe(true);
    });

    it('follows the control disabled state', async () => {
      host.control.disable();
      await fixture.whenStable();
      expect(nativeInput(fixture).disabled).toBe(true);

      host.control.enable();
      await fixture.whenStable();
      expect(nativeInput(fixture).disabled).toBe(false);
    });

    it('ignores form validity: an invalid touched control without errorText shows no error', async () => {
      host.control.markAsTouched();
      await fixture.whenStable();

      const field = await loader.getHarness(MatFormFieldHarness);
      expect(host.control.invalid).toBe(true);
      expect(await field.hasErrors()).toBe(false);
      expect(nativeInput(fixture).getAttribute('aria-invalid')).toBe('false');
    });
  });

  // =========================================================================
  // FORM_FIELD_CONTEXT (contract used by <app-form-field>)
  // =========================================================================

  describe('inside a form field context', () => {
    let fixture: ComponentFixture<InputContextHost>;
    let host: InputContextHost;
    let loader: HarnessLoader;

    beforeEach(async () => {
      fixture = TestBed.createComponent(InputContextHost);
      host = fixture.componentInstance;
      loader = TestbedHarnessEnvironment.loader(fixture);
      await fixture.whenStable();
    });

    it('renders the context label as the mat-label, linked to the input through the context controlId', async () => {
      const field = await loader.getHarness(MatFormFieldHarness);
      const label = fixture.nativeElement.querySelector('label') as HTMLLabelElement;

      expect(await field.getLabel()).toBe('Email');
      expect(nativeInput(fixture).id).toBe('ctx-control');
      expect(label.htmlFor).toBe('ctx-control');
    });

    it('prefers its own id over the context controlId', async () => {
      host.ownId.set('own-id');
      await fixture.whenStable();

      const label = fixture.nativeElement.querySelector('label') as HTMLLabelElement;
      expect(nativeInput(fixture).id).toBe('own-id');
      expect(label.htmlFor).toBe('own-id');
    });

    it('renders the context help text in a mat-hint with the context helpId, referenced by aria-describedby', async () => {
      host.helpText.set('Use the address you sign in with');
      await fixture.whenStable();

      const field = await loader.getHarness(MatFormFieldHarness);
      expect(await field.getTextHints()).toEqual(['Use the address you sign in with']);
      expect(nativeInput(fixture).getAttribute('aria-describedby')).toBe('ctx-help');
      expect(describedBy(fixture)?.textContent).toContain('Use the address you sign in with');
    });

    it('renders the context error text in a mat-error with the context errorId, replacing the hint', async () => {
      host.helpText.set('Use the address you sign in with');
      host.errorText.set('Enter a valid email');
      await fixture.whenStable();

      const field = await loader.getHarness(MatFormFieldHarness);
      const input = nativeInput(fixture);
      expect(await field.getTextErrors()).toEqual(['Enter a valid email']);
      expect(await field.getTextHints()).toEqual([]);
      expect(input.getAttribute('aria-invalid')).toBe('true');
      expect(input.getAttribute('aria-describedby')).toBe('ctx-error');
      expect(describedBy(fixture)?.textContent).toContain('Enter a valid email');
    });

    it('prefers its own errorText over the context errorText', async () => {
      host.errorText.set('Enter a valid email');
      host.ownErrorText.set('Email is already registered');
      await fixture.whenStable();

      const field = await loader.getHarness(MatFormFieldHarness);
      expect(await field.getTextErrors()).toEqual(['Email is already registered']);
    });

    it('returns to the hint when the context error clears', async () => {
      host.helpText.set('Use the address you sign in with');
      host.errorText.set('Enter a valid email');
      await fixture.whenStable();
      host.errorText.set('');
      await fixture.whenStable();

      const field = await loader.getHarness(MatFormFieldHarness);
      expect(await field.hasErrors()).toBe(false);
      expect(nativeInput(fixture).getAttribute('aria-invalid')).toBe('false');
      expect(nativeInput(fixture).getAttribute('aria-describedby')).toBe('ctx-help');
    });

    it('when neither help nor error text is set, aria-describedby is absent', () => {
      expect(nativeInput(fixture).getAttribute('aria-describedby')).toBeNull();
    });
  });

  // =========================================================================
  // errorText already present on the first render
  // =========================================================================

  describe('when errorText is set before the first render', () => {
    it('without a context, the first render is already in the error state', async () => {
      const fixture = TestBed.createComponent(InputInitialErrorHost);
      const loader = TestbedHarnessEnvironment.loader(fixture);
      await fixture.whenStable();

      const field = await loader.getHarness(MatFormFieldHarness);
      const input = nativeInput(fixture);
      const error = fixture.nativeElement.querySelector('mat-error') as HTMLElement;

      expect(input.getAttribute('aria-invalid')).toBe('true');
      expect(await field.hasErrors()).toBe(true);
      expect(await field.getTextErrors()).toEqual(['Enter your name']);
      expect(error.id).toMatch(/^app-input-\d+-error$/);
      expect(input.getAttribute('aria-describedby')).toBe(error.id);
    });

    it('with a context, the first render shows the context error instead of the hint', async () => {
      const fixture = TestBed.createComponent(InputContextInitialErrorHost);
      const loader = TestbedHarnessEnvironment.loader(fixture);
      await fixture.whenStable();

      const field = await loader.getHarness(MatFormFieldHarness);
      const input = nativeInput(fixture);

      expect(input.getAttribute('aria-invalid')).toBe('true');
      expect(await field.getTextErrors()).toEqual(['Enter a valid email']);
      expect(await field.getTextHints()).toEqual([]);
      expect(input.getAttribute('aria-describedby')).toBe('ctx-error');
      expect(describedBy(fixture)?.textContent).toContain('Enter a valid email');
    });
  });
});
