import { ChangeDetectionStrategy, Component, signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';

import { ContainerComponent } from './container';

@Component({
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ContainerComponent],
  template: `
    <app-container [size]="size()">
      <p class="projected">Projected body</p>
    </app-container>
  `,
})
class ContainerHostComponent {
  readonly size = signal('lg');
}

/** Text of every stylesheet attached to the document (component styles land in <head>). */
function attachedStyleText(): string {
  return Array.from(document.querySelectorAll('style'))
    .map((style) => style.textContent ?? '')
    .join('\n');
}

describe('ContainerComponent', () => {
  let fixture: ComponentFixture<ContainerHostComponent>;
  let host: HTMLElement;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ContainerHostComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(ContainerHostComponent);
    fixture.detectChanges();
    host = fixture.nativeElement.querySelector('app-container');
  });

  function setSize(size: string): void {
    fixture.componentInstance.size.set(size);
    fixture.detectChanges();
  }

  it('when created, the component renders without error', () => {
    expect(host).toBeTruthy();
  });

  it('when content is projected, it renders directly inside the container host', () => {
    const projected = host.querySelector('.projected');
    expect(projected?.textContent).toBe('Projected body');
    expect(projected?.parentElement).toBe(host);
  });

  it('when no size is chosen, the host reflects the default lg size', () => {
    expect(host.getAttribute('data-size')).toBe('lg');
  });

  it.each(['sm', 'md', 'lg', 'xl', 'full'])(
    'when size is %s, the host reflects it for the size cap',
    (size) => {
      setSize(size);
      expect(host.getAttribute('data-size')).toBe(size);
    },
  );

  it('when size is unknown, the host falls back to lg', () => {
    setSize('huge');
    expect(host.getAttribute('data-size')).toBe('lg');
    expect(fixture.debugElement.children[0].componentInstance.resolvedSize()).toBe('lg');
  });

  it('when rendered, the host is a block box', () => {
    expect(getComputedStyle(host).display).toBe('block');
  });

  it('when rendered, the styles pad by the M3 window margin plus the safe-area insets', () => {
    const css = attachedStyleText();
    expect(css).toContain('env(safe-area-inset-left');
    expect(css).toContain('env(safe-area-inset-right');
    expect(css).toMatch(/--app-container-margin:\s*16px/);
    expect(css).toMatch(/min-width:\s*600px/);
    expect(css).toMatch(/--app-container-margin:\s*24px/);
  });

  it('when rendered, the host carries no utility classes', () => {
    expect(host.classList.length).toBe(0);
  });

  it('when rendered, no hardcoded hex colors appear in any inline element styles', () => {
    const hexPattern = /#[0-9a-fA-F]{3,8}\b/;
    const allElements = [host, ...Array.from(host.querySelectorAll<HTMLElement>('*'))];
    for (const el of allElements) {
      expect(el.getAttribute('style') ?? '').not.toMatch(hexPattern);
    }
  });
});
