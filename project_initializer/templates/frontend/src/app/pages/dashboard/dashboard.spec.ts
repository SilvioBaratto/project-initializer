import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HarnessLoader } from '@angular/cdk/testing';
import { TestbedHarnessEnvironment } from '@angular/cdk/testing/testbed';
import { MatCardHarness } from '@angular/material/card/testing';

import { DashboardComponent } from './dashboard';

describe('DashboardComponent', () => {
  let fixture: ComponentFixture<DashboardComponent>;
  let el: HTMLElement;
  let loader: HarnessLoader;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [DashboardComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(DashboardComponent);
    el = fixture.nativeElement;
    loader = TestbedHarnessEnvironment.loader(fixture);
    fixture.detectChanges();
    await fixture.whenStable();
  });

  it('when the dashboard renders, one h1 names the view', () => {
    const headings = el.querySelectorAll('h1');
    expect(headings.length).toBe(1);
    expect(headings[0].textContent?.trim()).toBe('Dashboard');
  });

  it('when the dashboard renders, heading levels never skip a level', () => {
    const levels = Array.from(el.querySelectorAll('h1, h2, h3, h4, h5, h6')).map((h) =>
      Number(h.tagName.slice(1)),
    );
    expect(levels[0]).toBe(1);
    levels.slice(1).forEach((level, i) => {
      expect(level - levels[i]).toBeLessThanOrEqual(1);
    });
  });

  it('when the dashboard renders, each metric card shows its label, locale-formatted value and hint', async () => {
    const metrics = fixture.componentInstance.metrics;
    // Default en-US locale: the currency, number and percent pipes format the raw numbers.
    const values = ['$42,500', '1,204', '2.1%', '64'];
    const cards = await loader.getAllHarnesses(MatCardHarness.with({ selector: '.metric-card' }));

    expect(cards.length).toBe(values.length);
    expect(metrics.length).toBe(values.length);
    for (const [i, card] of cards.entries()) {
      const text = await card.getText();
      expect(text).toContain(metrics[i].label);
      expect(text).toContain(values[i]);
      expect(text).toContain(metrics[i].hint);
    }
  });

  it('when the metric labels render, they are written out in full, with no abbreviations', () => {
    const labels = Array.from(el.querySelectorAll('.metric-label')).map((h) => h.textContent?.trim());
    expect(labels).toEqual(['Revenue', 'Signups', 'Churn', 'Net Promoter Score']);
    expect(el.querySelector('.metric-feed')?.textContent).not.toMatch(/\d+(\.\d+)?k\b/);
  });

  it('when the dashboard renders, the header and the metrics region share one centered page wrapper', () => {
    const wrapper = el.querySelector(':scope > .dashboard');
    expect(wrapper).toBeTruthy();
    expect(el.children.length).toBe(1);
    expect(wrapper!.querySelector(':scope > header h1')?.textContent?.trim()).toBe('Dashboard');
    expect(wrapper!.querySelectorAll(':scope > section[aria-labelledby]').length).toBe(1);
  });

  it('when the metrics render, they form a list inside a region labelled by its heading', () => {
    const region = el.querySelector<HTMLElement>('section[aria-labelledby="dashboard-metrics-heading"]');
    expect(region).toBeTruthy();
    expect(el.querySelector('#dashboard-metrics-heading')?.textContent?.trim()).toBe('Key metrics');

    const list = region!.querySelector('ul');
    expect(list?.getAttribute('role')).toBe('list');
    expect(list?.querySelectorAll(':scope > li').length).toBe(fixture.componentInstance.metrics.length);
  });

  it('when the metric card renders, its label is a heading below the section heading', () => {
    const labels = Array.from(el.querySelectorAll('.metric-card h3')).map((h) => h.textContent?.trim());
    expect(labels).toEqual(fixture.componentInstance.metrics.map((m) => m.label));
  });

  it('when nothing is loading, no busy state, skeleton or loading status is rendered', () => {
    const status = el.querySelectorAll('[role="status"]');

    expect(fixture.componentInstance.isLoading()).toBe(false);
    expect(el.querySelector('[aria-busy]')).toBeNull();
    expect(el.querySelector('app-skeleton')).toBeNull();
    // The live region stays mounted, so the text it gains when loading starts is announced.
    expect(status).toHaveLength(1);
    expect(status[0].textContent?.trim()).toBe('');
  });

  describe('while the metrics are loading', () => {
    beforeEach(async () => {
      fixture.componentInstance.isLoading.set(true);
      await fixture.whenStable();
    });

    it('when loading, placeholder tiles replace the metric cards inside a busy feed', async () => {
      const busy = el.querySelector('.metric-feed[aria-busy="true"]');
      const skeletons = el.querySelectorAll('app-skeleton');

      expect(busy).toBeTruthy();
      expect(el.querySelectorAll('.metric-card h3')).toHaveLength(0);
      expect(await loader.getAllHarnesses(MatCardHarness.with({ selector: '.metric-card' }))).toHaveLength(
        fixture.componentInstance.metrics.length,
      );
      expect(skeletons.length).toBeGreaterThan(0);
      skeletons.forEach((skeleton) => expect(busy!.contains(skeleton)).toBe(true));
    });

    it('when loading, the same status names what is loading outside the busy container', () => {
      const statuses = el.querySelectorAll('[role="status"]');
      expect(statuses).toHaveLength(1);
      expect(statuses[0].textContent?.trim()).toBe('Loading metrics…');
      expect(statuses[0].closest('[aria-busy]')).toBeNull();
    });

    it('when loading ends, the metric cards return and the status goes quiet', async () => {
      fixture.componentInstance.isLoading.set(false);
      await fixture.whenStable();

      expect(el.querySelector('[aria-busy]')).toBeNull();
      expect(el.querySelectorAll('.metric-card h3')).toHaveLength(fixture.componentInstance.metrics.length);
      expect(el.querySelector('[role="status"]')?.textContent?.trim()).toBe('');
    });
  });

  it('when the region renders, it is labelled by the Key metrics heading', () => {
    const labels = Array.from(el.querySelectorAll('section[aria-labelledby]')).map((section) =>
      el.querySelector(`#${section.getAttribute('aria-labelledby')}`)?.textContent?.trim(),
    );
    expect(labels).toEqual(['Key metrics']);
  });

  it('when the copy renders, single-sentence text has no trailing period', () => {
    const texts = Array.from(el.querySelectorAll('h1, h2, h3, p')).map((node) => node.textContent?.trim() ?? '');
    expect(texts.length).toBeGreaterThan(0);
    texts.forEach((text) => expect(text.endsWith('.')).toBe(false));
  });
});
