import { Component, signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { vi } from 'vitest';
import { TestbedHarnessEnvironment } from '@angular/cdk/testing/testbed';
import { MatListModule } from '@angular/material/list';
import { MatListHarness } from '@angular/material/list/testing';
import { LucideAngularModule } from 'lucide-angular';

import { ICON_PROVIDER } from '../../../icons';
import { ListComponent, ListVariant } from './list';

// ---------------------------------------------------------------------------
// Host wrappers for content projection tests
// ---------------------------------------------------------------------------

@Component({
  imports: [ListComponent, MatListModule],
  template: `
    <ui-list [variant]="variant()">
      @for (item of items(); track item) {
        <mat-list-item>{{ item }}</mat-list-item>
      }
    </ui-list>
  `,
})
class HostComponent {
  readonly variant = signal<ListVariant>('default');
  readonly items = signal(['Item A', 'Item B', 'Item C']);
}

@Component({
  imports: [ListComponent, MatListModule, LucideAngularModule],
  template: `
    <ui-list>
      <mat-list-item>
        <lucide-icon matListItemIcon name="Mail" />
        <span matListItemTitle>Inbox</span>
        <span matListItemLine>Two new messages</span>
      </mat-list-item>
      <mat-list-item role="presentation">Consumer role</mat-list-item>
    </ui-list>
  `,
})
class SlotsHostComponent {}

@Component({
  imports: [ListComponent, MatListModule],
  template: `
    <ui-list>
      <mat-list-item>Static row</mat-list-item>
      <button mat-list-item>Archive message</button>
      <a mat-list-item href="#">Open inbox</a>
    </ui-list>
  `,
})
class InteractiveRowsHostComponent {}

@Component({
  imports: [ListComponent, MatListModule],
  template: `
    <ui-list>
      <mat-list-item lines="3">
        <span matListItemTitle>Release notes</span>
        The new version adds offline editing, faster search across every project, and a redesigned
        settings page with clearer privacy controls
      </mat-list-item>
    </ui-list>
  `,
})
class ThreeLineHostComponent {}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function render<T>(component: new () => T): Promise<ComponentFixture<T>> {
  await TestBed.configureTestingModule({
    imports: [component],
    providers: [ICON_PROVIDER],
  }).compileComponents();

  const f = TestBed.createComponent(component);
  f.detectChanges();
  await f.whenStable();
  return f;
}

async function setupHost(variant: ListVariant = 'default'): Promise<ComponentFixture<HostComponent>> {
  const f = await render(HostComponent);
  f.componentInstance.variant.set(variant);
  f.detectChanges();
  await f.whenStable();
  return f;
}

function matList(f: ComponentFixture<unknown>): HTMLElement {
  return (f.nativeElement as HTMLElement).querySelector('mat-list')!;
}

function listItems(f: ComponentFixture<unknown>): HTMLElement[] {
  return Array.from((f.nativeElement as HTMLElement).querySelectorAll<HTMLElement>('mat-list-item'));
}

/** Text of the unencapsulated stylesheet the component adds to the document. */
function listStylesheet(): string {
  return Array.from(document.querySelectorAll('style'))
    .map((style) => style.textContent ?? '')
    .filter((css) => css.includes('.app-list'))
    .join('\n');
}

/** Selectors of the list stylesheet rules whose declarations match `declaration`. */
function selectorsDeclaring(declaration: RegExp): string[] {
  const css = listStylesheet().replace(/\/\*[\s\S]*?\*\//g, '');
  return Array.from(css.matchAll(/([^{}]+)\{([^{}]*)\}/g))
    .filter(([, , body]) => declaration.test(body))
    .map(([, selector]) => selector.trim());
}

/** True when `el` is matched by a list rule that declares `declaration`. */
function styledBy(el: Element, declaration: RegExp): boolean {
  return selectorsDeclaring(declaration).some((selector) => el.matches(selector));
}

// ===========================================================================
// Criterion — Material list with list semantics
// ===========================================================================

describe('ListComponent — semantic element', () => {
  it('when created, the component renders without error', async () => {
    const f = await render(ListComponent);
    expect(f.componentInstance).toBeTruthy();
  });

  it('when rendered, the host carries the app-list class that scopes its styles', async () => {
    const f = await setupHost();
    expect((f.nativeElement as HTMLElement).querySelector('ui-list')!.classList).toContain('app-list');
  });

  it('when rendered, a Material list is present', async () => {
    const f = await setupHost();
    const loader = TestbedHarnessEnvironment.loader(f);
    expect(await loader.getAllHarnesses(MatListHarness)).toHaveLength(1);
  });

  it('when rendered, the list carries role="list"', async () => {
    const f = await setupHost();
    expect(matList(f).getAttribute('role')).toBe('list');
  });

  it('when items are projected, every item gets role="listitem"', async () => {
    const f = await setupHost();
    const items = listItems(f);
    expect(items).toHaveLength(3);
    for (const item of items) {
      expect(item.getAttribute('role')).toBe('listitem');
    }
  });

  it('when an item is added later, it also gets role="listitem"', async () => {
    const f = await setupHost();
    f.componentInstance.items.set(['Item A', 'Item B', 'Item C', 'Item D']);
    f.detectChanges();
    await f.whenStable();

    const items = listItems(f);
    expect(items).toHaveLength(4);
    expect(items[3].getAttribute('role')).toBe('listitem');
  });

  it('when an item declares its own role, the consumer role is kept', async () => {
    const f = await render(SlotsHostComponent);
    const [first, second] = listItems(f);
    expect(first.getAttribute('role')).toBe('listitem');
    expect(second.getAttribute('role')).toBe('presentation');
  });

  describe('with native interactive rows', () => {
    afterEach(() => {
      vi.restoreAllMocks();
    });

    function rows(f: ComponentFixture<unknown>): Record<'static' | 'button' | 'link', HTMLElement> {
      const root = f.nativeElement as HTMLElement;
      return {
        static: root.querySelector<HTMLElement>('mat-list-item')!,
        button: root.querySelector<HTMLElement>('button[mat-list-item]')!,
        link: root.querySelector<HTMLElement>('a[mat-list-item]')!,
      };
    }

    it('when a button or link row is projected, no role is written over its native role', async () => {
      vi.spyOn(console, 'warn').mockImplementation(() => undefined);
      const f = await render(InteractiveRowsHostComponent);
      const { static: staticRow, button, link } = rows(f);

      expect(staticRow.getAttribute('role')).toBe('listitem');
      expect(button.hasAttribute('role')).toBe(false);
      expect(link.hasAttribute('role')).toBe(false);
    });

    it('when a button or link row is projected, dev mode warns once per row naming the interactive lists', async () => {
      const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
      const f = await render(InteractiveRowsHostComponent);
      f.detectChanges();
      await f.whenStable();

      const messages = warn.mock.calls.map(([message]) => String(message));
      expect(messages).toHaveLength(2);
      expect(messages.some((m) => m.includes('<button mat-list-item>'))).toBe(true);
      expect(messages.some((m) => m.includes('<a mat-list-item>'))).toBe(true);
      for (const message of messages) {
        expect(message).toContain('mat-action-list');
        expect(message).toContain('mat-nav-list');
      }
    });

    it('when only static rows are projected, no warning is logged', async () => {
      const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
      await setupHost();
      expect(warn).not.toHaveBeenCalled();
    });
  });

  it('when content is projected, the items appear inside the list in order', async () => {
    const f = await setupHost();
    const loader = TestbedHarnessEnvironment.loader(f);
    const list = await loader.getHarness(MatListHarness);
    const texts = await Promise.all((await list.getItems()).map((item) => item.getFullText()));
    expect(texts).toEqual(['Item A', 'Item B', 'Item C']);
  });
});

// ===========================================================================
// Criterion — Material item slots (title, supporting line, leading icon)
// ===========================================================================

describe('ListComponent — item slots', () => {
  it('when an item projects a title and a line, it renders as a two-line item', async () => {
    const f = await render(SlotsHostComponent);
    const loader = TestbedHarnessEnvironment.loader(f);
    const [item] = await (await loader.getHarness(MatListHarness)).getItems();

    expect(await item.getTitle()).toBe('Inbox');
    expect(await item.getSecondaryText()).toBe('Two new messages');
    expect(listItems(f)[0].classList).toContain('mdc-list-item--with-two-lines');
  });

  it('when an item projects a leading icon, the icon fills the leading slot', async () => {
    const f = await render(SlotsHostComponent);
    const loader = TestbedHarnessEnvironment.loader(f);
    const [item] = await (await loader.getHarness(MatListHarness)).getItems();

    expect(await item.hasIcon()).toBe(true);
    expect(listItems(f)[0].classList).toContain('mdc-list-item--with-leading-icon');
  });

  it('when an item projects a decorative icon, the icon is hidden from assistive technology', async () => {
    const f = await render(SlotsHostComponent);
    const icon = (f.nativeElement as HTMLElement).querySelector('lucide-icon')!;
    expect(icon.getAttribute('aria-hidden')).toBe('true');
  });
});

// ===========================================================================
// Criterion — variants
// ===========================================================================

describe('ListComponent — variants', () => {
  it.each<ListVariant>(['default', 'divided', 'striped'])(
    'when variant is %s, the list reflects it in data-variant',
    async (variant) => {
      const f = await setupHost(variant);
      expect(matList(f).getAttribute('data-variant')).toBe(variant);
    },
  );

  it('when variant is divided, the stylesheet draws dividers from the mat-divider tokens with outline-variant fallback', async () => {
    await setupHost('divided');
    const divided = /data-variant=["']?divided["']?\][^{]*\{([^}]*)\}/.exec(listStylesheet());
    expect(divided).not.toBeNull();
    const rule = divided![1];
    expect(rule).toMatch(/var\(--mat-divider-width,\s*1px\)/);
    expect(rule).toMatch(/var\(--mat-divider-color,\s*var\(--mat-sys-outline-variant\)\)/);
  });

  it('when variant is striped, the stylesheet tints odd items through the list item container token', async () => {
    await setupHost('striped');
    expect(listStylesheet()).toMatch(
      /data-variant=["']?striped["']?\][^{]*\{[^}]*--mat-list-list-item-container-color:\s*var\(--mat-sys-surface-container\)/,
    );
  });

  it('when rendered, the stylesheet paints the group from surface tokens', async () => {
    await setupHost();
    const css = listStylesheet();
    expect(css).toContain('var(--mat-sys-surface)');
    expect(css).toContain('var(--mat-sys-on-surface)');
    expect(css).toContain('var(--mat-sys-corner-medium)');
  });
});

// ===========================================================================
// Criterion — text is never cut off (200% text, longer translations)
// ===========================================================================

describe('ListComponent — flexible items for larger text', () => {
  it('when a one-line item renders, its fixed height gives way to a 48px minimum that grows with text size', async () => {
    const f = await setupHost();
    const item = listItems(f)[0];

    expect(item.classList).toContain('mdc-list-item--with-one-line');
    expect(styledBy(item, /(?:^|[;\s])block-size:\s*auto/)).toBe(true);
    expect(styledBy(item, /min-block-size:\s*max\(48px,\s*3rem\)/)).toBe(true);
    expect(styledBy(item.querySelector('.mdc-list-item__content')!, /padding-block:\s*8px/)).toBe(true);
  });

  it('when a two-line item renders, its fixed height gives way to a 64px minimum that grows with text size', async () => {
    const f = await render(SlotsHostComponent);
    const item = listItems(f)[0];

    expect(item.classList).toContain('mdc-list-item--with-two-lines');
    expect(styledBy(item, /(?:^|[;\s])block-size:\s*auto/)).toBe(true);
    expect(styledBy(item, /min-block-size:\s*max\(64px,\s*4rem\)/)).toBe(true);
    expect(styledBy(item.querySelector('.mdc-list-item__content')!, /padding-block-end:\s*4px/)).toBe(true);
  });

  it('when an item has a title and a supporting line, both wrap instead of truncating', async () => {
    const f = await render(SlotsHostComponent);
    const item = listItems(f)[0];
    const wraps = /white-space:\s*normal;[^}]*overflow-wrap:\s*anywhere/;

    expect(styledBy(item.querySelector('.mat-mdc-list-item-title')!, wraps)).toBe(true);
    expect(styledBy(item.querySelector('.mat-mdc-list-item-line')!, wraps)).toBe(true);
  });

  it('when an item holds plain text, that text wraps instead of truncating', async () => {
    const f = await setupHost();
    const text = listItems(f)[0].querySelector('.mat-mdc-list-item-unscoped-content')!;

    expect(text.textContent!.trim()).toBe('Item A');
    expect(styledBy(text, /white-space:\s*normal/)).toBe(true);
  });

  it('when a three-line item holds plain supporting text, Material\'s two-line clamp is lifted', async () => {
    const f = await render(ThreeLineHostComponent);
    const item = listItems(f)[0];
    const text = item.querySelector('.mat-mdc-list-item-unscoped-content')!;

    expect(item.classList).toContain('mdc-list-item--with-three-lines');
    expect(text.classList).toContain('mdc-list-item__secondary-text');
    expect(styledBy(text, /display:\s*block;[^}]*-webkit-line-clamp:\s*none/)).toBe(true);
    expect(
      styledBy(
        text,
        /line-height:\s*var\(--mat-list-list-item-supporting-text-line-height,\s*var\(--mat-sys-body-medium-line-height\)\)/,
      ),
    ).toBe(true);
    expect(styledBy(text, /white-space:\s*normal/)).toBe(true);
    expect(styledBy(item, /min-block-size:\s*max\(88px,\s*5\.5rem\)/)).toBe(true);
  });

  it('when rendered, the stylesheet sets no fixed list item height tokens', async () => {
    await setupHost();
    expect(listStylesheet()).not.toMatch(/--mat-list-list-item-(?:one|two|three)-line-container-height/);
  });
});

// ===========================================================================
// Criterion — Signal input reactivity
// ===========================================================================

describe('ListComponent — signal input reactivity', () => {
  it('when variant input changes from default to divided, the list switches variant', async () => {
    const f = await render(ListComponent);
    expect(matList(f).getAttribute('data-variant')).toBe('default');

    f.componentRef.setInput('variant', 'divided');
    f.detectChanges();
    await f.whenStable();
    expect(matList(f).getAttribute('data-variant')).toBe('divided');
  });
});

// ===========================================================================
// Criterion — token colours only; no hardcoded literals
// ===========================================================================

describe('ListComponent — token colours only', () => {
  const colorLiteral = /#[0-9a-fA-F]{3,8}\b|\b(?:rgba?|hsla?)\(/;

  it.each<ListVariant>(['divided', 'striped'])(
    'when rendered with %s variant, no hardcoded colours appear in inline styles',
    async (variant) => {
      const f = await setupHost(variant);
      const root = f.nativeElement as HTMLElement;
      const all: HTMLElement[] = [root, ...Array.from(root.querySelectorAll<HTMLElement>('*'))];
      for (const el of all) {
        expect(el.getAttribute('style') ?? '').not.toMatch(colorLiteral);
      }
    },
  );

  it('when rendered, the component stylesheet holds no colour literals', async () => {
    await setupHost();
    const css = listStylesheet();
    expect(css).not.toBe('');
    expect(css).not.toMatch(colorLiteral);
  });
});
