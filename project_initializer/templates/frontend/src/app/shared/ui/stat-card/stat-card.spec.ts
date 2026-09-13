import { ComponentFixture, TestBed } from '@angular/core/testing';
import { TestbedHarnessEnvironment } from '@angular/cdk/testing/testbed';
import { MatCardHarness } from '@angular/material/card/testing';

import { ICON_PROVIDER } from '../../../icons';
import { StatCardComponent, DeltaDirection } from './stat-card';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function setup(inputs: {
  metric: string;
  label: string;
  delta?: string | null;
  deltaDirection?: DeltaDirection;
}): Promise<ComponentFixture<StatCardComponent>> {
  await TestBed.configureTestingModule({
    imports: [StatCardComponent],
    providers: [ICON_PROVIDER],
  }).compileComponents();

  const f = TestBed.createComponent(StatCardComponent);
  f.componentRef.setInput('metric', inputs.metric);
  f.componentRef.setInput('label', inputs.label);
  if (inputs.delta !== undefined) f.componentRef.setInput('delta', inputs.delta);
  if (inputs.deltaDirection !== undefined) f.componentRef.setInput('deltaDirection', inputs.deltaDirection);
  f.detectChanges();
  return f;
}

function root(f: ComponentFixture<StatCardComponent>): HTMLElement {
  return f.nativeElement as HTMLElement;
}

function deltaElement(f: ComponentFixture<StatCardComponent>): HTMLElement | null {
  return root(f).querySelector<HTMLElement>('.stat-card-delta');
}

/** Text as a screen reader reads it: every text node, whitespace collapsed. */
function readText(el: Element | null): string {
  return (el?.textContent ?? '').replace(/\s+/g, ' ').trim();
}

/**
 * The color declaration stat-card.css applies to the element. jsdom matches the component's scoped rules but
 * does not resolve `var()`, so this is the token reference itself, e.g. `var(--app-success)`.
 */
function colorRole(el: Element): string {
  return getComputedStyle(el).color;
}

// ===========================================================================
// Criterion — metric is rendered
// ===========================================================================

describe('StatCardComponent — metric', () => {
  it('when created, the component renders without error', async () => {
    const f = await setup({ metric: '1,234', label: 'Users' });
    expect(f.componentInstance).toBeTruthy();
  });

  it('when metric is provided, it appears in the rendered output', async () => {
    const f = await setup({ metric: '42,000', label: 'Sessions' });
    expect(f.nativeElement.textContent).toContain('42,000');
  });

  it('when metric changes, the new value is rendered', async () => {
    const f = await setup({ metric: '100', label: 'Views' });
    f.componentRef.setInput('metric', '200');
    f.detectChanges();
    expect(f.nativeElement.textContent).toContain('200');
    expect(f.nativeElement.textContent).not.toContain('100');
  });
});

// ===========================================================================
// Criterion — label is rendered
// ===========================================================================

