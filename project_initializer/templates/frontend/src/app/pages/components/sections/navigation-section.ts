import { NgTemplateOutlet } from '@angular/common';
import { ChangeDetectionStrategy, Component, signal } from '@angular/core';
import { LucideAngularModule } from 'lucide-angular';

import type { IconName } from '../../../icons';
import { NavbarComponent } from '../../../shared/ui/navbar/navbar';
import { HamburgerComponent } from '../../../shared/ui/hamburger/hamburger';
import { TabsComponent, TabComponent, TabPanelComponent } from '../../../shared/ui/tabs/tabs';
import { BreadcrumbsComponent, CrumbItem } from '../../../shared/ui/breadcrumbs/breadcrumbs';
import { StackComponent } from '../../../shared/ui/stack/stack';

import { ThemePreviewComponent } from '../theme-preview';

/** Color scheme of the preview region a demo is stamped into. */
type PreviewScheme = 'light' | 'dark';

/** One row of the destination preview a navigation toggle drives. */
interface PreviewDestination {
  readonly label: string;
  readonly icon: IconName;
}

/** Keeps preview ids unique app-wide, even if the section is mounted more than once. */
let nextSectionId = 0;

/**
 * Navigation group of the /components catalog: navbar, hamburger, tabs and breadcrumbs,
 * each under an h3 and previewed in a light and a dark region.
 *
 * The toggles are live disclosures, so every state of the hamburger can be reached with a
 * click or the keyboard, and each state is true: the navbar and modal rail toggles show and
 * hide a destination preview, and the docked rail toggle expands and collapses one. Both
 * preview copies of a demo read the same signal and change together, and each copy's toggle
 * points `aria-controls` at the preview in its own copy (see `previewListId`).
 *
 * The tablist and the breadcrumb trail's navigation landmark are stamped into both regions,
 * so the template names each copy after its region (see `previewScheme`).
 */
@Component({
  selector: 'app-navigation-section',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    NgTemplateOutlet,
    LucideAngularModule,
    ThemePreviewComponent,
    StackComponent,
    NavbarComponent,
    HamburgerComponent,
    TabsComponent,
    TabComponent,
    TabPanelComponent,
    BreadcrumbsComponent,
  ],
  templateUrl: './navigation-section.html',
  styleUrl: './navigation-section.css',
})
export class NavigationSectionComponent {
  readonly breadcrumbs: CrumbItem[] = [
    { label: 'Home', routerLink: '/home' },
    { label: 'Settings', routerLink: '/settings' },
    { label: 'Profile' },
  ];

  /** Rows of every destination preview. Plain text, not links: a preview never navigates. */
  protected readonly destinations: readonly PreviewDestination[] = [
    { label: 'Home', icon: 'Home' },
    { label: 'Dashboard', icon: 'LayoutDashboard' },
    { label: 'Settings', icon: 'Settings' },
  ];

  /** Toggle in the navbar demo (modal variant). Starts closed: Menu icon, no preview. */
  protected readonly navbarNavOpen = signal(false);

  /** Standalone modal-variant toggle. Starts open, so the catalog also shows its X icon and preview. */
  protected readonly modalNavOpen = signal(true);

  /** Rail-variant toggle. Starts expanded, so the catalog shows its PanelLeftClose icon and labelled rows. */
  protected readonly railExpanded = signal(true);

  private readonly sectionId = `app-navigation-section-${nextSectionId++}`;
  private nextCopyId = 0;
  private readonly previewListIds = new WeakMap<Element, string>();

  /**
   * Id of the destination preview in one stamped copy of a toggle demo, keyed by that copy's
   * root element, so the light and dark copies never share an id.
   */
  protected previewListId(copy: Element): string {
    let id = this.previewListIds.get(copy);
    if (id === undefined) {
      id = `${this.sectionId}-destinations-${this.nextCopyId++}`;
      this.previewListIds.set(copy, id);
    }
    return id;
  }

  /**
   * Scheme of the nearest preview region around `anchor`. The nearest `.light` / `.dark` match
   * wins over the scheme class that ThemeService puts on `<html>`.
   *
   * Landmarks need distinct labels, so the template picks a whole-string name per scheme for
   * each stamped copy (never concatenated, so each translates as a unit).
   */
  protected previewScheme(anchor: Element): PreviewScheme {
    return anchor.closest('.light, .dark')?.classList.contains('dark') ? 'dark' : 'light';
  }
}
