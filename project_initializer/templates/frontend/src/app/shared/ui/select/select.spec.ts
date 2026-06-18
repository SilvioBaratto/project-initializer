/**
 * Source-blind tests for SelectComponent — authored from acceptance criteria only.
 * Criterion: Select consumes tokens, supports error/disabled, associates label via `id`.
 *
 * The component does not exist yet (Red phase). Every test here is expected to
 * fail until the implementation is in place.
 *
 * Chosen interpretation: SelectComponent renders a native <select> element with
 * design-token classes, an `id` that allows a <label for> association, and
 * error/disabled states expressed via ARIA + the native `disabled` property.
 */
import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { SelectComponent } from './select';

// ---------------------------------------------------------------------------
// Minimal TestHost
// ---------------------------------------------------------------------------
@Component({
  standalone: true,
  imports: [SelectComponent],
  template: `
    <label [attr.for]="controlId">{{ labelText }}</label>
    <app-select
      [id]="controlId"
      [errorText]="errorText"
      [disabled]="disabled"
      [options]="options"
    />
  `,
})
class SelectTestHost {
  controlId = 'test-select';
  labelText = 'Country';
  errorText = '';
  disabled = false;
  options: Array<{ value: string; label: string }> = [
    { value: 'us', label: 'United States' },
    { value: 'de', label: 'Germany' },
  ];
}

describe('SelectComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SelectTestHost],
    }).compileComponents();
  });

  // -- label association via id ---------------------------------------------

  it('when id is provided, the rendered select element has that id so a <label for> association works', () => {
    const fixture = TestBed.createComponent(SelectTestHost);
    fixture.detectChanges();

    const select = fixture.nativeElement.querySelector('select');
    expect(select?.id).toBe('test-select');
  });

  it('when id on SelectComponent matches the for attribute of a sibling label, the label programmatically references the select', () => {
    const fixture = TestBed.createComponent(SelectTestHost);
    fixture.detectChanges();

    const label = fixture.nativeElement.querySelector('label');
    const select = fixture.nativeElement.querySelector('select');
    expect(label?.htmlFor).toBe(select?.id);
  });

  // -- options projection ---------------------------------------------------

  it('when options are provided, each option value appears in the rendered select', () => {
    const fixture = TestBed.createComponent(SelectTestHost);
    fixture.detectChanges();

    const renderedValues = Array.from<HTMLOptionElement>(
      fixture.nativeElement.querySelectorAll('option'),
    ).map((o) => o.value);

    expect(renderedValues).toContain('us');
    expect(renderedValues).toContain('de');
  });

  // -- error state ----------------------------------------------------------

  it('when errorText is provided, the select has aria-invalid="true"', () => {
    const fixture = TestBed.createComponent(SelectTestHost);
    fixture.componentInstance.errorText = 'Please select a country';
    fixture.detectChanges();

    const select = fixture.nativeElement.querySelector('select');
    expect(select?.getAttribute('aria-invalid')).toBe('true');
  });

  it('when no errorText is provided, the select does not have aria-invalid="true"', () => {
    const fixture = TestBed.createComponent(SelectTestHost);
    fixture.detectChanges();

    const select = fixture.nativeElement.querySelector('select');
    const val = select?.getAttribute('aria-invalid');
    expect(val === null || val === 'false').toBe(true);
  });

  // -- disabled state -------------------------------------------------------

  it('when disabled is true, the select element is disabled', () => {
    const fixture = TestBed.createComponent(SelectTestHost);
    fixture.componentInstance.disabled = true;
    fixture.detectChanges();

    const select = fixture.nativeElement.querySelector('select');
    expect(select?.disabled).toBe(true);
  });

  it('when disabled is false, the select element is not disabled', () => {
    const fixture = TestBed.createComponent(SelectTestHost);
    fixture.componentInstance.disabled = false;
    fixture.detectChanges();

    const select = fixture.nativeElement.querySelector('select');
    expect(select?.disabled).toBe(false);
  });

  // -- token consumption (design system classes) ----------------------------

  it('when rendered, the select element carries at least one design-token class (not an unstyled native select)', () => {
    /**
     * Same invariant as InputComponent: the element must have CSS classes
     * that bind it to the @theme token palette. An empty class string
     * means the component is not consuming tokens.
     */
    const fixture = TestBed.createComponent(SelectTestHost);
    fixture.detectChanges();

    const select = fixture.nativeElement.querySelector('select');
    expect(select?.className.trim()).not.toBe('');
  });
});
