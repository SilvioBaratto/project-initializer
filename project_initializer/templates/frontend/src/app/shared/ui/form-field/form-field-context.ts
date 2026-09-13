import { InjectionToken, Signal } from '@angular/core';

/**
 * Contract between <app-form-field> and the controls projected into it
 * (<app-input>, <app-select>).
 *
 * The form field provides it from its component `providers`, so any control
 * projected into it can inject it through the element injector. A control injects
 * it with `{ optional: true }` and renders the label, hint and error inside its own
 * <mat-form-field>, because Angular Material's form field only discovers a `matInput`
 * or `mat-select` declared in the same template and cannot wrap projected controls.
 *
 * Injecting the context claims it. Once a projected control has injected it, the
 * form field stops rendering its own label, help and error text and leaves the ARIA
 * wiring (`label[for]` or `aria-labelledby`, `aria-describedby`, `aria-invalid`) to
 * that control's Material form field, so nothing is announced twice. Projected native
 * controls (`input`, `select`, `textarea`) never inject it and get the form field's
 * own label, supporting text and ARIA wiring instead.
 *
 * The claim holds only while no native control is projected outside a Material form
 * field. A consumer therefore renders any native element it contains inside its own
 * <mat-form-field>, and a form field that swaps a consumer for a native control labels
 * that control again.
 *
 * Context signals may already hold values when the control is created.
 */
export interface FormFieldContext {
  readonly label: Signal<string>;
  readonly helpText: Signal<string>;
  readonly errorText: Signal<string>;
  /** id the control element must carry so the label names it. */
  readonly controlId: string;
  /** id for the element that shows the help text. */
  readonly helpId: string;
  /** id for the element that shows the error text. */
  readonly errorId: string;
}

export const FORM_FIELD_CONTEXT = new InjectionToken<FormFieldContext>('FORM_FIELD_CONTEXT');
