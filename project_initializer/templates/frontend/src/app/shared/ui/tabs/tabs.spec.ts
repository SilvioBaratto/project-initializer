import { Component, signal, viewChildren } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { TestKey } from '@angular/cdk/testing';
import { TestbedHarnessEnvironment } from '@angular/cdk/testing/testbed';
import { MATERIAL_ANIMATIONS } from '@angular/material/core';
import { MatTabGroupHarness, MatTabHarness } from '@angular/material/tabs/testing';

import { TabComponent, TabPanelComponent, TabsComponent } from './tabs';

// ---------------------------------------------------------------------------
// Host stub
// ---------------------------------------------------------------------------

@Component({
  imports: [TabsComponent, TabComponent, TabPanelComponent],
  template: `
    <span id="tabs-heading">Project sections</span>
    <ui-tabs
      [(activeIndex)]="active"
      [ariaLabel]="label()"
      [ariaLabelledby]="labelledBy()"
      (tabChanged)="changes.push($event)"
    >
      @if (showA()) {
        <ui-tab [tabIndex]="0">Tab A</ui-tab>
      }
      <ui-tab [tabIndex]="1">Tab B</ui-tab>
      @if (showC()) {
        <ui-tab [tabIndex]="2">Tab C</ui-tab>
      }
      <ui-tab-panel [panelIndex]="0">Panel A</ui-tab-panel>
      <ui-tab-panel [panelIndex]="1">Panel B</ui-tab-panel>
      <ui-tab-panel [panelIndex]="2">Panel C</ui-tab-panel>
    </ui-tabs>
  `,
})
class HostComponent {
  readonly active = signal(0);
  readonly label = signal<string | undefined>(undefined);
  readonly labelledBy = signal<string | undefined>(undefined);
  readonly showA = signal(true);
  readonly showC = signal(true);
  readonly changes: number[] = [];
  readonly tabItems = viewChildren(TabComponent);
  readonly panelItems = viewChildren(TabPanelComponent);
}

/** A panel whose first content is a control, which the APG says needs no panel tab stop. */
@Component({
  imports: [TabsComponent, TabComponent, TabPanelComponent],
  template: `
    <ui-tabs ariaLabel="Account">
      <ui-tab [tabIndex]="0">Profile</ui-tab>
      <ui-tab-panel [panelIndex]="0" [focusable]="focusable()">
        <button type="button">Edit profile</button>
      </ui-tab-panel>
    </ui-tabs>
  `,
})
class ControlPanelHostComponent {
  readonly focusable = signal(false);
}

@Component({
  imports: [TabsComponent, TabComponent, TabPanelComponent],
  template: `
    <ui-tabs ariaLabel="Account">
      <ui-tab [tabIndex]="0">Profile</ui-tab>
      <ui-tab-panel [panelIndex]="0" focusable="false"><a href="#profile">Open profile</a></ui-tab-panel>
    </ui-tabs>
  `,
})
class StaticControlPanelHostComponent {}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

interface Setup {
  fixture: ComponentFixture<HostComponent>;
  host: HostComponent;
  tabs: TabsComponent;
  group: MatTabGroupHarness;
  tabHarnesses: MatTabHarness[];
}

async function setup(): Promise<Setup> {
  await TestBed.configureTestingModule({
    imports: [HostComponent],
    // Without this, Material's tab body waits for a transition fallback before swapping content.
    providers: [{ provide: MATERIAL_ANIMATIONS, useValue: { animationsDisabled: true } }],
  }).compileComponents();

  const fixture = TestBed.createComponent(HostComponent);
  fixture.detectChanges();
  await fixture.whenStable();

  const loader = TestbedHarnessEnvironment.loader(fixture);
  const group = await loader.getHarness(MatTabGroupHarness);
  return {
    fixture,
    host: fixture.componentInstance,
    tabs: fixture.debugElement.query(By.directive(TabsComponent)).componentInstance as TabsComponent,
    group,
    tabHarnesses: await group.getTabs(),
  };
}

