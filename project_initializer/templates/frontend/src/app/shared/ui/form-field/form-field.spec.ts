/**
 * Tests for FormFieldComponent.
 *
 * Criteria (issues #7 and #21, kept through the Material 3 migration):
 *   - A projected native control gets a visible <label for>, help or error text
 *     (the error has role="alert"), a generated id, aria-invalid and aria-describedby.
 *   - label.htmlFor === control.id at runtime, for a bare native control and for
 *     <app-input>. <app-select> renders a combobox, which a <label for> can't name, so
 *     it's named through aria-labelledby.
 *   - The errorText / helpText matrix for aria-invalid and aria-describedby.
 *   - Projected <app-input> / <app-select> consume FORM_FIELD_CONTEXT and render the
 *     label, hint and error inside their own mat-form-field, so the form field renders
 *     no duplicate label or supporting text. Their error text sits in Material's
 *     aria-live="polite" subscript, which replaces role="alert" on that path.
 *   - Swapping a projected Material control for a native one (and back) inside one form
 *     field keeps exactly one label, and the native control gets the fallback wiring.
 */
import { Component, inject, signal, Type } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { TestbedHarnessEnvironment } from '@angular/cdk/testing/testbed';
import { MatFormFieldHarness } from '@angular/material/form-field/testing';

import { FormFieldComponent } from './form-field';
import { FORM_FIELD_CONTEXT } from './form-field-context';
import { InputComponent } from '../input/input';
import { SelectComponent, SelectOption } from '../select/select';

// ---------------------------------------------------------------------------
// Hosts
// ---------------------------------------------------------------------------

/** Projects a bare native <input>, so the form field's own wiring is visible. */
@Component({
  imports: [FormFieldComponent],
  template: `
    <app-form-field [label]="label()" [helpText]="helpText()" [errorText]="errorText()">
      <input data-testid="ctrl" />
    </app-form-field>
  `,
})
class NativeHost {
  readonly label = signal('');
  readonly helpText = signal('');
  readonly errorText = signal('');
}

/** A native input that already has an id and its own description. */
@Component({
  imports: [FormFieldComponent],
  template: `
    <p id="email-policy">Only company addresses are accepted</p>
    <app-form-field label="Email" [helpText]="helpText()" [errorText]="errorText()">
      <input id="work-email" aria-describedby="email-policy" data-testid="ctrl" />
    </app-form-field>
  `,
})
class NativeWithIdHost {
  readonly helpText = signal('Use your work email');
  readonly errorText = signal('');
}

@Component({
  imports: [FormFieldComponent],
  template: `
    <app-form-field label="Message" helpText="Keep it under 500 characters">
      <textarea data-testid="ctrl"></textarea>
    </app-form-field>
  `,
})
class NativeTextareaHost {}

/** Projects <app-input>, which consumes FORM_FIELD_CONTEXT. */
@Component({
  imports: [FormFieldComponent, InputComponent],
  template: `
    <app-form-field [label]="label()" [helpText]="helpText()" [errorText]="errorText()">
      <app-input data-testid="app-input-wrapper" />
    </app-form-field>
  `,
})
class AppInputHost {
  readonly label = signal('Email');
  readonly helpText = signal('');
  readonly errorText = signal('');
}

/** Projects <app-select>, which consumes FORM_FIELD_CONTEXT. */
@Component({
  imports: [FormFieldComponent, SelectComponent],
  template: `
    <app-form-field [label]="label()" [helpText]="helpText()" [errorText]="errorText()">
      <app-select [options]="options" />
    </app-form-field>
  `,
})
class AppSelectHost {
  readonly label = signal('Country');
  readonly helpText = signal('');
  readonly errorText = signal('');
  readonly options: SelectOption[] = [
    { value: 'us', label: 'United States' },
    { value: 'de', label: 'Germany' },
  ];
}

