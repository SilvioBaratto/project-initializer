import { signal, WritableSignal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HarnessLoader } from '@angular/cdk/testing';
import { TestbedHarnessEnvironment } from '@angular/cdk/testing/testbed';
import {
  MatButtonToggleGroupHarness,
  MatButtonToggleHarness,
} from '@angular/material/button-toggle/testing';
import { vi } from 'vitest';

import { ICON_PROVIDER } from '../../icons';
import { ThemeMode, ThemeService } from '../../services/theme';
import { SettingsComponent } from './settings';

describe('SettingsComponent', () => {
  let theme: WritableSignal<ThemeMode>;
  let setTheme: ReturnType<typeof vi.fn>;
  let fixture: ComponentFixture<SettingsComponent>;
  let loader: HarnessLoader;

  beforeEach(async () => {
    theme = signal<ThemeMode>('system');
    // Mirrors ThemeService: setTheme updates the theme() signal the page reads.
    setTheme = vi.fn((mode: ThemeMode) => theme.set(mode));

    await TestBed.configureTestingModule({
      imports: [SettingsComponent],
      providers: [ICON_PROVIDER, { provide: ThemeService, useValue: { theme, setTheme } }],
    }).compileComponents();
  });

  async function render(): Promise<HTMLElement> {
    fixture = TestBed.createComponent(SettingsComponent);
    loader = TestbedHarnessEnvironment.loader(fixture);
    fixture.detectChanges();
    await fixture.whenStable();
    return fixture.nativeElement;
  }

  function toggleEl(el: HTMLElement, mode: ThemeMode): HTMLElement {
    return el.querySelector<HTMLElement>(`mat-button-toggle[data-theme-option="${mode}"]`)!;
  }

  it('when the settings page renders, it has one h1 and an Appearance h2', async () => {
    const el = await render();
    const h1s = el.querySelectorAll('h1');
    expect(h1s.length).toBe(1);
    expect(h1s[0].textContent?.trim()).toBe('Settings');
    expect(el.querySelector('h2')?.textContent?.trim()).toBe('Appearance');
  });

  it('when the settings page renders, the appearance section is a region named by its heading', async () => {
    const el = await render();
    const section = el.querySelector('section')!;
    const headingId = section.getAttribute('aria-labelledby');
    expect(headingId).toBeTruthy();
    expect(el.querySelector(`#${headingId}`)?.textContent?.trim()).toBe('Appearance');
  });

  it('when the settings page renders, three theme options are returned', async () => {
    const el = await render();
    const group = await loader.getHarness(MatButtonToggleGroupHarness);
    const toggles = await group.getToggles();
    expect(toggles.length).toBe(3);
    expect(await Promise.all(toggles.map((t) => t.getText()))).toEqual(['System', 'Light', 'Dark']);
    expect(el.querySelectorAll('mat-button-toggle[data-theme-option]').length).toBe(3);
  });

  it('when the settings page renders, the options form a radio group named Theme', async () => {
    await render();
    const group = await loader.getHarness(MatButtonToggleGroupHarness);
    const host = await group.host();
    expect(await host.getAttribute('role')).toBe('radiogroup');
    expect(await host.getAttribute('aria-label')).toBe('Theme');
  });

  it('when the Light option is clicked, setTheme is called with light', async () => {
    await render();
    const light = await loader.getHarness(MatButtonToggleHarness.with({ text: 'Light' }));
    await light.check();
    expect(setTheme).toHaveBeenCalledWith('light');
    expect(await light.isChecked()).toBe(true);
  });

  it('when the stored theme is system, the System option is marked active', async () => {
    const el = await render();
    const system = await loader.getHarness(MatButtonToggleHarness.with({ text: 'System' }));
    const light = await loader.getHarness(MatButtonToggleHarness.with({ text: 'Light' }));
    const dark = await loader.getHarness(MatButtonToggleHarness.with({ text: 'Dark' }));
    expect(await system.isChecked()).toBe(true);
    expect(await light.isChecked()).toBe(false);
    expect(await dark.isChecked()).toBe(false);
    const button = toggleEl(el, 'system').querySelector('button')!;
    expect(button.getAttribute('role')).toBe('radio');
    expect(button.getAttribute('aria-checked')).toBe('true');
  });

  it('when the theme changes elsewhere, the matching option becomes active', async () => {
    await render();
    theme.set('dark');
    fixture.detectChanges();
    await fixture.whenStable();
    const dark = await loader.getHarness(MatButtonToggleHarness.with({ text: 'Dark' }));
    const system = await loader.getHarness(MatButtonToggleHarness.with({ text: 'System' }));
    expect(await dark.isChecked()).toBe(true);
    expect(await system.isChecked()).toBe(false);
  });

  it('when an option is selected, a check mark replaces its icon so selection is not color alone', async () => {
    const el = await render();
    const system = toggleEl(el, 'system');
    const light = toggleEl(el, 'light');
    expect(system.querySelector('mat-pseudo-checkbox')).not.toBeNull();
    expect(system.querySelector('lucide-icon')).toBeNull();
    expect(light.querySelector('lucide-icon')).not.toBeNull();

    const lightHarness = await loader.getHarness(MatButtonToggleHarness.with({ text: 'Light' }));
    await lightHarness.check();
    fixture.detectChanges();
    await fixture.whenStable();
    expect(light.querySelector('lucide-icon')).toBeNull();
    expect(system.querySelector('lucide-icon')).not.toBeNull();
  });

  it('when ArrowRight is pressed on the selected option, the next theme is selected and focused', async () => {
    const el = await render();
    const systemButton = toggleEl(el, 'system').querySelector('button')!;
    systemButton.focus();
    const event = new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true, cancelable: true });
    Object.defineProperty(event, 'keyCode', { get: () => 39 });
    systemButton.dispatchEvent(event);
    fixture.detectChanges();
    await fixture.whenStable();

    expect(setTheme).toHaveBeenCalledWith('light');
    const lightButton = toggleEl(el, 'light').querySelector('button')!;
    expect(document.activeElement).toBe(lightButton);
    expect(lightButton.getAttribute('aria-checked')).toBe('true');
  });

  it('when the settings page renders, only the selected option is in the tab order', async () => {
    const el = await render();
    const tabIndexes = (['system', 'light', 'dark'] as const).map((mode) =>
      toggleEl(el, mode).querySelector('button')!.getAttribute('tabindex'),
    );
    expect(tabIndexes).toEqual(['0', '-1', '-1']);
  });
});