async function settle(fixture: ComponentFixture<unknown>): Promise<void> {
  fixture.detectChanges();
  await fixture.whenStable();
}

/**
 * Also waits out Material's deferred `selectedIndexChange`, which it emits from a microtask after
 * the selection moves, and renders whatever that emission changed.
 */
async function settleAll(fixture: ComponentFixture<unknown>): Promise<void> {
  await settle(fixture);
  await new Promise((resolve) => setTimeout(resolve));
  await settle(fixture);
}

/** Focuses the tab and dispatches the key; Material's tab header handles it. */
async function press(tab: MatTabHarness, key: TestKey | string): Promise<void> {
  await (await tab.host()).sendKeys(key);
}

function tabList(f: ComponentFixture<unknown>): HTMLElement | null {
  return f.nativeElement.querySelector('[role="tablist"]');
}

function tabs(f: ComponentFixture<unknown>): HTMLElement[] {
  return Array.from(f.nativeElement.querySelectorAll('[role="tab"]'));
}

function panels(f: ComponentFixture<unknown>): HTMLElement[] {
  return Array.from(f.nativeElement.querySelectorAll('[role="tabpanel"]'));
}

/** Material keeps a body per tab and hides the unselected ones from assistive technology. */
function shownPanels(f: ComponentFixture<unknown>): HTMLElement[] {
  return panels(f).filter((panel) => panel.getAttribute('aria-hidden') !== 'true');
}

async function selectedLabel(group: MatTabGroupHarness): Promise<string> {
  return (await group.getSelectedTab()).getLabel();
}

// ---------------------------------------------------------------------------
// Material tab group
// ---------------------------------------------------------------------------

describe('TabsComponent — Material tab group', () => {
  it('when tabs render, a mat-tab-group shows one tab per ui-tab in content order', async () => {
    const { tabHarnesses } = await setup();
    const labels = await Promise.all(tabHarnesses.map((tab) => tab.getLabel()));
    expect(labels).toEqual(['Tab A', 'Tab B', 'Tab C']);
  });

  it('when tabs render, the first tab is selected by default', async () => {
    const { group } = await setup();
    expect(await selectedLabel(group)).toBe('Tab A');
  });
});

// ---------------------------------------------------------------------------
// ARIA roles
// ---------------------------------------------------------------------------

describe('TabsComponent — ARIA roles', () => {
  it('when tabs render, a role="tablist" element is present', async () => {
    const { fixture } = await setup();
    expect(tabList(fixture)).not.toBeNull();
  });

  it('when tabs render, every tab carries role="tab" inside the tablist', async () => {
    const { fixture } = await setup();
    expect(tabs(fixture).length).toBe(3);
    tabs(fixture).forEach((tab) => expect(tabList(fixture)!.contains(tab)).toBe(true));
  });

  it('when a tab is active, exactly one role="tabpanel" is exposed and it holds that tab content', async () => {
    const { fixture } = await setup();
    const shown = shownPanels(fixture);
    expect(shown.length).toBe(1);
    expect(shown[0].getAttribute('role')).toBe('tabpanel');
    expect(shown[0].textContent).toContain('Panel A');
  });
});

// ---------------------------------------------------------------------------
// ARIA attributes
// ---------------------------------------------------------------------------

