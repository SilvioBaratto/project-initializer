import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Component, signal } from '@angular/core';

import { SlideOverComponent } from './slide-over';

@Component({
  standalone: true,
  imports: [SlideOverComponent],
  template: `
    <app-slide-over [open]="isOpen()" [side]="side" (closed)="onClosed()">
      <button id="first-btn">First</button>
      <button id="second-btn">Second</button>
    </app-slide-over>
  `,
})
class HostComponent {
  isOpen = signal(false);
  side: 'left' | 'right' = 'right';
  closedCount = 0;
  onClosed() { this.closedCount++; }
}

function getDialog(fixture: ComponentFixture<unknown>): HTMLElement | null {
  return fixture.nativeElement.querySelector('[role="dialog"]');
}

function dispatchKeydown(target: EventTarget, key: string): void {
  target.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true }));
}

// --- ARIA contract ---

describe('SlideOverComponent — ARIA contract', () => {
  let fixture: ComponentFixture<HostComponent>;
  let host: HostComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [HostComponent] }).compileComponents();
    fixture = TestBed.createComponent(HostComponent);
    host = fixture.componentInstance;
  });

  it('when slide-over is open, role="dialog" is present on the panel', () => {
    host.isOpen.set(true);
    fixture.detectChanges();
    expect(getDialog(fixture)?.getAttribute('role')).toBe('dialog');
  });

  it('when slide-over is open, aria-modal="true" is present on the panel', () => {
    host.isOpen.set(true);
    fixture.detectChanges();
    expect(getDialog(fixture)?.getAttribute('aria-modal')).toBe('true');
  });

  it('when slide-over is open, an accessible label is present', () => {
    host.isOpen.set(true);
    fixture.detectChanges();
    const el = getDialog(fixture);
    expect(el?.hasAttribute('aria-label') || el?.hasAttribute('aria-labelledby')).toBe(true);
  });
});

// --- Signal input/output ---

describe('SlideOverComponent — signal input/output', () => {
  let fixture: ComponentFixture<HostComponent>;
  let host: HostComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [HostComponent] }).compileComponents();
    fixture = TestBed.createComponent(HostComponent);
    host = fixture.componentInstance;
  });

  it('when open is false, the dialog panel is absent', () => {
    host.isOpen.set(false);
    fixture.detectChanges();
    expect(getDialog(fixture)).toBeNull();
  });

  it('when open changes to true, the dialog panel appears', () => {
    host.isOpen.set(true);
    fixture.detectChanges();
    expect(getDialog(fixture)).not.toBeNull();
  });

  it('when open changes to false, the dialog panel disappears', () => {
    host.isOpen.set(true);
    fixture.detectChanges();
    host.isOpen.set(false);
    fixture.detectChanges();
    expect(getDialog(fixture)).toBeNull();
  });
});

// --- Escape close ---

describe('SlideOverComponent — Escape closes', () => {
  let fixture: ComponentFixture<HostComponent>;
  let host: HostComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [HostComponent] }).compileComponents();
    fixture = TestBed.createComponent(HostComponent);
    host = fixture.componentInstance;
    document.body.appendChild(fixture.nativeElement);
  });

  afterEach(() => { document.body.removeChild(fixture.nativeElement); });

  it('when Escape is pressed while open, the closed output fires', () => {
    host.isOpen.set(true);
    fixture.detectChanges();
    dispatchKeydown(document, 'Escape');
    fixture.detectChanges();
    expect(host.closedCount).toBe(1);
  });
});

// --- Backdrop click ---

describe('SlideOverComponent — backdrop click closes', () => {
  let fixture: ComponentFixture<HostComponent>;
  let host: HostComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [HostComponent] }).compileComponents();
    fixture = TestBed.createComponent(HostComponent);
    host = fixture.componentInstance;
    document.body.appendChild(fixture.nativeElement);
  });

  afterEach(() => { document.body.removeChild(fixture.nativeElement); });

  it('when backdrop is clicked, the closed output fires', () => {
    host.isOpen.set(true);
    fixture.detectChanges();
    const backdrop = fixture.nativeElement.querySelector('[data-testid="slide-over-backdrop"]') as HTMLElement;
    expect(backdrop).not.toBeNull();
    backdrop.click();
    fixture.detectChanges();
    expect(host.closedCount).toBe(1);
  });
});

// --- Dark-mode tokens ---

describe('SlideOverComponent — dark-mode tokens', () => {
  it('when rendered open, at least one dark: class is present', async () => {
    await TestBed.configureTestingModule({ imports: [HostComponent] }).compileComponents();
    const fixture = TestBed.createComponent(HostComponent);
    (fixture.componentInstance as HostComponent).isOpen.set(true);
    fixture.detectChanges();
    const all = fixture.nativeElement.querySelectorAll('*');
    let hasDark = false;
    all.forEach((el: Element) => {
      if (Array.from(el.classList).some((c) => c.startsWith('dark:'))) hasDark = true;
    });
    expect(hasDark).toBe(true);
  });
});
