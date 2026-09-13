import { ChangeDetectionStrategy, Component, TemplateRef, contentChild, input } from '@angular/core';
import { NgTemplateOutlet } from '@angular/common';

/** Makes the caption ids unique: every catalog demo mounts its own preview. */
let nextPreviewId = 0;

/**
 * Renders a projected `<ng-template>` twice: once in a light region and once in a dark region.
 *
 * Each region carries the `light` or `dark` class, which sets `color-scheme` on that subtree
 * (styles.scss). The `--mat-sys-*` tokens are `light-dark()` values, so everything inside a region,
 * including the region's own surface and text color painted in theme-preview.css, resolves in that
 * region's scheme, whatever the global ThemeService setting is. Sections that need to know which
 * copy they are in look up the nearest `.light` / `.dark` ancestor, so both classes must stay on
 * the region elements.
 *
 * Content must be wrapped in an `<ng-template>` so it can be stamped twice; a bare `<ng-content />`
 * can only be projected into one slot, which would leave the other region empty.
 *
 * Each region is a `role="group"` named by its visible caption ("Light" or "Dark"), so a screen
 * reader tells the two copies of a control apart when focus moves into one.
 *
 * Overlays opened from inside a region (dialogs, side sheets, menus, select panels, tooltips) render
 * in the CDK overlay container under `<body>`, outside both regions, so they follow the global theme.
 */
@Component({
  selector: 'app-theme-preview',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [NgTemplateOutlet],
  templateUrl: './theme-preview.html',
  styleUrl: './theme-preview.css',
})
export class ThemePreviewComponent {
  /** Optional caption above both regions. Sections that render their own heading leave it empty. */
  readonly label = input('');
  readonly content = contentChild.required(TemplateRef);

  private readonly previewId = `app-theme-preview-${nextPreviewId++}`;

  /** Id of the "Light" caption, which names the light region. */
  protected readonly lightCaptionId = `${this.previewId}-light`;

  /** Id of the "Dark" caption, which names the dark region. */
  protected readonly darkCaptionId = `${this.previewId}-dark`;
}
