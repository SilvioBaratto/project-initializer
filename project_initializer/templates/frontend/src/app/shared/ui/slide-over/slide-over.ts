import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  afterEveryRender,
  computed,
  inject,
  input,
  output,
} from '@angular/core';
import { FocusTrapDirective } from '../focus-trap/focus-trap.directive';

export type SlideOverSide = 'left' | 'right';

const PANEL_BASE =
  'fixed top-0 z-50 h-dvh w-80 max-w-full flex flex-col ' +
  'bg-surface-raised dark:bg-surface-raised border-border dark:border-border shadow-xl pt-safe pb-safe';

const SLIDE_CLASSES: Record<SlideOverSide, string> = {
  left:  'left-0 animate-slide-in border-r',
  right: 'right-0 border-l',
};

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
  selector: 'app-slide-over',
  templateUrl: './slide-over.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [FocusTrapDirective],
  host: { '(document:keydown)': 'onDocumentKeydown($event)' },
})
export class SlideOverComponent {
  readonly open = input(false);
  readonly side = input<SlideOverSide>('right');
  readonly label = input('Panel');
  readonly closed = output<void>();

  private readonly el = inject(ElementRef<HTMLElement>);

  readonly allPanelClasses = computed(() => `${PANEL_BASE} ${SLIDE_CLASSES[this.side()]}`);

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
