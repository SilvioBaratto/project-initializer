import {
  ChangeDetectionStrategy,
  Component,
  computed,
  forwardRef,
  input,
  signal,
} from '@angular/core';
import { ControlValueAccessor, NG_VALUE_ACCESSOR } from '@angular/forms';

const BASE =
  'w-full min-h-11 rounded-md border border-border bg-surface-raised px-3 py-2 text-text ' +
  'placeholder:text-text-tertiary focus:outline-none focus:ring-2 focus:ring-primary ' +
  'disabled:cursor-not-allowed disabled:opacity-50 transition-colors';

const ERROR_BORDER = 'border-danger focus:ring-danger';

@Component({
  selector: 'app-input',
  changeDetection: ChangeDetectionStrategy.OnPush,
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => InputComponent),
      multi: true,
    },
  ],
  template: `
    <input
      [id]="id()"
      [class]="classes()"
      [disabled]="isDisabled()"
      [attr.aria-invalid]="errorText() ? 'true' : null"
      [value]="value()"
      (input)="onInput($event)"
      (blur)="onTouched()"
    />
  `,
})
export class InputComponent implements ControlValueAccessor {
  readonly id = input('');
  readonly errorText = input('');
  readonly disabled = input(false);

  readonly value = signal('');
  private readonly _formDisabled = signal(false);

  readonly isDisabled = computed(() => this._formDisabled() || this.disabled());

  readonly classes = computed(() =>
    this.errorText() ? `${BASE} ${ERROR_BORDER}` : BASE,
  );

  private _onChange: (v: string) => void = () => {};
  private _onTouched: () => void = () => {};

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
