import { ChangeDetectionStrategy, Component, ViewEncapsulation, computed, input } from '@angular/core';
import { MatCardModule, type MatCardAppearance } from '@angular/material/card';

/** Inset of the card body. `none` removes it for full-bleed content such as media or tables. */
export type CardPadding = 'none' | 'sm' | 'md' | 'lg';

/** M3 card type: `outlined`, `raised` (M3 "elevated") or `filled`. */
export type CardAppearance = MatCardAppearance;

const CARD_PADDINGS: readonly string[] = ['none', 'sm', 'md', 'lg'] satisfies CardPadding[];

function isCardPadding(value: string): value is CardPadding {
  return CARD_PADDINGS.includes(value);
}

/**
 * Material 3 card built on `<mat-card>`.
 *
 * Projection slots:
 * - `[slot-header]` → `<mat-card-header>` (title-medium type). The card never picks a heading level; project an
 *   `h2`/`h3`/… that fits the page outline when the header is a heading. A projected heading or paragraph loses its
 *   browser margins and takes the slot's title-medium type; a class on it still overrides that.
 * - default → `<mat-card-content>` (body-medium type, inset set by `padding`). The first child's top margin is
 *   removed, as Material already removes the last child's bottom margin.
 * - `[slot-footer]` → `<mat-card-footer>`: a wrapping row with 8px between items, for actions or supporting text.
 *
 * The header and footer share the body's inline inset, so text edges line up for every `padding`.
 * An empty header or footer takes no space.
 *
 * Encapsulation is None because the slot rules must reach projected nodes; card.css scopes every selector under
 * the `.app-card` host class with child combinators, so a card nested in another card keeps its own insets.
 */
@Component({
  selector: 'app-card',
  changeDetection: ChangeDetectionStrategy.OnPush,
  encapsulation: ViewEncapsulation.None,
  imports: [MatCardModule],
  templateUrl: './card.html',
  styleUrl: './card.css',
  host: { class: 'app-card' },
})
export class CardComponent {
  /** Body inset: `'none' | 'sm' | 'md' | 'lg'` (see {@link CardPadding}). Unknown values fall back to `'md'`. */
  readonly padding = input('md');

  /** M3 card type. Outlined by default: a grouped region on `surface` bounded by `outline-variant`. */
  readonly appearance = input<CardAppearance>('outlined');

  /** The inset actually applied, after falling back to `'md'` for unknown values. */
  readonly resolvedPadding = computed<CardPadding>(() => {
    const value = this.padding();
    return isCardPadding(value) ? value : 'md';
  });
}
