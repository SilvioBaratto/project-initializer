import { booleanAttribute, ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

/** Main axis: `'row'` lays items out in the inline direction, `'col'` stacks them in the block direction. */
export type StackDirection = 'row' | 'col';

/** Cross-axis alignment of the items, named after the matching CSS box-alignment keywords. */
export type StackAlign = 'start' | 'center' | 'end' | 'stretch' | 'baseline';

/** Main-axis distribution of the items, named after the matching CSS box-alignment keywords. */
export type StackJustify = 'start' | 'center' | 'end' | 'space-between' | 'space-around' | 'space-evenly';

/** Px per `gap` step: the Material 3 4px spacing grid. */
export const STACK_GAP_STEP_PX = 4;

/** Gap in steps when `gap` is unset, negative or not a finite number (4 steps = 16px). */
export const STACK_DEFAULT_GAP = 4;

const ALIGN_VALUES: readonly string[] = ['start', 'center', 'end', 'stretch', 'baseline'] satisfies StackAlign[];

const JUSTIFY_VALUES: readonly string[] = [
  'start',
  'center',
  'end',
  'space-between',
  'space-around',
  'space-evenly',
] satisfies StackJustify[];

function isStackAlign(value: string): value is StackAlign {
  return ALIGN_VALUES.includes(value);
}

function isStackJustify(value: string): value is StackJustify {
  return JUSTIFY_VALUES.includes(value);
}

/**
 * One-dimensional layout primitive: lays its projected items out in a row or a column with a gap on
 * the Material 3 4px spacing grid.
 *
 * The host element is the layout container, so projected items are its direct children. Every input is
 * reflected on the host (data attributes, plus the `--app-stack-gap` custom property) and mapped to
 * layout rules in `stack.css`, so layout stays in CSS and follows the writing direction in RTL.
 *
 * Purely structural: no landmark, role, heading or color of its own.
 */
@Component({
  selector: 'app-stack',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './stack.html',
  styleUrl: './stack.css',
  host: {
    '[attr.data-direction]': 'resolvedDirection()',
    '[attr.data-wrap]': "wrap() ? 'wrap' : 'nowrap'",
    '[attr.data-align]': 'resolvedAlign()',
    '[attr.data-justify]': 'resolvedJustify()',
    '[style.--app-stack-gap]': 'gapSize()',
  },
})
export class StackComponent {
  /** `'row'` or `'col'` (default). Unknown values fall back to `'col'`. */
  readonly direction = input<StackDirection>('col');

  /**
   * Space between items in 4px steps (`2` → 8px, `3` → 12px). Defaults to 4 (16px). Fractional steps
   * round to the nearest whole step so gaps stay on the 4px grid; negative or non-finite values use the default.
   */
  readonly gap = input<number>(STACK_DEFAULT_GAP);

  /** Let items wrap onto additional lines instead of overflowing. Accepts the bare attribute (`<app-stack wrap>`). */
  readonly wrap = input(false, { transform: booleanAttribute });

  /** Cross-axis alignment (default `'stretch'`). Unknown values fall back to `'stretch'`. */
  readonly align = input<StackAlign>('stretch');

  /** Main-axis distribution (default `'start'`). Unknown values fall back to `'start'`. */
  readonly justify = input<StackJustify>('start');

  /** The direction actually applied, after the `'col'` fallback. */
  readonly resolvedDirection = computed<StackDirection>(() => (this.direction() === 'row' ? 'row' : 'col'));

  /** The alignment actually applied, after the `'stretch'` fallback. */
  readonly resolvedAlign = computed<StackAlign>(() => {
    const value = this.align();
    return isStackAlign(value) ? value : 'stretch';
  });

  /** The distribution actually applied, after the `'start'` fallback. */
  readonly resolvedJustify = computed<StackJustify>(() => {
    const value = this.justify();
    return isStackJustify(value) ? value : 'start';
  });

  /** Gap in px written to `--app-stack-gap`: whole 4px steps. */
  readonly gapSize = computed<string>(() => {
    const steps = this.gap();
    const valid = Number.isFinite(steps) && steps >= 0 ? steps : STACK_DEFAULT_GAP;
    return `${Math.round(valid) * STACK_GAP_STEP_PX}px`;
  });
}
