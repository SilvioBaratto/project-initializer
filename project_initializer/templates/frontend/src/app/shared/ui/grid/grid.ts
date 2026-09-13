import {
  ChangeDetectionStrategy,
  Component,
  ViewEncapsulation,
  booleanAttribute,
  computed,
  input,
} from '@angular/core';

/** Px per `gap` step: the Material 3 4px spacing grid. */
export const GRID_GAP_STEP_PX = 4;

/**
 * Material 3 layout grid for peer content such as cards or stat tiles.
 *
 * Columns follow the M3 window size classes: 4 below 600px, 8 from 600px (medium and expanded share 8),
 * 12 from 1200px. Every projected cell spans 4 columns, so a row holds 1 cell below 600px, 2 from 600px
 * and 3 from 1200px. To widen one cell, set `--app-grid-cell-span` on the cell (for example 8 from 600px);
 * a value set on the cell beats the inherited 4 whatever the selector specificity. The default span rule has
 * zero specificity, so a consumer `grid-column` rule on a cell also wins. Keep a span at or below the column
 * count at that width (4 below 600px), or the grid adds implicit columns.
 *
 * The gutter is 16px below 600px and 24px from 600px, matching the M3 margins and pane spacers.
 *
 * With `containerQuery`, the same 600px / 1200px boundaries apply to the grid's own inline size instead
 * of the window, for grids inside panes, sidebars or previews narrower than the window. The grid then
 * needs a definite inline size from its parent (block flow or a stretched item).
 *
 * Purely structural: no landmark, role, heading or color of its own.
 *
 * Styles use `ViewEncapsulation.None` because the cells are projected content, which emulated styles
 * cannot reach; every selector in `grid.css` is scoped under the `app-grid` host class.
 */
@Component({
  selector: 'app-grid',
  changeDetection: ChangeDetectionStrategy.OnPush,
  encapsulation: ViewEncapsulation.None,
  templateUrl: './grid.html',
  styleUrl: './grid.css',
  host: {
    class: 'app-grid',
    '[class.app-grid--container-query]': 'containerQuery()',
  },
})
export class GridComponent {
  /**
   * Fixed gutter in 4px steps (`3` → 12px) at every width. Leave unset for the M3 responsive gutter
   * (16px below 600px, 24px from 600px). Negative or non-finite values fall back to the M3 gutter.
   */
  readonly gap = input<number | undefined>(undefined);

  /**
   * Size the columns by the grid's own inline size (CSS container query) instead of the window.
   * Accepts the bare attribute (`<app-grid containerQuery>`).
   */
  readonly containerQuery = input(false, { transform: booleanAttribute });

  /** Inline `gap` that replaces the M3 gutter, or `null` to keep it. */
  readonly gapOverride = computed<string | null>(() => {
    const steps = this.gap();
    if (steps === undefined || steps === null || !Number.isFinite(steps) || steps < 0) {
      return null;
    }
    return `${steps * GRID_GAP_STEP_PX}px`;
  });
}
