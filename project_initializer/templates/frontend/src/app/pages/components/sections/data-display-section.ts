import { DecimalPipe, PercentPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, WritableSignal, signal } from '@angular/core';
import {
  MatListItem,
  MatListItemAvatar,
  MatListItemLine,
  MatListItemTitle,
} from '@angular/material/list';

import { TableComponent, TableColumn } from '../../../shared/ui/table/table';
import { ListComponent } from '../../../shared/ui/list/list';
import { AvatarComponent } from '../../../shared/ui/avatar/avatar';
import { StatCardComponent } from '../../../shared/ui/stat-card/stat-card';
import { PaginationComponent } from '../../../shared/ui/pagination/pagination';
import { AccordionComponent, AccordionItemComponent } from '../../../shared/ui/accordion/accordion';
import { StackComponent } from '../../../shared/ui/stack/stack';
import { GridComponent } from '../../../shared/ui/grid/grid';

import { ThemePreviewComponent } from '../theme-preview';

/** Color scheme of the preview region a demo is stamped into. */
type PreviewScheme = 'light' | 'dark';

/** One row of the team demo, shared by the table and the list. */
interface TeamMember {
  name: string;
  role: string;
  status: string;
}

/**
 * Data display group of the /components catalog: table, list and avatar, stat cards, pagination
 * and accordion, each under an h3 and previewed in a light and a dark region.
 *
 * The page owns the `h1` and the group's `h2`; this section adds one `h3` per demo group.
 *
 * Each preview region paints the surface of its own color scheme, so every demo keeps its contrast
 * whichever scheme the page itself uses.
 *
 * The pagination demo is live, and each preview copy keeps its own page (`lightPage` / `darkPage`,
 * picked by `pageFor`), so a click announces one page change, not two. Each accordion copy keeps
 * its own expanded state too.
 */
@Component({
  selector: 'app-data-display-section',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    ThemePreviewComponent,
    StackComponent,
    GridComponent,
    TableComponent,
    ListComponent,
    MatListItem,
    MatListItemAvatar,
    MatListItemTitle,
    MatListItemLine,
    AvatarComponent,
    StatCardComponent,
    PaginationComponent,
    AccordionComponent,
    AccordionItemComponent,
    DecimalPipe,
    PercentPipe,
  ],
  templateUrl: './data-display-section.html',
  styleUrl: './data-display-section.css',
})
export class DataDisplaySectionComponent {
  readonly tableColumns: TableColumn[] = [
    { key: 'name', header: 'Name' },
    { key: 'role', header: 'Role' },
    { key: 'status', header: 'Status' },
  ];

  readonly teamMembers: readonly TeamMember[] = [
    { name: 'Alice Smith', role: 'Admin', status: 'Active' },
    { name: 'Bob Jones', role: 'Editor', status: 'Invited' },
    { name: 'Carol White', role: 'Viewer', status: 'Active' },
  ];

  readonly tableRows: Record<string, unknown>[] = this.teamMembers.map((member) => ({ ...member }));

  /** Pages in the pagination demo. */
  readonly pageCount = 5;

  /** Current page of the pagination copy in the light preview region. Starts mid-range. */
  readonly lightPage = signal(2);

  /** Current page of the pagination copy in the dark preview region. Starts mid-range. */
  readonly darkPage = signal(2);

  /**
   * Page state of the pagination copy stamped around `anchor`.
   *
   * Each copy renders its own polite "Page N of M" live region, so one shared signal would change
   * both regions on a single click and a screen reader would hear the status twice, once from the
   * copy the user never touched. One signal per region keeps it to one announcement per change.
   */
  protected pageFor(anchor: Element): WritableSignal<number> {
    return this.previewScheme(anchor) === 'dark' ? this.darkPage : this.lightPage;
  }

  /**
   * Scheme of the nearest preview region around `anchor`. The nearest `.light` / `.dark` match wins
   * over the scheme class that ThemeService puts on `<html>`.
   *
   * The table's scroll region, the pagination nav and each accordion panel's body region are
   * landmarks stamped into both regions, so the template picks a whole-string label per scheme
   * (never concatenated, so each translates as a unit). Material names a panel's body region after
   * its header, so the accordion headers carry that label as visually hidden text.
   */
  protected previewScheme(anchor: Element): PreviewScheme {
    return anchor.closest('.light, .dark')?.classList.contains('dark') ? 'dark' : 'light';
  }
}
