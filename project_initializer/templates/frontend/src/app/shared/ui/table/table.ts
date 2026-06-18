import { ChangeDetectionStrategy, Component, input } from '@angular/core';

export interface TableColumn {
  key: string;
  header: string;
}

@Component({
  selector: 'ui-table',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './table.html',
})
export class TableComponent {
  readonly columns = input([] as TableColumn[]);
  readonly rows = input([] as Record<string, unknown>[]);
}
