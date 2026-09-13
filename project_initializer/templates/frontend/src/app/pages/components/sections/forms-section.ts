import { ChangeDetectionStrategy, Component } from '@angular/core';
import { FormControl, ReactiveFormsModule, Validators } from '@angular/forms';

import { ButtonComponent } from '../../../shared/ui/button/button';
import { CheckboxComponent } from '../../../shared/ui/checkbox/checkbox';
import { FormFieldComponent } from '../../../shared/ui/form-field/form-field';
import { InputComponent } from '../../../shared/ui/input/input';
import { RadioComponent } from '../../../shared/ui/radio/radio';
import { SelectComponent, SelectOption } from '../../../shared/ui/select/select';
import { StackComponent } from '../../../shared/ui/stack/stack';

import { ThemePreviewComponent } from '../theme-preview';

/** Keeps radio set names unique app-wide, even if the section is mounted more than once. */
let nextSectionId = 0;

/**
 * Forms group of the /components catalog: button variants and states, the input and select inside
 * a form field, and checkbox and radio controls, each under an h3 and previewed in a light and a
 * dark region.
 *
 * The page owns the `h1` and the group's `h2`; this section adds one `h3` per demo group.
 *
 * `app-theme-preview` stamps each demo twice, and each copy keeps its own state. Material links
 * radios with the same `name` across the whole app, and a `FormControl` bound to two controls does
 * not sync a change made in one of them. So the size radios take a set name, and the status and
 * country selects a form control, that belong to the root element of their stamped copy.
 *
 * The status select is required and starts empty. Its error comes from that validation, and only
 * once the control is touched, so an untouched field never renders as invalid.
 */
@Component({
  selector: 'app-forms-section',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    ReactiveFormsModule,
    ThemePreviewComponent,
    StackComponent,
    ButtonComponent,
    InputComponent,
    SelectComponent,
    RadioComponent,
    CheckboxComponent,
    FormFieldComponent,
  ],
  templateUrl: './forms-section.html',
  styleUrl: './forms-section.css',
})
export class FormsSectionComponent {
  readonly statusOptions: SelectOption[] = [
    { value: 'active', label: 'Active' },
    { value: 'inactive', label: 'Inactive' },
  ];

  readonly countryOptions: SelectOption[] = [
    { value: 'us', label: 'United States' },
    { value: 'gb', label: 'United Kingdom' },
  ];

  private readonly sectionId = `app-forms-section-${nextSectionId++}`;
  private nextCopyId = 0;
  private readonly sizeSetNames = new WeakMap<Element, string>();
  private readonly statusControls = new WeakMap<Element, FormControl<string>>();
  private readonly countryControls = new WeakMap<Element, FormControl<string>>();

  /** Radio set name for one stamped copy of the size demo, keyed by that copy's fieldset. */
  protected sizeSetName(copy: Element): string {
    let name = this.sizeSetNames.get(copy);
    if (name === undefined) {
      name = `${this.sectionId}-size-${this.nextCopyId++}`;
      this.sizeSetNames.set(copy, name);
    }
    return name;
  }

  /** Required status control for one stamped copy of the field demo. Starts empty. */
  protected statusControl(copy: Element): FormControl<string> {
    let control = this.statusControls.get(copy);
    if (control === undefined) {
      control = new FormControl('', { nonNullable: true, validators: Validators.required });
      this.statusControls.set(copy, control);
    }
    return control;
  }

  /** Error for one copy's status field: shown once the control is touched and still empty. */
  protected statusErrorText(copy: Element): string {
    const control = this.statusControl(copy);
    return control.touched && control.invalid ? 'Choose a status' : '';
  }

  /** Country control for one stamped copy of the field demo. Starts on United Kingdom. */
  protected countryControl(copy: Element): FormControl<string> {
    let control = this.countryControls.get(copy);
    if (control === undefined) {
      control = new FormControl('gb', { nonNullable: true });
      this.countryControls.set(copy, control);
    }
    return control;
  }
}
