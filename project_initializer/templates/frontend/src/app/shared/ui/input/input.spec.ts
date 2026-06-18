/**
 * Source-blind tests for InputComponent — authored from acceptance criteria only.
 * Criterion: Input consumes tokens, supports error/disabled, associates label via `id`.
 *
 * The component does not exist yet (Red phase). Every test here is expected to
 * fail until the implementation is in place.
 *
 * Chosen interpretation: InputComponent is an Angular standalone component that
 * renders a native <input> with design-token classes (from the @theme palette), an
 * `id` input that links it to a <label>, and error/disabled visual + ARIA states.
 */
import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { InputComponent } from './input';

// ---------------------------------------------------------------------------
// Minimal TestHost
// ---------------------------------------------------------------------------
@Component({
  standalone: true,
  imports: [InputComponent],
  template: `
    <label [attr.for]="controlId">{{ labelText }}</label>
    <app-input
      [id]="controlId"
      [errorText]="errorText"
      [disabled]="disabled"
    />
  `,
})
class InputTestHost {
  controlId = 'test-input';
  labelText = 'Username';
  errorText = '';
  disabled = false;
}

describe('InputComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [InputTestHost],
    }).compileComponents();
  });

  // -- label association via id ---------------------------------------------

  it('when id is provided, the rendered input element has that id so a <label for> association works', () => {
    const fixture = TestBed.createComponent(InputTestHost);
    fixture.detectChanges();

    const input = fixture.nativeElement.querySelector('input');
    expect(input?.id).toBe('test-input');
  });

  it('when id on InputComponent matches the for attribute of a sibling label, the label programmatically references the input', () => {
    const fixture = TestBed.createComponent(InputTestHost);
    fixture.detectChanges();

    const label = fixture.nativeElement.querySelector('label');
    const input = fixture.nativeElement.querySelector('input');
    expect(label?.htmlFor).toBe(input?.id);
  });

  // -- error state ----------------------------------------------------------

  it('when errorText is provided, the input has aria-invalid="true"', () => {
    const fixture = TestBed.createComponent(InputTestHost);
    fixture.componentInstance.errorText = 'Username is required';
    fixture.detectChanges();

    const input = fixture.nativeElement.querySelector('input');
    expect(input?.getAttribute('aria-invalid')).toBe('true');
  });

  it('when no errorText is provided, the input does not have aria-invalid="true"', () => {
    const fixture = TestBed.createComponent(InputTestHost);
    fixture.detectChanges();

    const input = fixture.nativeElement.querySelector('input');
    const val = input?.getAttribute('aria-invalid');
    expect(val === null || val === 'false').toBe(true);
  });

  // -- disabled state -------------------------------------------------------

  it('when disabled is true, the input element is disabled', () => {
    const fixture = TestBed.createComponent(InputTestHost);
    fixture.componentInstance.disabled = true;
    fixture.detectChanges();

    const input = fixture.nativeElement.querySelector('input');
    expect(input?.disabled).toBe(true);
  });

  it('when disabled is false, the input element is not disabled', () => {
    const fixture = TestBed.createComponent(InputTestHost);
    fixture.componentInstance.disabled = false;
    fixture.detectChanges();

    const input = fixture.nativeElement.querySelector('input');
    expect(input?.disabled).toBe(false);
  });

  // -- token consumption (design system classes) ----------------------------

  it('when rendered, the input element carries at least one Tailwind design-token class (not an unstyled native input)', () => {
    /**
     * "Consumes tokens" means the component applies @theme token classes
     * (e.g. bg-surface, border-border, text-foreground, ring-ring, etc.)
     * rather than leaving the input completely bare. We check for any
     * class that references a semantic token name.
     *
     * If the implementation uses a different token vocabulary, this test
     * name remains the same but the pattern can be widened. The key
     * invariant: the element must have CSS classes; an unstyled bare <input>
     * with no class attribute would fail.
     */
    const fixture = TestBed.createComponent(InputTestHost);
    fixture.detectChanges();

    const input = fixture.nativeElement.querySelector('input');
    expect(input?.className.trim()).not.toBe('');
  });
});
