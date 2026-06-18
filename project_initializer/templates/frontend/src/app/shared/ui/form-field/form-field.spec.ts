/**
 * Source-blind tests for FormFieldComponent — authored from acceptance criteria only.
 * Criterion: FormField renders label + projected control + error/help,
 *             wiring `aria-describedby` and `aria-invalid`.
 *
 * Issue #21 additions:
 *   - label.htmlFor === control.id (runtime DOM assertion, bare projected <input>)
 *   - label.htmlFor === control.id with <app-input> and <app-select>
 *   - aria-invalid / aria-describedby matrix (errorText / helpText)
 */
import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { FormFieldComponent } from './form-field';
import { InputComponent } from '../input/input';
import { SelectComponent, SelectOption } from '../select/select';

// ---------------------------------------------------------------------------
// Shared TestHost — binds all FormField inputs and projects a plain <input>
// so we can inspect what aria attributes FormField places on its content.
// ---------------------------------------------------------------------------
@Component({
  standalone: true,
  imports: [FormFieldComponent],
  template: `
    <app-form-field
      [label]="label"
      [helpText]="helpText"
      [errorText]="errorText"
    >
      <input data-testid="ctrl" />
    </app-form-field>
  `,
})
class TestHost {
  label = '';
  helpText = '';
  errorText = '';
}

// ---------------------------------------------------------------------------
// AppInputHost — projects <app-input> inside FormField (issue #21 criterion)
// ---------------------------------------------------------------------------
@Component({
  standalone: true,
  imports: [FormFieldComponent, InputComponent],
  template: `
    <app-form-field
      [label]="label"
      [helpText]="helpText"
      [errorText]="errorText"
    >
      <app-input data-testid="app-input-wrapper" />
    </app-form-field>
  `,
})
class AppInputHost {
  label = 'Email';
  helpText = '';
  errorText = '';
}

// ---------------------------------------------------------------------------
// AppSelectHost — projects <app-select> inside FormField (issue #21 criterion)
// ---------------------------------------------------------------------------
@Component({
  standalone: true,
  imports: [FormFieldComponent, SelectComponent],
  template: `
    <app-form-field
      [label]="label"
      [helpText]="helpText"
      [errorText]="errorText"
    >
      <app-select [options]="options" />
    </app-form-field>
  `,
})
class AppSelectHost {
  label = 'Country';
  helpText = '';
  errorText = '';
  options: SelectOption[] = [
    { value: 'us', label: 'United States' },
    { value: 'de', label: 'Germany' },
  ];
}

