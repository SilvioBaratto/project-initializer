import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  afterEveryRender,
  inject,
  input,
  output,
} from '@angular/core';
import { FocusTrapDirective } from '../focus-trap/focus-trap.directive';

/** Inerts all body-level siblings of `host`'s top-level ancestor. */
function setBodySiblingsInert(host: HTMLElement, inert: boolean): void {
  let node: HTMLElement = host;
  while (node.parentElement && node.parentElement !== document.body) {
    node = node.parentElement;
  }
  if (node.parentElement !== document.body) return;
  Array.from(document.body.children).forEach((sibling) => {
    if (sibling === node) return;
    inert ? sibling.setAttribute('inert', '') : sibling.removeAttribute('inert');
  });
}

@Component({
  selector: 'app-modal',
  templateUrl: './modal.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [FocusTrapDirective],
  host: { '(document:keydown)': 'onDocumentKeydown($event)' },
})
export class ModalComponent {
  readonly open = input(false);
  readonly label = input('Dialog');
  readonly closed = output<void>();

  private readonly el = inject(ElementRef<HTMLElement>);

  constructor() {
    afterEveryRender(() => setBodySiblingsInert(this.el.nativeElement, this.open()));
  }

  handleClose(): void {
    this.closed.emit();
  }

  onDocumentKeydown(event: KeyboardEvent): void {
    if (this.open() && event.key === 'Escape' && !event.defaultPrevented) {
      this.handleClose();
    }
  }
}
