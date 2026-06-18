import {
  ChangeDetectionStrategy,
  Component,
  computed,
  forwardRef,
  input,
  signal,
} from '@angular/core';
import { ControlValueAccessor, NG_VALUE_ACCESSOR } from '@angular/forms';

const LABEL_BASE =
  'inline-flex items-center gap-3 min-h-[44px] cursor-pointer select-none ' +
  'text-sm text-text disabled:cursor-not-allowed';

const INPUT_BASE =
  'size-4 shrink-0 rounded border border-border bg-surface-raised accent-primary ' +
  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary ' +
  'disabled:cursor-not-allowed disabled:opacity-50 transition-colors';

const INPUT_ERROR = 'border-danger accent-danger focus-visible:ring-danger';

@Component({
  selector: 'app-checkbox',
  changeDetection: ChangeDetectionStrategy.OnPush,
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => CheckboxComponent),
      multi: true,
    },
  ],
  template: `
    <label [class]="labelClasses()">
      <input
        type="checkbox"
        [id]="id()"
        [class]="inputClasses()"
        [checked]="isChecked()"
        [disabled]="isDisabled()"
        [attr.aria-invalid]="errorText() ? 'true' : null"
        (change)="onChange($event)"
        (blur)="onTouched()"
      />
      @if (label()) {
        <span>{{ label() }}</span>
      }
    </label>
    @if (errorText()) {
      <span class="mt-1 text-sm text-danger" role="alert">{{ errorText() }}</span>
    }
  `,
})
export class CheckboxComponent implements ControlValueAccessor {
  readonly id = input('');
  readonly label = input('');
  readonly errorText = input('');
  readonly disabled = input(false);
  readonly checked = input(false);

  // CVA override: null means "use the checked input", boolean means "CVA controls it"
  private readonly _formChecked = signal<boolean | null>(null);
  private readonly _formDisabled = signal(false);

  readonly isChecked = computed(() => this._formChecked() ?? this.checked());
  readonly isDisabled = computed(() => this._formDisabled() || this.disabled());

  readonly labelClasses = computed(() =>
    this.isDisabled() ? `${LABEL_BASE} opacity-50` : LABEL_BASE,
  );

  readonly inputClasses = computed(() =>
    this.errorText() ? `${INPUT_BASE} ${INPUT_ERROR}` : INPUT_BASE,
  );

  private _onChange: (v: boolean) => void = () => {};
  private _onTouched: () => void = () => {};

  onChange(event: Event): void {
    const v = (event.target as HTMLInputElement).checked;
    this._formChecked.set(v);
    this._onChange(v);
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