describe('StatCardComponent — label', () => {
  it('when label is provided, it appears in the rendered output', async () => {
    const f = await setup({ metric: '99', label: 'Active users' });
    expect(f.nativeElement.textContent).toContain('Active users');
  });

  it('when label changes, the new value is rendered', async () => {
    const f = await setup({ metric: '1', label: 'Old label' });
    f.componentRef.setInput('label', 'New label');
    f.detectChanges();
    expect(f.nativeElement.textContent).toContain('New label');
    expect(f.nativeElement.textContent).not.toContain('Old label');
  });

  it('when rendered, the label is read before the metric and the delta', async () => {
    const f = await setup({ metric: '1,284', label: 'Active users', delta: '+12%', deltaDirection: 'up' });
    const label = root(f).querySelector('.stat-card-label')!;
    const metric = root(f).querySelector('.stat-card-metric')!;
    const delta = deltaElement(f)!;

    expect(readText(label)).toBe('Active users');
    expect(readText(metric)).toBe('1,284');
    expect(label.compareDocumentPosition(metric) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(metric.compareDocumentPosition(delta) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });
});

// ===========================================================================
// Criterion — delta with directional color, backed by an icon and text
// ===========================================================================

describe('StatCardComponent — delta', () => {
  it('when delta is null, no delta element is rendered', async () => {
    const f = await setup({ metric: '10', label: 'Sales', delta: null });
    expect(deltaElement(f)).toBeNull();
    expect(root(f).querySelector('lucide-icon')).toBeNull();
  });

  it('when delta is an empty string, no delta element is rendered', async () => {
    const f = await setup({ metric: '10', label: 'Sales', delta: '', deltaDirection: 'up' });
    expect(deltaElement(f)).toBeNull();
  });

  it('when delta is provided, the delta text appears in the rendered output', async () => {
    const f = await setup({ metric: '500', label: 'Revenue', delta: '+12%', deltaDirection: 'up' });
    expect(f.nativeElement.textContent).toContain('+12%');
  });

  // Object form with named placeholders, so the title can never drift from the row's field order.
  it.each<{ direction: DeltaDirection; delta: string; iconClass: string; word: string; role: string }>([
    { direction: 'up', delta: '+5%', iconClass: 'lucide-ChevronUp', word: 'Up', role: 'var(--app-success)' },
    { direction: 'down', delta: '-3%', iconClass: 'lucide-ChevronDown', word: 'Down', role: 'var(--mat-sys-error)' },
  ])(
    'when deltaDirection is $direction with delta $delta, the delta is colored $role and backed by the $iconClass icon and the hidden word $word',
    async ({ direction, delta, iconClass, word, role }) => {
      const f = await setup({ metric: '300', label: 'Revenue', delta, deltaDirection: direction });
      const el = deltaElement(f)!;

      // The direction attribute selects the color role in stat-card.css.
      expect(el.getAttribute('data-direction')).toBe(direction);
      expect(colorRole(el)).toBe(role);
      // The icon shape and the hidden word back up the color.
      expect(el.querySelector('.stat-card-delta-icon svg')?.classList).toContain(iconClass);
      expect(readText(el.querySelector('.cdk-visually-hidden'))).toBe(word);
      expect(readText(el)).toBe(`${word} ${delta}`);
    },
  );

  it('when deltaDirection is neutral, the delta is on-surface-variant with no icon and no direction word', async () => {
    const f = await setup({ metric: '100', label: 'Score', delta: '0%', deltaDirection: 'neutral' });
    const el = deltaElement(f)!;

    expect(el.getAttribute('data-direction')).toBe('neutral');
    expect(colorRole(el)).toBe('var(--mat-sys-on-surface-variant)');
    expect(el.querySelector('lucide-icon')).toBeNull();
    expect(el.querySelector('.cdk-visually-hidden')).toBeNull();
    expect(readText(el)).toBe('0%');
  });

  it('when deltaDirection is not set, the delta renders as neutral', async () => {
    const f = await setup({ metric: '100', label: 'Score', delta: '0%' });
    expect(deltaElement(f)!.getAttribute('data-direction')).toBe('neutral');
    expect(colorRole(deltaElement(f)!)).toBe('var(--mat-sys-on-surface-variant)');
    expect(f.componentInstance.deltaIcon()).toBeNull();
    expect(f.componentInstance.deltaLabel()).toBe('');
  });

  it('when deltaDirection is outside DeltaDirection at runtime, the delta falls back to neutral', async () => {
    const f = await setup({ metric: '100', label: 'Score', delta: '1%' });
    f.componentRef.setInput('deltaDirection', 'sideways' as DeltaDirection);
    f.detectChanges();

    expect(f.componentInstance.resolvedDirection()).toBe('neutral');
    expect(deltaElement(f)!.getAttribute('data-direction')).toBe('neutral');
    expect(colorRole(deltaElement(f)!)).toBe('var(--mat-sys-on-surface-variant)');
    expect(deltaElement(f)!.querySelector('lucide-icon')).toBeNull();
  });

  it('when a direction icon renders, it is hidden from assistive technology', async () => {
    const f = await setup({ metric: '500', label: 'Revenue', delta: '+12%', deltaDirection: 'up' });
    const icon = deltaElement(f)!.querySelector('lucide-icon')!;
    expect(icon.getAttribute('aria-hidden')).toBe('true');
  });

  it('when deltaDirection changes from up to down, the down icon, word, direction and error role replace the up ones', async () => {
    const f = await setup({ metric: '10', label: 'Rate', delta: '2%', deltaDirection: 'up' });
    expect(colorRole(deltaElement(f)!)).toBe('var(--app-success)');

    f.componentRef.setInput('deltaDirection', 'down' as DeltaDirection);
    f.detectChanges();
    const el = deltaElement(f)!;

    expect(el.getAttribute('data-direction')).toBe('down');
    expect(colorRole(el)).toBe('var(--mat-sys-error)');
    expect(el.querySelector('svg.lucide-ChevronUp')).toBeNull();
    expect(el.querySelector('svg.lucide-ChevronDown')).not.toBeNull();
    expect(readText(el)).toBe('Down 2%');
  });

  it('when delta is cleared after being shown, the delta element is removed', async () => {
    const f = await setup({ metric: '10', label: 'Rate', delta: '2%', deltaDirection: 'up' });
    f.componentRef.setInput('delta', null);
    f.detectChanges();
    expect(deltaElement(f)).toBeNull();
  });
});

// ===========================================================================
// Criterion — built on Card (app-card → mat-card in DOM)
// ===========================================================================

describe('StatCardComponent — built on Card', () => {
  it('when rendered, the component contains an app-card element', async () => {
    const f = await setup({ metric: '42', label: 'Items' });
    expect(f.nativeElement.querySelector('app-card')).not.toBeNull();
  });

  it('when rendered, the label and metric sit inside a Material card', async () => {
    const f = await setup({ metric: '42', label: 'Items', delta: '+1', deltaDirection: 'up' });
    const card = await TestbedHarnessEnvironment.loader(f).getHarness(MatCardHarness);
    const text = await card.getText();

    expect(text).toContain('Items');
    expect(text).toContain('42');
    expect(text).toContain('+1');
  });

  it('when rendered, the tile has no interactive elements', async () => {
    const f = await setup({ metric: '42', label: 'Items', delta: '+1', deltaDirection: 'up' });
    expect(root(f).querySelector('button, a[href], input, [tabindex]')).toBeNull();
  });
});

// ===========================================================================
// Criterion — dark-mode tokens; no hardcoded hex
// ===========================================================================

describe('StatCardComponent — token colours only', () => {
  it('when rendered, no hardcoded hex colours appear in inline element styles', async () => {
    const f = await setup({ metric: '5', label: 'Items', delta: '+1', deltaDirection: 'up' });
    const hexPattern = /#[0-9a-fA-F]{3,8}\b/;
    const all: HTMLElement[] = [root(f), ...Array.from(root(f).querySelectorAll<HTMLElement>('*'))];
    for (const el of all) {
      expect(el.getAttribute('style') ?? '').not.toMatch(hexPattern);
    }
  });
});
