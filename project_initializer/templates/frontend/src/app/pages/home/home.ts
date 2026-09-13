import { DecimalPipe, PercentPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component } from '@angular/core';
import { MatCard } from '@angular/material/card';

import { BadgeComponent } from '../../shared/ui/badge/badge';
import { DeltaDirection, StatCardComponent } from '../../shared/ui/stat-card/stat-card';

interface Stat {
  label: string;
  /** Raw count; the template formats it for the active locale. */
  value: number;
  /** Change as a fraction (0.12 is 12%); the template formats it as a percentage. */
  delta: number;
  direction: DeltaDirection;
}

/**
 * Home view: a hero card and three key metrics.
 *
 * The metrics reuse `app-stat-card` and the hero tag reuses `app-badge`, so they match the catalog
 * demos of those components. Rendered inside the shell's `<main>`, which adds no padding, so the
 * page owns its pane margins (see home.css).
 */
@Component({
  selector: 'app-home',
  imports: [MatCard, BadgeComponent, StatCardComponent, DecimalPipe, PercentPipe],
  templateUrl: './home.html',
  styleUrl: './home.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class HomeComponent {
  stats: Stat[] = [
    { label: 'Active users', value: 1284, delta: 0.12, direction: 'up' },
    { label: 'Sessions', value: 8932, delta: 0.04, direction: 'up' },
    { label: 'Conversations', value: 342, delta: 0.09, direction: 'up' },
  ];
}