/** Swaps <app-input> and a native <input> inside one form field. */
@Component({
  imports: [FormFieldComponent, InputComponent],
  template: `
    <app-form-field label="Email" [helpText]="helpText()" [errorText]="errorText()">
      @if (material()) {
        <app-input />
      } @else {
        <input data-testid="ctrl" />
      }
    </app-form-field>
  `,
})
class SwapInputHost {
  readonly material = signal(true);
  readonly helpText = signal('Use your work email');
  readonly errorText = signal('');
}

/** Swaps <app-select> and a native <select> inside one form field. */
@Component({
  imports: [FormFieldComponent, SelectComponent],
  template: `
    <app-form-field label="Country" helpText="Choose where you live">
      @if (material()) {
        <app-select [options]="options" />
      } @else {
        <select data-testid="ctrl">
          <option value="us">United States</option>
        </select>
      }
    </app-form-field>
  `,
})
class SwapSelectHost {
  readonly material = signal(true);
  readonly options: SelectOption[] = [{ value: 'us', label: 'United States' }];
}

/** A projected control that only injects the context, to observe what the form field hands out. */
@Component({ selector: 'app-context-probe', template: '' })
class ContextProbe {
  readonly context = inject(FORM_FIELD_CONTEXT);
}

@Component({
  imports: [FormFieldComponent, ContextProbe],
  template: `
    <app-form-field [label]="label()" [helpText]="helpText()" [errorText]="errorText()">
      <app-context-probe />
    </app-form-field>
    <app-form-field label="Nickname">
      <app-context-probe />
    </app-form-field>
  `,
})
class ContextHost {
  readonly label = signal('Email');
  readonly helpText = signal('Use your work email');
  readonly errorText = signal('');
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function render<T>(host: Type<T>, setup?: (instance: T) => void): ComponentFixture<T> {
  const fixture = TestBed.createComponent(host);
  setup?.(fixture.componentInstance);
  fixture.detectChanges();
  return fixture;
}

function root(fixture: ComponentFixture<unknown>): HTMLElement {
  return fixture.nativeElement as HTMLElement;
}

function formField(fixture: ComponentFixture<unknown>, index = 0): FormFieldComponent {
  return fixture.debugElement.queryAll(By.directive(FormFieldComponent))[index].componentInstance;
}

/** Text of every element the control's aria-describedby references, in order. */
function describedTexts(scope: HTMLElement, control: Element): string[] {
  const ids = (control.getAttribute('aria-describedby') ?? '').split(/\s+/).filter(Boolean);
  return ids.map((id) => scope.querySelector(`[id="${id}"]`)?.textContent?.trim() ?? '<missing>');
}

/** Elements the form field renders itself (as opposed to a projected control's mat-form-field). */
function fallbackElements(scope: HTMLElement): Element[] {
  return Array.from(
    scope.querySelectorAll('app-form-field > label, app-form-field > .supporting-text'),
  );
}

function occurrences(text: string, needle: string): number {
  return text.split(needle).length - 1;
}

// ===========================================================================
// Projected native control
// ===========================================================================

describe('FormFieldComponent with a projected native control', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({ imports: [NativeHost] });
  });

  const control = (fixture: ComponentFixture<NativeHost>) =>
    root(fixture).querySelector<HTMLInputElement>('[data-testid="ctrl"]')!;

  it('when label is provided, the label text is rendered in a <label>', () => {
    const fixture = render(NativeHost, (h) => h.label.set('Email address'));

    const label = root(fixture).querySelector('label');
    expect(label).not.toBeNull();
    expect(label!.textContent!.trim()).toBe('Email address');
  });

  it('when label is empty, no <label> element is rendered', () => {
    const fixture = render(NativeHost);

    expect(root(fixture).querySelector('label')).toBeNull();
  });

  it('when a control is projected, the control appears inside the rendered field', () => {
    const fixture = render(NativeHost, (h) => h.label.set('Name'));

    expect(root(fixture).querySelector('app-form-field [data-testid="ctrl"]')).not.toBeNull();
  });

  it('when helpText is provided, the help text is rendered in the DOM', () => {
    const fixture = render(NativeHost, (h) => {
      h.label.set('Email');
      h.helpText.set('Enter your work email');
    });

    expect(root(fixture).textContent).toContain('Enter your work email');
  });

  it('when errorText is provided, the error text is rendered in a role="alert" element', () => {
    const fixture = render(NativeHost, (h) => {
      h.label.set('Email');
      h.errorText.set('Enter a valid email address');
    });

    const alert = root(fixture).querySelector('[role="alert"]');
    expect(alert).not.toBeNull();
    expect(alert!.textContent!.trim()).toBe('Enter a valid email address');
  });

  it('when both helpText and errorText are provided, the error text replaces the help text', () => {
    const fixture = render(NativeHost, (h) => {
      h.label.set('Email');
      h.helpText.set('Enter your work email');
      h.errorText.set('Enter a valid email address');
    });

    expect(root(fixture).textContent).toContain('Enter a valid email address');
    expect(root(fixture).textContent).not.toContain('Enter your work email');
  });

  // -- aria-invalid ----------------------------------------------------------

  it('when errorText is provided, aria-invalid on the projected control is "true"', () => {
    const fixture = render(NativeHost, (h) => {
      h.label.set('Email');
      h.errorText.set('Enter your email');
    });

    expect(control(fixture).getAttribute('aria-invalid')).toBe('true');
  });

  it('when no errorText is provided, aria-invalid on the projected control is absent or "false"', () => {
    const fixture = render(NativeHost, (h) => h.label.set('Email'));

    const val = control(fixture).getAttribute('aria-invalid');
    expect(val === null || val === 'false').toBe(true);
  });

  // -- aria-describedby ------------------------------------------------------

  it('when errorText is provided, aria-describedby on the control references an element containing the error text', () => {
    const fixture = render(NativeHost, (h) => {
      h.label.set('Email');
      h.errorText.set('Enter a valid email address');
    });

    const describedBy = control(fixture).getAttribute('aria-describedby');
    expect(describedBy).toBeTruthy();
    expect(describedBy).toBe(formField(fixture).errorId);
    expect(describedTexts(root(fixture), control(fixture))).toEqual(['Enter a valid email address']);
  });

  it('when helpText is provided, aria-describedby on the control references an element containing the help text', () => {
    const fixture = render(NativeHost, (h) => {
      h.label.set('Email');
      h.helpText.set('Use the address you sign in with');
    });

    expect(control(fixture).getAttribute('aria-describedby')).toBe(formField(fixture).helpId);
    expect(describedTexts(root(fixture), control(fixture))).toEqual([
      'Use the address you sign in with',
    ]);
  });

  it('when neither errorText nor helpText is provided, aria-describedby is absent', () => {
    const fixture = render(NativeHost, (h) => h.label.set('Email'));

    expect(control(fixture).getAttribute('aria-describedby')).toBeNull();
  });

  it('when both helpText and errorText are provided, aria-invalid is "true" and only the error describes the control', () => {
    const fixture = render(NativeHost, (h) => {
      h.label.set('Email');
      h.helpText.set('Enter your work email');
      h.errorText.set('Enter a valid email address');
    });

    expect(control(fixture).getAttribute('aria-invalid')).toBe('true');
    expect(describedTexts(root(fixture), control(fixture))).toEqual(['Enter a valid email address']);
  });

  it('when errorText is cleared after the first render, aria-invalid is removed and the help text describes the control again', () => {
    const fixture = render(NativeHost, (h) => {
      h.label.set('Email');
      h.helpText.set('Enter your work email');
      h.errorText.set('Enter a valid email address');
    });

    fixture.componentInstance.errorText.set('');
    fixture.detectChanges();

    expect(control(fixture).getAttribute('aria-invalid')).toBeNull();
    expect(describedTexts(root(fixture), control(fixture))).toEqual(['Enter your work email']);
    expect(root(fixture).querySelector('[role="alert"]')).toBeNull();
  });
});

