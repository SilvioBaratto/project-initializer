import { AriaDescriber, FocusMonitor } from '@angular/cdk/a11y';
import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  Injectable,
  inject,
  isDevMode,
} from '@angular/core';
import { MatTooltip } from '@angular/material/tooltip';

/**
 * Elements that can take focus; the first one inside <ui-tooltip> is its trigger.
 * Natively disabled controls are skipped: they take no focus, so keyboard users could never
 * reach the text. `aria-disabled="true"` controls stay eligible, because they keep focus, and a
 * Material button with `disabledInteractive` is how a tooltip explains an unavailable action.
 */
const TRIGGER_SELECTOR = [
  'a[href]',
  'button:not(:disabled)',
  'input:not(:disabled):not([type="hidden"])',
  'select:not(:disabled)',
  'textarea:not(:disabled)',
  '[contenteditable="true"]',
  '[tabindex]:not([tabindex="-1"]):not(:disabled)',
].join(', ');

/**
 * MatTooltip describes the element it sits on, and on <ui-tooltip> that is a
 * wrapper nobody can focus, so a screen reader would never read the text.
 * Provided on the wrapper, this describer moves that description onto the
 * first focusable element projected inside it. With nothing focusable inside,
 * it describes nothing and warns in dev mode. Descriptions requested for any
 * other element (a tooltip nested in the projected content) pass through.
 */
@Injectable()
class ProjectedTriggerDescriber {
  private readonly describer = inject(AriaDescriber, { skipSelf: true });
  private readonly host: HTMLElement = inject(ElementRef).nativeElement;
  private describedTrigger: Element | null = null;

  describe(element: Element, message: string, role?: string): void {
    if (element === this.host) {
      this.describedTrigger = this.host.querySelector(TRIGGER_SELECTOR);
      if (!this.describedTrigger) {
        if (isDevMode()) {
          console.warn(
            'ui-tooltip: nothing inside can take focus, so keyboard and screen reader users never get the text. ' +
              'Put uiTooltip on the focusable element; to explain an unavailable action, use a button with disabledInteractive.',
          );
        }
        return;
      }
      element = this.describedTrigger;
    }
    this.describer.describe(element, message, role);
  }

  removeDescription(element: Element, message: string, role?: string): void {
    if (element === this.host) {
      const trigger = this.describedTrigger;
      this.describedTrigger = null;
      if (!trigger) return;
      element = trigger;
    }
    this.describer.removeDescription(element, message, role);
  }
}

/**
 * Plain M3 tooltip (Angular Material `MatTooltip`) for a trigger projected
 * inside the wrapper:
 *   <ui-tooltip text="Save changes"><button matButton>Save</button></ui-tooltip>
 *
 * - Hover shows it and pointer exit hides it; on iOS and Android a 500ms
 *   touch & hold shows it (MatTooltip `touchGestures: 'auto'`).
 * - Keyboard focus on the projected trigger shows it; focus from a click or a
 *   plain `focus()` call from code does not, exactly as `matTooltip` (the same
 *   FocusMonitor origin rules). Focus leaving the wrapper hides it; focus moving
 *   between elements inside the wrapper does not.
 * - Escape hides an open tooltip (MatTooltip overlay keydown stream).
 * - `aria-describedby` lands on the first focusable projected element. A natively
 *   disabled control never qualifies, since it takes no focus. With nothing
 *   focusable inside, nothing is described and a dev-mode warning is logged.
 *
 * Limits: the description is attached when `text` is set or changes, so a
 * trigger rendered later (inside `@if`), swapped out or disabled afterwards is
 * not re-targeted, and the wrapper box is the positioning origin. Prefer
 * `uiTooltip` on the focusable trigger itself (see tooltip.directive.ts) for new
 * code. Tooltip text supplements a label and is never an icon button's only
 * name. To explain why an action is unavailable, keep the button focusable with
 * `disabledInteractive` instead of wrapping a disabled one.
 */
@Component({
  selector: 'ui-tooltip',
  templateUrl: './tooltip.html',
  styleUrl: './tooltip.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
  hostDirectives: [
    {
      directive: MatTooltip,
      inputs: ['matTooltip: text', 'matTooltipPosition: position'],
    },
  ],
  providers: [{ provide: AriaDescriber, useClass: ProjectedTriggerDescriber }],
})
export class TooltipComponent {
  private readonly tooltip = inject(MatTooltip);

  constructor() {
    // MatTooltip watches focus on its host through FocusMonitor, but without
    // checkChildren, and the wrapper never takes focus itself. Monitoring the
    // same host with checkChildren switches that shared entry to the whole
    // subtree (FocusMonitor.monitor reuses the cached entry), so MatTooltip's
    // own subscription shows on a 'keyboard' origin from the projected trigger
    // and hides on blur out of the wrapper. MatTooltip stops monitoring on destroy.
    inject(FocusMonitor).monitor(inject(ElementRef), true);
  }

  show(): void {
    this.tooltip.show();
  }

  hide(): void {
    this.tooltip.hide();
  }
}
