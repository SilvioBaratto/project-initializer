import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { LucideAngularModule } from 'lucide-angular';

export type BadgeVariant = 'default' | 'primary' | 'info' | 'success' | 'warning' | 'danger';

/**
 * Leading icon per status variant. The icon gives each status a shape as well as
 * a color, so status never rests on color alone; `default` and `primary` carry
 * no status and stay text-only.
 */
const STATUS_ICONS: Partial<Record<BadgeVariant, string>> = {
  info: 'info',
  success: 'circle-check-big',
  warning: 'triangle-alert',
  danger: 'circle-alert',
};

/**
 * Inline, non-interactive status label ("Paid", "Pending", "Failed").
 *
 * Angular Material's `matBadge` decorates another element with a count, which
 * this is not, so the label is built on `--mat-sys-*` tokens (see badge.css):
 * `label-medium` type on a full-corner pill, each variant a container /
 * on-container color pair. Status variants add a decorative leading icon.
 *
 * The projected text must name the state: screen readers announce the text,
 * never the color or the icon.
 */
@Component({
  selector: 'app-badge',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [LucideAngularModule],
  templateUrl: './badge.html',
  styleUrl: './badge.css',
  host: {
    class: 'app-badge',
    '[attr.data-variant]': 'variant()',
    '[class.app-badge--with-icon]': 'statusIcon() !== null',
  },
})
export class BadgeComponent {
  readonly variant = input<BadgeVariant>('default');

  /** Lucide icon name for status variants, or null when the variant has no status. */
  protected readonly statusIcon = computed(() => STATUS_ICONS[this.variant()] ?? null);
}
