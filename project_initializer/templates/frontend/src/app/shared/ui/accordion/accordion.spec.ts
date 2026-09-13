import { Component, signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { ComponentHarness, HarnessLoader, TestKey } from '@angular/cdk/testing';
import { TestbedHarnessEnvironment } from '@angular/cdk/testing/testbed';
import {
  MatAccordionHarness,
  MatExpansionPanelHarness,
} from '@angular/material/expansion/testing';

import { AccordionComponent, AccordionItemComponent } from './accordion';

// ---------------------------------------------------------------------------
// Host wrapper
// ---------------------------------------------------------------------------

@Component({
  imports: [AccordionComponent, AccordionItemComponent],
  template: `
    <ui-accordion [single]="single()">
      <ui-accordion-item [index]="0">
        <span slot="header">Section 1</span>
        Content 1
      </ui-accordion-item>
      <ui-accordion-item [index]="1">
        <span slot="header">Section 2</span>
        Content 2
      </ui-accordion-item>
      <ui-accordion-item [index]="2">
        <span slot="header">Section 3</span>
        Content 3
      </ui-accordion-item>
    </ui-accordion>
  `,
})
class HostComponent {
  readonly single = signal(false);
}

/** The panel harness keeps its header private; this reaches the header host to send keys. */
class PanelHeaderHarness extends ComponentHarness {
  static hostSelector = '.mat-expansion-panel-header';
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

interface Setup {
  fixture: ComponentFixture<HostComponent>;
  loader: HarnessLoader;
  accordion: AccordionComponent;
}

async function setupHost(single = false): Promise<Setup> {
  await TestBed.configureTestingModule({ imports: [HostComponent] }).compileComponents();

  const fixture = TestBed.createComponent(HostComponent);
  fixture.componentInstance.single.set(single);
  fixture.detectChanges();
  const loader = TestbedHarnessEnvironment.loader(fixture);
  const accordion = fixture.debugElement.query(By.directive(AccordionComponent))
    .componentInstance as AccordionComponent;
  return { fixture, loader, accordion };
}

function headers(f: ComponentFixture<unknown>): HTMLElement[] {
  const root = f.nativeElement as HTMLElement;
  return Array.from(root.querySelectorAll<HTMLElement>('.mat-expansion-panel-header'));
}

function regionFor(f: ComponentFixture<unknown>, header: HTMLElement): HTMLElement | null {
  const root = f.nativeElement as HTMLElement;
  return root.querySelector<HTMLElement>(`[id="${header.getAttribute('aria-controls')}"]`);
}

/** Material's header reads the legacy `keyCode`, which a constructed KeyboardEvent leaves at 0. */
function keydown(key: string, keyCode: number): KeyboardEvent {
  const event = new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true });
  Object.defineProperty(event, 'keyCode', { get: () => keyCode });
  return event;
}

// ===========================================================================
// Header semantics (provided by Material's expansion panel header)
// ===========================================================================

describe('AccordionComponent — header semantics', () => {
  it('when rendered, each item has one header exposed as a button', async () => {
    const { fixture } = await setupHost();
    const btns = headers(fixture);
    expect(btns.length).toBe(3);
    btns.forEach((btn) => expect(btn.getAttribute('role')).toBe('button'));
  });

  it('when rendered, each header is in the tab order', async () => {
    const { fixture } = await setupHost();
    headers(fixture).forEach((btn) => expect(btn.getAttribute('tabindex')).toBe('0'));
  });

  it('when rendered, each header has aria-expanded and aria-controls', async () => {
    const { fixture } = await setupHost();
    headers(fixture).forEach((btn) => {
      expect(btn.hasAttribute('aria-expanded')).toBe(true);
      expect(btn.getAttribute('aria-controls')).toBeTruthy();
    });
  });

  it('when an item is collapsed, its header has aria-expanded="false"', async () => {
    const { fixture } = await setupHost();
    expect(headers(fixture)[0].getAttribute('aria-expanded')).toBe('false');
  });

  it('when a header is clicked, its header has aria-expanded="true"', async () => {
    const { fixture } = await setupHost();
    headers(fixture)[0].click();
    fixture.detectChanges();
    expect(headers(fixture)[0].getAttribute('aria-expanded')).toBe('true');
  });

  it('when rendered, the projected header slot is the panel title', async () => {
    const { loader } = await setupHost();
    const panels = await loader.getAllHarnesses(MatExpansionPanelHarness);
    expect(await Promise.all(panels.map((p) => p.getTitle()))).toEqual([
      'Section 1',
      'Section 2',
      'Section 3',
    ]);
  });

  it('when rendered, Material draws the chevron and no extra icon is added', async () => {
    const { fixture, loader } = await setupHost();
    const panel = await loader.getHarness(MatExpansionPanelHarness);
    expect(await panel.hasToggleIndicator()).toBe(true);
    expect((fixture.nativeElement as HTMLElement).querySelector('lucide-icon')).toBeNull();
  });
});

