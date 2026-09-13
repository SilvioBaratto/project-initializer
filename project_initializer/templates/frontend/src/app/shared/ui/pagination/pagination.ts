import {
  ChangeDetectionStrategy,
  Component,
  DOCUMENT,
  ElementRef,
  afterRenderEffect,
  computed,
  inject,
  input,
  output,
  viewChild,
} from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { LucideAngularModule } from 'lucide-angular';

/**
 * Most page slots (page numbers plus gaps) shown at once. With the four directional buttons the
 * widest row is 11 slots of 48px (528px); a paginator narrower than that shows the status instead.
 */
const MAX_PAGE_SLOTS = 7;

type Edge = 'start' | 'end';

function range(from: number, to: number): number[] {
  return Array.from({ length: Math.max(0, to - from + 1) }, (_, i) => from + i);
}

/**
 * Page numbers to render: every page when they fit in {@link MAX_PAGE_SLOTS}, otherwise the
 * first and last page plus a window around the current page (a gap stands in for the rest).
 */
function visiblePages(page: number, total: number): number[] {
  const count = Math.max(0, Math.floor(total));
  if (count <= MAX_PAGE_SLOTS) return range(1, count);
  const current = Math.min(Math.max(page, 1), count);
  if (current <= 4) return [...range(1, 5), count];
  if (current >= count - 3) return [1, ...range(count - 4, count)];
  return [1, current - 1, current, current + 1, count];
}

/**
 * Page navigation. Material ships `MatPaginator`, but it counts items (zero-based `pageIndex`,
 * `length`, `pageSize`) and has no numbered page buttons, so this control keeps its page-based
 * API and is built from Material buttons instead: icon buttons for first, previous, next and last
 * page, and text buttons for page numbers. The current page is a tonal button with a bold label,
 * marked `aria-current="page"`. The host is a CSS query container: while it is narrower than
 * its widest row (528px) the page numbers give way to a "Page 2 of 5" status, whatever the
 * window width. That status is also a polite live region at every width. Inline-size
 * containment sizes the host from its parent, so place it in block flow or a stretched item.
 */
@Component({
  selector: 'ui-pagination',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [MatButtonModule, LucideAngularModule],
  templateUrl: './pagination.html',
  styleUrl: './pagination.css',
})
export class PaginationComponent {
  private readonly document = inject(DOCUMENT);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);

  readonly page = input.required<number>();
  readonly total = input.required<number>();
  /** Accessible name of the navigation landmark. Give each paginator on a view its own label. */
  readonly label = input('Pagination');

  readonly pageChange = output<number>();

  readonly isFirstPage = computed(() => this.page() <= 1);
  readonly isLastPage = computed(() => this.page() >= this.total());

  /** Page numbers rendered as buttons (all pages up to seven, otherwise a window with gaps). */
  readonly pages = computed(() => visiblePages(this.page(), this.total()));

  /** Page numbers preceded by a gap in {@link pages}. */
  protected readonly gapBefore = computed(() => {
    const pages = this.pages();
    return new Set(pages.filter((p, i) => i > 0 && p - pages[i - 1] > 1));
  });

  private readonly firstButton = viewChild.required('firstButton', { read: ElementRef });
  private readonly previousButton = viewChild.required('previousButton', { read: ElementRef });
  private readonly nextButton = viewChild.required('nextButton', { read: ElementRef });
  private readonly lastButton = viewChild.required('lastButton', { read: ElementRef });

  /**
   * Edge the focused control just requested, whose buttons disable on arrival. Only set while
   * focus is inside the paginator, consumed by the next page change and cleared when focus leaves.
   */
  private pendingEdge: Edge | null = null;

  constructor() {
    // A disabled button can't hold focus. When the page reaches an edge through the button that
    // now disables, hand focus to the enabled button pointing the other way.
    afterRenderEffect(() => {
      // Read page() directly: the bound computeds don't notify for moves between inner pages.
      this.page();
      const atStart = this.isFirstPage();
      const atEnd = this.isLastPage();
      // Any page change answers the last request, so a stale edge never moves focus later.
      const edge = this.pendingEdge;
      this.pendingEdge = null;
      if (!edge || atStart === atEnd) return;
      if (edge === 'end' && atEnd) {
        this.handOffFocus([this.nextButton(), this.lastButton()], this.previousButton());
      } else if (edge === 'start' && atStart) {
        this.handOffFocus([this.firstButton(), this.previousButton()], this.nextButton());
      }
    });
  }

  onFirst(): void {
    if (this.isFirstPage()) return;
    this.expectEdge('start');
    this.pageChange.emit(1);
  }

  onPrev(): void {
    if (this.isFirstPage()) return;
    this.expectEdge(this.page() - 1 <= 1 ? 'start' : null);
    this.pageChange.emit(this.page() - 1);
  }

  onNext(): void {
    if (this.isLastPage()) return;
    this.expectEdge(this.page() + 1 >= this.total() ? 'end' : null);
    this.pageChange.emit(this.page() + 1);
  }

  onLast(): void {
    if (this.isLastPage()) return;
    this.expectEdge('end');
    this.pageChange.emit(this.total());
  }

  onPage(p: number): void {
    if (p === this.page()) return;
    this.pendingEdge = null;
    this.pageChange.emit(p);
  }

  /**
   * Focus leaving the paginator cancels a pending hand-off. The blur a button fires when it
   * disables under focus has no related target and a disabled source, so that one keeps it.
   */
  protected onFocusOut(event: FocusEvent): void {
    const to = event.relatedTarget;
    const from = event.target;
    const droppedByDisable = to === null && from instanceof HTMLButtonElement && from.disabled;
    const stayedInside = to instanceof Node && this.host.nativeElement.contains(to);
    if (!droppedByDisable && !stayedInside) this.pendingEdge = null;
  }

  /** Only a control that holds focus can lose it when it disables, so record the edge only then. */
  private expectEdge(edge: Edge | null): void {
    const focusInside = this.host.nativeElement.contains(this.document.activeElement);
    this.pendingEdge = edge && focusInside ? edge : null;
  }

  private handOffFocus(disabled: ElementRef<HTMLElement>[], target: ElementRef<HTMLElement>): void {
    const active = this.document.activeElement;
    const focusLost =
      !active ||
      active === this.document.body ||
      disabled.some((ref) => ref.nativeElement === active);
    if (focusLost) target.nativeElement.focus();
  }
}
