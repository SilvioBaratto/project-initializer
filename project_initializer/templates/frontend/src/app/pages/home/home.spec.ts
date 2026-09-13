import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HarnessLoader } from '@angular/cdk/testing';
import { TestbedHarnessEnvironment } from '@angular/cdk/testing/testbed';
import { MatCardHarness } from '@angular/material/card/testing';

import { ICON_PROVIDER } from '../../icons';
import { HomeComponent } from './home';

/** Label, value and change each stat tile shows under the default en-US locale. */
const RENDERED_STATS = [
  ['Active users', '1,284', '12%'],
  ['Sessions', '8,932', '4%'],
  ['Conversations', '342', '9%'],
] as const;

describe('HomeComponent', () => {
  let fixture: ComponentFixture<HomeComponent>;
  let host: HTMLElement;
  let loader: HarnessLoader;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [HomeComponent],
      providers: [ICON_PROVIDER],
    }).compileComponents();

    fixture = TestBed.createComponent(HomeComponent);
    host = fixture.nativeElement;
    loader = TestbedHarnessEnvironment.loader(fixture);
    fixture.detectChanges();
    await fixture.whenStable();
  });

  it('when the home page renders, exactly one h1 names the view', () => {
    const headings = host.querySelectorAll('h1');
    expect(headings.length).toBe(1);
    expect(headings[0].textContent?.trim()).toBe('Welcome back');
  });

  it('when the home page renders, no heading level is skipped', () => {
    const levels = Array.from(host.querySelectorAll('h1, h2, h3, h4, h5, h6')).map((h) =>
      Number(h.tagName.slice(1)),
    );
    expect(levels[0]).toBe(1);
    for (let i = 1; i < levels.length; i++) {
      expect(levels[i]).toBeLessThanOrEqual(levels[i - 1] + 1);
    }
  });

  it('when the home page renders, the hero and every stat tile are outlined Material cards', async () => {
    const cards = await loader.getAllHarnesses(MatCardHarness);
    expect(cards.length).toBe(1 + fixture.componentInstance.stats.length);

    for (const card of cards) {
      expect(await (await card.host()).hasClass('mat-mdc-card-outlined')).toBe(true);
    }
    expect(await cards[0].getText()).toContain('Welcome back');
  });

  it('when the home page renders, the shared primary badge tags the hero and no chip is used as a label', () => {
    const badge = host.querySelector('.hero app-badge');
    expect(badge?.textContent?.trim()).toBe('New');
    expect(badge?.getAttribute('data-variant')).toBe('primary');
    expect(host.querySelector('mat-chip, .mat-mdc-chip')).toBeNull();
  });

  it('when stats render, they form a list with one shared stat card per stat', () => {
    const list = host.querySelector('ul');
    expect(list?.getAttribute('role')).toBe('list');

    const items = list?.querySelectorAll(':scope > li') ?? [];
    expect(items.length).toBe(fixture.componentInstance.stats.length);
    items.forEach((item) => expect(item.querySelectorAll('app-stat-card')).toHaveLength(1));
  });

  it('when a stat renders, assistive technology reads its label, then its locale-formatted value, then its change', () => {
    const items = host.querySelectorAll('ul > li');
    expect(items.length).toBe(RENDERED_STATS.length);
    RENDERED_STATS.forEach(([label, value, delta], i) => {
      const text = items[i].textContent ?? '';
      expect(text.indexOf(label)).toBeGreaterThanOrEqual(0);
      expect(text.indexOf(label)).toBeLessThan(text.indexOf(value));
      expect(text.indexOf(value)).toBeLessThan(text.indexOf(delta));
    });
  });

  it('when a stat renders, its direction is named in text and its chevron is hidden from assistive technology', () => {
    const items = host.querySelectorAll('ul > li');
    items.forEach((item) => {
      expect(item.querySelector('.cdk-visually-hidden')?.textContent?.trim()).toBe('Up');
      const chevron = item.querySelector('lucide-icon');
      expect(chevron?.getAttribute('aria-hidden')).toBe('true');
    });
  });

  it('when the home page renders, the page has no interactive controls to reach by keyboard', () => {
    expect(host.querySelectorAll('button, a[href], input, select, textarea, [tabindex]').length).toBe(0);
  });
});