describe('FormFieldComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [TestHost],
    }).compileComponents();
  });

  // -- label rendering -------------------------------------------------------

  it('when label is provided, the label text is rendered in the DOM', () => {
    const fixture = TestBed.createComponent(TestHost);
    fixture.componentInstance.label = 'Email address';
    fixture.detectChanges();

    const label = fixture.nativeElement.querySelector('label');
    expect(label).not.toBeNull();
    expect(label.textContent.trim()).toBe('Email address');
  });

  // -- content projection ----------------------------------------------------

  it('when a control is projected, the control appears inside the rendered field', () => {
    const fixture = TestBed.createComponent(TestHost);
    fixture.componentInstance.label = 'Name';
    fixture.detectChanges();

    expect(
      fixture.nativeElement.querySelector('[data-testid="ctrl"]'),
    ).not.toBeNull();
  });

  // -- help text rendering ---------------------------------------------------

  it('when helpText is provided, the help text is rendered in the DOM', () => {
    const fixture = TestBed.createComponent(TestHost);
    fixture.componentInstance.label = 'Email';
    fixture.componentInstance.helpText = 'Enter your work email';
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Enter your work email');
  });

  // -- error text rendering --------------------------------------------------

  it('when errorText is provided, the error text is rendered in the DOM', () => {
    const fixture = TestBed.createComponent(TestHost);
    fixture.componentInstance.label = 'Email';
    fixture.componentInstance.errorText = 'Invalid email address';
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Invalid email address');
  });

  // -- aria-invalid ----------------------------------------------------------

  it('when errorText is provided, aria-invalid on the projected control is "true"', () => {
    const fixture = TestBed.createComponent(TestHost);
    fixture.componentInstance.label = 'Email';
    fixture.componentInstance.errorText = 'Required';
    fixture.detectChanges();

    const ctrl = fixture.nativeElement.querySelector('[data-testid="ctrl"]');
    expect(ctrl?.getAttribute('aria-invalid')).toBe('true');
  });

  it('when no errorText is provided, aria-invalid on the projected control is absent or "false"', () => {
    const fixture = TestBed.createComponent(TestHost);
    fixture.componentInstance.label = 'Email';
    fixture.detectChanges();

    const ctrl = fixture.nativeElement.querySelector('[data-testid="ctrl"]');
    const val = ctrl?.getAttribute('aria-invalid');
    expect(val === null || val === 'false').toBe(true);
  });

  // -- aria-describedby + error ---------------------------------------------

  it('when errorText is provided, aria-describedby on the control references an element containing the error text', () => {
    const fixture = TestBed.createComponent(TestHost);
    fixture.componentInstance.label = 'Email';
    fixture.componentInstance.errorText = 'Invalid email';
    fixture.detectChanges();

    const el = fixture.nativeElement;
    const ctrl = el.querySelector('[data-testid="ctrl"]');
    const describedBy: string | null = ctrl?.getAttribute('aria-describedby') ?? null;

    expect(describedBy).toBeTruthy();

    // aria-describedby may reference multiple space-separated ids; use the first
    const firstId = describedBy!.split(/\s+/)[0];
    const described = el.querySelector(`#${firstId}`);
    expect(described).not.toBeNull();
    expect(described!.textContent).toContain('Invalid email');
  });

  // -- aria-describedby + help ----------------------------------------------

  it('when helpText is provided, aria-describedby on the control references an element containing the help text', () => {
    const fixture = TestBed.createComponent(TestHost);
    fixture.componentInstance.label = 'Email';
    fixture.componentInstance.helpText = 'We will never share your email';
    fixture.detectChanges();

    const el = fixture.nativeElement;
    const ctrl = el.querySelector('[data-testid="ctrl"]');
    const describedBy: string | null = ctrl?.getAttribute('aria-describedby') ?? null;

    expect(describedBy).toBeTruthy();

    const firstId = describedBy!.split(/\s+/)[0];
    const described = el.querySelector(`#${firstId}`);
    expect(described).not.toBeNull();
    expect(described!.textContent).toContain('We will never share your email');
  });

  // -- errorText overrides helpText for aria-invalid -------------------------

  it('when both helpText and errorText are provided, aria-invalid on the control is "true"', () => {
    const fixture = TestBed.createComponent(TestHost);
    fixture.componentInstance.label = 'Email';
    fixture.componentInstance.helpText = 'Enter your work email';
    fixture.componentInstance.errorText = 'Invalid format';
    fixture.detectChanges();

    const ctrl = fixture.nativeElement.querySelector('[data-testid="ctrl"]');
    expect(ctrl?.getAttribute('aria-invalid')).toBe('true');
  });
});

// ===========================================================================
// Issue #21 — label.htmlFor === control.id (runtime DOM assertion)
// ===========================================================================

describe('FormFieldComponent — label.htmlFor association (bare projected input)', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [TestHost],
    }).compileComponents();
  });

  it('when a bare input is projected, label.htmlFor equals the rendered input id', () => {
    const fixture = TestBed.createComponent(TestHost);
    fixture.componentInstance.label = 'Email';
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    const label = el.querySelector('label')!;
    const ctrl = el.querySelector<HTMLInputElement>('[data-testid="ctrl"]')!;

    expect(label.htmlFor).toBeTruthy();
    expect(ctrl.id).toBeTruthy();
    expect(label.htmlFor).toBe(ctrl.id);
  });

  it('when a bare input is projected without an initial id, FormField assigns one', () => {
    const fixture = TestBed.createComponent(TestHost);
    fixture.componentInstance.label = 'Name';
    fixture.detectChanges();

    const root = fixture.nativeElement as HTMLElement;
    const ctrl = root.querySelector('[data-testid="ctrl"]') as HTMLInputElement;
    expect(ctrl.id).toBeTruthy();
  });
});

