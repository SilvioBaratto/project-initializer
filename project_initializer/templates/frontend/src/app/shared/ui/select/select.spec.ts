/**
 * Tests for SelectComponent (Angular Material outlined form field + mat-select).
 * Criteria: the combobox carries `id`; it is named by aria-label / aria-labelledby or
 * the context label; options() render as mat-options; errorText drives the error state
 * (mat-error, aria-invalid, aria-describedby); disabled, keyboard operation and
 * ControlValueAccessor work; inside a FORM_FIELD_CONTEXT the field renders the
 * context's label, hint and error with the context's ids.
 */
import { Component, forwardRef, signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { FormControl, ReactiveFormsModule, Validators } from '@angular/forms';
import { HarnessLoader, TestKey } from '@angular/cdk/testing';
import { TestbedHarnessEnvironment } from '@angular/cdk/testing/testbed';
import { MATERIAL_ANIMATIONS } from '@angular/material/core';
import { MatFormFieldHarness } from '@angular/material/form-field/testing';
import { MatSelectHarness } from '@angular/material/select/testing';
import { FORM_FIELD_CONTEXT, FormFieldContext } from '../form-field/form-field-context';
import { SelectComponent, SelectOption } from './select';

const OPTIONS: SelectOption[] = [
  { value: 'us', label: 'United States' },
  { value: 'de', label: 'Germany' },
];

// ---------------------------------------------------------------------------
// Hosts
// ---------------------------------------------------------------------------

@Component({
  imports: [SelectComponent],
  template: `
    <span id="country-label">Country</span>
    <app-select
      aria-labelledby="country-label"
      [id]="controlId()"
      [errorText]="errorText()"
      [disabled]="disabled()"
      [options]="options()"
    />
  `,
})
class SelectTestHost {
  readonly controlId = signal('test-select');
  readonly errorText = signal('');
  readonly disabled = signal(false);
  readonly options = signal<SelectOption[]>(OPTIONS);
}

@Component({
  imports: [SelectComponent, ReactiveFormsModule],
  template: `<app-select id="country" aria-label="Country" [options]="options" [formControl]="control" />`,
})
class SelectFormHost {
  readonly options = OPTIONS;
  readonly control = new FormControl('', { nonNullable: true, validators: Validators.required });
}

/** Stands in for <app-form-field>: provides the context the select renders from. */
@Component({
  imports: [SelectComponent],
  providers: [{ provide: FORM_FIELD_CONTEXT, useExisting: forwardRef(() => SelectContextHost) }],
  template: `<app-select [id]="ownId()" [errorText]="ownErrorText()" [options]="options" />`,
})
class SelectContextHost implements FormFieldContext {
  readonly label = signal('Country');
  readonly helpText = signal('');
  readonly errorText = signal('');
  readonly controlId = 'ctx-control';
  readonly helpId = 'ctx-help';
  readonly errorId = 'ctx-error';

  readonly options = OPTIONS;
  readonly ownId = signal('');
  readonly ownErrorText = signal('');
}

function combobox(fixture: ComponentFixture<unknown>): HTMLElement {
  return fixture.nativeElement.querySelector('[role="combobox"]') as HTMLElement;
}

/** Element the combobox's aria-describedby points at (first id), or null. */
function describedBy(fixture: ComponentFixture<unknown>): HTMLElement | null {
  const ids = combobox(fixture).getAttribute('aria-describedby');
  if (!ids) return null;
  return fixture.nativeElement.querySelector(`#${ids.split(/\s+/)[0]}`);
}

async function optionTexts(select: MatSelectHarness): Promise<string[]> {
  const options = await select.getOptions();
  return Promise.all(options.map((o) => o.getText()));
}

describe('SelectComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SelectTestHost, SelectFormHost, SelectContextHost],
      // The panel detaches synchronously on close instead of after its exit animation.
      providers: [{ provide: MATERIAL_ANIMATIONS, useValue: { animationsDisabled: true } }],
    }).compileComponents();
  });

  it('shows the error state on first render when errorText is already set', async () => {
    const fixture = TestBed.createComponent(SelectTestHost);
    fixture.componentInstance.errorText.set('Choose a country');
    const loader = TestbedHarnessEnvironment.loader(fixture);
    await fixture.whenStable();

    const field = await loader.getHarness(MatFormFieldHarness);
    expect(await field.getTextErrors()).toEqual(['Choose a country']);
    expect(combobox(fixture).getAttribute('aria-invalid')).toBe('true');
    expect(describedBy(fixture)?.textContent).toContain('Choose a country');
  });

  // =========================================================================
  // Standalone (no form field context)
  // =========================================================================

  describe('without a form field context', () => {
    let fixture: ComponentFixture<SelectTestHost>;
    let host: SelectTestHost;
    let loader: HarnessLoader;

    beforeEach(async () => {
      fixture = TestBed.createComponent(SelectTestHost);
      host = fixture.componentInstance;
      loader = TestbedHarnessEnvironment.loader(fixture);
      await fixture.whenStable();
    });

    // -- Material structure --------------------------------------------------

    it('renders an outlined Material form field around a mat-select combobox', async () => {
      const field = await loader.getHarness(MatFormFieldHarness);
      expect(await field.getAppearance()).toBe('outline');
      expect(await field.getControl(MatSelectHarness)).not.toBeNull();
      expect(combobox(fixture).tagName).toBe('MAT-SELECT');
      expect(combobox(fixture).getAttribute('aria-haspopup')).toBe('listbox');
    });

    it('renders no floating label of its own', async () => {
      const field = await loader.getHarness(MatFormFieldHarness);
      expect(await field.hasLabel()).toBe(false);
    });

    // -- id and accessible name ----------------------------------------------

    it('when id is provided, the combobox has that id', () => {
      expect(combobox(fixture).id).toBe('test-select');
    });

    it('when id is cleared, the combobox keeps a generated unique id', async () => {
      host.controlId.set('');
      await fixture.whenStable();

      expect(combobox(fixture).id).toMatch(/^mat-select-/);
    });

    it('names the combobox through aria-labelledby and keeps the attribute off the host', () => {
      const appSelect = fixture.nativeElement.querySelector('app-select') as HTMLElement;
      const labelledBy = combobox(fixture).getAttribute('aria-labelledby') ?? '';

      expect(labelledBy.split(/\s+/)).toContain('country-label');
      expect(appSelect.hasAttribute('aria-labelledby')).toBe(false);
    });

    // -- options -------------------------------------------------------------

    it('opens a listbox with one option per entry, showing the option labels', async () => {
      const select = await loader.getHarness(MatSelectHarness);
      await select.open();

      expect(await select.isOpen()).toBe(true);
      expect(await optionTexts(select)).toEqual(['United States', 'Germany']);
      expect(document.getElementById('test-select-panel')?.getAttribute('role')).toBe('listbox');
      expect(combobox(fixture).getAttribute('aria-expanded')).toBe('true');
    });

    it('renders the new entries when the options input changes', async () => {
      host.options.set([...OPTIONS, { value: 'fr', label: 'France' }]);
      await fixture.whenStable();

      const select = await loader.getHarness(MatSelectHarness);
      await select.open();
      expect(await optionTexts(select)).toEqual(['United States', 'Germany', 'France']);
    });

    // -- error state ----------------------------------------------------------

    it('when errorText is provided, the combobox has aria-invalid="true"', async () => {
      host.errorText.set('Choose a country');
      await fixture.whenStable();

      expect(combobox(fixture).getAttribute('aria-invalid')).toBe('true');
    });

    it('when no errorText is provided, the combobox does not have aria-invalid="true"', () => {
      const val = combobox(fixture).getAttribute('aria-invalid');
      expect(val === null || val === 'false').toBe(true);
    });

    it('when errorText is provided, the field shows it in a mat-error that aria-describedby references', async () => {
      host.errorText.set('Choose a country');
      await fixture.whenStable();

      const field = await loader.getHarness(MatFormFieldHarness);
      expect(await field.hasErrors()).toBe(true);
      expect(await field.getTextErrors()).toEqual(['Choose a country']);
      expect(describedBy(fixture)?.textContent).toContain('Choose a country');
    });

    it('when errorText is cleared, the error state, message and aria-describedby are removed', async () => {
      host.errorText.set('Choose a country');
      await fixture.whenStable();
      host.errorText.set('');
      await fixture.whenStable();

      const field = await loader.getHarness(MatFormFieldHarness);
      expect(await field.hasErrors()).toBe(false);
      expect(combobox(fixture).getAttribute('aria-invalid')).toBe('false');
      expect(combobox(fixture).getAttribute('aria-describedby')).toBeNull();
    });

    // -- disabled state -------------------------------------------------------

    it('when disabled is true, the combobox and the form field are disabled and leave the tab order', async () => {
      host.disabled.set(true);
      await fixture.whenStable();

      const field = await loader.getHarness(MatFormFieldHarness);
      const select = await loader.getHarness(MatSelectHarness);
      expect(await select.isDisabled()).toBe(true);
      expect(await field.isDisabled()).toBe(true);
      expect(combobox(fixture).getAttribute('aria-disabled')).toBe('true');
      expect(combobox(fixture).getAttribute('tabindex')).toBe('-1');
    });

    it('when disabled is true, clicking the field does not open the panel', async () => {
      host.disabled.set(true);
      await fixture.whenStable();

      const select = await loader.getHarness(MatSelectHarness);
      await select.open();
      expect(await select.isOpen()).toBe(false);
    });

    it('when disabled is false, the combobox is enabled and focusable', async () => {
      const select = await loader.getHarness(MatSelectHarness);
      expect(await select.isDisabled()).toBe(false);
      expect(combobox(fixture).getAttribute('aria-disabled')).toBe('false');
      expect(combobox(fixture).getAttribute('tabindex')).toBe('0');
    });
  });

  // =========================================================================
  // Forms API, keyboard, static attributes and aria-label passthrough
  // =========================================================================

  describe('with a FormControl', () => {
    let fixture: ComponentFixture<SelectFormHost>;
    let host: SelectFormHost;
    let loader: HarnessLoader;

    beforeEach(async () => {
      fixture = TestBed.createComponent(SelectFormHost);
      host = fixture.componentInstance;
      loader = TestbedHarnessEnvironment.loader(fixture);
      await fixture.whenStable();
    });

    it('moves a static id from the host element onto the combobox', () => {
      const appSelect = fixture.nativeElement.querySelector('app-select') as HTMLElement;
      const matches = fixture.nativeElement.querySelectorAll('#country');

      expect(appSelect.hasAttribute('id')).toBe(false);
      expect(matches.length).toBe(1);
      expect(matches[0]).toBe(combobox(fixture));
    });

    it('passes aria-label through to the combobox and keeps it off the host', () => {
      const appSelect = fixture.nativeElement.querySelector('app-select') as HTMLElement;

      expect(combobox(fixture).getAttribute('aria-label')).toBe('Country');
      expect(appSelect.hasAttribute('aria-label')).toBe(false);
    });

    it('starts empty when the control value matches no option', async () => {
      const select = await loader.getHarness(MatSelectHarness);
      expect(await select.isEmpty()).toBe(true);
    });

    it('writes the control value into the select as the matching option label', async () => {
      host.control.setValue('de');
      await fixture.whenStable();

      const select = await loader.getHarness(MatSelectHarness);
      expect(await select.getValueText()).toBe('Germany');
    });

    it('reports the picked option value back to the control and closes the panel', async () => {
      const select = await loader.getHarness(MatSelectHarness);
      await select.clickOptions({ text: 'Germany' });

      expect(host.control.value).toBe('de');
      expect(host.control.dirty).toBe(true);
      expect(await select.getValueText()).toBe('Germany');
      expect(await select.isOpen()).toBe(false);
    });

    it('marks the control touched when the field loses focus', async () => {
      const select = await loader.getHarness(MatSelectHarness);
      await select.focus();
      await select.blur();

      expect(host.control.touched).toBe(true);
    });

    it('marks the control touched when the panel closes', async () => {
      const select = await loader.getHarness(MatSelectHarness);
      await select.open();
      expect(host.control.touched).toBe(false);

      await select.close();
      await fixture.whenStable();
      expect(host.control.touched).toBe(true);
    });

    it('opens with Enter and closes with Escape, keeping focus on the combobox', async () => {
      const select = await loader.getHarness(MatSelectHarness);
      const trigger = await select.host();
      await select.focus();

      await trigger.sendKeys(TestKey.ENTER);
      expect(await select.isOpen()).toBe(true);

      await trigger.sendKeys(TestKey.ESCAPE);
      expect(await select.isOpen()).toBe(false);
      expect(document.activeElement).toBe(combobox(fixture));
      expect(host.control.value).toBe('');
    });

    it('picks the next option with ArrowDown while closed', async () => {
      const select = await loader.getHarness(MatSelectHarness);
      const trigger = await select.host();
      await select.focus();

      await trigger.sendKeys(TestKey.DOWN_ARROW);
      expect(host.control.value).toBe('us');
      await trigger.sendKeys(TestKey.DOWN_ARROW);
      expect(host.control.value).toBe('de');
      expect(await select.isOpen()).toBe(false);
    });

    it('follows the control disabled state', async () => {
      const select = await loader.getHarness(MatSelectHarness);

      host.control.disable();
      await fixture.whenStable();
      expect(await select.isDisabled()).toBe(true);

      host.control.enable();
      await fixture.whenStable();
      expect(await select.isDisabled()).toBe(false);
    });

    it('ignores form validity: an invalid touched control without errorText shows no error', async () => {
      host.control.markAsTouched();
      await fixture.whenStable();

      const field = await loader.getHarness(MatFormFieldHarness);
      expect(host.control.invalid).toBe(true);
      expect(await field.hasErrors()).toBe(false);
      expect(combobox(fixture).getAttribute('aria-invalid')).toBe('false');
    });
  });

  // =========================================================================
  // FORM_FIELD_CONTEXT (contract used by <app-form-field>)
  // =========================================================================

  describe('inside a form field context', () => {
    let fixture: ComponentFixture<SelectContextHost>;
    let host: SelectContextHost;
    let loader: HarnessLoader;

    beforeEach(async () => {
      fixture = TestBed.createComponent(SelectContextHost);
      host = fixture.componentInstance;
      loader = TestbedHarnessEnvironment.loader(fixture);
      await fixture.whenStable();
    });

    it('renders the context label as the mat-label and names the combobox with it', async () => {
      const field = await loader.getHarness(MatFormFieldHarness);
      const label = fixture.nativeElement.querySelector('label') as HTMLLabelElement;
      const labelledBy = combobox(fixture).getAttribute('aria-labelledby') ?? '';

      expect(await field.getLabel()).toBe('Country');
      expect(label.id).toBeTruthy();
      expect(labelledBy.split(/\s+/)).toContain(label.id);
    });

    it('gives the combobox the context controlId', () => {
      expect(combobox(fixture).id).toBe('ctx-control');
    });

    it('prefers its own id over the context controlId', async () => {
      host.ownId.set('own-id');
      await fixture.whenStable();

      expect(combobox(fixture).id).toBe('own-id');
    });

    it('renders the context help text in a mat-hint with the context helpId, referenced by aria-describedby', async () => {
      host.helpText.set('Pick the country on your ID');
      await fixture.whenStable();

      const field = await loader.getHarness(MatFormFieldHarness);
      expect(await field.getTextHints()).toEqual(['Pick the country on your ID']);
      expect(combobox(fixture).getAttribute('aria-describedby')).toBe('ctx-help');
      expect(describedBy(fixture)?.textContent).toContain('Pick the country on your ID');
    });

    it('renders the context error text in a mat-error with the context errorId, replacing the hint', async () => {
      host.helpText.set('Pick the country on your ID');
      host.errorText.set('Choose a country');
      await fixture.whenStable();

      const field = await loader.getHarness(MatFormFieldHarness);
      const el = combobox(fixture);
      expect(await field.getTextErrors()).toEqual(['Choose a country']);
      expect(await field.getTextHints()).toEqual([]);
      expect(el.getAttribute('aria-invalid')).toBe('true');
      expect(el.getAttribute('aria-describedby')).toBe('ctx-error');
      expect(describedBy(fixture)?.textContent).toContain('Choose a country');
    });

    it('prefers its own errorText over the context errorText', async () => {
      host.errorText.set('Choose a country');
      host.ownErrorText.set('Shipping is unavailable to this country');
      await fixture.whenStable();

      const field = await loader.getHarness(MatFormFieldHarness);
      expect(await field.getTextErrors()).toEqual(['Shipping is unavailable to this country']);
    });

    it('returns to the hint when the context error clears', async () => {
      host.helpText.set('Pick the country on your ID');
      host.errorText.set('Choose a country');
      await fixture.whenStable();
      host.errorText.set('');
      await fixture.whenStable();

      const field = await loader.getHarness(MatFormFieldHarness);
      expect(await field.hasErrors()).toBe(false);
      expect(combobox(fixture).getAttribute('aria-invalid')).toBe('false');
      expect(combobox(fixture).getAttribute('aria-describedby')).toBe('ctx-help');
    });

    it('when neither help nor error text is set, aria-describedby is absent', () => {
      expect(combobox(fixture).getAttribute('aria-describedby')).toBeNull();
    });
  });
});
