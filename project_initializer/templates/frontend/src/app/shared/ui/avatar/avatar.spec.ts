import { ComponentFixture, TestBed } from '@angular/core/testing';

import { AvatarComponent, AvatarSize } from './avatar';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function setup(inputs: {
  alt: string;
  src?: string | null;
  size?: AvatarSize;
  decorative?: boolean;
}): Promise<ComponentFixture<AvatarComponent>> {
  await TestBed.configureTestingModule({
    imports: [AvatarComponent],
  }).compileComponents();

  const f = TestBed.createComponent(AvatarComponent);
  f.componentRef.setInput('alt', inputs.alt);
  if (inputs.src !== undefined) f.componentRef.setInput('src', inputs.src);
  if (inputs.size !== undefined) f.componentRef.setInput('size', inputs.size);
  if (inputs.decorative !== undefined) f.componentRef.setInput('decorative', inputs.decorative);
  f.detectChanges();
  return f;
}

function host(f: ComponentFixture<AvatarComponent>): HTMLElement {
  return f.nativeElement as HTMLElement;
}

/** NgOptimizedImage fill mode: no fixed width/height, absolutely positioned over the host. */
function expectFillMode(img: HTMLImageElement): void {
  expect(img.hasAttribute('fill')).toBe(true);
  expect(img.hasAttribute('width')).toBe(false);
  expect(img.hasAttribute('height')).toBe(false);
  expect(img.style.position).toBe('absolute');
  expect(img.style.width).toBe('100%');
  expect(img.style.height).toBe('100%');
}

// ===========================================================================
// Criterion — image variant uses NgOptimizedImage
// ===========================================================================

describe('AvatarComponent — image variant', () => {
  it('when src is provided, an <img> element is rendered', async () => {
    const f = await setup({ alt: 'Alice', src: 'https://example.com/alice.jpg' });
    expect(host(f).querySelector('img')).not.toBeNull();
  });

  it('when src is provided, the <img> is driven by ngSrc (NgOptimizedImage) and loads the given URL', async () => {
    const f = await setup({ alt: 'Alice', src: 'https://example.com/alice.jpg' });
    const img = host(f).querySelector('img')!;
    expect(img.tagName.toLowerCase()).toBe('img');
    // NgOptimizedImage writes the resolved URL to the native src attribute itself.
    expect(img.getAttribute('src')).toContain('example.com/alice.jpg');
    expect(img.getAttribute('ng-img')).toBe('true');
  });

  it('when src is provided, the alt attribute on the image names the person', async () => {
    const f = await setup({ alt: 'Alice Brown', src: 'https://example.com/alice.jpg' });
    const img = host(f).querySelector('img')!;
    expect(img.getAttribute('alt')).toBe('Alice Brown');
  });

  it('when src is provided, the image uses NgOptimizedImage fill mode instead of fixed width and height', async () => {
    const f = await setup({ alt: 'Alice', src: 'https://example.com/alice.jpg' });
    expectFillMode(host(f).querySelector('img')!);
  });

  it('when an image is shown, the host is not marked as the initials variant', async () => {
    const f = await setup({ alt: 'Alice', src: 'https://example.com/alice.jpg' });
    expect(host(f).classList.contains('app-avatar--initials')).toBe(false);
  });

  it('when src is an empty string, the initials fallback is shown instead of a broken image', async () => {
    const f = await setup({ alt: 'Alice Brown', src: '' });
    expect(host(f).querySelector('img')).toBeNull();
    expect(host(f).querySelector('.initials')?.textContent?.trim()).toBe('AB');
  });
});

// ===========================================================================
// Criterion — image load failure falls back to initials
// ===========================================================================

