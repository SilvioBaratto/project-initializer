import { ChangeDetectionStrategy, Component } from '@angular/core';
import { provideRouter } from '@angular/router';

import { NavbarComponent } from '../../../shared/ui/navbar/navbar';
import { HamburgerComponent } from '../../../shared/ui/hamburger/hamburger';
import { TabsComponent, TabComponent, TabPanelComponent } from '../../../shared/ui/tabs/tabs';
import { BreadcrumbsComponent, CrumbItem } from '../../../shared/ui/breadcrumbs/breadcrumbs';
import { StackComponent } from '../../../shared/ui/stack/stack';

import { ThemePreviewComponent } from '../theme-preview';

@Component({
  selector: 'app-navigation-section',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    ThemePreviewComponent,
    StackComponent,
    NavbarComponent,
    HamburgerComponent,
    TabsComponent,
    TabComponent,
    TabPanelComponent,
    BreadcrumbsComponent,
  ],
  template: `
    <app-theme-preview label="Navbar / Hamburger">
      <app-stack [gap]="3">
        <app-navbar>
          <span navbarBrand class="font-semibold text-text text-sm">My App</span>
          <app-hamburger navbarActions [open]="false" />
        </app-navbar>
        <app-hamburger [open]="true" />
      </app-stack>
    </app-theme-preview>

    <app-theme-preview label="Tabs">
      <ui-tabs>
        <ui-tab [tabIndex]="0">Overview</ui-tab>
        <ui-tab [tabIndex]="1">Details</ui-tab>
        <ui-tab [tabIndex]="2">History</ui-tab>
        <ui-tab-panel [panelIndex]="0">Overview content</ui-tab-panel>
        <ui-tab-panel [panelIndex]="1">Details content</ui-tab-panel>
        <ui-tab-panel [panelIndex]="2">History content</ui-tab-panel>
      </ui-tabs>
    </app-theme-preview>

    <app-theme-preview label="Breadcrumbs">
      <ui-breadcrumbs [items]="breadcrumbs" />
    </app-theme-preview>
  `,
})
export class NavigationSectionComponent {
  readonly breadcrumbs: CrumbItem[] = [
    { label: 'Home', routerLink: '/home' },
    { label: 'Settings', routerLink: '/settings' },
    { label: 'Profile' },
  ];
}
