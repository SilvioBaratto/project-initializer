import { Component } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { TabsComponent, TabComponent, TabPanelComponent } from './tabs';

// ---------------------------------------------------------------------------
// Host stub
// ---------------------------------------------------------------------------

@Component({
  imports: [TabsComponent, TabComponent, TabPanelComponent],
  template: `
    <ui-tabs>
      <ui-tab [tabIndex]="0">Tab A</ui-tab>
      <ui-tab [tabIndex]="1">Tab B</ui-tab>
      <ui-tab [tabIndex]="2">Tab C</ui-tab>
      <ui-tab-panel [panelIndex]="0">Panel A</ui-tab-panel>
      <ui-tab-panel [panelIndex]="1">Panel B</ui-tab-panel>
      <ui-tab-panel [panelIndex]="2">Panel C</ui-tab-panel>
    </ui-tabs>
  `,
})
class HostComponent {}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function dispatchKey(target: EventTarget, key: string): void {
  target.dispatchEvent(
    new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true }),
  );
}

function tabList(f: ComponentFixture<unknown>): HTMLElement {
  return f.nativeElement.querySelector('[role="tablist"]')!;
}

function tabs(f: ComponentFixture<unknown>): HTMLElement[] {
  return Array.from(f.nativeElement.querySelectorAll('[role="tab"]'));
}

function panels(f: ComponentFixture<unknown>): HTMLElement[] {
  return Array.from(f.nativeElement.querySelectorAll('[role="tabpanel"]'));
}

function getTabs(f: ComponentFixture<unknown>): TabsComponent {
  return f.debugElement.children[0].componentInstance as TabsComponent;
}

// ---------------------------------------------------------------------------
// ARIA roles
// ---------------------------------------------------------------------------

describe('TabsComponent — ARIA roles', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [HostComponent] }).compileComponents();
  });

  it('when tabs render, a role="tablist" element is present', () => {
    const f = TestBed.createComponent(HostComponent);
    f.detectChanges();
    expect(tabList(f)).not.toBeNull();
  });

  it('when tabs render, all tab buttons carry role="tab"', () => {
    const f = TestBed.createComponent(HostComponent);
    f.detectChanges();
    expect(tabs(f).length).toBe(3);
  });

  it('when a tab is active, the visible panel carries role="tabpanel"', () => {
    const f = TestBed.createComponent(HostComponent);
    f.detectChanges();
    expect(panels(f).length).toBe(1);
    expect(panels(f)[0].getAttribute('role')).toBe('tabpanel');
  });
});

// ---------------------------------------------------------------------------
// ARIA attributes
// ---------------------------------------------------------------------------

describe('TabsComponent — ARIA attributes', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [HostComponent] }).compileComponents();
  });

  it('when tabs render, the active tab has aria-selected="true"', () => {
    const f = TestBed.createComponent(HostComponent);
    f.detectChanges();
    const activeTab = tabs(f)[0];
    expect(activeTab.getAttribute('aria-selected')).toBe('true');
  });

  it('when tabs render, inactive tabs have aria-selected="false"', () => {
    const f = TestBed.createComponent(HostComponent);
    f.detectChanges();
    const inactiveTab = tabs(f)[1];
    expect(inactiveTab.getAttribute('aria-selected')).toBe('false');
  });

  it('when tabs render, each tab has aria-controls pointing to a panel id', () => {
    const f = TestBed.createComponent(HostComponent);
    f.detectChanges();
    const tabEls = tabs(f);
    tabEls.forEach((tab) => {
      expect(tab.getAttribute('aria-controls')).toBeTruthy();
    });
  });

  it('when the active panel renders, it has aria-labelledby matching its tab id', () => {
    const f = TestBed.createComponent(HostComponent);
    f.detectChanges();
    const panel = panels(f)[0];
    const labelledBy = panel.getAttribute('aria-labelledby');
    expect(labelledBy).toBeTruthy();
    const tab = f.nativeElement.querySelector(`#${labelledBy}`);
    expect(tab).not.toBeNull();
    expect(tab.getAttribute('role')).toBe('tab');
  });

  it('when the panel renders, aria-controls on the tab matches the panel id', () => {
    const f = TestBed.createComponent(HostComponent);
    f.detectChanges();
    const activeTab = tabs(f)[0];
    const panel = panels(f)[0];
    expect(activeTab.getAttribute('aria-controls')).toBe(panel.id);
  });
});

// ---------------------------------------------------------------------------
// Roving tabindex
// ---------------------------------------------------------------------------

describe('TabsComponent — roving tabindex', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [HostComponent] }).compileComponents();
  });

  it('when tabs render, the active tab has tabindex=0', () => {
    const f = TestBed.createComponent(HostComponent);
    f.detectChanges();
    expect(tabs(f)[0].getAttribute('tabindex')).toBe('0');
  });

  it('when tabs render, inactive tabs have tabindex=-1', () => {
    const f = TestBed.createComponent(HostComponent);
    f.detectChanges();
    expect(tabs(f)[1].getAttribute('tabindex')).toBe('-1');
    expect(tabs(f)[2].getAttribute('tabindex')).toBe('-1');
  });

  it('when a tab is clicked, it becomes active with tabindex=0', () => {
    const f = TestBed.createComponent(HostComponent);
    f.detectChanges();
    tabs(f)[1].click();
    f.detectChanges();
    expect(tabs(f)[1].getAttribute('tabindex')).toBe('0');
    expect(tabs(f)[0].getAttribute('tabindex')).toBe('-1');
  });
});

