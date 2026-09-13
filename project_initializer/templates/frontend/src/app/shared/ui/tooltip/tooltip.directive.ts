import { Directive } from '@angular/core';
import { MatTooltip } from '@angular/material/tooltip';

/**
 * Plain M3 tooltip (Angular Material `MatTooltip`) on the element that carries
 * it. Put it on the focusable trigger itself, so `aria-describedby` lands where
 * focus goes:
 *   <button matIconButton aria-label="Delete draft" uiTooltip="Delete draft">…</button>
 *
 * Shows on hover and on keyboard focus (not on focus from a click or from a
 * plain `focus()` call in code), after a 500ms touch & hold on iOS and Android,
 * and hides on pointer exit, blur and
 * Escape. The text supplements a visible or aria label and is never the only
 * name of an icon button. Don't use it on a disabled button: it gets no pointer
 * events or focus, so the tooltip never shows.
 */
@Directive({
  selector: '[uiTooltip]',
  hostDirectives: [
    {
      directive: MatTooltip,
      inputs: [
        'matTooltip: uiTooltip',
        'matTooltipPosition: uiTooltipPosition',
        'matTooltipDisabled: uiTooltipDisabled',
      ],
    },
  ],
})
export class TooltipDirective {}
