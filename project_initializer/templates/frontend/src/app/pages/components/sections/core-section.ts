import { ChangeDetectionStrategy, Component } from '@angular/core';

import { ContainerComponent } from '../../../shared/ui/container/container';
import { StackComponent } from '../../../shared/ui/stack/stack';
import { GridComponent } from '../../../shared/ui/grid/grid';
import { CardComponent } from '../../../shared/ui/card/card';
import { SpinnerComponent } from '../../../shared/ui/spinner/spinner';
import { SkeletonComponent } from '../../../shared/ui/skeleton/skeleton';
import { AlertComponent } from '../../../shared/ui/alert/alert';
import { BadgeComponent } from '../../../shared/ui/badge/badge';

import { ThemePreviewComponent } from '../theme-preview';

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
  ],
  template: `
    <app-theme-preview label="Container / Stack / Grid / Card">
      <app-container size="sm">
        <app-stack [gap]="3">
          <app-card>
            <span slot-header class="text-sm font-medium">Card header</span>
            <p class="text-sm text-text-secondary">Card body content.</p>
            <span slot-footer class="text-xs text-text-tertiary">Footer</span>
          </app-card>
          <app-grid [gap]="3">
            <div class="rounded-md border border-border bg-surface-inset p-3 text-xs text-center text-text-secondary">Col 1</div>
            <div class="rounded-md border border-border bg-surface-inset p-3 text-xs text-center text-text-secondary">Col 2</div>
            <div class="rounded-md border border-border bg-surface-inset p-3 text-xs text-center text-text-secondary">Col 3</div>
          </app-grid>
        </app-stack>
      </app-container>
    </app-theme-preview>

    <app-theme-preview label="Spinner / Skeleton">
      <app-stack direction="row" [gap]="6" align="center">
        <app-spinner />
        <app-stack [gap]="2">
          <app-skeleton width="w-48" height="h-3" />
          <app-skeleton width="w-32" height="h-3" />
          <app-skeleton shape="avatar" width="w-8" height="h-8" />
        </app-stack>
      </app-stack>
    </app-theme-preview>

    <app-theme-preview label="Alert / Badge">
      <app-stack [gap]="3">
        <app-alert variant="info">Info alert message</app-alert>
        <app-alert variant="success">Success alert message</app-alert>
        <app-alert variant="warning">Warning alert message</app-alert>
        <app-alert variant="danger">Danger alert message</app-alert>
        <app-stack direction="row" [gap]="2" align="center">
          <app-badge>Default</app-badge>
          <app-badge variant="primary">Primary</app-badge>
          <app-badge variant="success">Success</app-badge>
          <app-badge variant="warning">Warning</app-badge>
          <app-badge variant="danger">Danger</app-badge>
        </app-stack>
      </app-stack>
    </app-theme-preview>
  `,
})
export class CoreSectionComponent {}