// ===========================================================================
// Panels: role="region" + aria-labelledby, hidden while collapsed
// ===========================================================================

describe('AccordionComponent — panels', () => {
  it('when rendered, each header controls a role="region" panel labelled by the header', async () => {
    const { fixture } = await setupHost();
    headers(fixture).forEach((btn) => {
      const panel = regionFor(fixture, btn);
      expect(panel).not.toBeNull();
      expect(panel!.getAttribute('role')).toBe('region');
      expect(btn.id).toBeTruthy();
      expect(panel!.getAttribute('aria-labelledby')).toBe(btn.id);
    });
  });

  it('when an item is collapsed, its panel content is inert', async () => {
    const { fixture } = await setupHost();
    const panel = regionFor(fixture, headers(fixture)[0])!;
    expect(panel.parentElement!.hasAttribute('inert')).toBe(true);
  });

  it('when an item is expanded, its panel content is reachable and rendered', async () => {
    const { fixture, loader } = await setupHost();
    const [first] = await loader.getAllHarnesses(MatExpansionPanelHarness);
    await first.expand();
    const panel = regionFor(fixture, headers(fixture)[0])!;
    expect(panel.parentElement!.hasAttribute('inert')).toBe(false);
    expect(await first.getTextContent()).toContain('Content 1');
  });

  it('when an item is collapsed after being expanded, its panel is inert again', async () => {
    const { fixture, loader } = await setupHost();
    const [first] = await loader.getAllHarnesses(MatExpansionPanelHarness);
    await first.expand();
    await first.collapse();
    expect(await first.isExpanded()).toBe(false);
    const panel = regionFor(fixture, headers(fixture)[0])!;
    expect(panel.parentElement!.hasAttribute('inert')).toBe(true);
  });
});

// ===========================================================================
// Keyboard
// ===========================================================================

describe('AccordionComponent — keyboard', () => {
  it('when Enter is pressed on a header, the item toggles', async () => {
    const { accordion, loader } = await setupHost();
    const [header] = await loader.getAllHarnesses(PanelHeaderHarness);
    await (await header.host()).sendKeys(TestKey.ENTER);
    expect(accordion.isExpanded(0)).toBe(true);
    await (await header.host()).sendKeys(TestKey.ENTER);
    expect(accordion.isExpanded(0)).toBe(false);
  });

  it('when Space is pressed on a header, the item toggles and page scroll is prevented', async () => {
    const { fixture, accordion } = await setupHost();
    const event = keydown(' ', 32);
    headers(fixture)[1].dispatchEvent(event);
    fixture.detectChanges();
    expect(event.defaultPrevented).toBe(true);
    expect(accordion.isExpanded(1)).toBe(true);
    expect(headers(fixture)[1].getAttribute('aria-expanded')).toBe('true');
  });

  it('when ArrowDown is pressed on a header, focus moves to the next header', async () => {
    const { fixture, loader } = await setupHost();
    const hs = await loader.getAllHarnesses(PanelHeaderHarness);
    await (await hs[0].host()).sendKeys(TestKey.DOWN_ARROW);
    expect(document.activeElement).toBe(headers(fixture)[1]);
  });

  it('when ArrowUp is pressed on the first header, focus wraps to the last header', async () => {
    const { fixture, loader } = await setupHost();
    const hs = await loader.getAllHarnesses(PanelHeaderHarness);
    await (await hs[0].host()).sendKeys(TestKey.UP_ARROW);
    expect(document.activeElement).toBe(headers(fixture)[2]);
  });

  it('when End and Home are pressed, focus jumps to the last and first header', async () => {
    const { fixture, loader } = await setupHost();
    const hs = await loader.getAllHarnesses(PanelHeaderHarness);
    await (await hs[0].host()).sendKeys(TestKey.END);
    expect(document.activeElement).toBe(headers(fixture)[2]);
    await (await hs[2].host()).sendKeys(TestKey.HOME);
    expect(document.activeElement).toBe(headers(fixture)[0]);
  });

  it('when an arrow key moves focus, no item changes its expansion', async () => {
    const { accordion, loader } = await setupHost();
    const hs = await loader.getAllHarnesses(PanelHeaderHarness);
    await (await hs[0].host()).sendKeys(TestKey.DOWN_ARROW);
    expect([0, 1, 2].map((i) => accordion.isExpanded(i))).toEqual([false, false, false]);
  });
});