describe('AvatarComponent — image load failure', () => {
  it('when the image fails to load, the initials fallback replaces it', async () => {
    const f = await setup({ alt: 'Alice Brown', src: 'https://example.com/missing.jpg' });
    host(f).querySelector('img')!.dispatchEvent(new Event('error'));
    f.detectChanges();

    expect(host(f).querySelector('img')).toBeNull();
    expect(host(f).querySelector('.initials')?.textContent?.trim()).toBe('AB');
    expect(host(f).classList.contains('app-avatar--initials')).toBe(true);
  });

  it('when src changes after a failure, the new image is tried again', async () => {
    const f = await setup({ alt: 'Alice Brown', src: 'https://example.com/missing.jpg' });
    host(f).querySelector('img')!.dispatchEvent(new Event('error'));
    f.detectChanges();
    expect(host(f).querySelector('img')).toBeNull();

    f.componentRef.setInput('src', 'https://example.com/alice.jpg');
    f.detectChanges();
    expect(host(f).querySelector('img')).not.toBeNull();
  });
});

// ===========================================================================
// Criterion — inline (data: / blob:) URLs, which NgOptimizedImage rejects
// ===========================================================================

describe('AvatarComponent — inline image URLs', () => {
  const inlineUrls: [string, string][] = [
    ['data:', 'data:image/png;base64,iVBORw0KGgo='],
    ['blob:', 'blob:https://example.com/0b8f5a2e-1c3d-4e5f-8a9b-0c1d2e3f4a5b'],
  ];

  for (const [scheme, url] of inlineUrls) {
    // In dev mode NgOptimizedImage throws NG02952 from ngOnInit for both schemes, so setup() would throw.
    it(`when src is a ${scheme} URL, a plain <img> shows it without NgOptimizedImage`, async () => {
      const f = await setup({ alt: 'Alice Brown', src: url });
      const img = host(f).querySelector('img')!;

      expect(img).not.toBeNull();
      expect(img.hasAttribute('ng-img')).toBe(false);
      expect(img.getAttribute('src')).toBe(url);
      expect(img.getAttribute('alt')).toBe('Alice Brown');
      expect(img.classList).toContain('image-inline');
      expect(host(f).classList.contains('app-avatar--initials')).toBe(false);
    });
  }

  it('when an ordinary URL changes to a data: URL, the photo switches to a plain <img> without an error', async () => {
    const f = await setup({ alt: 'Alice Brown', src: 'https://example.com/alice.jpg' });
    expect(host(f).querySelector('img')!.getAttribute('ng-img')).toBe('true');

    f.componentRef.setInput('src', inlineUrls[0][1]);
    expect(() => f.detectChanges()).not.toThrow();

    const img = host(f).querySelector('img')!;
    expect(img.hasAttribute('ng-img')).toBe(false);
    expect(img.getAttribute('src')).toBe(inlineUrls[0][1]);
  });

  it('when an inline image fails to load, the initials fallback replaces it', async () => {
    const f = await setup({ alt: 'Alice Brown', src: inlineUrls[1][1] });
    host(f).querySelector('img')!.dispatchEvent(new Event('error'));
    f.detectChanges();

    expect(host(f).querySelector('img')).toBeNull();
    expect(host(f).querySelector('.initials')?.textContent?.trim()).toBe('AB');
  });

  it('when decorative with an inline image, the image gets an empty alt', async () => {
    const f = await setup({ alt: 'Alice', src: inlineUrls[0][1], decorative: true });
    expect(host(f).querySelector('img')!.getAttribute('alt')).toBe('');
  });
});

// ===========================================================================
// Criterion — initials fallback
// ===========================================================================

