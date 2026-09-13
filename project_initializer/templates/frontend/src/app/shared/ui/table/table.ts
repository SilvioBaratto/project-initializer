import {
  ChangeDetectionStrategy,
  Component,
  DOCUMENT,
  DestroyRef,
  ElementRef,
  afterNextRender,
  afterRenderEffect,
  computed,
  inject,
  input,
  isDevMode,
  signal,
  viewChild,
} from '@angular/core';
import { MatTableModule } from '@angular/material/table';

/** One column of the table: `key` reads the row value, `header` is the visible column name. */
export interface TableColumn {
  key: string;
  header: string;
}

/**
 * Responsive, read-only data table built on Angular Material's `<table mat-table>`.
 *
 * - From 600px (M3 medium and wider) a native `mat-table` renders, so column headers keep real
 *   `<thead>`/`<th scope="col">` semantics.
 * - Below 600px (M3 compact) each row reflows into a stacked card: a `<dl>` of header / value pairs.
 *
 * Both layouts sit inside one scroll region (`overflow-x: auto`, `overscroll-behavior: contain`).
 * While its content is wider than the region, the region is a tab stop (`tabindex="0"`) so keyboard
 * users can scroll it. A table that fits adds no tab stop and no landmark. The overflow is measured
 * after every content change and whenever the region or the table resizes.
 * Only one layout is displayed at a time (CSS `display: none` on the other), so assistive technology
 * never reads the rows twice.
 *
 * Always pass a specific `label` (for example "Team members"), and a different one for every table on
 * the page. The label names the table, the stacked list and, while it scrolls, the region landmark.
 * Without a label, dev mode logs a warning and a scrolling wrapper stays keyboard-scrollable but is not
 * a `region` landmark: an unnamed or generically named region would add a landmark that users can't
 * tell apart from the others.
 */
@Component({
  selector: 'ui-table',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [MatTableModule],
  templateUrl: './table.html',
  styleUrl: './table.css',
})
export class TableComponent {
  private readonly document = inject(DOCUMENT);

  /** Column definitions, in display order. */
  readonly columns = input<TableColumn[]>([]);

  /** Row records; each cell reads `row[column.key]`. */
  readonly rows = input<Record<string, unknown>[]>([]);

  /**
   * Accessible name of the table, the stacked list and the scrolling region, unique on the page.
   * Never include a role word ("table", "region"). No default: a blank label renders no landmark.
   */
  readonly label = input<string>();

  /** The trimmed label, or `null` when it is missing or blank (removes the ARIA attributes). */
  protected readonly accessibleName = computed(() => this.label()?.trim() || null);

  /** Column keys handed to `matHeaderRowDef` / `matRowDef`. */
  protected readonly columnKeys = computed(() => this.columns().map((column) => column.key));

  /**
   * Whether the region is a keyboard scroll stop: its content overflows it horizontally. A focused
   * region keeps the stop until it blurs, because removing `tabindex` would drop focus to the page.
   */
  protected readonly scrollable = signal(false);

  private readonly region = viewChild.required<ElementRef<HTMLElement>>('region');

  constructor() {
    // New rows or columns change the content width: measure once they are in the DOM.
    afterRenderEffect({
      read: () => {
        this.rows();
        this.columns();
        this.measure();
      },
    });

    const destroyRef = inject(DestroyRef);
    afterNextRender({
      read: () => {
        if (isDevMode() && !this.accessibleName()) {
          console.warn(
            'ui-table: set a specific `label` (for example "Team members") so the table, its stacked ' +
              'list and its scroll region have an accessible name.',
          );
        }
        // A window resize, the 600px layout switch or resized text changes the widths without a render.
        if (typeof ResizeObserver === 'undefined') return;
        const region = this.region().nativeElement;
        const observer = new ResizeObserver(() => this.measure());
        observer.observe(region);
        const table = region.querySelector('table');
        if (table) observer.observe(table);
        destroyRef.onDestroy(() => observer.disconnect());
      },
    });
  }

  /** A region that kept its tab stop only because it was focused gives it up once focus leaves. */
  protected onRegionBlur(): void {
    this.scrollable.set(this.overflows());
  }

  private measure(): void {
    const focused = this.region().nativeElement === this.document.activeElement;
    this.scrollable.set(this.overflows() || (focused && this.scrollable()));
  }

  private overflows(): boolean {
    const region = this.region().nativeElement;
    return region.scrollWidth > region.clientWidth;
  }
}
