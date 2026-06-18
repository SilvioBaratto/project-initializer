/**
 * Tests for RadioComponent.
 * Criterion: Radio renders with an associated <label>; supports
 * checked/disabled/errorText; implements ControlValueAccessor (value-based).
 */
import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { RadioComponent } from './radio';

@Component({
  standalone: true,
  imports: [RadioComponent],
  template: `
    <app-radio
      [id]="controlId"
      [name]="groupName"
      [value]="value"
      [label]="labelText"
      [errorText]="errorText"
      [disabled]="disabled"
    />
  `,
})
class RadioTestHost {
  controlId = 'test-radio';
  groupName = 'size';
  value = 'medium';
  labelText = 'Medium';
  errorText = '';
  disabled = false;
}

describe('RadioComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [RadioTestHost],
    }).compileComponents();
  });

  // -- label association via wrapping ----------------------------------------

  it('when rendered, a <label> element is present', () => {
    const fixture = TestBed.createComponent(RadioTestHost);
    fixture.detectChanges();

    const label = fixture.nativeElement.querySelector('label');
    expect(label).not.toBeNull();
  });

  it('when rendered, the native <input type="radio"> is inside the <label>', () => {
    const fixture = TestBed.createComponent(RadioTestHost);
    fixture.detectChanges();

    const input = fixture.nativeElement.querySelector('label input[type="radio"]');
    expect(input).not.toBeNull();
  });

  it('when label text is provided, the label text appears in the DOM', () => {
    const fixture = TestBed.createComponent(RadioTestHost);
    fixture.detectChanges();

    const label = fixture.nativeElement.querySelector('label');
    expect(label?.textContent?.trim()).toContain('Medium');
  });

  // -- name attribute for group behaviour ------------------------------------

  it('when name is provided, the native input carries that name attribute', () => {
    const fixture = TestBed.createComponent(RadioTestHost);
    fixture.detectChanges();

    const input = fixture.nativeElement.querySelector('input') as HTMLInputElement;
    expect(input.name).toBe('size');
  });

  // -- checked state via ControlValueAccessor --------------------------------

  it('when writeValue matches the radio value, the native input is checked', () => {
    const fixture = TestBed.createComponent(RadioTestHost);
    fixture.detectChanges();

    const comp = fixture.debugElement.query(
      (el) => el.componentInstance instanceof RadioComponent,
    )?.componentInstance as RadioComponent;

    comp.writeValue('medium');
    fixture.detectChanges();

    const input = fixture.nativeElement.querySelector('input') as HTMLInputElement;
    expect(input.checked).toBe(true);
  });

  it('when writeValue does not match the radio value, the native input is not checked', () => {
    const fixture = TestBed.createComponent(RadioTestHost);
    fixture.detectChanges();

    const comp = fixture.debugElement.query(
      (el) => el.componentInstance instanceof RadioComponent,
    )?.componentInstance as RadioComponent;

    comp.writeValue('large');
    fixture.detectChanges();

    const input = fixture.nativeElement.querySelector('input') as HTMLInputElement;
    expect(input.checked).toBe(false);
  });

  // -- disabled state --------------------------------------------------------

  it('when disabled is true, the native input is disabled', () => {
    const fixture = TestBed.createComponent(RadioTestHost);
    fixture.componentInstance.disabled = true;
    fixture.detectChanges();

    const input = fixture.nativeElement.querySelector('input') as HTMLInputElement;
    expect(input.disabled).toBe(true);
  });

  it('when disabled is false, the native input is not disabled', () => {
    const fixture = TestBed.createComponent(RadioTestHost);
    fixture.componentInstance.disabled = false;
    fixture.detectChanges();

    const input = fixture.nativeElement.querySelector('input') as HTMLInputElement;
    expect(input.disabled).toBe(false);
  });

  // -- error state -----------------------------------------------------------

  it('when errorText is provided, the input has aria-invalid="true"', () => {
    const fixture = TestBed.createComponent(RadioTestHost);
    fixture.componentInstance.errorText = 'Please select a size';
    fixture.detectChanges();

    const input = fixture.nativeElement.querySelector('input');
    expect(input?.getAttribute('aria-invalid')).toBe('true');
  });

  it('when no errorText is provided, aria-invalid is absent on the input', () => {
    const fixture = TestBed.createComponent(RadioTestHost);
    fixture.detectChanges();

    const input = fixture.nativeElement.querySelector('input');
    const val = input?.getAttribute('aria-invalid');
    expect(val === null || val === 'false').toBe(true);
  });

  it('when errorText is provided, the error message appears in the DOM', () => {
    const fixture = TestBed.createComponent(RadioTestHost);
    fixture.componentInstance.errorText = 'Please select a size';
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Please select a size');
  });

  // -- token classes ---------------------------------------------------------

  it('when rendered, the input element carries at least one design-token class', () => {
    const fixture = TestBed.createComponent(RadioTestHost);
    fixture.detectChanges();

    const input = fixture.nativeElement.querySelector('input');
    expect(input?.className.trim()).not.toBe('');
  });

  // -- ControlValueAccessor: onChange emits the value string -----------------

  it('when the radio is selected, the registered change callback receives the radio value', () => {
    const fixture = TestBed.createComponent(RadioTestHost);
    fixture.detectChanges();

    const comp = fixture.debugElement.query(
      (el) => el.componentInstance instanceof RadioComponent,
    )?.componentInstance as RadioComponent;

    let received: string | undefined;
    comp.registerOnChange((v: string) => { received = v; });

    const input = fixture.nativeElement.querySelector('input') as HTMLInputElement;
    input.checked = true;
    input.dispatchEvent(new Event('change'));
    fixture.detectChanges();

    expect(received).toBe('medium');
  });
});
