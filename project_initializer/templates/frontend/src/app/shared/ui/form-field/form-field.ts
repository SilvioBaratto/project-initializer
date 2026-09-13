import {
  AfterViewChecked,
  ChangeDetectionStrategy,
  Component,
  computed,
  ElementRef,
  inject,
  input,
  signal,
} from '@angular/core';

import { FORM_FIELD_CONTEXT, FormFieldContext } from './form-field-context';

let nextUniqueId = 0;

/** Projected native controls that the form field labels and wires itself. */
const NATIVE_CONTROL_SELECTOR = 'input, select, textarea';

/**
 * Host class of every `<mat-form-field>` (also what MatFormFieldHarness looks for).
 * A native control inside one belongs to that Material field, not to this component.
 */
const MATERIAL_FORM_FIELD_SELECTOR = '.mat-mdc-form-field';

/**
 * Labels a projected form control and shows its help or error text.
 *
 * - `<app-input>` / `<app-select>` inject FORM_FIELD_CONTEXT (provided here) and
 *   render the label, hint and error inside their own outlined `<mat-form-field>`,
 *   with the ids this component generates. Material then owns the ARIA wiring, and
 *   this component renders only the projected control.
 * - A projected native `input`, `select` or `textarea` gets a visible `<label for>`,
 *   help text, or error text (`role="alert"`), styled with `--mat-sys-*` tokens. After
 *   each check the component gives the control `controlId` when it has no id (an
 *   existing id is kept and the label follows it), sets `aria-invalid="true"` while
 *   there is error text, and points `aria-describedby` at the error, otherwise the
 *   help text, keeping any other ids the control already lists.
 *
 * The choice follows what is projected now, so a form field can swap between the two
 * (for example an `@if` choosing `<app-input>` or a native `<input>`): the fallback
 * shows while no control has injected the context, or while a native control sits
 * outside any Material form field. Wrap one control per form field.
 */
@Component({
  selector: 'app-form-field',
  templateUrl: './form-field.html',
  styleUrl: './form-field.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
  providers: [
    {
      provide: FORM_FIELD_CONTEXT,
      useFactory: (): FormFieldContext => inject(FormFieldComponent).claimContext(),
    },
  ],
})
export class FormFieldComponent implements AfterViewChecked {
  private readonly host: HTMLElement = inject(ElementRef).nativeElement;

  readonly label = input('');
  readonly helpText = input('');
  readonly errorText = input('');

  private readonly uniqueId = `app-form-field-${nextUniqueId++}`;

  /** id the projected control carries so the label names it. */
  readonly controlId = `${this.uniqueId}-control`;
  /** Alias of `controlId`. */
  readonly fieldId = this.controlId;
  readonly helpId = `${this.uniqueId}-hint`;
  readonly errorId = `${this.uniqueId}-error`;

  /**
   * True once a projected control has injected FORM_FIELD_CONTEXT. The element injector
   * caches the provided value, so the factory runs only for the first consumer; this is
   * what hides the fallback on the first render, before any view check.
   */
  private readonly consumerSeen = signal(false);
  /** True while a projected native control sits outside any Material form field. */
  private readonly hasOwnControl = signal(false);

  /**
   * A context consumer renders the label and supporting text, unless a native control
   * that no Material form field owns is projected now (a consumer was swapped out).
   */
  protected readonly contextClaimed = computed(() => this.consumerSeen() && !this.hasOwnControl());
  /** id of the projected native control, which the fallback label points at. */
  protected readonly labelFor = signal(this.controlId);

  private readonly context: FormFieldContext = {
    label: this.label,
    helpText: this.helpText,
    errorText: this.errorText,
    controlId: this.controlId,
    helpId: this.helpId,
    errorId: this.errorId,
  };

  /**
   * Hands FORM_FIELD_CONTEXT to the control that injects it and hides this
   * component's own label and supporting text. Called by the provider factory.
   */
  claimContext(): FormFieldContext {
    this.consumerSeen.set(true);
    return this.context;
  }

  // A view hook, because projected content can't take bindings from this template.
  // Runs whenever the view that declares this form field is checked, which is also
  // when its projected content and inputs change. A signal write here refreshes this
  // view again in the same change detection pass.
  ngAfterViewChecked(): void {
    const control = this.findOwnControl();
    this.hasOwnControl.set(control !== null);
    if (!control) return;
    this.applyId(control);
    this.applyInvalid(control);
    this.applyDescribedBy(control);
  }

  /** The first projected native control that no Material form field owns. */
  private findOwnControl(): HTMLElement | null {
    const controls = Array.from(this.host.querySelectorAll<HTMLElement>(NATIVE_CONTROL_SELECTOR));
    return controls.find((control) => !this.isInsideMaterialField(control)) ?? null;
  }

  private isInsideMaterialField(control: HTMLElement): boolean {
    const field = control.closest(MATERIAL_FORM_FIELD_SELECTOR);
    return field !== null && this.host.contains(field);
  }

  /** Gives the control `controlId` when it has no id; an existing id is kept. */
  private applyId(control: HTMLElement): void {
    if (!control.id) control.id = this.controlId;
    if (this.labelFor() !== control.id) this.labelFor.set(control.id);
  }

  private applyInvalid(control: HTMLElement): void {
    if (this.errorText()) control.setAttribute('aria-invalid', 'true');
    else control.removeAttribute('aria-invalid');
  }

  /** Error text replaces help text; ids that other code put on the control stay. */
  private applyDescribedBy(control: HTMLElement): void {
    const current = control.getAttribute('aria-describedby') ?? '';
    const others = current
      .split(/\s+/)
      .filter((id) => id !== '' && id !== this.helpId && id !== this.errorId);
    const own = this.errorText() ? this.errorId : this.helpText() ? this.helpId : '';
    const next = (own ? [own, ...others] : others).join(' ');
    if (next === current) return;
    if (next) control.setAttribute('aria-describedby', next);
    else control.removeAttribute('aria-describedby');
  }
}