describe('AvatarComponent — initials fallback', () => {
  it('when src is null, no <img> is rendered', async () => {
    const f = await setup({ alt: 'Alice', src: null });
    expect(host(f).querySelector('img')).toBeNull();
  });

  it('when src is not provided, no <img> is rendered', async () => {
    const f = await setup({ alt: 'Alice' });
    expect(host(f).querySelector('img')).toBeNull();
  });

  it('when src is null, a text element with initials is visible', async () => {
    const f = await setup({ alt: 'Alice', src: null });
    const text = host(f).textContent ?? '';
    expect(text.trim().length).toBeGreaterThan(0);
  });

  it('when src is null, the host is marked as the initials variant (primary-container styling)', async () => {
    const f = await setup({ alt: 'Alice', src: null });
    expect(host(f).classList.contains('app-avatar--initials')).toBe(true);
  });

  it('when alt is a single word, initials are the first two characters uppercased', async () => {
    const f = await setup({ alt: 'alice', src: null });
    const span = host(f).querySelector('span[aria-hidden="true"]')!;
    expect(span.textContent?.trim()).toBe('AL');
  });

  it('when alt is two words, initials are the first letters of first and last word uppercased', async () => {
    const f = await setup({ alt: 'Alice Brown', src: null });
    const span = host(f).querySelector('span[aria-hidden="true"]')!;
    expect(span.textContent?.trim()).toBe('AB');
  });

  it('when alt is multiple words, initials use first and last word initial', async () => {
    const f = await setup({ alt: 'Alice Marie Brown', src: null });
    const span = host(f).querySelector('span[aria-hidden="true"]')!;
    expect(span.textContent?.trim()).toBe('AB');
  });

  it('when alt has surrounding whitespace, initials ignore it', async () => {
    const f = await setup({ alt: '  alice   brown ', src: null });
    expect(f.componentInstance.initials()).toBe('AB');
  });

  it('when alt starts with a character outside the BMP, the initial is not split into a broken surrogate', async () => {
    const f = await setup({ alt: '\u{1D400}lpha Beta', src: null });
    expect(f.componentInstance.initials()).toBe('\u{1D400}B');
  });

  it('when src is null, a visually hidden element containing the alt text is present for accessibility', async () => {
    const f = await setup({ alt: 'Alice Brown', src: null });
    const hidden = host(f).querySelector('.cdk-visually-hidden');
    expect(hidden).not.toBeNull();
    expect(hidden!.textContent?.trim()).toBe('Alice Brown');
  });

  it('when src is null, the visible initials are hidden from assistive technology', async () => {
    const f = await setup({ alt: 'Alice Brown', src: null });
    expect(host(f).querySelector('.initials')!.getAttribute('aria-hidden')).toBe('true');
  });
});

// ===========================================================================
// Criterion — decorative avatar (visible name beside it)
// ===========================================================================

describe('AvatarComponent — decorative', () => {
  it('by default, the avatar is not decorative', async () => {
    const f = await setup({ alt: 'Alice' });
    expect(f.componentInstance.decorative()).toBe(false);
  });

  it('when decorative with an image, the image gets an empty alt so it is skipped by screen readers', async () => {
    const f = await setup({ alt: 'Alice', src: 'https://example.com/alice.jpg', decorative: true });
    const img = host(f).querySelector('img')!;
    expect(img.hasAttribute('alt')).toBe(true);
    expect(img.getAttribute('alt')).toBe('');
  });

  it('when decorative with initials, no visually hidden name is rendered', async () => {
    const f = await setup({ alt: 'Alice Brown', src: null, decorative: true });
    expect(host(f).querySelector('.cdk-visually-hidden')).toBeNull();
    expect(host(f).querySelector('.initials')?.textContent?.trim()).toBe('AB');
  });

  it('when decorative is set through a template attribute, the boolean attribute transform applies', async () => {
    const f = await setup({ alt: 'Alice', src: null });
    f.componentRef.setInput('decorative', '');
    f.detectChanges();
    expect(f.componentInstance.decorative()).toBe(true);
  });
});

// ===========================================================================
// Criterion — sizes (px on the 4px grid)
// ===========================================================================