// ===========================================================================
// Issue #21 — label.htmlFor === control.id (runtime DOM assertion)
// ===========================================================================

describe('FormFieldComponent — label.htmlFor association (bare projected input)', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({ imports: [NativeHost, NativeWithIdHost, NativeTextareaHost] });
  });

  it('when a bare input is projected, label.htmlFor equals the rendered input id', () => {
    const fixture = render(NativeHost, (h) => h.label.set('Email'));

    const label = root(fixture).querySelector('label')!;
    const ctrl = root(fixture).querySelector<HTMLInputElement>('[data-testid="ctrl"]')!;

    expect(label.htmlFor).toBeTruthy();
    expect(ctrl.id).toBeTruthy();
    expect(label.htmlFor).toBe(ctrl.id);
  });

  it('when a bare input is projected without an initial id, FormField assigns its controlId', () => {
    const fixture = render(NativeHost, (h) => h.label.set('Name'));

    const ctrl = root(fixture).querySelector<HTMLInputElement>('[data-testid="ctrl"]')!;
    expect(ctrl.id).toBe(formField(fixture).controlId);
  });

  it('when the projected input already has an id, the id is kept and the label points at it', () => {
    const fixture = render(NativeWithIdHost);

    const label = root(fixture).querySelector<HTMLLabelElement>('app-form-field label')!;
    const ctrl = root(fixture).querySelector<HTMLInputElement>('[data-testid="ctrl"]')!;

    expect(ctrl.id).toBe('work-email');
    expect(label.htmlFor).toBe('work-email');
  });

  it('when the projected input already lists aria-describedby ids, they are kept after the form field ids', () => {
    const fixture = render(NativeWithIdHost);
    const ctrl = root(fixture).querySelector<HTMLInputElement>('[data-testid="ctrl"]')!;

    expect(describedTexts(root(fixture), ctrl)).toEqual([
      'Use your work email',
      'Only company addresses are accepted',
    ]);

    fixture.componentInstance.errorText.set('Enter a company email address');
    fixture.detectChanges();
    expect(describedTexts(root(fixture), ctrl)).toEqual([
      'Enter a company email address',
      'Only company addresses are accepted',
    ]);

    fixture.componentInstance.errorText.set('');
    fixture.componentInstance.helpText.set('');
    fixture.detectChanges();
    expect(ctrl.getAttribute('aria-describedby')).toBe('email-policy');
  });

  it('when a textarea is projected, it is labelled and described the same way', () => {
    const fixture = render(NativeTextareaHost);

    const label = root(fixture).querySelector('label')!;
    const textarea = root(fixture).querySelector('textarea')!;

    expect(label.htmlFor).toBe(textarea.id);
    expect(describedTexts(root(fixture), textarea)).toEqual(['Keep it under 500 characters']);
  });
});

