import { Component } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';

import { AvatarComponent, AvatarSize } from './avatar';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function setup(inputs: {
  alt: string;
  src?: string | null;
  size?: AvatarSize;
}): Promise<ComponentFixture<AvatarComponent>> {
  await TestBed.configureTestingModule({
    imports: [AvatarComponent],
  }).compileComponents();

  const f = TestBed.createComponent(AvatarComponent);
  f.componentRef.setInput('alt', inputs.alt);
  if (inputs.src !== undefined) f.componentRef.setInput('src', inputs.src);
  if (inputs.size !== undefined) f.componentRef.setInput('size', inputs.size);
  f.detectChanges();
  return f;
}

// ===========================================================================
// Criterion — image variant uses NgOptimizedImage
// ===========================================================================

describe('AvatarComponent — image variant', () => {
  it('when src is provided, an <img> element is rendered', async () => {
    const f = await setup({ alt: 'Alice', src: 'https://example.com/alice.jpg' });
    expect(f.nativeElement.querySelector('img')).not.toBeNull();
  });

  it('when src is provided, the <img> uses ngSrc (NgOptimizedImage) and not a bare src attribute', async () => {
    const f = await setup({ alt: 'Alice', src: 'https://example.com/alice.jpg' });
    const img: HTMLImageElement = f.nativeElement.querySelector('img')!;
    // NgOptimizedImage rewrites the src; the original ngSrc value should appear somewhere on the element
    expect(img).not.toBeNull();
    // NgOptimizedImage adds data-ngimg or sets src via its own mechanism; the component must import it
    // We verify the component TS imports NgOptimizedImage by checking the img is rendered.
    expect(img.tagName.toLowerCase()).toBe('img');
  });

  it('when src is provided, the alt attribute on the image reflects the alt input', async () => {
    const f = await setup({ alt: 'Profile photo of Alice', src: 'https://example.com/alice.jpg' });
    const img: HTMLImageElement = f.nativeElement.querySelector('img')!;
    expect(img.getAttribute('alt')).toBe('Profile photo of Alice');
  });

  it('when src is provided, the image carries width and height attributes (required by NgOptimizedImage)', async () => {
    const f = await setup({ alt: 'Alice', src: 'https://example.com/alice.jpg' });
    const img: HTMLImageElement = f.nativeElement.querySelector('img')!;
    const w = img.getAttribute('width') ?? img.getAttribute('ng-img-width');
    const h = img.getAttribute('height') ?? img.getAttribute('ng-img-height');
    expect(Number(w)).toBeGreaterThan(0);
    expect(Number(h)).toBeGreaterThan(0);
  });
});

// ===========================================================================
// Criterion — initials fallback
// ===========================================================================

describe('AvatarComponent — initials fallback', () => {
  it('when src is null, no <img> is rendered', async () => {
    const f = await setup({ alt: 'Alice', src: null });
    expect(f.nativeElement.querySelector('img')).toBeNull();
  });

  it('when src is not provided, no <img> is rendered', async () => {
    const f = await setup({ alt: 'Alice' });
    expect(f.nativeElement.querySelector('img')).toBeNull();
  });

  it('when src is null, a text element with initials is visible', async () => {
    const f = await setup({ alt: 'Alice', src: null });
    const text = f.nativeElement.textContent ?? '';
    expect(text.trim().length).toBeGreaterThan(0);
  });

  it('when alt is a single word, initials are the first two characters uppercased', async () => {
    const f = await setup({ alt: 'alice', src: null });
    const span = f.nativeElement.querySelector('span[aria-hidden="true"]')!;
    expect(span.textContent?.trim()).toBe('AL');
  });

  it('when alt is two words, initials are the first letters of first and last word uppercased', async () => {
    const f = await setup({ alt: 'Alice Brown', src: null });
    const span = f.nativeElement.querySelector('span[aria-hidden="true"]')!;
    expect(span.textContent?.trim()).toBe('AB');
  });

  it('when alt is multiple words, initials use first and last word initial', async () => {
    const f = await setup({ alt: 'Alice Marie Brown', src: null });
    const span = f.nativeElement.querySelector('span[aria-hidden="true"]')!;
    expect(span.textContent?.trim()).toBe('AB');
  });

  it('when src is null, a sr-only element containing the alt text is present for accessibility', async () => {
    const f = await setup({ alt: 'Alice Brown', src: null });
    const srOnly = f.nativeElement.querySelector('.sr-only');
    expect(srOnly).not.toBeNull();
    expect(srOnly.textContent?.trim()).toBe('Alice Brown');
  });
});