describe('TabsComponent — ARIA attributes', () => {
  it('when tabs render, the active tab has aria-selected="true"', async () => {
    const { fixture, tabHarnesses } = await setup();
    expect(tabs(fixture)[0].getAttribute('aria-selected')).toBe('true');
    expect(await tabHarnesses[0].isSelected()).toBe(true);
  });

  it('when tabs render, inactive tabs have aria-selected="false"', async () => {
    const { fixture } = await setup();
    expect(tabs(fixture)[1].getAttribute('aria-selected')).toBe('false');
    expect(tabs(fixture)[2].getAttribute('aria-selected')).toBe('false');
  });

  it('when tabs render, each tab has aria-controls pointing to a tabpanel id', async () => {
    const { fixture } = await setup();
    tabs(fixture).forEach((tab) => {
      const controls = tab.getAttribute('aria-controls');
      expect(controls).toBeTruthy();
      const panel = fixture.nativeElement.querySelector(`#${controls}`);
      expect(panel).not.toBeNull();
      expect(panel.getAttribute('role')).toBe('tabpanel');
    });
  });

  it('when the active panel renders, it has aria-labelledby matching its tab id', async () => {
    const { fixture } = await setup();
    const labelledBy = shownPanels(fixture)[0].getAttribute('aria-labelledby');
    expect(labelledBy).toBeTruthy();
    const tab = fixture.nativeElement.querySelector(`#${labelledBy}`);
    expect(tab).not.toBeNull();
    expect(tab.getAttribute('role')).toBe('tab');
    expect(tab.getAttribute('aria-selected')).toBe('true');
  });

  it('when the panel renders, aria-controls on the active tab matches the panel id', async () => {
    const { fixture } = await setup();
    expect(tabs(fixture)[0].getAttribute('aria-controls')).toBe(shownPanels(fixture)[0].id);
  });

  it('when no label is given, the tablist has no aria-label or aria-labelledby', async () => {
    const { fixture } = await setup();
    expect(tabList(fixture)!.hasAttribute('aria-label')).toBe(false);
    expect(tabList(fixture)!.hasAttribute('aria-labelledby')).toBe(false);
  });

  it('when ariaLabel is set, it names the tablist', async () => {
    const { fixture, host } = await setup();
    host.label.set('Project sections');
    await settle(fixture);
    expect(tabList(fixture)!.getAttribute('aria-label')).toBe('Project sections');
  });

  it('when ariaLabelledby is set, the tablist points at the visible label', async () => {
    const { fixture, host } = await setup();
    host.labelledBy.set('tabs-heading');
    await settle(fixture);
    expect(tabList(fixture)!.getAttribute('aria-labelledby')).toBe('tabs-heading');
  });
});

// ---------------------------------------------------------------------------
// Roving tabindex
// ---------------------------------------------------------------------------

describe('TabsComponent — roving tabindex', () => {
  it('when tabs render, the active tab has tabindex=0', async () => {
    const { fixture } = await setup();
    expect(tabs(fixture)[0].getAttribute('tabindex')).toBe('0');
  });

  it('when tabs render, inactive tabs have tabindex=-1', async () => {
    const { fixture } = await setup();
    expect(tabs(fixture)[1].getAttribute('tabindex')).toBe('-1');
    expect(tabs(fixture)[2].getAttribute('tabindex')).toBe('-1');
  });

  it('when a tab is clicked, it becomes active with tabindex=0', async () => {
    const { fixture, tabHarnesses } = await setup();
    await tabHarnesses[1].select();
    expect(tabs(fixture)[1].getAttribute('tabindex')).toBe('0');
    expect(tabs(fixture)[0].getAttribute('tabindex')).toBe('-1');
  });

  it('when an arrow key moves focus, the single tab stop follows the focused tab', async () => {
    const { fixture, tabHarnesses } = await setup();
    await press(tabHarnesses[0], TestKey.RIGHT_ARROW);
    await settle(fixture);
    const stops = tabs(fixture).map((tab) => tab.getAttribute('tabindex'));
    expect(stops).toEqual(['-1', '0', '-1']);
  });
});

// ---------------------------------------------------------------------------
// Keyboard navigation — ArrowRight / ArrowLeft
// ---------------------------------------------------------------------------