// ===========================================================================
// Issue #21 — label.htmlFor association with <app-input>
// ===========================================================================

describe('FormFieldComponent — label.htmlFor association (projected app-input)', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({ imports: [AppInputHost] });
  });

  it('when app-input is projected, label.htmlFor equals the rendered native input id', () => {
    const fixture = render(AppInputHost);

    const label = root(fixture).querySelector('label')!;
    const nativeInput = root(fixture).querySelector('input')!;

    expect(label.htmlFor).toBeTruthy();
    expect(nativeInput.id).toBeTruthy();
    expect(label.htmlFor).toBe(nativeInput.id);
    expect(nativeInput.id).toBe(formField(fixture).controlId);
  });

  it('when app-input is projected, a single label is rendered, by the Material form field', async () => {
    const fixture = render(AppInputHost);
    const field = await TestbedHarnessEnvironment.loader(fixture).getHarness(MatFormFieldHarness);

    expect(await field.getLabel()).toBe('Email');
    expect(root(fixture).querySelectorAll('label').length).toBe(1);
    expect(fallbackElements(root(fixture))).toEqual([]);
  });

  it('when app-input is projected with help text, the text renders once, as a Material hint', async () => {
    const fixture = render(AppInputHost, (h) => h.helpText.set('Enter your work email'));
    const field = await TestbedHarnessEnvironment.loader(fixture).getHarness(MatFormFieldHarness);

    expect(await field.getTextHints()).toEqual(['Enter your work email']);
    expect(occurrences(root(fixture).textContent!, 'Enter your work email')).toBe(1);
  });

  it('when app-input is projected with error text, the text renders once, as a Material error', async () => {
    const fixture = render(AppInputHost, (h) => h.errorText.set('Enter a valid email address'));
    const field = await TestbedHarnessEnvironment.loader(fixture).getHarness(MatFormFieldHarness);

    expect(await field.getTextErrors()).toEqual(['Enter a valid email address']);
    expect(occurrences(root(fixture).textContent!, 'Enter a valid email address')).toBe(1);
    expect(root(fixture).querySelector('[role="alert"]')).toBeNull();
    // Material's subscript live region announces the error instead of role="alert".
    expect(root(fixture).querySelector('mat-error')!.closest('[aria-live="polite"]')).not.toBeNull();
  });
});