describe('AvatarComponent — sizes', () => {
  const cases: [AvatarSize, number][] = [
    ['sm', 32],
    ['md', 40],
    ['lg', 48],
    ['xl', 64],
  ];

  for (const [size, px] of cases) {
    it(`when size is ${size}, the host exposes data-size="${size}" and a ${px}px diameter`, async () => {
      const f = await setup({ alt: 'A', size });
      expect(host(f).getAttribute('data-size')).toBe(size);
      expect(f.componentInstance.sizePx()).toBe(px);
      expect(px % 4).toBe(0);
    });

    it(`when size is ${size} with an image, the image fills the host instead of fixing its own size`, async () => {
      const f = await setup({ alt: 'A', src: 'https://example.com/a.jpg', size });
      expect(host(f).getAttribute('data-size')).toBe(size);
      expectFillMode(host(f).querySelector('img')!);
    });
  }

  it('when no size is provided, the default md size is applied', async () => {
    const f = await setup({ alt: 'A' });
    expect(host(f).getAttribute('data-size')).toBe('md');
    expect(f.componentInstance.sizePx()).toBe(40);
  });

  it('when size changes, the data-size attribute follows', async () => {
    const f = await setup({ alt: 'A', size: 'sm' });
    f.componentRef.setInput('size', 'xl');
    f.detectChanges();
    expect(host(f).getAttribute('data-size')).toBe('xl');
  });

  it('when size changes on a photo avatar, the same image stays and NgOptimizedImage raises no error', async () => {
    const f = await setup({ alt: 'Alice Brown', src: 'https://example.com/alice.jpg', size: 'sm' });
    const img = host(f).querySelector('img')!;

    f.componentRef.setInput('size', 'xl');
    expect(() => f.detectChanges()).not.toThrow();
    await f.whenStable();

    expect(host(f).getAttribute('data-size')).toBe('xl');
    expect(host(f).querySelector('img')).toBe(img);
    expectFillMode(img);
  });

  it('the host carries only its own avatar classes (no utility classes)', async () => {
    const withInitials = await setup({ alt: 'A', size: 'lg' });
    expect(Array.from(host(withInitials).classList).sort()).toEqual(
      ['app-avatar', 'app-avatar--initials'],
    );

    withInitials.componentRef.setInput('src', 'https://example.com/a.jpg');
    withInitials.detectChanges();
    expect(Array.from(host(withInitials).classList)).toEqual(['app-avatar']);
  });
});

// ===========================================================================
// Criterion — required alt
// ===========================================================================

describe('AvatarComponent — required alt', () => {
  it('when alt is provided with an image, the alt attribute matches the input', async () => {
    const f = await setup({ alt: 'Alice Brown', src: 'https://example.com/alice.jpg' });
    const img = host(f).querySelector('img')!;
    expect(img.getAttribute('alt')).toBe('Alice Brown');
  });

  it('when alt changes, the image alt attribute reflects the new value', async () => {
    const f = await setup({ alt: 'Alice Brown', src: 'https://example.com/alice.jpg' });
    f.componentRef.setInput('alt', 'Alice Smith');
    f.detectChanges();
    const img = host(f).querySelector('img')!;
    expect(img.getAttribute('alt')).toBe('Alice Smith');
  });
});

// ===========================================================================
// Criterion — token colours only; no hardcoded colour literals
// ===========================================================================

describe('AvatarComponent — token colours only', () => {
  const literal = /#[0-9a-fA-F]{3,8}\b|\b(rgb|rgba|hsl|hsla)\(/;

  it('when rendered with initials, no hardcoded colours appear in inline styles', async () => {
    const f = await setup({ alt: 'Alice Brown', src: null });
    const root = host(f);
    const all: HTMLElement[] = [root, ...Array.from(root.querySelectorAll<HTMLElement>('*'))];
    for (const el of all) {
      expect(el.getAttribute('style') ?? '').not.toMatch(literal);
    }
  });

  it('when rendered with image src, no hardcoded colours appear in inline styles', async () => {
    const f = await setup({ alt: 'Alice', src: 'https://example.com/alice.jpg' });
    const root = host(f);
    const all: HTMLElement[] = [root, ...Array.from(root.querySelectorAll<HTMLElement>('*'))];
    for (const el of all) {
      expect(el.getAttribute('style') ?? '').not.toMatch(literal);
    }
  });
});

// ===========================================================================
// Criterion — signal reactivity
// ===========================================================================

describe('AvatarComponent — signal input reactivity', () => {
  it('when src changes from null to a URL, the image variant is shown', async () => {
    const f = await setup({ alt: 'Alice', src: null });
    expect(host(f).querySelector('img')).toBeNull();

    f.componentRef.setInput('src', 'https://example.com/alice.jpg');
    f.detectChanges();
    expect(host(f).querySelector('img')).not.toBeNull();
  });

  it('when src changes from a URL to null, the initials fallback is shown', async () => {
    const f = await setup({ alt: 'Alice', src: 'https://example.com/alice.jpg' });
    expect(host(f).querySelector('img')).not.toBeNull();

    f.componentRef.setInput('src', null);
    f.detectChanges();
    expect(host(f).querySelector('img')).toBeNull();
  });
});
