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
import { MatSelect, MatSelectChange, MatSelectModule } from '@angular/material/select';

import { FORM_FIELD_CONTEXT } from '../form-field/form-field-context';

export interface SelectOption {
  value: string;
  label: string;
}

let nextUniqueId = 0;

/**
 * Material 3 outlined select: `<mat-form-field appearance="outline">` around a
 * `<mat-select>` with one `<mat-option>` per entry of `options()`, and
 * ControlValueAccessor support so it works with `[formControl]` / `ngModel` as well
 * as the plain `disabled` input.
 *
 * `<mat-select>` is an ARIA combobox: it opens a listbox on click, Enter or Space,
 * moves through options with the arrow keys (also while closed), supports typeahead,
 * and Esc closes the panel with focus staying on the combobox.
 *
 * Inside `<app-form-field>` it reads FORM_FIELD_CONTEXT and renders the label
 * (`<mat-label>`), help text (`<mat-hint [id]="ctx.helpId">`) and error text
 * (`<mat-error [id]="ctx.errorId">`) inside its own form field, because Material
 * only discovers a `mat-select` declared in the same template as the form field.
 * The combobox takes `id()` when given, otherwise `ctx.controlId`.
 *
 * Labelling: MatSelect sets `aria-labelledby` to the form field's `<label>` id and
 * never gives that label a `for` attribute (a combobox is not a labelable element).
 * Without a context, name the field with `aria-label`, or with `aria-labelledby`
 * pointing at a visible label; a sibling `<label for>` alone does not name it.
 *
 * Error state follows `errorText` (own input first, then the context), not form
 * validity: a non-empty message turns the field into its error state, shows the
 * message and makes MatSelect bind `aria-invalid="true"`. Material's form field
 * points `aria-describedby` at the visible hint or error and removes the attribute
 * when neither is shown.
 */
@Component({
  selector: 'app-select',
  imports: [MatSelectModule],
  templateUrl: './select.html',
  styleUrl: './select.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => SelectComponent),
      multi: true,
    },
  ],
  host: {
    // `id` and the ARIA naming attributes belong on the combobox. Static attributes
    // would otherwise also stay on this host: a duplicate id, and a name on a generic element.
    '[attr.id]': 'null',
    '[attr.aria-label]': 'null',
    '[attr.aria-labelledby]': 'null',
  },
})
export class SelectComponent implements ControlValueAccessor {
  private readonly context = inject(FORM_FIELD_CONTEXT, { optional: true });

  /** Id of the combobox. Falls back to the form field context's controlId. */
  readonly id = input('');
  readonly errorText = input('');
  readonly disabled = input(false);
  readonly options = input<SelectOption[]>([]);
  /** Accessible name for a field with no visible label. */
  readonly ariaLabel = input('', { alias: 'aria-label' });
  /** Space-separated ids of visible elements that name the field. */
  readonly ariaLabelledby = input('', { alias: 'aria-labelledby' });

  readonly value = signal('');
  private readonly _formDisabled = signal(false);
  private readonly _uniqueId = `app-select-${nextUniqueId++}`;

  readonly isDisabled = computed(() => this._formDisabled() || this.disabled());

  readonly label = computed(() => this.context?.label() ?? '');
  readonly helpText = computed(() => this.context?.helpText() ?? '');
  readonly resolvedErrorText = computed(
    () => this.errorText() || this.context?.errorText() || '',
  );
  readonly hasError = computed(() => this.resolvedErrorText() !== '');

  /** Empty string lets MatSelect keep its own generated unique id. */
  readonly selectId = computed(() => this.id() || this.context?.controlId || '');
  readonly hintId = this.context?.helpId ?? `${this._uniqueId}-hint`;
  readonly errorId = this.context?.errorId ?? `${this._uniqueId}-error`;

  /** Drives Material's error state (outline, label, arrow and mat-error) from errorText. */
  readonly errorStateMatcher: ErrorStateMatcher = {
    isErrorState: () => this.hasError(),
  };

  private readonly matSelect = viewChild(MatSelect);

  private _onChange: (v: string) => void = () => {};
  private _onTouched: () => void = () => {};

  constructor() {
    // MatSelect re-runs its ErrorStateMatcher in ngDoCheck only when a forms directive
    // sits on the mat-select itself, which never happens here (the forms directive is on
    // <app-select>). So hand it the matcher and re-evaluate whenever errorText flips.
    // The matcher is assigned here rather than bound in the template because this
    // effect's first run precedes the template's input bindings: bound, the first
    // evaluation would use Material's default matcher and miss an initial errorText.
    // Running before the template also settles errorState within the same change
    // detection pass, so aria-invalid and the form field's error slot render at once.
    effect(() => {
      this.hasError();
      const select = this.matSelect();
      if (!select) return;
      untracked(() => {
        select.errorStateMatcher = this.errorStateMatcher;
        select.updateErrorState();
      });
    });
  }

  onSelectionChange(event: MatSelectChange<string>): void {
    const v = event.value ?? '';
    this.value.set(v);
    this._onChange(v);
  }

  /** Mirrors MatSelect: closing the panel marks the control touched. */
  onOpenedChange(open: boolean): void {
    if (!open) this.onTouched();
  }

  /** Focus moving into the open panel is not a blur of the field. */
  onBlur(panelOpen: boolean): void {
    if (!panelOpen) this.onTouched();
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