// ===========================================================================
// Issue #21 — <app-select>: a combobox is named through aria-labelledby
// ===========================================================================

describe('FormFieldComponent — label association (projected app-select)', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({ imports: [AppSelectHost] });
  });

  it('when app-select is projected, the combobox aria-labelledby references the single rendered label', async () => {
    const fixture = render(AppSelectHost);
    const field = await TestbedHarnessEnvironment.loader(fixture).getHarness(MatFormFieldHarness);

    const labels = root(fixture).querySelectorAll('label');
    const combobox = root(fixture).querySelector('[role="combobox"]')!;
    const labelledBy = (combobox.getAttribute('aria-labelledby') ?? '').split(/\s+/);

    expect(labels.length).toBe(1);
    expect(labels[0].id).toBeTruthy();
    expect(labelledBy).toContain(labels[0].id);
    expect(await field.getLabel()).toBe('Country');
    expect(fallbackElements(root(fixture))).toEqual([]);
  });

  it('when app-select is projected, the combobox carries the form field controlId', () => {
    const fixture = render(AppSelectHost);

    const combobox = root(fixture).querySelector('[role="combobox"]')!;
    expect(combobox.id).toBe(formField(fixture).controlId);
  });

  it('when errorText is set, the combobox is invalid and described by the error text only', () => {
    const fixture = render(AppSelectHost, (h) => {
      h.helpText.set('Choose where you live');
      h.errorText.set('Choose a country');
    });

    const combobox = root(fixture).querySelector('[role="combobox"]')!;
    expect(combobox.getAttribute('aria-invalid')).toBe('true');
    expect(describedTexts(root(fixture), combobox)).toEqual(['Choose a country']);
    expect(occurrences(root(fixture).textContent!, 'Choose a country')).toBe(1);
    expect(root(fixture).querySelector('[role="alert"]')).toBeNull();
    // Material's subscript live region announces the error instead of role="alert".
    expect(root(fixture).querySelector('mat-error')!.closest('[aria-live="polite"]')).not.toBeNull();
  });
});

// ===========================================================================
// Swapping a projected Material control for a native one inside one form field
// ===========================================================================

