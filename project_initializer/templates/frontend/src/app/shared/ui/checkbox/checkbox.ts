import {
  afterRenderEffect,
  ChangeDetectionStrategy,
  Component,
  computed,
  ElementRef,
  forwardRef,
  input,
  model,
  signal,
  viewChild,
} from '@angular/core';
import { ControlValueAccessor, NG_VALUE_ACCESSOR } from '@angular/forms';
import { MatCheckbox, MatCheckboxChange } from '@angular/material/checkbox';

let nextUniqueId = 0;

/**
 * Material 3 checkbox (MatCheckbox) with a string label, an error message and
 * ControlValueAccessor support, so it works with `[formControl]` / `ngModel`
 * as well as the plain `checked` / `disabled` inputs.
 *
 * Material renders the `<label for>` around the projected label text and gives
 * the native input the 48px touch target at density 0.
 */
@Component({
  selector: 'app-checkbox',
  imports: [MatCheckbox],
  templateUrl: './checkbox.html',
  styleUrl: './checkbox.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => CheckboxComponent),
      multi: true,
    },
  ],
})
export class CheckboxComponent implements ControlValueAccessor {
  /** Id of the `<mat-checkbox>` host; Material gives the native input `<id>-input`. */
  readonly id = input('');
  readonly label = input('');
  readonly errorText = input('');
  readonly disabled = input(false);
  readonly checked = input(false);
  /** Mixed state. Material clears it when the user toggles the checkbox, and the model syncs back. */
  readonly indeterminate = model(false);

  // CVA override: null means "use the checked input", boolean means "CVA controls it"
  private readonly _formChecked = signal<boolean | null>(null);
  private readonly _formDisabled = signal(false);
  private readonly _uniqueId = `app-checkbox-${nextUniqueId++}`;

  readonly isChecked = computed(() => this._formChecked() ?? this.checked());
  readonly isDisabled = computed(() => this._formDisabled() || this.disabled());
  readonly hasError = computed(() => this.errorText() !== '');
  readonly checkboxId = computed(() => this.id() || this._uniqueId);
  readonly errorId = computed(() => `${this.checkboxId()}-error`);

  private readonly _checkboxRef = viewChild.required(MatCheckbox, { read: ElementRef });

  private _onChange: (v: boolean) => void = () => {};
  private _onTouched: () => void = () => {};

  constructor() {
    // MatCheckbox has no aria-invalid input. Its aria-describedby input is typed
    // `string` (MatRadioButton's accepts null), so under strictTemplates the only
    // way to say "no description" is '', which renders an empty attribute. Write
    // both onto the native input it renders instead.
    afterRenderEffect({
      write: () => {
        const host = this._checkboxRef().nativeElement as HTMLElement;
        const nativeInput = host.querySelector('input[type="checkbox"]');
        if (!nativeInput) return;
        if (this.hasError()) {
          nativeInput.setAttribute('aria-invalid', 'true');
          nativeInput.setAttribute('aria-describedby', this.errorId());
        } else {
          nativeInput.removeAttribute('aria-invalid');
          nativeInput.removeAttribute('aria-describedby');
        }
      },
    });
  }

  onChange(event: MatCheckboxChange): void {
    this._formChecked.set(event.checked);
    this._onChange(event.checked);
  }

  onTouched(): void {
    this._onTouched();
  }

  writeValue(v: boolean): void {
    this._formChecked.set(!!v);
  }

  registerOnChange(fn: (v: boolean) => void): void {
    this._onChange = fn;
  }

  registerOnTouched(fn: () => void): void {
    this._onTouched = fn;
  }

  setDisabledState(isDisabled: boolean): void {
    this._formDisabled.set(isDisabled);
  }
}
