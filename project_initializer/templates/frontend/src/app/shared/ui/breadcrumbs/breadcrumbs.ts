import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { MatRipple } from '@angular/material/core';
import { RouterLink } from '@angular/router';
import { LucideAngularModule } from 'lucide-angular';

export interface CrumbItem {
  label: string;
  routerLink?: string | string[];
}

/**
 * Breadcrumb trail. Material 3 and Angular Material ship no breadcrumbs, so the
 * trail is built on `--mat-sys-*` tokens. Ancestor crumbs with a route are links
 * with a state layer, a pressed ripple, a focus ring outside the link and a 48px
 * target; an ancestor without a route is plain text. The last crumb is the
 * current page (marked with aria-current, not a link). Chevron separators are
 * decorative and mirror in right-to-left layouts.
 */
@Component({
  selector: 'ui-breadcrumbs',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, MatRipple, LucideAngularModule],
  templateUrl: './breadcrumbs.html',
  styleUrl: './breadcrumbs.css',
})
export class BreadcrumbsComponent {
  readonly items = input([] as CrumbItem[]);

  /**
   * Accessible name of the navigation landmark. When a page shows more than one
   * trail, give each a distinct label (without the word "navigation").
   */
  readonly label = input('Breadcrumb');
}