describe('FormFieldComponent — swapping the projected control', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({ imports: [SwapInputHost, SwapSelectHost] });
  });

  const labels = (fixture: ComponentFixture<unknown>) =>
    Array.from(root(fixture).querySelectorAll('label'));

  it('when app-input is swapped for a native input, the native input gets the single label, its id and the help text', () => {
    const fixture = render(SwapInputHost);

    fixture.componentInstance.material.set(false);
    fixture.detectChanges();

    const native = root(fixture).querySelector<HTMLInputElement>('[data-testid="ctrl"]')!;
    expect(labels(fixture).length).toBe(1);
    expect(labels(fixture)[0].textContent!.trim()).toBe('Email');
    expect(native.id).toBe(formField(fixture).controlId);
    expect(labels(fixture)[0].htmlFor).toBe(native.id);
    expect(describedTexts(root(fixture), native)).toEqual(['Use your work email']);
  });

  it('when app-input is swapped for a native input, error text marks the native input invalid in a role="alert" element', () => {
    const fixture = render(SwapInputHost);

    fixture.componentInstance.material.set(false);
    fixture.componentInstance.errorText.set('Enter a valid email address');
    fixture.detectChanges();

    const native = root(fixture).querySelector<HTMLInputElement>('[data-testid="ctrl"]')!;
    expect(native.getAttribute('aria-invalid')).toBe('true');
    expect(describedTexts(root(fixture), native)).toEqual(['Enter a valid email address']);
    expect(root(fixture).querySelector('[role="alert"]')!.textContent!.trim()).toBe(
      'Enter a valid email address',
    );
  });

  it('when the native input is swapped back for app-input, only the Material label and hint remain', async () => {
    const fixture = render(SwapInputHost);
    fixture.componentInstance.material.set(false);
    fixture.detectChanges();

    fixture.componentInstance.material.set(true);
    fixture.detectChanges();

    const field = await TestbedHarnessEnvironment.loader(fixture).getHarness(MatFormFieldHarness);
    const input = root(fixture).querySelector('input')!;
    expect(fallbackElements(root(fixture))).toEqual([]);
    expect(labels(fixture).length).toBe(1);
    expect(await field.getLabel()).toBe('Email');
    expect(labels(fixture)[0].htmlFor).toBe(input.id);
    expect(await field.getTextHints()).toEqual(['Use your work email']);
    expect(occurrences(root(fixture).textContent!, 'Use your work email')).toBe(1);
  });

  it('when a native input is shown first and then swapped for app-input, only the Material label remains', async () => {
    const fixture = render(SwapInputHost, (h) => h.material.set(false));
    expect(labels(fixture).length).toBe(1);

    fixture.componentInstance.material.set(true);
    fixture.detectChanges();

    const field = await TestbedHarnessEnvironment.loader(fixture).getHarness(MatFormFieldHarness);
    expect(fallbackElements(root(fixture))).toEqual([]);
    expect(labels(fixture).length).toBe(1);
    expect(await field.getLabel()).toBe('Email');
  });

  it('when app-select is swapped for a native select and back, exactly one label names the control each time', () => {
    const fixture = render(SwapSelectHost);

    fixture.componentInstance.material.set(false);
    fixture.detectChanges();
    const select = root(fixture).querySelector('select')!;
    expect(labels(fixture).length).toBe(1);
    expect(labels(fixture)[0].htmlFor).toBe(select.id);
    expect(describedTexts(root(fixture), select)).toEqual(['Choose where you live']);

    fixture.componentInstance.material.set(true);
    fixture.detectChanges();
    const combobox = root(fixture).querySelector('[role="combobox"]')!;
    expect(fallbackElements(root(fixture))).toEqual([]);
    expect(labels(fixture).length).toBe(1);
    expect((combobox.getAttribute('aria-labelledby') ?? '').split(/\s+/)).toContain(
      labels(fixture)[0].id,
    );
  });
});

// ===========================================================================
// Issue #21 — aria-invalid / aria-describedby matrix with app-input
// ===========================================================================

