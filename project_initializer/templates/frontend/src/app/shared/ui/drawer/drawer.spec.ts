import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Component } from '@angular/core';
import { DrawerComponent } from './drawer';

@Component({
  standalone: true,
  imports: [DrawerComponent],
  template: `
    <app-drawer [side]="side" [open]="isOpen" (close)="onClose()">
      <button id="btn-a">A</button>
      <button id="btn-b">B</button>
    </app-drawer>
  `,
})
class HostComponent {
  side: 'left' | 'right' = 'left';
  isOpen = false;
  closeCount = 0;
  onClose() { this.closeCount++; }
}

function getPanel(f: ComponentFixture<unknown>): HTMLElement | null {
  return f.nativeElement.querySelector('aside');
}

function dispatchKey(target: EventTarget, key: string): void {
  target.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true }));
}

// ── side input ──────────────────────────────────────────────────────────────

describe('DrawerComponent — side input', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [HostComponent] }).compileComponents();
  });

  it('when side is left, the panel carries border-r', () => {
    const f = TestBed.createComponent(HostComponent);
    f.componentInstance.side = 'left';
    f.detectChanges();
    expect(getPanel(f)?.className).toContain('border-r');
  });

  it('when side is right, the panel carries border-l', () => {
    const f = TestBed.createComponent(HostComponent);
    f.componentInstance.side = 'right';
    f.detectChanges();
    expect(getPanel(f)?.className).toContain('border-l');
  });
});

// ── open signal ─────────────────────────────────────────────────────────────

describe('DrawerComponent — open signal', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [HostComponent] }).compileComponents();
  });

  it('when open is false, the panel has -translate-x-full (left side)', () => {
    const f = TestBed.createComponent(HostComponent);
    f.componentInstance.side = 'left';
    f.componentInstance.isOpen = false;
    f.detectChanges();
    expect(getPanel(f)?.className).toContain('-translate-x-full');
  });

  it('when open is true, the panel has translate-x-0', () => {
    const f = TestBed.createComponent(HostComponent);
    f.componentInstance.isOpen = true;
    f.detectChanges();
    expect(getPanel(f)?.className).toContain('translate-x-0');
  });
});

// ── close output ─────────────────────────────────────────────────────────────

describe('DrawerComponent — close output', () => {
  let fixture: ComponentFixture<HostComponent>;
  let host: HostComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [HostComponent] }).compileComponents();
    fixture = TestBed.createComponent(HostComponent);
    host = fixture.componentInstance;
    document.body.appendChild(fixture.nativeElement);
  });

  afterEach(() => { document.body.removeChild(fixture.nativeElement); });

  it('when overlay is clicked, close output fires', () => {
    host.isOpen = true;
    fixture.detectChanges();
    const overlay = fixture.nativeElement.querySelector('[data-testid="drawer-overlay"]') as HTMLElement;
    expect(overlay).not.toBeNull();
    overlay.click();
    fixture.detectChanges();
    expect(host.closeCount).toBe(1);
  });

  it('when Escape is pressed while open, close output fires', () => {
    host.isOpen = true;
    fixture.detectChanges();
    dispatchKey(document, 'Escape');
    fixture.detectChanges();
    expect(host.closeCount).toBe(1);
  });

  it('when Escape is pressed while closed, close output does not fire', () => {
    host.isOpen = false;
    fixture.detectChanges();
    dispatchKey(document, 'Escape');
    fixture.detectChanges();
    expect(host.closeCount).toBe(0);
  });
});

// ── overlay only shows on mobile ─────────────────────────────────────────────

describe('DrawerComponent — overlay visibility', () => {
  it('when open is false, the overlay backdrop is absent', async () => {
    await TestBed.configureTestingModule({ imports: [HostComponent] }).compileComponents();
    const f = TestBed.createComponent(HostComponent);
    f.componentInstance.isOpen = false;
    f.detectChanges();
    expect(f.nativeElement.querySelector('[data-testid="drawer-overlay"]')).toBeNull();
  });

  it('when open is true, the overlay backdrop is present', async () => {
    await TestBed.configureTestingModule({ imports: [HostComponent] }).compileComponents();
    const f = TestBed.createComponent(HostComponent);
    f.componentInstance.isOpen = true;
    f.detectChanges();
    expect(f.nativeElement.querySelector('[data-testid="drawer-overlay"]')).not.toBeNull();
  });
});

// ── dark-mode tokens ─────────────────────────────────────────────────────────

describe('DrawerComponent — dark-mode tokens', () => {
  it('when open, at least one dark: class is present', async () => {
    await TestBed.configureTestingModule({ imports: [HostComponent] }).compileComponents();
    const f = TestBed.createComponent(HostComponent);
    f.componentInstance.isOpen = true;
    f.detectChanges();
    const hasDark = Array.from(f.nativeElement.querySelectorAll('*')).some((el) =>
      Array.from((el as Element).classList).some((c) => c.startsWith('dark:'))
    );
    expect(hasDark).toBe(true);
  });
});

// ── focus trap ───────────────────────────────────────────────────────────────

describe('DrawerComponent — focus trap', () => {
  let fixture: ComponentFixture<HostComponent>;
  let host: HostComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [HostComponent] }).compileComponents();
    fixture = TestBed.createComponent(HostComponent);
    host = fixture.componentInstance;
    document.body.appendChild(fixture.nativeElement);
  });

  afterEach(() => { document.body.removeChild(fixture.nativeElement); });

  it('when drawer opens, first focusable element receives focus', () => {
    host.isOpen = true;
    fixture.detectChanges();
    const first = fixture.nativeElement.querySelector('#btn-a') as HTMLElement;
    expect(document.activeElement).toBe(first);
  });
});
