/**
 * Tests for CheckboxComponent.
 * Criterion: Checkbox renders with an associated <label>; supports
 * checked/disabled/errorText; implements ControlValueAccessor.
 */
import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { CheckboxComponent } from './checkbox';

@Component({
  standalone: true,
  imports: [CheckboxComponent],
  template: `
    <app-checkbox
      [id]="controlId"
      [label]="labelText"
      [errorText]="errorText"
      [disabled]="disabled"
    />
  `,
})
class CheckboxTestHost {
  controlId = 'test-checkbox';
  labelText = 'Accept terms';
  errorText = '';
  disabled = false;
}

describe('CheckboxComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [CheckboxTestHost],
    }).compileComponents();
  });

  // -- label association via wrapping ----------------------------------------

  it('when rendered, a <label> element is present', () => {
    const fixture = TestBed.createComponent(CheckboxTestHost);
    fixture.detectChanges();

    const label = fixture.nativeElement.querySelector('label');
    expect(label).not.toBeNull();
  });

  it('when rendered, the native <input type="checkbox"> is inside the <label>', () => {
    const fixture = TestBed.createComponent(CheckboxTestHost);
    fixture.detectChanges();

    const input = fixture.nativeElement.querySelector('label input[type="checkbox"]');
    expect(input).not.toBeNull();
  });

  it('when label text is provided, the label text appears in the DOM', () => {
    const fixture = TestBed.createComponent(CheckboxTestHost);
    fixture.detectChanges();

    const label = fixture.nativeElement.querySelector('label');
    expect(label?.textContent?.trim()).toContain('Accept terms');
  });

  // -- checked state ---------------------------------------------------------

  it('when writeValue is called with true, the native input is checked', async () => {
    const fixture = TestBed.createComponent(CheckboxTestHost);
    fixture.detectChanges();

    const comp = fixture.debugElement.query(
      (el) => el.componentInstance instanceof CheckboxComponent,
    )?.componentInstance as CheckboxComponent;

    comp.writeValue(true);
    fixture.detectChanges();
    await fixture.whenStable();

    const input = fixture.nativeElement.querySelector('input[type="checkbox"]') as HTMLInputElement;
    expect(input.checked).toBe(true);
  });

  it('when writeValue is called with false, the native input is not checked', async () => {
    const fixture = TestBed.createComponent(CheckboxTestHost);
    fixture.detectChanges();

    const comp = fixture.debugElement.query(
      (el) => el.componentInstance instanceof CheckboxComponent,
    )?.componentInstance as CheckboxComponent;

    comp.writeValue(false);
    fixture.detectChanges();
    await fixture.whenStable();

    const input = fixture.nativeElement.querySelector('input[type="checkbox"]') as HTMLInputElement;
    expect(input.checked).toBe(false);
  });

  // -- disabled state --------------------------------------------------------

  it('when disabled is true, the native input is disabled', () => {
    const fixture = TestBed.createComponent(CheckboxTestHost);
    fixture.componentInstance.disabled = true;
    fixture.detectChanges();

    const input = fixture.nativeElement.querySelector('input') as HTMLInputElement;
    expect(input.disabled).toBe(true);
  });

  it('when disabled is false, the native input is not disabled', () => {
    const fixture = TestBed.createComponent(CheckboxTestHost);
    fixture.componentInstance.disabled = false;
    fixture.detectChanges();

    const input = fixture.nativeElement.querySelector('input') as HTMLInputElement;
    expect(input.disabled).toBe(false);
  });

  // -- error state -----------------------------------------------------------

  it('when errorText is provided, the input has aria-invalid="true"', () => {
    const fixture = TestBed.createComponent(CheckboxTestHost);
    fixture.componentInstance.errorText = 'You must accept the terms';
    fixture.detectChanges();

    const input = fixture.nativeElement.querySelector('input');
    expect(input?.getAttribute('aria-invalid')).toBe('true');
  });

  it('when no errorText is provided, aria-invalid is absent on the input', () => {
    const fixture = TestBed.createComponent(CheckboxTestHost);
    fixture.detectChanges();

    const input = fixture.nativeElement.querySelector('input');
    const val = input?.getAttribute('aria-invalid');
    expect(val === null || val === 'false').toBe(true);
  });

  it('when errorText is provided, the error message appears in the DOM', () => {
    const fixture = TestBed.createComponent(CheckboxTestHost);
    fixture.componentInstance.errorText = 'You must accept the terms';
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('You must accept the terms');
  });

  // -- token classes ---------------------------------------------------------

  it('when rendered, the input element carries at least one design-token class', () => {
    const fixture = TestBed.createComponent(CheckboxTestHost);
    fixture.detectChanges();

    const input = fixture.nativeElement.querySelector('input');
    expect(input?.className.trim()).not.toBe('');
  });

  // -- ControlValueAccessor --------------------------------------------------

  it('when onChange fires, the registered change callback receives the checked boolean', () => {
    const fixture = TestBed.createComponent(CheckboxTestHost);
    fixture.detectChanges();

    const comp = fixture.debugElement.query(
      (el) => el.componentInstance instanceof CheckboxComponent,
    )?.componentInstance as CheckboxComponent;

    let received: boolean | undefined;
    comp.registerOnChange((v: boolean) => { received = v; });

    const input = fixture.nativeElement.querySelector('input') as HTMLInputElement;
    input.checked = true;
    input.dispatchEvent(new Event('change'));
    fixture.detectChanges();

    expect(received).toBe(true);
  });
});