describe('FormFieldComponent — aria-invalid / aria-describedby matrix (app-input)', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({ imports: [AppInputHost] });
  });

  const nativeInput = (fixture: ComponentFixture<AppInputHost>) =>
    root(fixture).querySelector('input')!;

  it('when errorText is set, the native input has aria-invalid="true"', () => {
    const fixture = render(AppInputHost, (h) => h.errorText.set('Enter your email'));

    expect(nativeInput(fixture).getAttribute('aria-invalid')).toBe('true');
  });

  it('when errorText is not set, the native input has no aria-invalid="true"', () => {
    const fixture = render(AppInputHost);

    const val = nativeInput(fixture).getAttribute('aria-invalid');
    expect(val === null || val === 'false').toBe(true);
  });

  it('when errorText is set, aria-describedby references an element containing the error text', () => {
    const fixture = render(AppInputHost, (h) => h.errorText.set('Enter a valid email address'));

    const describedById = nativeInput(fixture).getAttribute('aria-describedby');
    expect(describedById).toBeTruthy();
    expect(describedById).toBe(formField(fixture).errorId);
    expect(describedTexts(root(fixture), nativeInput(fixture))).toEqual([
      'Enter a valid email address',
    ]);
  });

  it('when helpText is set and errorText is not, aria-describedby references an element containing the help text', () => {
    const fixture = render(AppInputHost, (h) => h.helpText.set('Use the address you sign in with'));

    expect(nativeInput(fixture).getAttribute('aria-describedby')).toBe(formField(fixture).helpId);
    expect(describedTexts(root(fixture), nativeInput(fixture))).toEqual([
      'Use the address you sign in with',
    ]);
  });

  it('when neither errorText nor helpText is set, aria-describedby is absent on the input', () => {
    const fixture = render(AppInputHost);

    expect(nativeInput(fixture).getAttribute('aria-describedby')).toBeNull();
  });

  it('when errorText is set after the first render, the input turns invalid and the error replaces the help text', () => {
    const fixture = render(AppInputHost, (h) => h.helpText.set('Enter your work email'));

    fixture.componentInstance.errorText.set('Enter a valid email address');
    fixture.detectChanges();

    expect(nativeInput(fixture).getAttribute('aria-invalid')).toBe('true');
    expect(describedTexts(root(fixture), nativeInput(fixture))).toEqual([
      'Enter a valid email address',
    ]);
  });
});

// ===========================================================================
// FORM_FIELD_CONTEXT provision
// ===========================================================================

describe('FormFieldComponent — FORM_FIELD_CONTEXT', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({ imports: [ContextHost] });
  });

  const probes = (fixture: ComponentFixture<ContextHost>): ContextProbe[] =>
    fixture.debugElement.queryAll(By.directive(ContextProbe)).map((d) => d.componentInstance);

  it('gives a projected control label, help and error signals that follow the form field inputs', () => {
    const fixture = render(ContextHost);
    const [context] = probes(fixture).map((p) => p.context);

    expect(context.label()).toBe('Email');
    expect(context.helpText()).toBe('Use your work email');
    expect(context.errorText()).toBe('');

    fixture.componentInstance.label.set('Work email');
    fixture.componentInstance.errorText.set('Enter a valid email address');
    fixture.detectChanges();

    expect(context.label()).toBe('Work email');
    expect(context.errorText()).toBe('Enter a valid email address');
  });

  it('gives each form field its own ids, matching the component and stable across checks', () => {
    const fixture = render(ContextHost);
    const [first, second] = probes(fixture).map((p) => p.context);
    const ids = [first.controlId, first.helpId, first.errorId];

    expect(ids).toEqual([
      formField(fixture, 0).controlId,
      formField(fixture, 0).helpId,
      formField(fixture, 0).errorId,
    ]);
    expect(new Set([...ids, second.controlId, second.helpId, second.errorId]).size).toBe(6);
    expect(formField(fixture, 0).fieldId).toBe(first.controlId);

    fixture.componentInstance.label.set('Work email');
    fixture.detectChanges();
    expect([first.controlId, first.helpId, first.errorId]).toEqual(ids);
  });

  it('when a projected control injects the context, the form field renders no label or supporting text of its own', () => {
    const fixture = render(ContextHost);

    expect(root(fixture).querySelector('label')).toBeNull();
    expect(fallbackElements(root(fixture))).toEqual([]);
    expect(root(fixture).textContent).not.toContain('Use your work email');

    fixture.componentInstance.errorText.set('Enter a valid email address');
    fixture.detectChanges();
    expect(root(fixture).querySelector('[role="alert"]')).toBeNull();
  });
});
