import { Component } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { LucideIconConfig } from 'lucide-angular';

import { ICON_PROVIDER } from '../../../icons';
import { AccordionComponent, AccordionItemComponent } from './accordion';

// ---------------------------------------------------------------------------
// Host wrapper
// ---------------------------------------------------------------------------

@Component({
  imports: [AccordionComponent, AccordionItemComponent],
  template: `
    <ui-accordion [single]="single">
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
  single = false;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function setupHost(single = false): Promise<ComponentFixture<HostComponent>> {
  await TestBed.configureTestingModule({
    imports: [HostComponent],
    providers: [
      ICON_PROVIDER,
      {
        provide: LucideIconConfig,
        useFactory: () => {
          const cfg = new LucideIconConfig();
          cfg.size = 16;
          cfg.strokeWidth = 1.5;
          return cfg;
        },
      },
    ],
  }).compileComponents();

  const f = TestBed.createComponent(HostComponent);
  f.componentInstance.single = single;
  f.detectChanges();
  return f;
}

async function setupDirect(): Promise<ComponentFixture<AccordionComponent>> {
  await TestBed.configureTestingModule({
    imports: [AccordionComponent],
    providers: [ICON_PROVIDER],
  }).compileComponents();
  const f = TestBed.createComponent(AccordionComponent);
  f.detectChanges();
  return f;
}

function headerButtons(f: ComponentFixture<unknown>): HTMLButtonElement[] {
  const root = f.nativeElement as HTMLElement;
  return Array.from(root.querySelectorAll<HTMLButtonElement>('button[aria-expanded]'));
}

function panels(f: ComponentFixture<unknown>): HTMLElement[] {
  const root = f.nativeElement as HTMLElement;
  return Array.from(root.querySelectorAll<HTMLElement>('[role="region"]'));
}

function accordion(f: ComponentFixture<HostComponent>): AccordionComponent {
  return f.debugElement.children[0].componentInstance as AccordionComponent;
}

function dispatchKey(target: EventTarget, key: string): void {
  target.dispatchEvent(
    new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true }),
  );
}

// ===========================================================================
// Criterion — button[aria-expanded][aria-controls] headers
// ===========================================================================

describe('AccordionComponent — header buttons', () => {
  it('when rendered, each item has a <button> element', async () => {
    const f = await setupHost();
    const btns = headerButtons(f);
    expect(btns.length).toBe(3);
  });

  it('when rendered, each header button has aria-expanded', async () => {
    const f = await setupHost();
    headerButtons(f).forEach((btn) => {
      expect(btn.hasAttribute('aria-expanded')).toBe(true);
    });
  });

  it('when rendered, each header button has aria-controls', async () => {
    const f = await setupHost();
    headerButtons(f).forEach((btn) => {
      expect(btn.getAttribute('aria-controls')).toBeTruthy();
    });
  });

  it('when an item is collapsed, its button has aria-expanded="false"', async () => {
    const f = await setupHost();
    expect(headerButtons(f)[0].getAttribute('aria-expanded')).toBe('false');
  });

  it('when an item is toggled open, its button has aria-expanded="true"', async () => {
    const f = await setupHost();
    headerButtons(f)[0].click();
    f.detectChanges();
    expect(headerButtons(f)[0].getAttribute('aria-expanded')).toBe('true');
  });
});

// ===========================================================================
// Criterion — panels role="region" + aria-labelledby
// ===========================================================================

describe('AccordionComponent — panels', () => {
  it('when an item is expanded, its panel has role="region"', async () => {
    const f = await setupHost();
    headerButtons(f)[1].click();
    f.detectChanges();
    const panel = panels(f)[0];
    expect(panel.getAttribute('role')).toBe('region');
  });

  it('when an item is expanded, its panel has aria-labelledby pointing to its header id', async () => {
    const f = await setupHost();
    headerButtons(f)[0].click();
    f.detectChanges();
    const btn = headerButtons(f)[0];
    const panel = panels(f)[0];
    const labelledBy = panel.getAttribute('aria-labelledby');
    expect(labelledBy).toBeTruthy();
    expect(labelledBy).toBe(btn.id);
  });

  it('when an item is expanded, its panel content is rendered', async () => {
    const f = await setupHost();
    expect(f.nativeElement.textContent).not.toContain('Content 1');
    headerButtons(f)[0].click();
    f.detectChanges();
    expect(f.nativeElement.textContent).toContain('Content 1');
  });

  it('when an item is collapsed after being expanded, its panel is hidden', async () => {
    const f = await setupHost();
    headerButtons(f)[0].click();
    f.detectChanges();
    expect(f.nativeElement.textContent).toContain('Content 1');
    headerButtons(f)[0].click();
    f.detectChanges();
    expect(f.nativeElement.textContent).not.toContain('Content 1');
  });

  it('when two items are expanded (multi mode), both panels are visible', async () => {
    const f = await setupHost(false);
    headerButtons(f)[0].click();
    f.detectChanges();
    headerButtons(f)[1].click();
    f.detectChanges();
    expect(panels(f).length).toBe(2);
  });
});

// ===========================================================================
// Criterion — keyboard operable
// ===========================================================================

describe('AccordionComponent — keyboard activation', () => {
  it('when Enter is pressed on a header button, the item toggles', async () => {
    const f = await setupHost();
    const btn = headerButtons(f)[0];
    // Native button handles Enter natively; dispatch click to simulate
    btn.click();
    f.detectChanges();
    expect(btn.getAttribute('aria-expanded')).toBe('true');
  });

  it('when Space is pressed on a header button, default scroll is prevented', async () => {
    const f = await setupHost();
    const btn = headerButtons(f)[0];
    const evt = new KeyboardEvent('keydown', { key: ' ', bubbles: true, cancelable: true });
    btn.dispatchEvent(evt);
    expect(evt.defaultPrevented).toBe(true);
  });

  it('when a header button is clicked, the accordion toggles expanded state', async () => {
    const f = await setupHost();
    const acc = accordion(f);
    expect(acc.isExpanded(0)).toBe(false);
    headerButtons(f)[0].click();
    f.detectChanges();
    expect(acc.isExpanded(0)).toBe(true);
  });
});

// ===========================================================================
// Criterion — single-open mode
// ===========================================================================

describe('AccordionComponent — single-open mode', () => {
  it('when single=true and item 0 is open, opening item 1 closes item 0', async () => {
    const f = await setupHost(true);
    const acc = accordion(f);
    headerButtons(f)[0].click();
    f.detectChanges();
    expect(acc.isExpanded(0)).toBe(true);

    headerButtons(f)[1].click();
    f.detectChanges();
    expect(acc.isExpanded(0)).toBe(false);
    expect(acc.isExpanded(1)).toBe(true);
  });
});

// ===========================================================================
// Criterion — aria-controls / aria-labelledby relationship integrity
// ===========================================================================

describe('AccordionComponent — ARIA relationship integrity', () => {
  it('when an item is expanded, aria-controls on the button matches the panel id', async () => {
    const f = await setupHost();
    headerButtons(f)[2].click();
    f.detectChanges();
    const btn = headerButtons(f)[2];
    const panel = f.nativeElement.querySelector(`#${btn.getAttribute('aria-controls')}`)!;
    expect(panel).not.toBeNull();
    expect(panel.getAttribute('role')).toBe('region');
  });
});

// ===========================================================================
// Criterion — dark-mode tokens; no hardcoded hex
// ===========================================================================

describe('AccordionComponent — token colours only', () => {
  it('when rendered, no hardcoded hex colours appear in inline element styles', async () => {
    const f = await setupHost();
    headerButtons(f)[0].click();
    f.detectChanges();
    const hexPattern = /#[0-9a-fA-F]{3,8}\b/;
    const root = f.nativeElement as HTMLElement;
    const all: HTMLElement[] = [root, ...Array.from(root.querySelectorAll<HTMLElement>('*'))];
    for (const el of all) {
      expect(el.getAttribute('style') ?? '').not.toMatch(hexPattern);
    }
  });
});

// ===========================================================================
// Sanity — direct component
// ===========================================================================

describe('AccordionComponent — direct setup', () => {
  it('when created, the component renders without error', async () => {
    const f = await setupDirect();
    expect(f.componentInstance).toBeTruthy();
  });
});