// ===========================================================================
// Issue #21 — label.htmlFor association with <app-input>
// ===========================================================================

describe('FormFieldComponent — label.htmlFor association (projected app-input)', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AppInputHost],
    }).compileComponents();
  });

  it('when app-input is projected, label.htmlFor equals the rendered native input id', () => {
    const fixture = TestBed.createComponent(AppInputHost);
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    const label = el.querySelector('label')!;
    const nativeInput = el.querySelector('input')!;

    expect(label.htmlFor).toBeTruthy();
    expect(nativeInput.id).toBeTruthy();
    expect(label.htmlFor).toBe(nativeInput.id);
  });
});

// ===========================================================================
// Issue #21 — label.htmlFor association with <app-select>
// ===========================================================================

describe('FormFieldComponent — label.htmlFor association (projected app-select)', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AppSelectHost],
    }).compileComponents();
  });

  it('when app-select is projected, label.htmlFor equals the rendered native select id', () => {
    const fixture = TestBed.createComponent(AppSelectHost);
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    const label = el.querySelector('label')!;
    const nativeSelect = el.querySelector('select')!;

    expect(label.htmlFor).toBeTruthy();
    expect(nativeSelect.id).toBeTruthy();
    expect(label.htmlFor).toBe(nativeSelect.id);
  });
});

// ===========================================================================
// Issue #21 — aria-invalid / aria-describedby matrix with app-input
// ===========================================================================

describe('FormFieldComponent — aria-invalid / aria-describedby matrix (app-input)', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AppInputHost],
    }).compileComponents();
  });

  it('when errorText is set, the native input has aria-invalid="true"', () => {
    const fixture = TestBed.createComponent(AppInputHost);
    fixture.componentInstance.errorText = 'Required field';
    fixture.detectChanges();

    const input = fixture.nativeElement.querySelector('input')!;
    expect(input.getAttribute('aria-invalid')).toBe('true');
  });

  it('when errorText is not set, the native input has no aria-invalid="true"', () => {
    const fixture = TestBed.createComponent(AppInputHost);
    fixture.componentInstance.errorText = '';
    fixture.detectChanges();

    const input = fixture.nativeElement.querySelector('input')!;
    const val = input.getAttribute('aria-invalid');
    expect(val === null || val === 'false').toBe(true);
  });

  it('when errorText is set, aria-describedby references an element containing the error text', () => {
    const fixture = TestBed.createComponent(AppInputHost);
    fixture.componentInstance.errorText = 'Must be a valid email';
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    const input = el.querySelector('input')!;
    const describedById = input.getAttribute('aria-describedby');

    expect(describedById).toBeTruthy();
    const describedEl = el.querySelector(`#${describedById!.split(/\s+/)[0]}`)!;
    expect(describedEl).not.toBeNull();
    expect(describedEl.textContent).toContain('Must be a valid email');
  });

  it('when helpText is set and errorText is not, aria-describedby references an element containing the help text', () => {
    const fixture = TestBed.createComponent(AppInputHost);
    fixture.componentInstance.helpText = 'We will never share your email';
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    const input = el.querySelector('input')!;
    const describedById = input.getAttribute('aria-describedby');

    expect(describedById).toBeTruthy();
    const describedEl = el.querySelector(`#${describedById!.split(/\s+/)[0]}`)!;
    expect(describedEl).not.toBeNull();
    expect(describedEl.textContent).toContain('We will never share your email');
  });

  it('when neither errorText nor helpText is set, aria-describedby is absent on the input', () => {
    const fixture = TestBed.createComponent(AppInputHost);
    fixture.detectChanges();

    const input = fixture.nativeElement.querySelector('input')!;
    expect(input.getAttribute('aria-describedby')).toBeNull();
  });
});
