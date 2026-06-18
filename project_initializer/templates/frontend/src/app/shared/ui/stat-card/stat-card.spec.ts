import { ComponentFixture, TestBed } from '@angular/core/testing';

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
  }).compileComponents();

  const f = TestBed.createComponent(StatCardComponent);
  f.componentRef.setInput('metric', inputs.metric);
  f.componentRef.setInput('label', inputs.label);
  if (inputs.delta !== undefined) f.componentRef.setInput('delta', inputs.delta);
  if (inputs.deltaDirection !== undefined) f.componentRef.setInput('deltaDirection', inputs.deltaDirection);
  f.detectChanges();
  return f;
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
});

// ===========================================================================
// Criterion — delta with directional color
// ===========================================================================

describe('StatCardComponent — delta', () => {
  it('when delta is null, no delta element is rendered', async () => {
    const f = await setup({ metric: '10', label: 'Sales', delta: null });
    // Should have metric + label but no delta token classes
    const el = f.nativeElement as HTMLElement;
    const textEl = Array.from(el.querySelectorAll<HTMLElement>('span'))
      .find(s => s.className.includes('text-success') || s.className.includes('text-danger'));
    expect(textEl).toBeUndefined();
  });

  it('when delta is provided, the delta text appears in the rendered output', async () => {
    const f = await setup({ metric: '500', label: 'Revenue', delta: '+12%', deltaDirection: 'up' });
    expect(f.nativeElement.textContent).toContain('+12%');
  });

  it('when deltaDirection is up, the success token class is applied to the delta element', async () => {
    const f = await setup({ metric: '500', label: 'Revenue', delta: '5%', deltaDirection: 'up' });
    const el = f.nativeElement as HTMLElement;
    const deltaEl = Array.from(el.querySelectorAll<HTMLElement>('span'))
      .find(s => s.className.includes('text-success'));
    expect(deltaEl).not.toBeUndefined();
  });

  it('when deltaDirection is down, the danger token class is applied to the delta element', async () => {
    const f = await setup({ metric: '300', label: 'Revenue', delta: '-3%', deltaDirection: 'down' });
    const el = f.nativeElement as HTMLElement;
    const deltaEl = Array.from(el.querySelectorAll<HTMLElement>('span'))
      .find(s => s.className.includes('text-danger'));
    expect(deltaEl).not.toBeUndefined();
  });

  it('when deltaDirection is neutral, the secondary token class is applied to the delta element', async () => {
    const f = await setup({ metric: '100', label: 'Score', delta: '0%', deltaDirection: 'neutral' });
    const el = f.nativeElement as HTMLElement;
    const deltaEl = Array.from(el.querySelectorAll<HTMLElement>('span'))
      .find(s => s.className.includes('text-text-secondary'));
    expect(deltaEl).not.toBeUndefined();
  });

  it('when deltaDirection changes from up to down, the danger class replaces the success class', async () => {
    const f = await setup({ metric: '10', label: 'Rate', delta: '2%', deltaDirection: 'up' });
    f.componentRef.setInput('deltaDirection', 'down' as DeltaDirection);
    f.detectChanges();
    const el = f.nativeElement as HTMLElement;
    const successEl = Array.from(el.querySelectorAll<HTMLElement>('span'))
      .find(s => s.className.includes('text-success'));
    const dangerEl = Array.from(el.querySelectorAll<HTMLElement>('span'))
      .find(s => s.className.includes('text-danger'));
    expect(successEl).toBeUndefined();
    expect(dangerEl).not.toBeUndefined();
  });
});

// ===========================================================================
// Criterion — built on Card (app-card in DOM)
// ===========================================================================

describe('StatCardComponent — built on Card', () => {
  it('when rendered, the component contains an app-card element', async () => {
    const f = await setup({ metric: '42', label: 'Items' });
    expect(f.nativeElement.querySelector('app-card')).not.toBeNull();
  });
});

// ===========================================================================
// Criterion — container-query aware (@container class)
// ===========================================================================

describe('StatCardComponent — container-query aware', () => {
  it('when rendered, the inner layout carries @container class', async () => {
    const f = await setup({ metric: '99', label: 'Views' });
    const el = f.nativeElement as HTMLElement;
    const containerEl = el.querySelector('[class*="@container"]');
    expect(containerEl).not.toBeNull();
  });
});

// ===========================================================================
// Criterion — dark-mode tokens; no hardcoded hex
// ===========================================================================

describe('StatCardComponent — token colours only', () => {
  it('when rendered, no hardcoded hex colours appear in inline element styles', async () => {
    const f = await setup({ metric: '5', label: 'Items', delta: '+1', deltaDirection: 'up' });
    const hexPattern = /#[0-9a-fA-F]{3,8}\b/;
    const root = f.nativeElement as HTMLElement;
    const all: HTMLElement[] = [root, ...Array.from(root.querySelectorAll<HTMLElement>('*'))];
    for (const el of all) {
      expect(el.getAttribute('style') ?? '').not.toMatch(hexPattern);
    }
  });
});
