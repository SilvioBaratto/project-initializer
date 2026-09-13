import { Component } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { TestbedHarnessEnvironment } from '@angular/cdk/testing/testbed';
import { MatCardHarness } from '@angular/material/card/testing';

import { CardComponent } from './card';

/** Host wrapper that drives all three ng-content slots from the outside. */
@Component({
  selector: 'test-card-host',
  imports: [CardComponent],
  template: `
    <app-card>
      <span slot-header>Header text</span>
      <span>Body text</span>
      <span slot-footer>Footer text</span>
    </app-card>
  `,
})
class TestCardHostComponent {}

/** Host wrapper that projects only default content (the stat-card shape). */
@Component({
  selector: 'test-card-body-only-host',
  imports: [CardComponent],
  template: `
    <app-card>
      <span>Body only</span>
    </app-card>
  `,
})
class TestCardBodyOnlyHostComponent {}

/** Host wrapper that projects a heading and paragraphs, which carry browser-default margins and sizes. */
@Component({
  selector: 'test-card-heading-host',
  imports: [CardComponent],
  template: `
    <app-card>
      <h3 slot-header>Card title</h3>
      <p>First body paragraph</p>
      <p>Last body paragraph</p>
      <p slot-footer>Footer note</p>
    </app-card>
  `,
})
class TestCardHeadingHostComponent {}

/** Host wrapper that nests one card in another's body with a different inset. */
@Component({
  selector: 'test-card-nested-host',
  imports: [CardComponent],
  template: `
    <app-card padding="lg">
      <app-card padding="sm">
        <span>Inner body</span>
      </app-card>
    </app-card>
  `,
})
class TestCardNestedHostComponent {}

/** jsdom reports logical margins as declared (`0`), so compare them as numbers. */
function marginBlock(el: HTMLElement, side: 'start' | 'end'): number {
  return parseFloat(getComputedStyle(el).getPropertyValue(`margin-block-${side}`));
}

function cardInset(el: HTMLElement): string {
  return getComputedStyle(el).getPropertyValue('--app-card-inset').trim();
}

