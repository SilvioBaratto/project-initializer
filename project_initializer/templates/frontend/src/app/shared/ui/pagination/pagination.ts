import { ChangeDetectionStrategy, Component, computed, input, output } from '@angular/core';
import { LucideAngularModule } from 'lucide-angular';

const PAGE_BTN =
  'inline-flex items-center justify-center min-h-11 min-w-11 rounded-md text-sm font-medium transition-colors' +
  ' focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2' +
  ' dark:focus-visible:ring-offset-surface disabled:opacity-50 disabled:cursor-not-allowed';

const PAGE_ACTIVE =
  `${PAGE_BTN} bg-primary text-white`;

const PAGE_INACTIVE =
  `${PAGE_BTN} text-text hover:bg-surface-inset dark:text-text dark:hover:bg-surface-inset`;

@Component({
  selector: 'ui-pagination',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [LucideAngularModule],
  template: `
    <nav aria-label="Pagination">
      <ul class="flex items-center gap-1">
        <li>
          <button
            [class]="PAGE_INACTIVE"
            [disabled]="isFirstPage()"
            [attr.aria-disabled]="isFirstPage() || null"
            aria-label="Previous page"
            (click)="onPrev()"
          >
            <lucide-icon name="ChevronLeft" [size]="16" aria-hidden="true" />
          </button>
        </li>
        @for (p of pages(); track p) {
          <li>
            <button
              [class]="p === page() ? PAGE_ACTIVE : PAGE_INACTIVE"
              [attr.aria-current]="p === page() ? 'page' : null"
              [attr.aria-label]="'Page ' + p"
              (click)="onPage(p)"
            >
              {{ p }}
            </button>
          </li>
        }
        <li>
          <button
            [class]="PAGE_INACTIVE"
            [disabled]="isLastPage()"
            [attr.aria-disabled]="isLastPage() || null"
            aria-label="Next page"
            (click)="onNext()"
          >
            <lucide-icon name="ChevronRight" [size]="16" aria-hidden="true" />
          </button>
        </li>
      </ul>
    </nav>
  `,
})
export class PaginationComponent {
  protected readonly PAGE_INACTIVE = PAGE_INACTIVE;
  protected readonly PAGE_ACTIVE = PAGE_ACTIVE;

  readonly page = input.required<number>();
  readonly total = input.required<number>();

  readonly pageChange = output<number>();

  readonly isFirstPage = computed(() => this.page() <= 1);
  readonly isLastPage = computed(() => this.page() >= this.total());

  readonly pages = computed(() => {
    const count = this.total();
    return Array.from({ length: count }, (_, i) => i + 1);
  });

  onPrev(): void {
    if (this.isFirstPage()) return;
    this.pageChange.emit(this.page() - 1);
  }

  onNext(): void {
    if (this.isLastPage()) return;
    this.pageChange.emit(this.page() + 1);
  }

  onPage(p: number): void {
    if (p === this.page()) return;
    this.pageChange.emit(p);
  }
}