// ---------------------------------------------------------------------------
// Keyboard navigation — ArrowRight / ArrowLeft
// ---------------------------------------------------------------------------

describe('TabsComponent — ArrowRight / ArrowLeft navigation', () => {
  let fixture: ComponentFixture<HostComponent>;
  let tabsEl: HTMLElement;

  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [HostComponent] }).compileComponents();
    fixture = TestBed.createComponent(HostComponent);
    fixture.detectChanges();
    tabsEl = fixture.nativeElement.querySelector('ui-tabs')!;
  });

  it('when ArrowRight is pressed, focus moves to the next tab', () => {
    dispatchKey(tabsEl, 'ArrowRight');
    fixture.detectChanges();
    expect(getTabs(fixture).activeIndex()).toBe(1);
  });

  it('when ArrowRight is pressed on the last tab, focus wraps to the first tab', () => {
    getTabs(fixture).activeIndex.set(2);
    fixture.detectChanges();
    dispatchKey(tabsEl, 'ArrowRight');
    fixture.detectChanges();
    expect(getTabs(fixture).activeIndex()).toBe(0);
  });

  it('when ArrowLeft is pressed, focus moves to the previous tab', () => {
    getTabs(fixture).activeIndex.set(2);
    fixture.detectChanges();
    dispatchKey(tabsEl, 'ArrowLeft');
    fixture.detectChanges();
    expect(getTabs(fixture).activeIndex()).toBe(1);
  });

  it('when ArrowLeft is pressed on the first tab, focus wraps to the last tab', () => {
    dispatchKey(tabsEl, 'ArrowLeft');
    fixture.detectChanges();
    expect(getTabs(fixture).activeIndex()).toBe(2);
  });
});

// ---------------------------------------------------------------------------
// Keyboard navigation — Home / End
// ---------------------------------------------------------------------------

describe('TabsComponent — Home / End navigation', () => {
  let fixture: ComponentFixture<HostComponent>;
  let tabsEl: HTMLElement;

  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [HostComponent] }).compileComponents();
    fixture = TestBed.createComponent(HostComponent);
    fixture.detectChanges();
    tabsEl = fixture.nativeElement.querySelector('ui-tabs')!;
  });

  it('when Home is pressed, focus moves to the first tab', () => {
    getTabs(fixture).activeIndex.set(2);
    fixture.detectChanges();
    dispatchKey(tabsEl, 'Home');
    fixture.detectChanges();
    expect(getTabs(fixture).activeIndex()).toBe(0);
  });

  it('when End is pressed, focus moves to the last tab', () => {
    dispatchKey(tabsEl, 'End');
    fixture.detectChanges();
    expect(getTabs(fixture).activeIndex()).toBe(2);
  });
});

// ---------------------------------------------------------------------------
// Keyboard activation — Enter / Space
// ---------------------------------------------------------------------------

describe('TabsComponent — Enter / Space activation', () => {
  let fixture: ComponentFixture<HostComponent>;
  let tabsEl: HTMLElement;
  let emitted: number[];

  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [HostComponent] }).compileComponents();
    fixture = TestBed.createComponent(HostComponent);
    fixture.detectChanges();
    tabsEl = fixture.nativeElement.querySelector('ui-tabs')!;
    emitted = [];
    getTabs(fixture).tabChanged.subscribe((i: number) => emitted.push(i));
  });

  it('when Enter is pressed, tabChanged emits the current index', () => {
    getTabs(fixture).activeIndex.set(1);
    fixture.detectChanges();
    dispatchKey(tabsEl, 'Enter');
    fixture.detectChanges();
    expect(emitted).toContain(1);
  });

  it('when Space is pressed, tabChanged emits the current index', () => {
    getTabs(fixture).activeIndex.set(2);
    fixture.detectChanges();
    dispatchKey(tabsEl, ' ');
    fixture.detectChanges();
    expect(emitted).toContain(2);
  });
});

// ---------------------------------------------------------------------------
// Panel visibility
// ---------------------------------------------------------------------------

describe('TabsComponent — panel visibility', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [HostComponent] }).compileComponents();
  });

  it('when tab 0 is active, Panel A content is visible', () => {
    const f = TestBed.createComponent(HostComponent);
    f.detectChanges();
    expect(f.nativeElement.textContent).toContain('Panel A');
    expect(f.nativeElement.textContent).not.toContain('Panel B');
  });

  it('when tab 1 is clicked, Panel B becomes visible', () => {
    const f = TestBed.createComponent(HostComponent);
    f.detectChanges();
    tabs(f)[1].click();
    f.detectChanges();
    expect(f.nativeElement.textContent).toContain('Panel B');
    expect(f.nativeElement.textContent).not.toContain('Panel A');
  });
});

// ---------------------------------------------------------------------------
// Dark-mode tokens — no hardcoded hex colours
// ---------------------------------------------------------------------------

describe('TabsComponent — token colours only', () => {
  it('when rendered, no inline hardcoded hex colour appears', async () => {
    await TestBed.configureTestingModule({ imports: [HostComponent] }).compileComponents();
    const f = TestBed.createComponent(HostComponent);
    f.detectChanges();
    const hexPattern = /#[0-9a-fA-F]{3,8}\b/;
    const root = f.nativeElement as HTMLElement;
    const all: HTMLElement[] = [root, ...Array.from(root.querySelectorAll<HTMLElement>('*'))];
    for (const el of all) {
      expect(el.getAttribute('style') ?? '').not.toMatch(hexPattern);
    }
  });
});
