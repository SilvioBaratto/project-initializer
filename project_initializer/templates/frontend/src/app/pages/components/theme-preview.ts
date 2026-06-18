import { ChangeDetectionStrategy, Component, TemplateRef, contentChild, input } from '@angular/core';
import { NgTemplateOutlet } from '@angular/common';

/**
 * Renders a projected `<ng-template>` in both a light region and a scoped
 * dark region. The dark region uses the `dark` CSS class on a container
 * element, which activates @custom-variant dark (&:where(.dark, .dark *))
 * from styles.css. This is independent of the global ThemeService toggle.
 *
 * Content must be wrapped in an `<ng-template>` so it can be stamped twice;
 * a bare `<ng-content />` cannot be projected into two slots at once (only
 * the last slot receives it, leaving the light region empty).
 *
 * Overlays (modal, slide-over, drawer) use fixed positioning and escape this
 * container — use OverlayPreviewComponent for those instead.
 */
@Component({
  selector: 'app-theme-preview',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [NgTemplateOutlet],
  template: `
    <div class="space-y-2 mb-6">
      <p class="text-xs font-medium text-text-secondary uppercase tracking-wide">{{ label() }}</p>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <!-- Light region — scoped via light class, independent of global theme -->
        <div class="light rounded-lg border border-border bg-surface p-4">
          <p class="mb-2 text-xs text-text-tertiary">Light</p>
          <ng-container [ngTemplateOutlet]="content()" />
        </div>
        <!-- Dark region — scoped via dark class, independent of global theme -->
        <div class="dark rounded-lg border border-border bg-surface p-4">
          <p class="mb-2 text-xs text-text-tertiary">Dark</p>
          <ng-container [ngTemplateOutlet]="content()" />
        </div>
      </div>
    </div>
  `,
})
export class ThemePreviewComponent {
  readonly label = input('');
  readonly content = contentChild.required(TemplateRef);
}
