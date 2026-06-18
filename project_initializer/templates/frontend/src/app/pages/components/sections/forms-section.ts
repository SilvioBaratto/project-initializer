import { ChangeDetectionStrategy, Component } from '@angular/core';
import { ReactiveFormsModule } from '@angular/forms';

import { ButtonComponent } from '../../../shared/ui/button/button';
import { InputComponent } from '../../../shared/ui/input/input';
import { SelectComponent } from '../../../shared/ui/select/select';
import { RadioComponent } from '../../../shared/ui/radio/radio';
import { CheckboxComponent } from '../../../shared/ui/checkbox/checkbox';
import { FormFieldComponent } from '../../../shared/ui/form-field/form-field';
import { StackComponent } from '../../../shared/ui/stack/stack';

import { ThemePreviewComponent } from '../theme-preview';

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
  template: `
    <app-theme-preview label="Button variants">
      <app-stack direction="row" [gap]="2" align="center">
        <app-button variant="primary">Primary</app-button>
        <app-button variant="secondary">Secondary</app-button>
        <app-button variant="ghost">Ghost</app-button>
        <app-button variant="danger">Danger</app-button>
        <app-button [loading]="true">Loading</app-button>
        <app-button [disabled]="true">Disabled</app-button>
      </app-stack>
    </app-theme-preview>

    <app-theme-preview label="Input / Select / Form field">
      <app-stack [gap]="3">
        <app-form-field label="Name" helpText="Enter your full name">
          <app-input />
        </app-form-field>
        <app-form-field label="Status" errorText="Required field">
          <app-select [options]="statusOptions" />
        </app-form-field>
        <app-form-field label="Country">
          <app-select [options]="countryOptions" />
        </app-form-field>
      </app-stack>
    </app-theme-preview>

    <app-theme-preview label="Checkbox / Radio">
      <app-stack [gap]="2">
        <app-checkbox label="Accept terms" />
        <app-checkbox label="Subscribe to newsletter" [checked]="true" />
        <app-radio name="size-demo" value="sm" label="Small" />
        <app-radio name="size-demo" value="lg" label="Large" [checked]="true" />
      </app-stack>
    </app-theme-preview>
  `,
})
export class FormsSectionComponent {
  readonly statusOptions = [
    { value: 'active', label: 'Active' },
    { value: 'inactive', label: 'Inactive' },
  ];

  readonly countryOptions = [
    { value: 'us', label: 'United States' },
    { value: 'gb', label: 'United Kingdom' },
  ];
}
