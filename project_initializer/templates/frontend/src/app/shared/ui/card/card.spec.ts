import { Component } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';

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

describe('CardComponent', () => {
  let fixture: ComponentFixture<CardComponent>;
  let host: HTMLElement;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [CardComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(CardComponent);
    host = fixture.nativeElement;
    fixture.detectChanges();
  });

  it('when created, the component renders without error', () => {
    expect(fixture.componentInstance).toBeTruthy();
  });

  it('when rendered, no hardcoded hex colors appear in any inline element styles', () => {
    // @theme token proxy: hardcoded hex in inline styles would bypass the token system.
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
    fixture.detectChanges();
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
});