describe('TabsComponent — ArrowRight / ArrowLeft navigation', () => {
  it('when ArrowRight is pressed, focus moves to the next tab and the selection stays', async () => {
    const { fixture, group, tabHarnesses, host } = await setup();
    await press(tabHarnesses[0], TestKey.RIGHT_ARROW);
    expect(document.activeElement).toBe(tabs(fixture)[1]);
    expect(await selectedLabel(group)).toBe('Tab A');
    expect(host.changes).toEqual([]);
  });

  it('when ArrowRight is pressed on the last tab, focus wraps to the first tab', async () => {
    const { fixture, tabHarnesses, host } = await setup();
    host.active.set(2);
    await settle(fixture);
    await press(tabHarnesses[2], TestKey.RIGHT_ARROW);
    expect(document.activeElement).toBe(tabs(fixture)[0]);
  });

  it('when ArrowLeft is pressed, focus moves to the previous tab', async () => {
    const { fixture, tabHarnesses, host } = await setup();
    host.active.set(2);
    await settle(fixture);
    await press(tabHarnesses[2], TestKey.LEFT_ARROW);
    expect(document.activeElement).toBe(tabs(fixture)[1]);
  });

  it('when ArrowLeft is pressed on the first tab, focus wraps to the last tab', async () => {
    const { fixture, tabHarnesses } = await setup();
    await press(tabHarnesses[0], TestKey.LEFT_ARROW);
    expect(document.activeElement).toBe(tabs(fixture)[2]);
  });
});

// ---------------------------------------------------------------------------
// Keyboard navigation — Home / End
// ---------------------------------------------------------------------------

describe('TabsComponent — Home / End navigation', () => {
  it('when Home is pressed, focus moves to the first tab', async () => {
    const { fixture, tabHarnesses, host } = await setup();
    host.active.set(2);
    await settle(fixture);
    await press(tabHarnesses[2], TestKey.HOME);
    expect(document.activeElement).toBe(tabs(fixture)[0]);
  });

  it('when End is pressed, focus moves to the last tab', async () => {
    const { fixture, tabHarnesses } = await setup();
    await press(tabHarnesses[0], TestKey.END);
    expect(document.activeElement).toBe(tabs(fixture)[2]);
  });
});

// ---------------------------------------------------------------------------
// Keyboard activation — Enter / Space
// ---------------------------------------------------------------------------

