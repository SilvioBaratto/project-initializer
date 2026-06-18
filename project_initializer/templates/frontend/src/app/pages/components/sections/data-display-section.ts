import { ChangeDetectionStrategy, Component } from '@angular/core';

import { TableComponent, TableColumn } from '../../../shared/ui/table/table';
import { ListComponent } from '../../../shared/ui/list/list';
import { AvatarComponent } from '../../../shared/ui/avatar/avatar';
import { StatCardComponent } from '../../../shared/ui/stat-card/stat-card';
import { PaginationComponent } from '../../../shared/ui/pagination/pagination';
import { AccordionComponent, AccordionItemComponent } from '../../../shared/ui/accordion/accordion';
import { StackComponent } from '../../../shared/ui/stack/stack';
import { GridComponent } from '../../../shared/ui/grid/grid';

import { ThemePreviewComponent } from '../theme-preview';

@Component({
  selector: 'app-data-display-section',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    ThemePreviewComponent,
    StackComponent,
    GridComponent,
    TableComponent,
    ListComponent,
    AvatarComponent,
    StatCardComponent,
    PaginationComponent,
    AccordionComponent,
    AccordionItemComponent,
  ],
  template: `
    <app-theme-preview label="Table">
      <ui-table [columns]="tableColumns" [rows]="tableRows" />
    </app-theme-preview>

    <app-theme-preview label="List / Avatar">
      <app-stack direction="row" [gap]="4" align="start">
        <ui-list variant="divided">
          <li class="px-4 py-2 text-sm text-text">Item one</li>
          <li class="px-4 py-2 text-sm text-text">Item two</li>
          <li class="px-4 py-2 text-sm text-text">Item three</li>
        </ui-list>
        <app-stack direction="row" [gap]="2" align="center">
          <app-avatar alt="Alice Smith" size="sm" />
          <app-avatar alt="Bob Jones" size="md" />
          <app-avatar alt="Carol White" size="lg" />
        </app-stack>
      </app-stack>
    </app-theme-preview>

    <app-theme-preview label="Stat Cards">
      <app-grid [gap]="3">
        <app-stat-card metric="1,284" label="Active users" delta="+12%" deltaDirection="up" />
        <app-stat-card metric="8,932" label="Sessions" delta="-3%" deltaDirection="down" />
        <app-stat-card metric="342" label="Conversations" />
      </app-grid>
    </app-theme-preview>

    <app-theme-preview label="Pagination">
      <ui-pagination [page]="2" [total]="5" />
    </app-theme-preview>

    <app-theme-preview label="Accordion">
      <ui-accordion>
        <ui-accordion-item [index]="0">
          <span slot="header">What is Angular?</span>
          A platform for building web apps.
        </ui-accordion-item>
        <ui-accordion-item [index]="1">
          <span slot="header">What is Tailwind?</span>
          A utility-first CSS framework.
        </ui-accordion-item>
      </ui-accordion>
    </app-theme-preview>
  `,
})
export class DataDisplaySectionComponent {
  readonly tableColumns: TableColumn[] = [
    { key: 'name', header: 'Name' },
    { key: 'role', header: 'Role' },
    { key: 'status', header: 'Status' },
  ];

  readonly tableRows = [
    { name: 'Alice', role: 'Admin', status: 'Active' },
    { name: 'Bob', role: 'Editor', status: 'Inactive' },
  ];
}
