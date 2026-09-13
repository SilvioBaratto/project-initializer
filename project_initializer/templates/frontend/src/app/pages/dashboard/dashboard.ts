import { CurrencyPipe, DecimalPipe, PercentPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, signal } from '@angular/core';
import { MatCard, MatCardContent } from '@angular/material/card';

import { SkeletonComponent } from '../../shared/ui/skeleton/skeleton';

/** How the template formats a metric's value: a currency amount, a count, or a fraction shown as a percentage. */
type MetricFormat = 'currency' | 'number' | 'percent';

interface Metric {
  label: string;
  /** Raw value. `percent` values are fractions (0.021 is 2.1%). */
  value: number;
  format: MetricFormat;
  hint: string;
}

/**
 * Dashboard view: a feed of peer metric cards (M3 feed canonical layout).
 *
 * Rendered inside the shell's `<main>`, which adds no padding, so the page owns
 * its pane margins (see dashboard.css). Cards are Angular Material elevated
 * cards on `surface-container-low`. Values are stored as numbers and formatted
 * in the template by locale pipes, so they localize and never need abbreviations.
 *
 * While `isLoading` is true, placeholder tiles take the cards' place in the same
 * grid and a status names what is loading. The starter's metrics are static, so
 * it stays false: set it while the request that fills `metrics` is pending.
 */
@Component({
  selector: 'app-dashboard',
  imports: [MatCard, MatCardContent, SkeletonComponent, CurrencyPipe, DecimalPipe, PercentPipe],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DashboardComponent {
  /** True while the metrics are being fetched. Nothing loads in the starter, so nothing sets it yet. */
  readonly isLoading = signal(false);

  /** One placeholder tile per expected metric card while `isLoading` is true. */
  protected readonly placeholders = [0, 1, 2, 3];

  metrics: Metric[] = [
    { label: 'Revenue', value: 42500, format: 'currency', hint: 'Last 30 days' },
    { label: 'Signups', value: 1204, format: 'number', hint: 'Last 30 days' },
    { label: 'Churn', value: 0.021, format: 'percent', hint: 'Last 30 days' },
    { label: 'Net Promoter Score', value: 64, format: 'number', hint: 'Last survey' },
  ];
}
