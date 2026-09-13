/**
 * ModalComponent: a declarative M3 simple dialog on MatDialog.
 *
 * Covers the WAI-ARIA dialog contract (dialog and alertdialog roles), the simple dialog
 * anatomy (headline, content, actions, no close icon button), focus (initial focus, trap,
 * restore), Esc, scrim and Close-action dismissal, hiding the background from assistive
 * technology, the open/label/role/closed API (including [(open)]), close() for projected
 * buttons, the app-modal-actions row, the fallback Close action and teardown.
 *
 * Dialog content renders in document.body's .cdk-overlay-container, so harnesses
 * come from the document root loader rather than the fixture.
 */

import { Component, signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { InteractivityChecker } from '@angular/cdk/a11y';
import { HarnessLoader } from '@angular/cdk/testing';
import { TestbedHarnessEnvironment } from '@angular/cdk/testing/testbed';
import { MatButton } from '@angular/material/button';
import { MatButtonHarness } from '@angular/material/button/testing';
import { MATERIAL_ANIMATIONS } from '@angular/material/core';
import { MatDialogHarness } from '@angular/material/dialog/testing';

import { ModalComponent } from './modal';
import { ModalActionsComponent } from './modal-actions';

/**
 * jsdom does no layout, so CDK's InteractivityChecker would treat every element as
 * invisible and the focus trap would find nothing to focus. Real browsers need no override.
 */
class LayoutFreeInteractivityChecker extends InteractivityChecker {
  override isVisible(): boolean {
    return true;
  }
}

@Component({
  imports: [ModalComponent],
  template: `
    <button type="button" id="trigger">Edit profile</button>
    @if (rendered()) {
      <app-modal [open]="isOpen()" [label]="label()" (closed)="onClosed()">
        <p id="body-text">Your changes apply to every device</p>
        <button type="button" id="first-btn">First</button>
        <button type="button" id="second-btn">Second</button>
      </app-modal>
    }
  `,
})
class HostComponent {
  readonly rendered = signal(true);
  readonly isOpen = signal(false);
  readonly label = signal('Edit profile');
  closedCount = 0;

  onClosed(): void {
    this.closedCount++;
    this.isOpen.set(false);
  }
}

@Component({
  imports: [ModalComponent],
  template: `
    <app-modal [(open)]="isOpen" label="Rename file">
      <label for="file-name">File name</label>
      <input id="file-name" cdkFocusInitial />
    </app-modal>
  `,
})
class TwoWayHostComponent {
  readonly isOpen = signal(true);
}

@Component({
  imports: [ModalComponent, ModalActionsComponent, MatButton],
  template: `
    <button type="button" id="delete-trigger">Delete file</button>
    <app-modal
      #modal
      [(open)]="isOpen"
      label="Delete report.pdf?"
      role="alertdialog"
      (closed)="onClosed()"
    >
      <p id="delete-body">The file is removed from every device</p>
      <app-modal-actions>
        <button matButton type="button" (click)="modal.close()">Cancel</button>
        <button matButton="filled" type="button" (click)="deleteFile()">Delete file</button>
      </app-modal-actions>
    </app-modal>
  `,
})
class ActionsHostComponent {
  readonly isOpen = signal(false);
  readonly deleted = signal(false);
  closedCount = 0;

  onClosed(): void {
    this.closedCount++;
  }

  deleteFile(): void {
    this.deleted.set(true);
    this.isOpen.set(false);
  }
}

const TEST_PROVIDERS = [
  { provide: MATERIAL_ANIMATIONS, useValue: { animationsDisabled: true } },
  { provide: InteractivityChecker, useClass: LayoutFreeInteractivityChecker },
];

function overlayPane(): HTMLElement | null {
  return document.querySelector('.cdk-overlay-pane.app-modal-panel');
}

function actionRow(): HTMLElement | null {
  return document.querySelector('.cdk-overlay-container .mat-mdc-dialog-actions');
}

describe('ModalComponent', () => {
  let fixture: ComponentFixture<HostComponent>;
  let host: HostComponent;
  let loader: HarnessLoader;

  async function openModal(): Promise<MatDialogHarness> {
    host.isOpen.set(true);
    await fixture.whenStable();
    const dialog = await loader.getHarness(MatDialogHarness);
    // MatDialogActions registers with the container in a microtask, then marks it for check.
    await fixture.whenStable();
    return dialog;
  }

  async function openDialogCount(): Promise<number> {
    await fixture.whenStable();
    return (await loader.getAllHarnesses(MatDialogHarness)).length;
  }

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [HostComponent],
      providers: TEST_PROVIDERS,
    }).compileComponents();

    fixture = TestBed.createComponent(HostComponent);
    host = fixture.componentInstance;
    loader = TestbedHarnessEnvironment.documentRootLoader(fixture);
    await fixture.whenStable();
  });

  describe('open input', () => {
    it('renders no dialog while open is false', async () => {
      expect(await openDialogCount()).toBe(0);
    });

    it('opens one dialog when open turns true', async () => {
      await openModal();
      expect(await openDialogCount()).toBe(1);
    });

    it('closes the dialog without emitting closed when open turns false', async () => {
      await openModal();

      host.isOpen.set(false);

      expect(await openDialogCount()).toBe(0);
      expect(host.closedCount).toBe(0);
    });

    it('shows the projected content again when reopened', async () => {
      const first = await openModal();
      await first.close();
      expect(await openDialogCount()).toBe(0);

      const second = await openModal();

      expect(await second.getContentText()).toContain('Your changes apply to every device');
    });
  });

  describe('ARIA contract', () => {
    it('exposes role="dialog" by default and makes it modal by hiding everything outside it', async () => {
      const main = document.createElement('main');
      document.body.appendChild(main);
      try {
        const dialog = await openModal();

        expect(await dialog.getRole()).toBe('dialog');
        // Angular Material leaves aria-modal off by default: it would hide overlay panels
        // opened from inside the dialog (mat-select, menus), and the page outside the
        // overlay container is already aria-hidden while the dialog is open.
        expect(main.getAttribute('aria-hidden')).toBe('true');
        expect(document.querySelector('.cdk-overlay-container')?.hasAttribute('aria-hidden')).toBe(false);
      } finally {
        main.remove();
      }
    });

    it('is labelled by an h2 heading that shows the label', async () => {
      const dialog = await openModal();

      const labelledBy = await dialog.getAriaLabelledby();
      const heading = labelledBy ? document.getElementById(labelledBy) : null;

      expect(heading?.tagName).toBe('H2');
      expect(heading?.textContent?.trim()).toBe('Edit profile');
      expect(await dialog.getTitleText()).toBe('Edit profile');
    });

    it('updates the title when label changes', async () => {
      const dialog = await openModal();

      host.label.set('Change password');
      await fixture.whenStable();

      expect(await dialog.getTitleText()).toBe('Change password');
    });

    it('projects content into the dialog content region', async () => {
      const dialog = await openModal();

      expect(await dialog.getContentText()).toContain('Your changes apply to every device');
    });

    it('follows the simple dialog anatomy: the headline sits directly before the content, with no close icon button', async () => {
      await openModal();

      const title = overlayPane()?.querySelector('.mat-mdc-dialog-title');
      expect(title?.nextElementSibling?.classList.contains('mat-mdc-dialog-content')).toBe(true);
      expect(overlayPane()?.querySelector('.mat-mdc-icon-button')).toBeNull();
    });

    it('renders one end-aligned Close text button when no app-modal-actions is projected', async () => {
      const dialog = await openModal();

      const buttons = await dialog.getAllHarnesses(
        MatButtonHarness.with({ ancestor: '.mat-mdc-dialog-actions' }),
      );
      expect(await Promise.all(buttons.map((b) => b.getText()))).toEqual(['Close']);
      expect(await (await buttons[0].host()).getAttribute('type')).toBe('button');
      expect(await (await buttons[0].host()).hasClass('mat-mdc-button')).toBe(true);
      expect(actionRow()?.classList.contains('mat-mdc-dialog-actions-align-end')).toBe(true);
    });
  });

  describe('dismissal', () => {
    it('closes on Escape and emits closed once', async () => {
      const dialog = await openModal();

      await dialog.close();

      expect(await openDialogCount()).toBe(0);
      expect(host.closedCount).toBe(1);
    });

    it('closes on a scrim click and emits closed once', async () => {
      await openModal();

      const scrim = document.querySelector('.cdk-overlay-backdrop') as HTMLElement | null;
      expect(scrim).not.toBeNull();
      scrim!.click();

      expect(await openDialogCount()).toBe(0);
      expect(host.closedCount).toBe(1);
    });

    it('stays open when the dialog content is clicked', async () => {
      await openModal();

      (document.getElementById('body-text') as HTMLElement).click();

      expect(await openDialogCount()).toBe(1);
      expect(host.closedCount).toBe(0);
    });

    it('closes from the Close action and emits closed once', async () => {
      const dialog = await openModal();
      const close = await dialog.getHarness(MatButtonHarness.with({ text: 'Close' }));

      await close.click();

      expect(await openDialogCount()).toBe(0);
      expect(host.closedCount).toBe(1);
    });

    it('closes without emitting closed when the component is destroyed', async () => {
      await openModal();

      host.rendered.set(false);

      expect(await openDialogCount()).toBe(0);
      expect(host.closedCount).toBe(0);
    });

    it('close() does nothing while the dialog is closed', async () => {
      const modal = fixture.debugElement.query(By.directive(ModalComponent))
        .componentInstance as ModalComponent;

      modal.close();

      expect(await openDialogCount()).toBe(0);
      expect(host.closedCount).toBe(0);
      expect(host.isOpen()).toBe(false);
    });
  });

  describe('focus', () => {
    it('moves focus to the first tabbable element in the content when it opens', async () => {
      await openModal();

      expect(document.activeElement?.id).toBe('first-btn');
    });

    it('wraps Tab from the last tabbable element to the first, and Shift+Tab back', async () => {
      await openModal();

      // CDK's focus trap places focusable anchors around the dialog: Tab past the last
      // element lands on the end anchor, Shift+Tab before the first lands on the start anchor.
      const anchors = overlayPane()?.querySelectorAll<HTMLElement>('.cdk-focus-trap-anchor') ?? [];
      expect(anchors.length).toBe(2);

      anchors[1].focus();
      expect(document.activeElement?.id).toBe('first-btn');

      anchors[0].focus();
      expect(document.activeElement?.closest('.mat-mdc-dialog-actions')).not.toBeNull();
      expect(document.activeElement?.textContent?.trim()).toBe('Close');
    });

    it('returns focus to the trigger after the dialog closes', async () => {
      const trigger = document.getElementById('trigger') as HTMLButtonElement;
      trigger.focus();

      const dialog = await openModal();
      expect(document.activeElement).not.toBe(trigger);

      await dialog.close();
      await fixture.whenStable();

      expect(document.activeElement).toBe(trigger);
    });

    it("renders Material's focus indicator element on the Close action", async () => {
      await openModal();

      // This span only hosts the ring; the ring itself comes from mat.strong-focus-indicators()
      // in src/styles.scss, which tests/test_issue_11_modal_slideover.py asserts.
      const close = actionRow()?.querySelector('button');
      expect(close?.querySelector(':scope > .mat-focus-indicator')).not.toBeNull();
    });
  });

  describe('background', () => {
    it('hides the rest of the page from assistive technology only while open', async () => {
      const main = document.createElement('main');
      document.body.appendChild(main);
      try {
        await openModal();
        expect(main.getAttribute('aria-hidden')).toBe('true');

        host.isOpen.set(false);
        expect(await openDialogCount()).toBe(0);
        await fixture.whenStable();

        expect(main.hasAttribute('aria-hidden')).toBe(false);
      } finally {
        main.remove();
      }
    });
  });

  describe('styling', () => {
    it('puts the app-modal-panel class on the overlay pane', async () => {
      await openModal();

      expect(overlayPane()).not.toBeNull();
    });

    it('renders no utility-variant classes or inline hex colours', async () => {
      await openModal();

      const elements = [overlayPane()!, ...Array.from(overlayPane()!.querySelectorAll('*'))];
      for (const el of elements) {
        expect(Array.from(el.classList).filter((c) => c.includes(':'))).toEqual([]);
        expect(el.getAttribute('style') ?? '').not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
      }
    });
  });
});

