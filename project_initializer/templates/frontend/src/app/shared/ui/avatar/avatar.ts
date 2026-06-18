import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { NgOptimizedImage } from '@angular/common';

export type AvatarSize = 'sm' | 'md' | 'lg' | 'xl';

const SIZE_CLASSES: Record<AvatarSize, string> = {
  sm: 'size-8 text-xs',
  md: 'size-10 text-sm',
  lg: 'size-12 text-base',
  xl: 'size-16 text-xl',
};

const SIZE_PX: Record<AvatarSize, number> = {
  sm: 32,
  md: 40,
  lg: 48,
  xl: 64,
};

@Component({
  selector: 'app-avatar',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [NgOptimizedImage],
  template: `
    @if (src()) {
      <img
        [ngSrc]="src()!"
        [width]="sizePx()"
        [height]="sizePx()"
        [alt]="alt()"
        [class]="imgClasses()"
      />
    } @else {
      <span [class]="initialsClasses()" aria-hidden="true">{{ initials() }}</span>
      <span class="sr-only">{{ alt() }}</span>
    }
  `,
  host: { '[class]': 'hostClasses()' },
})
export class AvatarComponent {
  readonly src = input<string | null>(null);
  readonly alt = input.required<string>();
  readonly size = input<AvatarSize>('md');

  readonly sizePx = computed(() => SIZE_PX[this.size()]);

  readonly hostClasses = computed(() =>
    `inline-flex items-center justify-center rounded-full overflow-hidden shrink-0 ${SIZE_CLASSES[this.size()]}`
  );

  readonly imgClasses = computed(() => 'rounded-full object-cover w-full h-full');

  readonly initialsClasses = computed(
    () => 'font-medium text-text-secondary bg-surface-inset rounded-full w-full h-full flex items-center justify-center select-none'
  );

  readonly initials = computed(() => {
    const a = this.alt();
    const words = a.trim().split(/\s+/).filter(Boolean);
    if (words.length === 0) return '';
    if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
    return (words[0][0] + words[words.length - 1][0]).toUpperCase();
  });
}
