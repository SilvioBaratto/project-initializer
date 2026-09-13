import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  forwardRef,
  inject,
  input,
  signal,
  untracked,
  viewChild,
} from '@angular/core';
import { ControlValueAccessor, NG_VALUE_ACCESSOR } from '@angular/forms';
import { ErrorStateMatcher } from '@angular/material/core';
import { MatInput, MatInputModule } from '@angular/material/input';

import { FORM_FIELD_CONTEXT } from '../form-field/form-field-context';

let nextUniqueId = 0;

/**
 * Material 3 outlined text field: `<mat-form-field appearance="outline">` around a
 * native `<input matInput>`, with ControlValueAccessor support so it works with
 * `[formControl]` / `ngModel` as well as the plain `disabled` input.
 *
 * Inside `<app-form-field>` it reads FORM_FIELD_CONTEXT and renders the label
 * (`<mat-label>`), help text (`<mat-hint [id]="ctx.helpId">`) and error text
 * (`<mat-error [id]="ctx.errorId">`) inside its own form field, because Material
 * only discovers a `matInput` declared in the same template as the form field.
 * The native input takes `id()` when given, otherwise `ctx.controlId`.
 *
 * Error state follows `errorText` (own input first, then the context), not form
 * validity: a non-empty message, including one already set on the first render,
 * turns the field into its error state, shows the message and makes MatInput bind
 * `aria-invalid="true"`. Material's form field points `aria-describedby` at the
 * visible hint or error and removes the attribute when neither is shown.
 *
 * Without a context and without a visible label, name the field with a sibling
 * `<label for>` matching `id`, or pass `aria-label`.
 */
@Component({
  selector: 'app-input',
  imports: [MatInputModule],
  templateUrl: './input.html',
  styleUrl: './input.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => InputComponent),
      multi: true,
    },
  ],
  viewProviders: [
    // MatInput creates its error state tracker in its constructor from the injected
    // ErrorStateMatcher. An [errorStateMatcher] binding would land only in the
    // template update pass, after the first evaluation, so an errorText present on
    // the first render would never show. DI hands MatInput this matcher up front.
    {
      provide: ErrorStateMatcher,
      useFactory: () => inject(InputComponent).errorStateMatcher,
    },
  ],
  host: {
    // `id` and `aria-label` belong on the native input. Static attributes would
    // otherwise also stay on this host: a duplicate id, and a name on a generic element.
    '[attr.id]': 'null',
    '[attr.aria-label]': 'null',
  },
})
export class InputComponent implements ControlValueAccessor {
  private readonly context = inject(FORM_FIELD_CONTEXT, { optional: true });

  /** Id of the native input. Falls back to the form field context's controlId. */
  readonly id = input('');
  readonly errorText = input('');
  readonly disabled = input(false);
  /** Accessible name for a field with no visible label. */
  readonly ariaLabel = input('', { alias: 'aria-label' });

  readonly value = signal('');
  private readonly _formDisabled = signal(false);
  private readonly _uniqueId = `app-input-${nextUniqueId++}`;

  readonly isDisabled = computed(() => this._formDisabled() || this.disabled());

  readonly label = computed(() => this.context?.label() ?? '');
  readonly helpText = computed(() => this.context?.helpText() ?? '');
  readonly resolvedErrorText = computed(
    () => this.errorText() || this.context?.errorText() || '',
  );
  readonly hasError = computed(() => this.resolvedErrorText() !== '');

  /** Empty string lets MatInput generate its own unique id. */
  readonly inputId = computed(() => this.id() || this.context?.controlId || '');
  readonly hintId = this.context?.helpId ?? `${this._uniqueId}-hint`;
  readonly errorId = this.context?.errorId ?? `${this._uniqueId}-error`;

  /**
   * Drives Material's error state (outline, label, mat-error, aria-invalid) from
   * errorText. Handed to MatInput through `viewProviders`.
   */
  readonly errorStateMatcher: ErrorStateMatcher = {
    isErrorState: () => this.hasError(),
  };

  private readonly _matInput = viewChild(MatInput);

  private _onChange: (v: string) => void = () => {};
  private _onTouched: () => void = () => {};

  constructor() {
    // MatInput re-evaluates its matcher by itself (ngDoCheck) only when a forms
    // directive sits on the native input; the FormControl binds to this host
    // instead, so re-evaluate whenever the error text changes. A component effect
    // runs before this view's template is refreshed, so aria-invalid and the form
    // field's error/hint switch pick up the new state in the same pass.
    effect(() => {
      const matInput = this._matInput();
      this.hasError();
      untracked(() => matInput?.updateErrorState());
    });
  }

  onInput(event: Event): void {
    const v = (event.target as HTMLInputElement).value;
    this.value.set(v);
    this._onChange(v);
  }

  onTouched(): void {
    this._onTouched();
  }

  writeValue(v: string): void {
    this.value.set(v ?? '');
  }

  registerOnChange(fn: (v: string) => void): void {
    this._onChange = fn;
  }

  registerOnTouched(fn: () => void): void {
    this._onTouched = fn;
  }

  setDisabledState(isDisabled: boolean): void {
    this._formDisabled.set(isDisabled);
  }
}
