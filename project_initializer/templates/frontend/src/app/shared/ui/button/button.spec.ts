import { ComponentFixture, TestBed } from '@angular/core/testing';
import { LucideIconConfig } from 'lucide-angular';

import { ICON_PROVIDER } from '../../../icons';
import { ButtonComponent } from './button';

describe('ButtonComponent', () => {
  let fixture: ComponentFixture<ButtonComponent>;
  let host: HTMLElement;

  function button(): HTMLButtonElement {
    return host.querySelector('button')!;
  }

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ButtonComponent],
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

    fixture = TestBed.createComponent(ButtonComponent);
    host = fixture.nativeElement;
    fixture.detectChanges();
  });

  it('when created, the component renders without error', () => {
    expect(fixture.componentInstance).toBeTruthy();
  });

  // --- Criterion: variant and size signal inputs ---

  it('when variant is primary, the primary background class is applied to the button', () => {
    fixture.componentRef.setInput('variant', 'primary');
    fixture.detectChanges();
    expect(button().className).toContain('bg-primary');
  });

  it('when variant is secondary, the secondary surface class is applied to the button', () => {
    fixture.componentRef.setInput('variant', 'secondary');
    fixture.detectChanges();
    expect(button().className).toContain('bg-surface-raised');
  });

  it('when variant is ghost, the ghost class is applied to the button', () => {
    fixture.componentRef.setInput('variant', 'ghost');
    fixture.detectChanges();
    expect(button().className).toContain('bg-transparent');
  });

  it('when variant is danger, the danger background class is applied to the button', () => {
    fixture.componentRef.setInput('variant', 'danger');
    fixture.detectChanges();
    expect(button().className).toContain('bg-danger');
  });

  it('when size is sm, the sm padding class is applied to the button', () => {
    fixture.componentRef.setInput('size', 'sm');
    fixture.detectChanges();
    expect(button().className).toContain('px-3');
  });

  it('when size is md, the md padding class is applied to the button', () => {
    fixture.componentRef.setInput('size', 'md');
    fixture.detectChanges();
    expect(button().className).toContain('px-4');
  });

  it('when size is lg, the lg padding class is applied to the button', () => {
    fixture.componentRef.setInput('size', 'lg');
    fixture.detectChanges();
    expect(button().className).toContain('px-6');
  });

  it('when any size is used, the min-h-11 class is present for the 44px touch target', () => {
    for (const size of ['sm', 'md', 'lg'] as const) {
      fixture.componentRef.setInput('size', size);
      fixture.detectChanges();
      expect(button().className).toContain('min-h-11');
    }
  });

  // --- Criterion: loading shows a spinner + sets aria-busy ---

  it('when loading is true, a lucide-icon spinner is rendered inside the button', async () => {
    fixture.componentRef.setInput('loading', true);
    fixture.detectChanges();
    await fixture.whenStable();
    expect(host.querySelector('lucide-icon')).toBeTruthy();
  });

  it('when loading is true, aria-busy is set on the button element', () => {
    fixture.componentRef.setInput('loading', true);
    fixture.detectChanges();
    expect(button().getAttribute('aria-busy')).toBe('true');
  });

  it('when loading is false, aria-busy is not set on the button element', () => {
    fixture.componentRef.setInput('loading', false);
    fixture.detectChanges();
    expect(button().getAttribute('aria-busy')).toBeNull();
  });

  // --- Criterion: disabled sets disabled + aria-disabled ---

  it('when disabled is true, the button element has the disabled attribute', () => {
    fixture.componentRef.setInput('disabled', true);
    fixture.detectChanges();
    expect(button().disabled).toBe(true);
  });

  it('when disabled is true, aria-disabled is set on the button element', () => {
    fixture.componentRef.setInput('disabled', true);
    fixture.detectChanges();
    expect(button().getAttribute('aria-disabled')).toBe('true');
  });

  it('when disabled is false, aria-disabled is not set on the button element', () => {
    fixture.componentRef.setInput('disabled', false);
    fixture.detectChanges();
    expect(button().getAttribute('aria-disabled')).toBeNull();
  });

  // --- Criterion: Emits click only when not disabled/loading ---

  it('when the button is clicked and neither disabled nor loading, clicked event is emitted', () => {
    fixture.componentRef.setInput('disabled', false);
    fixture.componentRef.setInput('loading', false);
    fixture.detectChanges();

    let emitted = false;
    fixture.componentInstance.clicked.subscribe(() => { emitted = true; });

    fixture.componentInstance.handleClick();
    expect(emitted).toBe(true);
  });

  it('when the button is clicked and disabled is true, clicked event is not emitted', () => {
    fixture.componentRef.setInput('disabled', true);
    fixture.detectChanges();

    let emitted = false;
    fixture.componentInstance.clicked.subscribe(() => { emitted = true; });

    fixture.componentInstance.handleClick();
    expect(emitted).toBe(false);
  });

  it('when the button is clicked and loading is true, clicked event is not emitted', () => {
    fixture.componentRef.setInput('loading', true);
    fixture.detectChanges();

    let emitted = false;
    fixture.componentInstance.clicked.subscribe(() => { emitted = true; });

    fixture.componentInstance.handleClick();
    expect(emitted).toBe(false);
  });

  it('when disabled is true, the native button element is disabled (DOM click blocked)', () => {
    fixture.componentRef.setInput('disabled', true);
    fixture.detectChanges();
    expect(button().disabled).toBe(true);
  });

  it('when loading is true, the native button element is disabled (DOM click blocked)', () => {
    fixture.componentRef.setInput('loading', true);
    fixture.detectChanges();
    expect(button().disabled).toBe(true);
  });

  // --- No hardcoded hex colours ---

  it('when rendered, no hardcoded hex colors appear in any inline element styles', () => {
    const hexPattern = /#[0-9a-fA-F]{3,8}\b/;
    const allElements = [host, ...Array.from(host.querySelectorAll<HTMLElement>('*'))];
    for (const el of allElements) {
      expect(el.getAttribute('style') ?? '').not.toMatch(hexPattern);
    }
  });
});
