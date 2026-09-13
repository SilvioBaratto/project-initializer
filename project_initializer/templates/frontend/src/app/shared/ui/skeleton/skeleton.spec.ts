import { ComponentFixture, TestBed } from '@angular/core/testing';

import { SkeletonComponent } from './skeleton';

/** The skeleton's compiled component stylesheet, as Angular attached it to the document. */
function skeletonStylesheet(): string {
  return Array.from(document.querySelectorAll('style'))
    .map((style) => style.textContent ?? '')
    .filter((css) => css.includes('skeleton-shimmer'))
    .join('\n');
}

/**
 * Declarations of every innermost rule in `css` whose selector passes `matches`,
 * joined. A rule nested in @media is matched by its own selector.
 */
function declarationsFor(css: string, matches: (selector: string) => boolean): string {
  return Array.from(css.matchAll(/([^{}]+)\{([^{}]*)\}/g))
    .filter(([, selector]) => matches(selector))
    .map(([, , declarations]) => declarations)
    .join('\n');
}

/** The placeholder rule with no shape or direction qualifier (the line default). */
function isBasePlaceholderRule(selector: string): boolean {
  return (
    selector.includes('.skeleton') &&
    !selector.includes('data-shape') &&
    !/:dir\(|\[dir/.test(selector)
  );
}

/** The placeholder rule for one data-shape value. */
function isShapePlaceholderRule(shape: 'block' | 'avatar'): (selector: string) => boolean {
  return (selector) =>
    selector.includes('.skeleton') && new RegExp(`data-shape=["']?${shape}\\b`).test(selector);
}

/** Distinct --mat-sys-corner-* names used by border-radius in a set of declarations. */
function cornerTokens(declarations: string): Set<string> {
  return new Set(
    Array.from(
      declarations.matchAll(/border-radius:\s*var\(--mat-sys-corner-([\w-]+)\)/g),
      (match) => match[1],
    ),
  );
}

describe('SkeletonComponent', () => {
  let fixture: ComponentFixture<SkeletonComponent>;
  let host: HTMLElement;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SkeletonComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(SkeletonComponent);
    host = fixture.nativeElement;
    fixture.detectChanges();
  });

  function placeholder(): HTMLElement {
    const el = host.querySelector<HTMLElement>('.skeleton');
    expect(el).not.toBeNull();
    return el as HTMLElement;
  }

  // --- Decorative placeholder, hidden from screen readers ---

  it('when rendered, a single placeholder element is rendered with no text content', () => {
    expect(host.querySelectorAll('.skeleton').length).toBe(1);
    expect(host.textContent?.trim()).toBe('');
  });

  it('when rendered, the skeleton element has aria-hidden="true" so screen readers skip it', () => {
    expect(placeholder().getAttribute('aria-hidden')).toBe('true');
  });

  it('when rendered, the host carries the app-skeleton class', () => {
    expect(host.classList.contains('app-skeleton')).toBe(true);
  });

  // --- Shape variants ---

  it('when shape is not set, the host reflects the line shape', () => {
    expect(host.getAttribute('data-shape')).toBe('line');
  });

  it('when shape is block, the host reflects the block shape', () => {
    fixture.componentRef.setInput('shape', 'block');
    fixture.detectChanges();

    expect(host.getAttribute('data-shape')).toBe('block');
  });

  it('when shape is avatar, the host reflects the avatar shape', () => {
    fixture.componentRef.setInput('shape', 'avatar');
    fixture.detectChanges();

    expect(host.getAttribute('data-shape')).toBe('avatar');
  });

  // --- No layout shift: explicit dimensions ---

  it('when width and height are not set, no inline size is written so the shape default applies', () => {
    const el = placeholder();
    expect(el.style.getPropertyValue('inline-size')).toBe('');
    expect(el.style.getPropertyValue('block-size')).toBe('');
  });

  it('when width input is changed, the placeholder takes it as its inline size', () => {
    fixture.componentRef.setInput('width', '192px');
    fixture.detectChanges();

    expect(placeholder().style.getPropertyValue('inline-size')).toBe('192px');
  });

  it('when height input is changed, the placeholder takes it as its block size', () => {
    fixture.componentRef.setInput('height', '48px');
    fixture.detectChanges();

    expect(placeholder().style.getPropertyValue('block-size')).toBe('48px');
  });

  it('when shape is line and only height is set, the inline size stays the shape default', () => {
    fixture.componentRef.setInput('height', '12px');
    fixture.detectChanges();

    expect(placeholder().style.getPropertyValue('inline-size')).toBe('');
  });

  it('when width is cleared again, the inline size is removed', () => {
    fixture.componentRef.setInput('width', '192px');
    fixture.detectChanges();
    fixture.componentRef.setInput('width', '');
    fixture.detectChanges();

    expect(placeholder().style.getPropertyValue('inline-size')).toBe('');
  });

  it('when shape is line, the stylesheet gives it a 16px default block size', () => {
    expect(skeletonStylesheet()).toMatch(/block-size:\s*16px/);
  });

  it('when shape is block or avatar, the stylesheet gives each shape its own default size', () => {
    const css = skeletonStylesheet();
    const block = declarationsFor(css, isShapePlaceholderRule('block'));
    const avatar = declarationsFor(css, isShapePlaceholderRule('avatar'));

    expect(block).toMatch(/block-size:\s*96px/);
    expect(avatar).toMatch(/inline-size:\s*40px/);
    expect(avatar).toMatch(/block-size:\s*auto/);
    expect(avatar).toMatch(/aspect-ratio:\s*1\b/);
  });

  // --- Avatar keeps one diameter, so it stays a circle ---

  it('when shape is avatar and only height is set, height becomes the diameter and no block size is written', () => {
    fixture.componentRef.setInput('shape', 'avatar');
    fixture.componentRef.setInput('height', '32px');
    fixture.detectChanges();

    const el = placeholder();
    expect(el.style.getPropertyValue('inline-size')).toBe('32px');
    expect(el.style.getPropertyValue('block-size')).toBe('');
  });

  it('when shape is avatar with a width and a different height, width stays the only diameter', () => {
    fixture.componentRef.setInput('shape', 'avatar');
    fixture.componentRef.setInput('width', '32px');
    fixture.componentRef.setInput('height', '48px');
    fixture.detectChanges();

    const el = placeholder();
    expect(el.style.getPropertyValue('inline-size')).toBe('32px');
    expect(el.style.getPropertyValue('block-size')).toBe('');
  });

  it('when a line with a height becomes an avatar, its block size is dropped so the circle stays round', () => {
    fixture.componentRef.setInput('height', '12px');
    fixture.detectChanges();
    expect(placeholder().style.getPropertyValue('block-size')).toBe('12px');

    fixture.componentRef.setInput('shape', 'avatar');
    fixture.detectChanges();
    expect(placeholder().style.getPropertyValue('block-size')).toBe('');
  });

  // --- Tokens and motion ---

  it('when the stylesheet is attached, the shimmer runs on surface-container tokens', () => {
    const css = skeletonStylesheet();

    expect(css).toMatch(/@keyframes\s+\S*skeleton-shimmer/);
    expect(css).toMatch(/animation:\s*\S*skeleton-shimmer/);
    expect(css).toContain('var(--mat-sys-surface-container-high)');
    expect(css).toContain('var(--mat-sys-surface-container-highest)');
  });

  it('when the stylesheet is attached, each shape rule takes its own corner token', () => {
    const css = skeletonStylesheet();

    expect(cornerTokens(declarationsFor(css, isBasePlaceholderRule))).toEqual(
      new Set(['extra-small']),
    );
    expect(cornerTokens(declarationsFor(css, isShapePlaceholderRule('block')))).toEqual(
      new Set(['medium']),
    );
    expect(cornerTokens(declarationsFor(css, isShapePlaceholderRule('avatar')))).toEqual(
      new Set(['full']),
    );
  });

  it('when the user prefers reduced motion, the stylesheet turns the shimmer off', () => {
    const css = skeletonStylesheet();
    const reduced = css.match(/@media[^{]*prefers-reduced-motion:\s*reduce[^{]*\{([\s\S]*?\}\s*)\}/);

    expect(reduced).not.toBeNull();
    expect(reduced?.[1]).toMatch(/animation:\s*none/);
  });

  // --- No hardcoded colours ---

  it('when rendered, no hardcoded hex colors appear in any inline element styles', () => {
    fixture.componentRef.setInput('width', '192px');
    fixture.componentRef.setInput('height', '12px');
    fixture.detectChanges();

    const hexPattern = /#[0-9a-fA-F]{3,8}\b/;
    const allElements = [host, ...Array.from(host.querySelectorAll<HTMLElement>('*'))];
    for (const el of allElements) {
      expect(el.getAttribute('style') ?? '').not.toMatch(hexPattern);
    }
  });

  it('when the stylesheet is attached, it contains no color literals or !important', () => {
    const css = skeletonStylesheet();

    expect(css).not.toBe('');
    expect(css).not.toMatch(/#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(/);
    expect(css).not.toContain('!important');
  });
});
