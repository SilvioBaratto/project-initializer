import { HarnessLoader } from '@angular/cdk/testing';
import { TestbedHarnessEnvironment } from '@angular/cdk/testing/testbed';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { MatProgressSpinnerHarness } from '@angular/material/progress-spinner/testing';

import { SPINNER_DIAMETERS, SpinnerComponent, SpinnerSize } from './spinner';

describe('SpinnerComponent', () => {
  let fixture: ComponentFixture<SpinnerComponent>;
  let host: HTMLElement;
  let loader: HarnessLoader;

  const status = () => host.querySelector<HTMLElement>('[role="status"]');
  const label = () => status()?.querySelector<HTMLElement>('.label') ?? null;
  const indicator = () => host.querySelector<HTMLElement>('mat-progress-spinner');

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SpinnerComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(SpinnerComponent);
    host = fixture.nativeElement;
    loader = TestbedHarnessEnvironment.loader(fixture);
    fixture.detectChanges();
  });

  // --- Criterion: role="status" ---

  it('when rendered, the host contains an element with role="status"', () => {
    expect(status()).not.toBeNull();
  });

  // --- Material 3 circular progress indicator ---

  it('when rendered, the indicator is an indeterminate mat-progress-spinner', async () => {
    const spinner = await loader.getHarness(MatProgressSpinnerHarness);

    expect(await spinner.getMode()).toBe('indeterminate');
    expect(await spinner.getValue()).toBeNull();
  });

  it('when rendered, the indicator is decorative so the label alone names the state', () => {
    const el = indicator();

    expect(el).not.toBeNull();
    expect(status()?.contains(el)).toBe(true);
    expect(el?.getAttribute('aria-hidden')).toBe('true');
  });

  // --- Criterion: screen-reader-only label ---

  it('when rendered, a visually hidden label is present inside the status region', () => {
    expect(label()).not.toBeNull();
    expect(label()?.classList).toContain('cdk-visually-hidden');
  });

  it('when label input is provided, the label text reflects it', () => {
    fixture.componentRef.setInput('label', 'Saving changes…');
    fixture.detectChanges();

    expect(label()?.textContent?.trim()).toBe('Saving changes…');
  });

  it('when no label input is provided, the label defaults to Loading…', () => {
    expect(label()?.textContent?.trim()).toBe('Loading…');
  });

  it('when rendered, the status region announces the label text exactly once', () => {
    expect(status()?.textContent?.trim()).toBe('Loading…');
  });

  it('when showLabel is set, the label is visible and stays in the status region', () => {
    fixture.componentRef.setInput('showLabel', true);
    fixture.detectChanges();

    expect(label()).not.toBeNull();
    expect(label()?.classList).not.toContain('cdk-visually-hidden');
    expect(status()?.textContent?.trim()).toBe('Loading…');
  });

  it('when showLabel is given as an empty attribute value, it is coerced to true', () => {
    fixture.componentRef.setInput('showLabel', '');
    fixture.detectChanges();

    expect(label()?.classList).not.toContain('cdk-visually-hidden');
  });

  // --- Size maps to the Material diameter ---

  it('when no size is provided, the indicator uses the M3 default 48px diameter', () => {
    expect(indicator()?.style.width).toBe('48px');
    expect(indicator()?.style.height).toBe('48px');
  });

  it.each(Object.entries(SPINNER_DIAMETERS) as [SpinnerSize, number][])(
    'when size is %s, the indicator diameter is %ipx',
    (size, diameter) => {
      fixture.componentRef.setInput('size', size);
      fixture.detectChanges();

      expect(indicator()?.style.width).toBe(`${diameter}px`);
      expect(indicator()?.style.height).toBe(`${diameter}px`);
    },
  );

  // --- Criterion: reduced-motion safe ---

  it('when the user prefers reduced motion, a screen-reader-only label stays visually hidden, because Material slows the indicator instead of stopping it', () => {
    const componentCss = Array.from(document.querySelectorAll('style'))
      .map((style) => style.textContent ?? '')
      .filter((css) => css.includes('.indicator'))
      .join('\n');

    expect(componentCss).not.toBe('');
    expect(componentCss).not.toMatch(/prefers-reduced-motion/);
    expect(label()?.classList).toContain('cdk-visually-hidden');
  });

  // --- No hardcoded hex colours ---

  it('when rendered, no hardcoded hex colors appear in any inline element styles', () => {
    const hexPattern = /#[0-9a-fA-F]{3,8}\b/;
    const allElements = [host, ...Array.from(host.querySelectorAll<HTMLElement>('*'))];
    for (const el of allElements) {
      expect(el.getAttribute('style') ?? '').not.toMatch(hexPattern);
    }
  });
});
