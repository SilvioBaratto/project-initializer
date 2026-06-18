import { ChangeDetectionStrategy, Component, input } from '@angular/core';

/**
 * Renders its ng-content in both a light region and a scoped dark region.
 * The dark region uses the `dark` CSS class on a container element, which
 * activates @custom-variant dark (&:where(.dark, .dark *)) from styles.css.
 * This is independent of the global ThemeService toggle.
 *
 * Overlays (modal, slide-over, drawer) use fixed positioning and escape this
 * container — use OverlayPreviewComponent for those instead.
 */
@Component({
  selector: 'app-theme-preview',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="space-y-2 mb-6">
      <p class="text-xs font-medium text-text-secondary uppercase tracking-wide">{{ label() }}</p>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <!-- Light region -->
        <div class="rounded-lg border border-border bg-surface p-4">
          <p class="mb-2 text-xs text-text-tertiary">Light</p>
          <ng-content />
        </div>
        <!-- Dark region — scoped via dark class, independent of global theme -->
        <div class="dark rounded-lg border border-border bg-surface p-4">
          <p class="mb-2 text-xs text-text-tertiary">Dark</p>
          <ng-content />
        </div>
      </div>
    </div>
  `,
})
export class ThemePreviewComponent {
  readonly label = input('');
}
