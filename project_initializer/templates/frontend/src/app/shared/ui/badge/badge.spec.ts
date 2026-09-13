import { ChangeDetectionStrategy, Component, signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';

import { ICON_PROVIDER } from '../../../icons';
import { BadgeComponent, BadgeVariant } from './badge';

@Component({
  imports: [BadgeComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<app-badge [variant]="variant()">{{ text() }}</app-badge>`,
})
class BadgeHostComponent {
  readonly variant = signal<BadgeVariant>('default');
  readonly text = signal('Paid');
}

const VARIANTS: BadgeVariant[] = ['default', 'primary', 'info', 'success', 'warning', 'danger'];

/** The badge's compiled component stylesheet, as Angular attached it to the document. */
function badgeStylesheet(): string {
  return Array.from(document.querySelectorAll('style'))
    .map((style) => style.textContent ?? '')
    .filter((css) => css.includes('app-badge--with-icon'))
    .join('\n');
}

/** Declarations of the `:host([data-variant='<variant>'])` rule. */
function variantRule(variant: BadgeVariant): string {
  const pattern = new RegExp(`\\[data-variant=['"]?${variant}['"]?\\][^{]*\\{([^}]*)\\}`);
  return badgeStylesheet().match(pattern)?.[1] ?? '';
}

describe('BadgeComponent', () => {
  let fixture: ComponentFixture<BadgeHostComponent>;
  let host: HTMLElement;

  function badge(): HTMLElement {
    return host.querySelector<HTMLElement>('app-badge')!;
  }

  async function setVariant(variant: BadgeVariant): Promise<void> {
    fixture.componentInstance.variant.set(variant);
    fixture.detectChanges();
    await fixture.whenStable();
  }

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [BadgeHostComponent],
      providers: [ICON_PROVIDER],
    }).compileComponents();

    fixture = TestBed.createComponent(BadgeHostComponent);
    host = fixture.nativeElement;
    fixture.detectChanges();
    await fixture.whenStable();
  });

  // --- Structural ---

  it('when created, the component renders without error', () => {
    expect(badge()).toBeTruthy();
    expect(badge().classList).toContain('app-badge');
  });

  it('when content is projected, the text renders inside the label', () => {
    expect(badge().querySelector('.label')?.textContent?.trim()).toBe('Paid');
  });

  it('when no variant is bound, the default variant is used', () => {
    const standalone = TestBed.createComponent(BadgeComponent);
    standalone.detectChanges();

    expect(standalone.nativeElement.getAttribute('data-variant')).toBe('default');
  });

  it.each(VARIANTS)('when variant is %s, the host reflects it as data-variant', async (variant) => {
    await setVariant(variant);

    expect(badge().getAttribute('data-variant')).toBe(variant);
  });

  // --- Status never by color alone ---

  it.each([
    ['info', 'lucide-info'],
    ['success', 'lucide-circle-check-big'],
    ['warning', 'lucide-triangle-alert'],
    ['danger', 'lucide-circle-alert'],
  ] as const)('when variant is %s, a distinct %s status icon leads the label', async (variant, iconClass) => {
    await setVariant(variant);

    const icon = badge().querySelector('lucide-icon');
    expect(icon).not.toBeNull();
    expect(icon!.querySelector('svg')?.classList).toContain(iconClass);
    expect(badge().classList).toContain('app-badge--with-icon');
    expect(badge().firstElementChild).toBe(icon);
  });

  it.each(['default', 'primary'] as const)(
    'when variant is %s, no status icon renders',
    async (variant) => {
      await setVariant(variant);

      expect(badge().querySelector('lucide-icon')).toBeNull();
      expect(badge().classList).not.toContain('app-badge--with-icon');
    },
  );

  it('when the variant changes from a status to default, the icon is removed', async () => {
    await setVariant('warning');
    expect(badge().querySelector('lucide-icon')).not.toBeNull();

    await setVariant('default');
    expect(badge().querySelector('lucide-icon')).toBeNull();
  });

  // --- Accessibility ---

  it('when a status icon renders, it is hidden from assistive technology', async () => {
    await setVariant('success');

    expect(badge().querySelector('lucide-icon')?.getAttribute('aria-hidden')).toBe('true');
    expect(badge().textContent?.trim()).toBe('Paid');
  });

  it('when rendered, the badge is plain text: no live region and nothing focusable', async () => {
    for (const variant of VARIANTS) {
      await setVariant(variant);

      expect(badge().hasAttribute('role')).toBe(false);
      expect(badge().querySelector('[role]')).toBeNull();
      expect(badge().hasAttribute('tabindex')).toBe(false);
      expect(badge().querySelector('button, a[href], input, [tabindex]')).toBeNull();
    }
  });

  // --- Criterion: variant via tokens ---

  it('when the stylesheet is attached, the default badge uses the neutral container pair and label type', () => {
    const css = badgeStylesheet();

    expect(css).toContain('var(--mat-sys-surface-container-highest)');
    expect(css).toContain('var(--mat-sys-on-surface-variant)');
    expect(css).toContain('var(--mat-sys-label-medium)');
    expect(css).toContain('var(--mat-sys-label-medium-tracking)');
    expect(css).toContain('var(--mat-sys-corner-full)');
  });

  it.each([
    ['primary', '--mat-sys-primary-container', '--mat-sys-on-primary-container'],
    ['info', '--app-info-container', '--app-on-info-container'],
    ['success', '--app-success-container', '--app-on-success-container'],
    ['warning', '--app-warning-container', '--app-on-warning-container'],
    ['danger', '--mat-sys-error-container', '--mat-sys-on-error-container'],
  ] as const)(
    'when variant is %s, its rule paints the %s / on-container token pair',
    (variant, container, onContainer) => {
      const rule = variantRule(variant);

      expect(rule).toContain(`var(${container})`);
      expect(rule).toContain(`var(${onContainer})`);
    },
  );

  // --- Text resizing ---

  it('when the stylesheet is attached, the label wraps long words without collapsing to one glyph', () => {
    const labelRule = badgeStylesheet().match(/\.label[^{]*\{([^}]*)\}/)?.[1] ?? '';

    expect(labelRule).toMatch(/overflow-wrap:\s*break-word/);
    expect(labelRule).not.toContain('anywhere');
  });

  // --- No hardcoded colours ---

  it('when rendered, no hardcoded hex colors appear in any inline element styles', () => {
    const hexPattern = /#[0-9a-fA-F]{3,8}\b/;
    const allElements = [host, ...Array.from(host.querySelectorAll<HTMLElement>('*'))];
    for (const el of allElements) {
      expect(el.getAttribute('style') ?? '').not.toMatch(hexPattern);
    }
  });

  it('when the stylesheet is attached, it contains no color literals', () => {
    const css = badgeStylesheet();

    expect(css).not.toBe('');
    expect(css).not.toMatch(/#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(/);
    expect(css).not.toContain('!important');
  });
});
