import {
  booleanAttribute,
  ChangeDetectionStrategy,
  Component,
  computed,
  input,
  linkedSignal,
} from '@angular/core';
import { NgOptimizedImage } from '@angular/common';

export type AvatarSize = 'sm' | 'md' | 'lg' | 'xl';

/** Avatar diameter per size, in CSS px on the M3 4px grid. */
const SIZE_PX: ReadonlyMap<AvatarSize, number> = new Map<AvatarSize, number>([
  ['sm', 32],
  ['md', 40],
  ['lg', 48],
  ['xl', 64],
]);

const DEFAULT_SIZE_PX = 40;

/** URLs NgOptimizedImage rejects in dev mode (NG02952): Base64 `data:` and `blob:` URLs. */
const INLINE_URL = /^\s*(data|blob):/i;

/**
 * Circular user avatar: a photo when `src` is set, otherwise the initials
 * derived from `alt` on `primary-container`. Angular Material has no avatar
 * component, so it is built on `--mat-sys-*` tokens (see avatar.css).
 *
 * `src` accepts ordinary and relative URLs, rendered through NgOptimizedImage, and inline
 * `data:` / `blob:` URLs (an upload preview, a Microsoft Graph photo), rendered with a plain
 * `<img>` because NgOptimizedImage rejects them.
 *
 * `alt` names the person (up to 125 characters, never "Image of …").
 * Set `decorative` when the same name is already visible beside the avatar so
 * screen readers do not announce it twice.
 */
@Component({
  selector: 'app-avatar',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [NgOptimizedImage],
  templateUrl: './avatar.html',
  styleUrl: './avatar.css',
  host: {
    class: 'app-avatar',
    '[attr.data-size]': 'size()',
    '[class.app-avatar--initials]': '!imageSrc()',
  },
})
export class AvatarComponent {
  readonly src = input<string | null>(null);
  readonly alt = input.required<string>();
  readonly size = input<AvatarSize>('md');
  /** Hide the avatar from assistive technology when a visible name sits beside it. */
  readonly decorative = input(false, { transform: booleanAttribute });

  /**
   * Diameter in CSS px for the current size. avatar.css applies it; the photo
   * fills that circle in NgOptimizedImage `fill` mode, so no bound width/height
   * can change after the image directive initializes.
   */
  readonly sizePx = computed(() => SIZE_PX.get(this.size()) ?? DEFAULT_SIZE_PX);

  /** True once the current `src` failed to load; resets whenever `src` changes. */
  private readonly imageFailed = linkedSignal({ source: this.src, computation: () => false });

  /** The image URL to render, or null to fall back to initials. */
  readonly imageSrc = computed(() => (this.imageFailed() ? null : this.src() || null));

  /** True for `data:` and `blob:` URLs, which NgOptimizedImage throws on, so a plain `<img>` shows them. */
  protected readonly isInlineUrl = computed(() => INLINE_URL.test(this.imageSrc() ?? ''));

  /** Empty alt marks the photo decorative; otherwise it carries the person's name. */
  readonly imageAlt = computed(() => (this.decorative() ? '' : this.alt()));

  readonly initials = computed(() => {
    const words = this.alt().trim().split(/\s+/).filter(Boolean);
    if (words.length === 0) return '';
    if (words.length === 1) return Array.from(words[0]).slice(0, 2).join('').toUpperCase();
    return (Array.from(words[0])[0] + Array.from(words[words.length - 1])[0]).toUpperCase();
  });

  onImageError(): void {
    this.imageFailed.set(true);
  }
}
