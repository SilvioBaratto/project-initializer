import {
  afterRenderEffect,
  ChangeDetectionStrategy,
  Component,
  computed,
  DestroyRef,
  ElementRef,
  forwardRef,
  inject,
  input,
  linkedSignal,
  signal,
  viewChild,
} from '@angular/core';
import { UniqueSelectionDispatcher } from '@angular/cdk/collections';
import { ControlValueAccessor, NG_VALUE_ACCESSOR } from '@angular/forms';
import { MatRadioButton } from '@angular/material/radio';

let nextUniqueId = 0;

/**
 * Material 3 radio button (MatRadioButton) with a string label, an error message
 * and a value-based ControlValueAccessor: bind the same `[formControl]` or
 * `ngModel` to every radio of a set, and each radio is checked when the value
 * equals its own `value`. The plain `checked` / `disabled` inputs work too.
 *
 * Radios that share a `name` form one set. Selecting one unchecks the others,
 * and because the native inputs share that name the browser keeps the set to a
 * single Tab stop and moves the selection with the arrow keys. Material links
 * the set through a root-level dispatcher, so equal names form one set across
 * the whole app, even in separate `<form>` elements: give each set its own name.
 *
 * A radio with no `name` gets a generated one, so it stays independent like a
 * native radio with an empty name instead of joining every other unnamed radio.
 *
 * Material renders the `<label for>` around the projected label text and gives
 * the native input a 48px touch target at density 0.
 */
@Component({
  selector: 'app-radio',
  imports: [MatRadioButton],
  templateUrl: './radio.html',
  styleUrl: './radio.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => RadioComponent),
      multi: true,
    },
  ],
})
export class RadioComponent implements ControlValueAccessor {
  /** Id of the `<mat-radio-button>` host; Material gives the native input `<id>-input`. */
  readonly id = input('');
  /** Radios with the same name form one set. With no name, the radio stands alone. */
  readonly name = input('');
  readonly value = input('');
  readonly label = input('');
  readonly errorText = input('');
  readonly disabled = input(false);
  readonly checked = input(false);

  // Follows the checked input. writeValue, a user selection and a selection in
  // another radio of the same set override it until the checked input changes.
  private readonly _checked = linkedSignal(() => this.checked());
  private readonly _formDisabled = signal(false);
  private readonly _uniqueId = `app-radio-${nextUniqueId++}`;

  readonly isChecked = this._checked.asReadonly();
  readonly isDisabled = computed(() => this._formDisabled() || this.disabled());
  readonly hasError = computed(() => this.errorText() !== '');
  readonly radioId = computed(() => this.id() || this._uniqueId);
  readonly errorId = computed(() => `${this.radioId()}-error`);

  // Material's dispatcher treats equal names as one set, and '' === '' would
  // link every unnamed radio in the app. A generated name keeps each one alone.
  protected readonly groupName = computed(() => this.name() || this._uniqueId);

  private readonly _radio = viewChild(MatRadioButton);
  private readonly _radioRef = viewChild.required(MatRadioButton, { read: ElementRef });

  private _onChange: (v: string) => void = () => {};
  private _onTouched: () => void = () => {};

  constructor() {
    // MatRadioButton unchecks itself, without emitting, when another radio with
    // the same name is checked. Mirror that rule so isChecked() and the [checked]
    // binding never go stale and a later writeValue can check this radio again.
    const stopListening = inject(UniqueSelectionDispatcher).listen((id, name) => {
      const radio = this._radio();
      if (radio && id !== radio.id && name === radio.name) {
        this._checked.set(false);
      }
    });
    inject(DestroyRef).onDestroy(stopListening);

    // MatRadioButton renders a static aria-invalid="false" on its native input
    // and has no input for it, so the error state is written onto that input.
    afterRenderEffect({
      write: () => {
        const host = this._radioRef().nativeElement as HTMLElement;
        const nativeInput = host.querySelector('input[type="radio"]');
        nativeInput?.setAttribute('aria-invalid', String(this.hasError()));
      },
    });
  }

  onChange(): void {
    this._checked.set(true);
    this._onChange(this.value());
  }

  onTouched(): void {
    this._onTouched();
  }

  writeValue(v: string): void {
    this._checked.set(v === this.value());
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
