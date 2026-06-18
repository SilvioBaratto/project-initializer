import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { LucideAngularModule } from 'lucide-angular';

export interface CrumbItem {
  label: string;
  routerLink?: string | string[];
}

@Component({
  selector: 'ui-breadcrumbs',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, LucideAngularModule],
  template: `
    <nav aria-label="Breadcrumb">
      <ol class="flex flex-wrap items-center gap-1 text-sm
                 text-text-secondary dark:text-text-secondary">
        @for (crumb of items(); track crumb.label; let last = $last) {
          <li class="flex items-center gap-1">
            @if (last) {
              <span aria-current="page"
                    class="font-medium text-text dark:text-text">
                {{ crumb.label }}
              </span>
            } @else {
              <a [routerLink]="crumb.routerLink ?? []"
                 class="transition-colors hover:text-text dark:hover:text-text">
                {{ crumb.label }}
              </a>
              <lucide-icon name="ChevronRight" class="h-3.5 w-3.5 shrink-0"
                           aria-hidden="true" />
            }
          </li>
        }
      </ol>
    </nav>
  `,
})
export class BreadcrumbsComponent {
  readonly items = input([] as CrumbItem[]);
}
