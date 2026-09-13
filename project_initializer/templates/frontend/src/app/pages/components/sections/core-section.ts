import { ChangeDetectionStrategy, Component } from '@angular/core';
import { MatButton } from '@angular/material/button';

import { AlertComponent } from '../../../shared/ui/alert/alert';
import { BadgeComponent } from '../../../shared/ui/badge/badge';
import { CardComponent } from '../../../shared/ui/card/card';
import { ContainerComponent } from '../../../shared/ui/container/container';
import { GridComponent } from '../../../shared/ui/grid/grid';
import { SkeletonComponent } from '../../../shared/ui/skeleton/skeleton';
import { SpinnerComponent } from '../../../shared/ui/spinner/spinner';
import { StackComponent } from '../../../shared/ui/stack/stack';

import { ThemePreviewComponent } from '../theme-preview';

/**
 * Core group of the /components catalog: layout primitives, loading indicators and status messages,
 * each stamped in a light and a dark region by `app-theme-preview`.
 *
 * The page owns the `h1` and the group's `h2`; this section adds one `h3` per demo group.
 *
 * Stateless: the dismissible alert demo reads and reopens each stamped alert through its own template
 * reference, so the light and dark copies keep separate `open` state.
 */
@Component({
  selector: 'app-core-section',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    ThemePreviewComponent,
    ContainerComponent,
    StackComponent,
    GridComponent,
    CardComponent,
    SpinnerComponent,
    SkeletonComponent,
    AlertComponent,
    BadgeComponent,
    MatButton,
  ],
  templateUrl: './core-section.html',
  styleUrl: './core-section.css',
})
export class CoreSectionComponent {}
