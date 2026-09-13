import { TestBed } from '@angular/core/testing';
import { MediaMatcher } from '@angular/cdk/layout';

import { WINDOW_SIZE_QUERIES, WindowSizeClass, WindowSizeClassService } from './window-size-class';

function mediaMatcherFor(active: WindowSizeClass): Partial<MediaMatcher> {
  return {
    matchMedia: (query: string) =>
      ({
        matches: query === WINDOW_SIZE_QUERIES[active],
        media: query,
        addListener: () => undefined,
        removeListener: () => undefined,
        addEventListener: () => undefined,
        removeEventListener: () => undefined,
      }) as unknown as MediaQueryList,
  };
}

describe('WindowSizeClassService', () => {
  function createService(active: WindowSizeClass): WindowSizeClassService {
    TestBed.configureTestingModule({
      providers: [{ provide: MediaMatcher, useValue: mediaMatcherFor(active) }],
    });
    return TestBed.inject(WindowSizeClassService);
  }

  it('uses the M3 breakpoints, not the CDK presets', () => {
    expect(WINDOW_SIZE_QUERIES.compact).toBe('(max-width: 599.98px)');
    expect(WINDOW_SIZE_QUERIES.medium).toContain('600px');
    expect(WINDOW_SIZE_QUERIES.expanded).toContain('840px');
    expect(WINDOW_SIZE_QUERIES.large).toContain('1200px');
    expect(WINDOW_SIZE_QUERIES.extraLarge).toBe('(min-width: 1600px)');
  });

  it('when the medium query matches, current is medium', () => {
    const service = createService('medium');
    expect(service.current()).toBe('medium');
    expect(service.isCompact()).toBe(false);
  });

  it('when the compact query matches, isCompact is true', () => {
    expect(createService('compact').isCompact()).toBe(true);
  });

  it('when the window is large, atLeast compares by size-class order', () => {
    const service = createService('large');
    expect(service.atLeast('expanded')).toBe(true);
    expect(service.atLeast('large')).toBe(true);
    expect(service.atLeast('extraLarge')).toBe(false);
  });
});
