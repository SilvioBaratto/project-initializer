import {
  AfterViewChecked,
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  inject,
  input,
} from '@angular/core';

let _idCounter = 0;

@Component({
  selector: 'app-form-field',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="flex flex-col gap-1.5">
      <label [attr.for]="fieldId" class="text-sm font-medium text-text">{{ label() }}</label>
      <ng-content />
      @if (errorText()) {
        <span [id]="errorId" class="text-sm text-danger" role="alert">{{ errorText() }}</span>
      } @else if (helpText()) {
        <span [id]="helpId" class="text-sm text-text-secondary">{{ helpText() }}</span>
      }
    </div>
  `,
})
export class FormFieldComponent implements AfterViewChecked {
  private readonly el = inject(ElementRef<HTMLElement>);

  readonly label = input('');
  readonly helpText = input('');
  readonly errorText = input('');

  readonly fieldId: string;
  readonly errorId: string;
  readonly helpId: string;

  constructor() {
    const n = ++_idCounter;
    this.fieldId = `ff-ctrl-${n}`;
    this.errorId = `ff-error-${n}`;
    this.helpId = `ff-help-${n}`;
  }

  ngAfterViewChecked(): void {
    const ctrl = this.el.nativeElement.querySelector(
      'input, select, textarea',
    ) as HTMLElement | null;
    if (!ctrl) return;
    this.applyId(ctrl);
    this.applyInvalid(ctrl);
    this.applyDescribedBy(ctrl);
  }

  // Assigns the generated fieldId to the control so label[for] resolves.
  // Only writes when absent; respects an explicit id set by the host template.
  private applyId(ctrl: HTMLElement): void {
    if (!ctrl.id) ctrl.id = this.fieldId;
  }

  private applyInvalid(ctrl: HTMLElement): void {
    if (this.errorText()) ctrl.setAttribute('aria-invalid', 'true');
    else ctrl.removeAttribute('aria-invalid');
  }

  private applyDescribedBy(ctrl: HTMLElement): void {
    if (this.errorText()) ctrl.setAttribute('aria-describedby', this.errorId);
    else if (this.helpText()) ctrl.setAttribute('aria-describedby', this.helpId);
    else ctrl.removeAttribute('aria-describedby');
  }
}