describe('TabsComponent — Enter / Space activation', () => {
  it('when Enter is pressed on the focused tab, it is selected and tabChanged emits its index', async () => {
    const { fixture, group, tabHarnesses, tabs: tabsCmp, host } = await setup();
    await press(tabHarnesses[0], TestKey.RIGHT_ARROW);
    await press(tabHarnesses[1], TestKey.ENTER);
    await settle(fixture);
    expect(await selectedLabel(group)).toBe('Tab B');
    expect(tabsCmp.activeIndex()).toBe(1);
    expect(host.changes).toEqual([1]);
  });

  it('when Space is pressed on the focused tab, it is selected and tabChanged emits its index', async () => {
    const { fixture, group, tabHarnesses, host } = await setup();
    await press(tabHarnesses[0], TestKey.END);
    await press(tabHarnesses[2], ' ');
    await settle(fixture);
    expect(await selectedLabel(group)).toBe('Tab C');
    expect(host.changes).toEqual([2]);
  });

  it('when Enter is pressed on the already selected tab, tabChanged does not emit', async () => {
    const { fixture, tabHarnesses, host } = await setup();
    await press(tabHarnesses[0], TestKey.ENTER);
    await settle(fixture);
    expect(host.changes).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// Selection API — activeIndex, activate(), tabChanged
// ---------------------------------------------------------------------------

describe('TabsComponent — selection API', () => {
  it('when a tab is clicked, tabChanged emits its index and [(activeIndex)] updates', async () => {
    const { fixture, tabHarnesses, host } = await setup();
    await tabHarnesses[1].select();
    await settle(fixture);
    expect(host.changes).toEqual([1]);
    expect(host.active()).toBe(1);
  });

  it('when the selected tab is clicked again, tabChanged does not emit', async () => {
    const { fixture, tabHarnesses, host } = await setup();
    await tabHarnesses[0].select();
    await settle(fixture);
    expect(host.changes).toEqual([]);
  });

  it('when the bound activeIndex changes, that tab is selected without emitting tabChanged', async () => {
    const { fixture, group, host } = await setup();
    host.active.set(2);
    await settle(fixture);
    expect(await selectedLabel(group)).toBe('Tab C');
    expect(host.changes).toEqual([]);
  });

  it('when activeIndex is set on the component, that tab is selected', async () => {
    const { fixture, group, tabs: tabsCmp } = await setup();
    tabsCmp.activeIndex.set(1);
    await settle(fixture);
    expect(await selectedLabel(group)).toBe('Tab B');
  });

  it('when activate() is called, that tab is selected and tabChanged emits once', async () => {
    const { fixture, group, tabs: tabsCmp, host } = await setup();
    tabsCmp.activate(2);
    await settle(fixture);
    expect(await selectedLabel(group)).toBe('Tab C');
    expect(host.changes).toEqual([2]);
  });

  it('when the selection changes, ui-tab and ui-tab-panel isActive follow it', async () => {
    const { fixture, tabHarnesses, host } = await setup();
    expect(host.tabItems().map((tab) => tab.isActive())).toEqual([true, false, false]);
    await tabHarnesses[1].select();
    await settle(fixture);
    expect(host.tabItems().map((tab) => tab.isActive())).toEqual([false, true, false]);
    expect(host.panelItems().map((panel) => panel.isActive())).toEqual([false, true, false]);
  });

  it('when activeIndex names no tab, the first tab is selected and activeIndex follows it without emitting', async () => {
    const { fixture, group, tabs: tabsCmp, host } = await setup();
    host.active.set(7);
    await settleAll(fixture);
    expect(tabsCmp.activeIndex()).toBe(0);
    expect(host.active()).toBe(0);
    expect(host.changes).toEqual([]);
    expect(await selectedLabel(group)).toBe('Tab A');
    expect(tabs(fixture).map((tab) => tab.getAttribute('aria-selected'))).toEqual(['true', 'false', 'false']);
    expect(host.tabItems().map((tab) => tab.isActive())).toEqual([true, false, false]);
  });

  it('when activeIndex named no tab, clicking another tab still selects it and emits', async () => {
    const { fixture, tabHarnesses, host } = await setup();
    host.active.set(7);
    await settleAll(fixture);
    await tabHarnesses[1].select();
    await settleAll(fixture);
    expect(host.active()).toBe(1);
    expect(host.changes).toEqual([1]);
  });
});

// ---------------------------------------------------------------------------
// Tab list changes
// ---------------------------------------------------------------------------

describe('TabsComponent — tab list changes', () => {
  it('when the selected tab is removed, the first tab is selected without emitting tabChanged', async () => {
    const { fixture, group, host } = await setup();
    host.active.set(2);
    await settleAll(fixture);
    host.showC.set(false);
    await settleAll(fixture);
    expect(host.changes).toEqual([]);
    expect(host.active()).toBe(0);
    expect(await selectedLabel(group)).toBe('Tab A');
    expect(host.tabItems().map((tab) => tab.isActive())).toEqual([true, false]);
    expect(shownPanels(fixture)[0].textContent).toContain('Panel A');
  });

  it('when a tab before the selected one is removed, the selection stays without emitting', async () => {
    const { fixture, group, host } = await setup();
    host.active.set(2);
    await settleAll(fixture);
    host.showA.set(false);
    await settleAll(fixture);
    expect(host.changes).toEqual([]);
    expect(host.active()).toBe(2);
    expect(await selectedLabel(group)).toBe('Tab C');
    expect(tabs(fixture).map((tab) => tab.getAttribute('aria-selected'))).toEqual(['false', 'true']);
  });

  it('when an unselected tab is removed, the selection stays without emitting', async () => {
    const { fixture, group, host } = await setup();
    host.showC.set(false);
    await settleAll(fixture);
    expect(host.changes).toEqual([]);
    expect(host.active()).toBe(0);
    expect(await selectedLabel(group)).toBe('Tab A');
  });

  it('when a removed tab comes back, the current selection stays without emitting', async () => {
    const { fixture, group, host } = await setup();
    host.showA.set(false);
    await settleAll(fixture);
    expect(host.active()).toBe(1);
    host.showA.set(true);
    await settleAll(fixture);
    expect(host.changes).toEqual([]);
    expect(host.active()).toBe(1);
    expect(await selectedLabel(group)).toBe('Tab B');
  });
});

// ---------------------------------------------------------------------------
// Panel visibility
// ---------------------------------------------------------------------------

describe('TabsComponent — panel visibility', () => {
  it('when tab 0 is active, Panel A content is visible', async () => {
    const { fixture } = await setup();
    expect(fixture.nativeElement.textContent).toContain('Panel A');
    expect(fixture.nativeElement.textContent).not.toContain('Panel B');
  });

  it('when tab 1 is clicked, Panel B becomes visible', async () => {
    const { fixture, group, tabHarnesses } = await setup();
    await tabHarnesses[1].select();
    await settle(fixture);
    expect(fixture.nativeElement.textContent).toContain('Panel B');
    expect(fixture.nativeElement.textContent).not.toContain('Panel A');
    expect((await (await group.getSelectedTab()).getTextContent()).trim()).toBe('Panel B');
  });

  it('when a panel is shown, its content is a keyboard tab stop', async () => {
    const { fixture } = await setup();
    const stop = shownPanels(fixture)[0].querySelector<HTMLElement>('[tabindex="0"]');
    expect(stop).not.toBeNull();
    expect(stop!.textContent!.trim()).toBe('Panel A');
  });

  async function renderPanelHost<T>(component: new () => T): Promise<ComponentFixture<T>> {
    await TestBed.configureTestingModule({
      imports: [component],
      providers: [{ provide: MATERIAL_ANIMATIONS, useValue: { animationsDisabled: true } }],
    }).compileComponents();
    const fixture = TestBed.createComponent(component);
    await settle(fixture);
    return fixture;
  }

  it('when focusable is false, a panel that starts with a control adds no tab stop before it', async () => {
    const fixture = await renderPanelHost(ControlPanelHostComponent);
    const [panel] = shownPanels(fixture);

    expect(panel.querySelector('[tabindex]')).toBeNull();
    expect(panel.querySelector('button')!.textContent!.trim()).toBe('Edit profile');
  });

  it('when focusable changes to true, the panel becomes a tab stop again', async () => {
    const fixture = await renderPanelHost(ControlPanelHostComponent);
    fixture.componentInstance.focusable.set(true);
    await settle(fixture);

    const stop = shownPanels(fixture)[0].querySelector<HTMLElement>('[tabindex]');
    expect(stop).not.toBeNull();
    expect(stop!.getAttribute('tabindex')).toBe('0');
    expect(stop!.querySelector('button')).not.toBeNull();
  });

  it('when focusable="false" is a static attribute, the boolean attribute transform removes the stop', async () => {
    const fixture = await renderPanelHost(StaticControlPanelHostComponent);
    const [panel] = shownPanels(fixture);

    expect(panel.querySelector('[tabindex]')).toBeNull();
    expect(panel.querySelector('a')!.textContent!.trim()).toBe('Open profile');
  });
});

// ---------------------------------------------------------------------------
// Theme tokens — no hardcoded hex colours
// ---------------------------------------------------------------------------

describe('TabsComponent — token colours only', () => {
  it('when rendered, no inline hardcoded hex colour appears', async () => {
    const { fixture } = await setup();
    const hexPattern = /#[0-9a-fA-F]{3,8}\b/;
    const root = fixture.nativeElement as HTMLElement;
    const all: HTMLElement[] = [root, ...Array.from(root.querySelectorAll<HTMLElement>('*'))];
    for (const el of all) {
      expect(el.getAttribute('style') ?? '').not.toMatch(hexPattern);
    }
  });
});
