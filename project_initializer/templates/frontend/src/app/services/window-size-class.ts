import { Injectable, computed, inject } from '@angular/core';
import { BreakpointObserver } from '@angular/cdk/layout';
import { toSignal } from '@angular/core/rxjs-interop';
import { map } from 'rxjs';

/**
 * Material 3 window size classes (m3.material.io → Layout → Breakpoints).
 *
 * Do NOT use the CDK `Breakpoints` presets: they are M2-era (600/960/1280/1920).
 * CSS can't read custom properties inside media queries, so stylesheets repeat
 * these literals: 600px, 840px, 1200px, 1600px.
 */
export const WINDOW_SIZE_QUERIES = {
  compact: '(max-width: 599.98px)',
  medium: '(min-width: 600px) and (max-width: 839.98px)',
  expanded: '(min-width: 840px) and (max-width: 1199.98px)',
  large: '(min-width: 1200px) and (max-width: 1599.98px)',
  extraLarge: '(min-width: 1600px)',
} as const;

export type WindowSizeClass = keyof typeof WINDOW_SIZE_QUERIES;

const ORDER: readonly WindowSizeClass[] = ['compact', 'medium', 'expanded', 'large', 'extraLarge'];

@Injectable({ providedIn: 'root' })
export class WindowSizeClassService {
  private readonly observer = inject(BreakpointObserver);

  /** The window size class that matches the current viewport width. */
  readonly current = toSignal(
    this.observer.observe(Object.values(WINDOW_SIZE_QUERIES)).pipe(map(() => this.match())),
    { initialValue: this.match() },
  );

  /** True below 600px: navigation bar, bottom sheets, full-screen dialogs. */
  readonly isCompact = computed(() => this.current() === 'compact');

  /** True when the current class is `sizeClass` or wider. */
  atLeast(sizeClass: WindowSizeClass): boolean {
    return ORDER.indexOf(this.current()) >= ORDER.indexOf(sizeClass);
  }

  private match(): WindowSizeClass {
    // SSR: MediaMatcher matches nothing on the server, so fall back to compact.
    return ORDER.find((c) => this.observer.isMatched(WINDOW_SIZE_QUERIES[c])) ?? 'compact';
  }
}