describe('ModalComponent with [(open)] and cdkFocusInitial', () => {
  let fixture: ComponentFixture<TwoWayHostComponent>;
  let loader: HarnessLoader;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [TwoWayHostComponent],
      providers: TEST_PROVIDERS,
    }).compileComponents();

    fixture = TestBed.createComponent(TwoWayHostComponent);
    loader = TestbedHarnessEnvironment.documentRootLoader(fixture);
    await fixture.whenStable();
  });

  it('focuses the projected cdkFocusInitial element', async () => {
    await loader.getHarness(MatDialogHarness);

    expect(document.activeElement?.id).toBe('file-name');
  });

  it('writes false back through [(open)] when the user dismisses the dialog', async () => {
    const dialog = await loader.getHarness(MatDialogHarness);

    await dialog.close();
    await fixture.whenStable();

    expect(fixture.componentInstance.isOpen()).toBe(false);
    expect((await loader.getAllHarnesses(MatDialogHarness)).length).toBe(0);
  });
});

describe('ModalComponent with app-modal-actions, role="alertdialog" and close()', () => {
  let fixture: ComponentFixture<ActionsHostComponent>;
  let host: ActionsHostComponent;
  let loader: HarnessLoader;

  async function openModal(): Promise<MatDialogHarness> {
    host.isOpen.set(true);
    await fixture.whenStable();
    const dialog = await loader.getHarness(MatDialogHarness);
    // MatDialogActions registers with the container in a microtask, then marks it for check.
    await fixture.whenStable();
    return dialog;
  }

  async function openDialogCount(): Promise<number> {
    await fixture.whenStable();
    return (await loader.getAllHarnesses(MatDialogHarness)).length;
  }

  async function actionButton(dialog: MatDialogHarness, text: string): Promise<MatButtonHarness> {
    return dialog.getHarness(MatButtonHarness.with({ text }));
  }

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ActionsHostComponent],
      providers: TEST_PROVIDERS,
    }).compileComponents();

    fixture = TestBed.createComponent(ActionsHostComponent);
    host = fixture.componentInstance;
    loader = TestbedHarnessEnvironment.documentRootLoader(fixture);
    await fixture.whenStable();
  });

  it('exposes role="alertdialog" for a confirmation, still labelled by its headline', async () => {
    const dialog = await openModal();

    expect(await dialog.getRole()).toBe('alertdialog');
    expect(await dialog.getTitleText()).toBe('Delete report.pdf?');
  });

  it('keeps the static role attribute off the empty app-modal host, so the page has no unnamed dialog', async () => {
    // Angular writes static attributes onto the host even when they feed an input.
    const modalHost = (fixture.nativeElement as HTMLElement).querySelector('app-modal')!;
    expect(modalHost.childElementCount).toBe(0);
    expect(modalHost.hasAttribute('role')).toBe(false);

    const dialog = await openModal();

    expect(modalHost.hasAttribute('role')).toBe(false);
    expect(await dialog.getRole()).toBe('alertdialog');
  });

  it('renders the projected actions in an end-aligned mat-dialog-actions row', async () => {
    const dialog = await openModal();

    expect(await dialog.getActionsText()).toContain('Cancel');
    expect(await dialog.getActionsText()).toContain('Delete file');

    expect(actionRow()?.classList.contains('mat-mdc-dialog-actions-align-end')).toBe(true);
    // Material registered the row, so it gives the content region its with-actions padding.
    expect(document.querySelector('.mat-mdc-dialog-container-with-actions')).not.toBeNull();
  });

  it('keeps the action row outside the scrolling content region', async () => {
    const dialog = await openModal();

    expect(document.querySelector('.mat-mdc-dialog-content app-modal-actions')).toBeNull();
    expect(document.querySelector('.mat-mdc-dialog-actions app-modal-actions')).not.toBeNull();
    expect(await dialog.getContentText()).toContain('The file is removed from every device');
    expect(await dialog.getContentText()).not.toContain('Cancel');
  });

  it('puts the dismissive action before the confirming one, with no fallback Close action', async () => {
    const dialog = await openModal();
    const buttons = await dialog.getAllHarnesses(
      MatButtonHarness.with({ ancestor: '.mat-mdc-dialog-actions' }),
    );

    expect(await Promise.all(buttons.map((b) => b.getText()))).toEqual(['Cancel', 'Delete file']);
  });

  it('gives initial focus to the dismissive action when the content has nothing tabbable', async () => {
    await openModal();

    expect(document.activeElement?.textContent?.trim()).toBe('Cancel');
  });

  it('closes through close() from a projected button, emits closed once and resets [(open)]', async () => {
    const dialog = await openModal();

    await (await actionButton(dialog, 'Cancel')).click();

    expect(await openDialogCount()).toBe(0);
    expect(host.closedCount).toBe(1);
    expect(host.isOpen()).toBe(false);
  });

  it('returns focus to the trigger after close()', async () => {
    const trigger = document.getElementById('delete-trigger') as HTMLButtonElement;
    trigger.focus();

    const dialog = await openModal();
    expect(document.activeElement).not.toBe(trigger);

    await (await actionButton(dialog, 'Cancel')).click();
    await fixture.whenStable();

    expect(document.activeElement).toBe(trigger);
  });

  it('opens again after close()', async () => {
    const dialog = await openModal();
    await (await actionButton(dialog, 'Cancel')).click();
    expect(await openDialogCount()).toBe(0);

    const reopened = await openModal();

    expect(await openDialogCount()).toBe(1);
    expect(await reopened.getActionsText()).toContain('Delete file');
  });

  it('closes without emitting closed when a projected action sets [(open)] to false', async () => {
    const dialog = await openModal();

    await (await actionButton(dialog, 'Delete file')).click();

    expect(host.deleted()).toBe(true);
    expect(await openDialogCount()).toBe(0);
    expect(host.closedCount).toBe(0);
  });
});
