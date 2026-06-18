import {
  ChangeDetectionStrategy,
  Component,
  OnDestroy,
  input,
  signal,
} from '@angular/core';

let nextId = 0;

/** Tooltip bubble with hover/focus/touch/Escape wiring on the host element.
 *  Wrap the trigger with <ui-tooltip>:
 *    <ui-tooltip text="Save"><button>Save</button></ui-tooltip>
 */
@Component({
  selector: 'ui-tooltip',
  templateUrl: './tooltip.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    'class': 'relative inline-block',
    '(mouseenter)': 'show()',
    '(mouseleave)': 'hide()',
    '(focusin)': 'show()',
    '(focusout)': 'hide()',
    '(touchstart)': 'onTouchStart($event)',
    '(click)': 'onClick()',
    '(document:keydown)': 'onDocumentKeydown($event)',
  },
})
export class TooltipComponent implements OnDestroy {
  readonly text = input('');

  readonly visible = signal(false);

  // Plain string field — used as [id] binding on the tooltip bubble and [attr.aria-describedby].
  readonly tooltipId = `ui-tooltip-${nextId++}`;

  show(): void {
    this.visible.set(true);
  }

  hide(): void {
    this.visible.set(false);
  }

  // Touch tap fallback: toggles visibility; preventDefault stops the
  // synthetic mouse events that follow touchstart on iOS/Android.
  onTouchStart(event: Event): void {
    event.preventDefault();
    this.visible.update((v) => !v);
  }

  // Secondary click fallback for devices that emit only click (not touchstart).
  // On real touch devices touchstart prevents this from firing.
  onClick(): void {
    this.visible.set(true);
  }

  onDocumentKeydown(event: KeyboardEvent): void {
    if (event.key === 'Escape') {
      this.hide();
    }
  }

  ngOnDestroy(): void {
    this.visible.set(false);
  }
}