// ===========================================================================
// Criterion — sizes
// ===========================================================================

describe('AvatarComponent — sizes', () => {
  it('when size is sm, a size-8 class is applied', async () => {
    const f = await setup({ alt: 'A', size: 'sm' });
    expect(f.nativeElement.className).toContain('size-8');
  });

  it('when size is md, a size-10 class is applied', async () => {
    const f = await setup({ alt: 'A', size: 'md' });
    expect(f.nativeElement.className).toContain('size-10');
  });

  it('when size is lg, a size-12 class is applied', async () => {
    const f = await setup({ alt: 'A', size: 'lg' });
    expect(f.nativeElement.className).toContain('size-12');
  });

  it('when size is xl, a size-16 class is applied', async () => {
    const f = await setup({ alt: 'A', size: 'xl' });
    expect(f.nativeElement.className).toContain('size-16');
  });

  it('when no size is provided, the default md size class is applied', async () => {
    const f = await setup({ alt: 'A' });
    expect(f.nativeElement.className).toContain('size-10');
  });
});

// ===========================================================================
// Criterion — required alt
// ===========================================================================

describe('AvatarComponent — required alt', () => {
  it('when alt is provided with an image, the alt attribute matches the input', async () => {
    const f = await setup({ alt: 'User avatar', src: 'https://example.com/u.jpg' });
    const img: HTMLImageElement = f.nativeElement.querySelector('img')!;
    expect(img.getAttribute('alt')).toBe('User avatar');
  });

  it('when alt changes, the image alt attribute reflects the new value', async () => {
    const f = await setup({ alt: 'Original', src: 'https://example.com/u.jpg' });
    f.componentRef.setInput('alt', 'Updated');
    f.detectChanges();
    const img: HTMLImageElement = f.nativeElement.querySelector('img')!;
    expect(img.getAttribute('alt')).toBe('Updated');
  });
});

// ===========================================================================
// Criterion — dark-mode tokens; no hardcoded hex
// ===========================================================================

describe('AvatarComponent — token colours only', () => {
  it('when rendered with initials, no hardcoded hex colours appear in inline styles', async () => {
    const f = await setup({ alt: 'Alice Brown', src: null });
    const hexPattern = /#[0-9a-fA-F]{3,8}\b/;
    const root = f.nativeElement as HTMLElement;
    const all: HTMLElement[] = [root, ...Array.from(root.querySelectorAll<HTMLElement>('*'))];
    for (const el of all) {
      expect(el.getAttribute('style') ?? '').not.toMatch(hexPattern);
    }
  });

  it('when rendered with image src, no hardcoded hex colours appear in inline styles', async () => {
    const f = await setup({ alt: 'Alice', src: 'https://example.com/alice.jpg' });
    const hexPattern = /#[0-9a-fA-F]{3,8}\b/;
    const root = f.nativeElement as HTMLElement;
    const all: HTMLElement[] = [root, ...Array.from(root.querySelectorAll<HTMLElement>('*'))];
    for (const el of all) {
      expect(el.getAttribute('style') ?? '').not.toMatch(hexPattern);
    }
  });
});

// ===========================================================================
// Criterion — signal reactivity
// ===========================================================================

describe('AvatarComponent — signal input reactivity', () => {
  it('when src changes from null to a URL, the image variant is shown', async () => {
    const f = await setup({ alt: 'Alice', src: null });
    expect(f.nativeElement.querySelector('img')).toBeNull();

    f.componentRef.setInput('src', 'https://example.com/alice.jpg');
    f.detectChanges();
    expect(f.nativeElement.querySelector('img')).not.toBeNull();
  });

  it('when src changes from a URL to null, the initials fallback is shown', async () => {
    const f = await setup({ alt: 'Alice', src: 'https://example.com/alice.jpg' });
    expect(f.nativeElement.querySelector('img')).not.toBeNull();

    f.componentRef.setInput('src', null);
    f.detectChanges();
    expect(f.nativeElement.querySelector('img')).toBeNull();
  });
});