// ===========================================================================
// Multi-open (default) and single-open modes
// ===========================================================================

describe('AccordionComponent — expansion modes', () => {
  it('when single is false, the Material accordion is multi and two items stay open', async () => {
    const { loader, accordion } = await setupHost(false);
    const acc = await loader.getHarness(MatAccordionHarness);
    expect(await acc.isMulti()).toBe(true);

    const panels = await acc.getExpansionPanels();
    await panels[0].expand();
    await panels[1].expand();
    expect(await acc.getExpansionPanels({ expanded: true })).toHaveLength(2);
    expect(accordion.isExpanded(0)).toBe(true);
    expect(accordion.isExpanded(1)).toBe(true);
  });

  it('when single is true and item 0 is open, opening item 1 closes item 0', async () => {
    const { loader, accordion } = await setupHost(true);
    const acc = await loader.getHarness(MatAccordionHarness);
    expect(await acc.isMulti()).toBe(false);

    const panels = await acc.getExpansionPanels();
    await panels[0].expand();
    expect(accordion.isExpanded(0)).toBe(true);

    await panels[1].expand();
    expect(await panels[0].isExpanded()).toBe(false);
    expect(await panels[1].isExpanded()).toBe(true);
    expect(accordion.isExpanded(0)).toBe(false);
    expect(accordion.isExpanded(1)).toBe(true);
  });

  it('when single changes at runtime, the Material accordion follows it', async () => {
    const { fixture, loader } = await setupHost(false);
    const acc = await loader.getHarness(MatAccordionHarness);
    fixture.componentInstance.single.set(true);
    fixture.detectChanges();
    expect(await acc.isMulti()).toBe(false);
  });

  it('when single is given as a bare attribute, it is coerced to true and the accordion is not multi', async () => {
    @Component({
      imports: [AccordionComponent, AccordionItemComponent],
      template: `
        <ui-accordion single>
          <ui-accordion-item [index]="0">
            <span slot="header">Section 1</span>
            Content 1
          </ui-accordion-item>
          <ui-accordion-item [index]="1">
            <span slot="header">Section 2</span>
            Content 2
          </ui-accordion-item>
        </ui-accordion>
      `,
    })
    class BareSingleHostComponent {}

    await TestBed.configureTestingModule({ imports: [BareSingleHostComponent] }).compileComponents();
    const fixture = TestBed.createComponent(BareSingleHostComponent);
    fixture.detectChanges();
    const acc = await TestbedHarnessEnvironment.loader(fixture).getHarness(MatAccordionHarness);
    expect(await acc.isMulti()).toBe(false);
  });
});

// ===========================================================================
// Programmatic API (AccordionContext)
// ===========================================================================