describe('CardComponent', () => {
  let fixture: ComponentFixture<CardComponent>;
  let host: HTMLElement;

  const matCard = () => host.querySelector<HTMLElement>('mat-card')!;
  const body = () => host.querySelector<HTMLElement>('.mat-mdc-card-content')!;

  async function cardHarness(): Promise<MatCardHarness> {
    return TestbedHarnessEnvironment.loader(fixture).getHarness(MatCardHarness);
  }

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [CardComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(CardComponent);
    host = fixture.nativeElement;
    await fixture.whenStable();
  });

  it('when created, the component renders without error', () => {
    expect(fixture.componentInstance).toBeTruthy();
  });

  it('when rendered, the host carries the app-card class that scopes the card styles', () => {
    expect(host.classList).toContain('app-card');
  });

  it('when rendered, exactly one Material card is present', async () => {
    expect(host.querySelectorAll('mat-card').length).toBe(1);
    expect(await cardHarness()).toBeTruthy();
  });

  it('when rendered, the card has header, content and footer sections in reading order', () => {
    const header = host.querySelector('.mat-mdc-card-header')!;
    const content = body();
    const footer = host.querySelector('.mat-mdc-card-footer')!;

    expect(header).not.toBeNull();
    expect(content).not.toBeNull();
    expect(footer).not.toBeNull();
    expect(header.compareDocumentPosition(content) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(content.compareDocumentPosition(footer) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('when no appearance is set, the card uses the M3 outlined appearance', async () => {
    const cardHost = await (await cardHarness()).host();
    expect(await cardHost.hasClass('mat-mdc-card-outlined')).toBe(true);
    expect(await cardHost.hasClass('mat-mdc-card-filled')).toBe(false);
  });

  it('when appearance is filled, the card renders the M3 filled container', async () => {
    fixture.componentRef.setInput('appearance', 'filled');
    await fixture.whenStable();

    const cardHost = await (await cardHarness()).host();
    expect(await cardHost.hasClass('mat-mdc-card-filled')).toBe(true);
    expect(await cardHost.hasClass('mat-mdc-card-outlined')).toBe(false);
  });

  it('when appearance is raised, the card renders the M3 elevated container', async () => {
    fixture.componentRef.setInput('appearance', 'raised');
    await fixture.whenStable();

    const cardHost = await (await cardHarness()).host();
    expect(await cardHost.hasClass('mat-mdc-card-outlined')).toBe(false);
    expect(await cardHost.hasClass('mat-mdc-card-filled')).toBe(false);
  });

  it('when padding is not set, the body uses the md inset', () => {
    expect(fixture.componentInstance.resolvedPadding()).toBe('md');
    expect(matCard().getAttribute('data-padding')).toBe('md');
  });

  it.each(['none', 'sm', 'md', 'lg'])('when padding is %s, the card applies that inset', async (padding) => {
    fixture.componentRef.setInput('padding', padding);
    await fixture.whenStable();

    expect(fixture.componentInstance.resolvedPadding()).toBe(padding);
    expect(matCard().getAttribute('data-padding')).toBe(padding);
  });

  it('when padding is an unknown value, the body falls back to the md inset', async () => {
    fixture.componentRef.setInput('padding', 'xl');
    await fixture.whenStable();

    expect(fixture.componentInstance.resolvedPadding()).toBe('md');
    expect(matCard().getAttribute('data-padding')).toBe('md');
  });

  it.each([
    ['none', '16px'],
    ['sm', '12px'],
    ['md', '16px'],
    ['lg', '24px'],
  ])('when padding is %s, the header and footer share the %s inline inset', async (padding, inset) => {
    fixture.componentRef.setInput('padding', padding);
    await fixture.whenStable();

    // The header slot, the body's inline inset and the footer all read this one property, so text edges align.
    expect(cardInset(matCard())).toBe(inset);
  });

  it('when rendered, no hardcoded hex colors appear in any inline element styles', () => {
    // Token proxy: a hex literal in an inline style would bypass the --mat-sys-* roles.
    const hexPattern = /#[0-9a-fA-F]{3,8}\b/;
    const allElements = [host, ...Array.from(host.querySelectorAll<HTMLElement>('*'))];
    for (const el of allElements) {
      expect(el.getAttribute('style') ?? '').not.toMatch(hexPattern);
    }
  });
});

describe('CardComponent — content projection', () => {
  let fixture: ComponentFixture<TestCardHostComponent>;
  let host: HTMLElement;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [TestCardHostComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(TestCardHostComponent);
    host = fixture.nativeElement;
    await fixture.whenStable();
  });

  it('when header slot content is projected, the projected text is present in the DOM', () => {
    expect(host.textContent).toContain('Header text');
  });

  it('when default slot content is projected, the projected body text is present in the DOM', () => {
    expect(host.textContent).toContain('Body text');
  });

  it('when footer slot content is projected, the projected text is present in the DOM', () => {
    expect(host.textContent).toContain('Footer text');
  });

  it('when all slots are projected, the card harness reads their text', async () => {
    const card = await TestbedHarnessEnvironment.loader(fixture).getHarness(MatCardHarness);
    const text = await card.getText();

    expect(text).toContain('Header text');
    expect(text).toContain('Body text');
    expect(text).toContain('Footer text');
  });

  it('when header slot content is projected, it lands in the Material card header', () => {
    const header = host.querySelector('.mat-mdc-card-header')!;
    expect(header.querySelector('[slot-header]')?.textContent).toBe('Header text');
  });

  it('when default slot content is projected, it lands in the Material card content', () => {
    const content = host.querySelector('.mat-mdc-card-content')!;
    expect(content.textContent).toContain('Body text');
    expect(content.textContent).not.toContain('Header text');
    expect(content.textContent).not.toContain('Footer text');
  });

  it('when footer slot content is projected, it lands in the Material card footer', () => {
    const footer = host.querySelector('.mat-mdc-card-footer')!;
    expect(footer.querySelector('[slot-footer]')?.textContent).toBe('Footer text');
  });

  it('when header and footer are projected, both regions are displayed', () => {
    const headerSlot = host.querySelector<HTMLElement>('.app-card__header-slot')!;
    const footer = host.querySelector<HTMLElement>('.app-card__footer')!;

    expect(getComputedStyle(headerSlot).display).not.toBe('none');
    expect(getComputedStyle(footer).display).not.toBe('none');
  });
});

describe('CardComponent — empty slots', () => {
  let fixture: ComponentFixture<TestCardBodyOnlyHostComponent>;
  let host: HTMLElement;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [TestCardBodyOnlyHostComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(TestCardBodyOnlyHostComponent);
    host = fixture.nativeElement;
    await fixture.whenStable();
  });

  it('when only body content is projected, the body text is present', () => {
    expect(host.querySelector('.mat-mdc-card-content')?.textContent).toContain('Body only');
  });

  it('when no header is projected, the header region is empty and takes no space', () => {
    const headerSlot = host.querySelector<HTMLElement>('.app-card__header-slot')!;

    expect(headerSlot.matches(':empty')).toBe(true);
    expect(getComputedStyle(headerSlot).display).toBe('none');
  });

  it('when no footer is projected, the footer region is empty and takes no space', () => {
    const footer = host.querySelector<HTMLElement>('.app-card__footer')!;

    expect(footer.matches(':empty')).toBe(true);
    expect(getComputedStyle(footer).display).toBe('none');
  });
});

describe('CardComponent — projected headings and paragraphs', () => {
  let fixture: ComponentFixture<TestCardHeadingHostComponent>;
  let host: HTMLElement;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [TestCardHeadingHostComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(TestCardHeadingHostComponent);
    host = fixture.nativeElement;
    await fixture.whenStable();
  });

  it('when an h3 is projected into the header slot, it lands in the header slot wrapper', () => {
    const heading = host.querySelector<HTMLElement>('.mat-mdc-card-header > .app-card__header-slot > h3');

    expect(heading?.textContent).toBe('Card title');
    expect(host.querySelector('.mat-mdc-card-content h3')).toBeNull();
  });

  it('when a heading is projected into the header slot, its browser margins are removed', () => {
    const heading = host.querySelector<HTMLElement>('.app-card__header-slot > h3')!;
    const style = getComputedStyle(heading);

    expect(style.marginTop).toBe('0px');
    expect(style.marginBottom).toBe('0px');
  });

  it('when a paragraph is the first body child, only its top margin is removed', () => {
    const [first, last] = Array.from(host.querySelectorAll<HTMLElement>('.mat-mdc-card-content > p'));

    expect(marginBlock(first, 'start')).toBe(0);
    expect(marginBlock(last, 'start')).not.toBe(0);
  });

  it('when a paragraph is projected into the footer row, its block margins are removed', () => {
    const note = host.querySelector<HTMLElement>('.mat-mdc-card-footer > p')!;

    expect(note.textContent).toBe('Footer note');
    expect(marginBlock(note, 'start')).toBe(0);
    expect(marginBlock(note, 'end')).toBe(0);
  });
});

describe('CardComponent — nested cards', () => {
  let fixture: ComponentFixture<TestCardNestedHostComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [TestCardNestedHostComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(TestCardNestedHostComponent);
    await fixture.whenStable();
  });

  it('when a card is nested in another card, each keeps its own inset', () => {
    const [outer, inner] = Array.from(fixture.nativeElement.querySelectorAll('mat-card')) as HTMLElement[];

    expect(outer.getAttribute('data-padding')).toBe('lg');
    expect(inner.getAttribute('data-padding')).toBe('sm');
    expect(cardInset(outer)).toBe('24px');
    expect(cardInset(inner)).toBe('12px');
  });
});