describe('AccordionComponent — toggle() / isExpanded()', () => {
  it('when toggle() is called, the panel and its header reflect the new state', async () => {
    const { fixture, loader, accordion } = await setupHost();
    accordion.toggle(2);
    fixture.detectChanges();
    const panels = await loader.getAllHarnesses(MatExpansionPanelHarness);
    expect(await panels[2].isExpanded()).toBe(true);
    expect(headers(fixture)[2].getAttribute('aria-expanded')).toBe('true');

    accordion.toggle(2);
    fixture.detectChanges();
    expect(await panels[2].isExpanded()).toBe(false);
  });

  it('when single is true, toggle() on another item closes the open one', async () => {
    const { fixture, loader, accordion } = await setupHost(true);
    accordion.toggle(0);
    fixture.detectChanges();
    accordion.toggle(2);
    fixture.detectChanges();
    const panels = await loader.getAllHarnesses(MatExpansionPanelHarness);
    expect(await Promise.all(panels.map((p) => p.isExpanded()))).toEqual([false, false, true]);
  });

  it('when a header is clicked, isExpanded() reports the toggle', async () => {
    const { fixture, accordion } = await setupHost();
    expect(accordion.isExpanded(0)).toBe(false);
    headers(fixture)[0].click();
    fixture.detectChanges();
    expect(accordion.isExpanded(0)).toBe(true);
  });
});

// ===========================================================================
// Token colours only
// ===========================================================================

describe('AccordionComponent — token colours only', () => {
  it('when rendered, no hardcoded hex colours appear in inline element styles', async () => {
    const { fixture } = await setupHost();
    headers(fixture)[0].click();
    fixture.detectChanges();
    const hexPattern = /#[0-9a-fA-F]{3,8}\b/;
    const root = fixture.nativeElement as HTMLElement;
    const all: HTMLElement[] = [root, ...Array.from(root.querySelectorAll<HTMLElement>('*'))];
    for (const el of all) {
      expect(el.getAttribute('style') ?? '').not.toMatch(hexPattern);
    }
  });
});

// ===========================================================================
// State layers, ring corners and header motion (hooks the item CSS keys on)
// ===========================================================================

/** Text of every stylesheet Angular has attached to the document for the rendered components. */
function documentStyles(): string {
  return Array.from(document.querySelectorAll('style'))
    .map((style) => style.textContent ?? '')
    .join('\n');
}

describe('AccordionComponent — state layers and header motion', () => {
  it('when rendered, each header hosts Material focus indicator, which the ring corner tokens drive', async () => {
    const { fixture } = await setupHost();
    headers(fixture).forEach((btn) => expect(btn.classList).toContain('mat-focus-indicator'));
  });

  it('when an item is expanded, only its header carries .mat-expanded', async () => {
    const { fixture } = await setupHost();
    headers(fixture)[2].click();
    fixture.detectChanges();
    expect(headers(fixture).map((btn) => btn.classList.contains('mat-expanded'))).toEqual([
      false,
      false,
      true,
    ]);
  });

  it('when rendered, the item stylesheet draws a hover layer on every header, expanded included', async () => {
    await setupHost();
    const css = documentStyles();
    const hoverRule = css.match(
      /@media\s*\(hover:\s*hover\)\s*\{\s*([^{}]*:hover::after)\s*\{([^{}]*)\}/,
    );
    expect(hoverRule).not.toBeNull();
    expect(hoverRule![1]).toContain('.mat-expansion-panel-header');
    expect(hoverRule![1]).not.toContain('mat-expanded');
    expect(hoverRule![2]).toMatch(/opacity:\s*var\(--mat-sys-hover-state-layer-opacity\)/);
    expect(hoverRule![2]).toMatch(/background:\s*var\(--mat-sys-on-surface\)/);
  });

  it('when animations are enabled, the header minimum height transitions with the body', async () => {
    await setupHost();
    expect(documentStyles()).toMatch(
      /\.mat-expansion-panel-animations-enabled[^{}]*\.mat-expansion-panel-header[^{}]*\{\s*transition:\s*min-block-size 225ms/,
    );
  });
});

// ===========================================================================
// Sanity — direct component
// ===========================================================================

describe('AccordionComponent — direct setup', () => {
  it('when created, the component renders as a Material accordion', async () => {
    await TestBed.configureTestingModule({ imports: [AccordionComponent] }).compileComponents();
    const f = TestBed.createComponent(AccordionComponent);
    f.detectChanges();
    expect(f.componentInstance).toBeTruthy();
    expect((f.nativeElement as HTMLElement).classList).toContain('mat-accordion');
  });
});
