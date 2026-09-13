/**
 * Spec for the /components catalog (issues #22 and #25).
 *
 * Asserts:
 * - The page renders a section per component group (Core, Forms, Navigation, Overlays, Data Display),
 *   each a region named by its h2, under a single h1 with no skipped heading levels
 * - Both a light region and a dark-scoped region are rendered per group, each named by its caption
 * - Each overlay demo group is an h3 previewed in a light and a dark region, and at most one overlay is open at a time
 * - Opening an overlay from a trigger, dismissing it (Cancel, Esc) and returning focus to the trigger
 * - A dismissal only clears its own overlay, so a late one never closes an overlay opened after it
 * - The modal's action row puts the dismissive text button first and the filled confirming action last
 * - Dialog triggers take aria-haspopup="dialog" and no aria-expanded
 * - The snackbar triggers show their snackbar through ToastService
 * - Demos stamped into both regions name their landmarks and tablists after the region, so the two
 *   copies never share an accessible name
 * - Every navigation toggle controls a real destination preview in its own copy
 * - The required Status field shows its error only after it is touched without a choice
 * - The skeleton demo names its loading state in a status outside the busy region
 * - The stat card demo formats its numbers with locale pipes and signals direction without a sign
 * - ThemePreviewComponent stamps its template into both regions and shows its label only when set
 *
 * The modal, slide-over and drawer are Material dialogs: they render in document.body's
 * .cdk-overlay-container, so overlay assertions query the document (or use the document root
 * harness loader), never the fixture.
 */

import { Component, Injectable, signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { InteractivityChecker } from '@angular/cdk/a11y';
import { HarnessLoader } from '@angular/cdk/testing';
import { TestbedHarnessEnvironment } from '@angular/cdk/testing/testbed';
import { MatButtonHarness } from '@angular/material/button/testing';
import { MATERIAL_ANIMATIONS } from '@angular/material/core';
import { MatDialog } from '@angular/material/dialog';
import { MatDialogHarness } from '@angular/material/dialog/testing';
import { MatFormFieldHarness } from '@angular/material/form-field/testing';
import { MatSelectHarness } from '@angular/material/select/testing';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatSnackBarHarness } from '@angular/material/snack-bar/testing';
import { vi } from 'vitest';

import { ICON_PROVIDER } from '../../icons';
import { ToastService } from '../../shared/ui/toast/toast.service';
import { ComponentsComponent } from './components';
import { ThemePreviewComponent } from './theme-preview';

const GROUPS = ['Core', 'Forms', 'Navigation', 'Overlays', 'Data Display'];

/**
 * jsdom does no layout, so CDK's InteractivityChecker would treat every element as invisible and the
 * dialogs' focus traps would find nothing to focus. Real browsers need no override.
 */
@Injectable()
class LayoutFreeInteractivityChecker extends InteractivityChecker {
  override isVisible(): boolean {
    return true;
  }
}

/** Text of the element(s) an aria-labelledby attribute points at. */
function labelledByText(element: Element): string {
  const ids = (element.getAttribute('aria-labelledby') ?? '').split(/\s+/).filter(Boolean);
  return ids.map((id) => document.getElementById(id)?.textContent?.trim() ?? '').join(' ');
}

/** Accessible name from aria-label, else aria-labelledby, with whitespace collapsed. */
function accessibleName(element: Element): string {
  return (element.getAttribute('aria-label') ?? labelledByText(element)).replace(/\s+/g, ' ').trim();
}

/** Roles that need a distinct name whenever they appear more than once on a page. */
const NAMED_ROLES = 'nav, [role="navigation"], [role="region"], [role="tablist"]';

/**
 * Budget for the one-time warm-up render. The first catalog render in a test file pays costs later
 * renders don't (first instantiation of every section's components, Material and CDK setup, first
 * style parsing in jsdom). That can exceed Vitest's 5 s per-test timeout on a saturated machine.
 */
const WARM_UP_TIMEOUT_MS = 30_000;

async function configureCatalogTestBed(): Promise<void> {
  await TestBed.configureTestingModule({
    imports: [ComponentsComponent],
    providers: [
      provideRouter([]),
      ICON_PROVIDER,
      { provide: MATERIAL_ANIMATIONS, useValue: { animationsDisabled: true } },
      { provide: InteractivityChecker, useClass: LayoutFreeInteractivityChecker },
    ],
  }).compileComponents();
}

describe('ComponentsComponent', () => {
  let fixture: ComponentFixture<ComponentsComponent>;

  // Render once before the tests, under its own explicit budget, so the one-time cost never lands
  // on whichever test happens to run first. Every test keeps Vitest's default timeout, so a render
  // that really hangs still fails there.
  beforeAll(async () => {
    await configureCatalogTestBed();
    const warmUp = TestBed.createComponent(ComponentsComponent);
    warmUp.detectChanges();
    await warmUp.whenStable();
    // Destroys the warm-up fixture, so each test's beforeEach can configure a fresh module.
    TestBed.resetTestingModule();
  }, WARM_UP_TIMEOUT_MS);

  beforeEach(async () => {
    await configureCatalogTestBed();
  });

  async function render(): Promise<HTMLElement> {
    fixture = TestBed.createComponent(ComponentsComponent);
    fixture.detectChanges();
    await fixture.whenStable();
    return fixture.nativeElement;
  }

  describe('structure', () => {
    for (const group of GROUPS) {
      it(`when the catalog renders, a section for '${group}' is present`, async () => {
        const el = await render();
        const sections = Array.from(el.querySelectorAll('[data-section]'));
        const match = sections.find((s) => s.getAttribute('data-section') === group);
        expect(match).toBeTruthy();
      });

      it(`when the catalog renders, the '${group}' section is a region named by its h2`, async () => {
        const el = await render();
        const section = el.querySelector(`section[data-section="${group}"]`);
        const heading = section?.querySelector('h2');

        expect(heading).toBeTruthy();
        expect(section?.getAttribute('aria-labelledby')).toBe(heading?.id);
        // Sentence case on screen ("Data display"); the data-section key keeps its original spelling.
        expect(labelledByText(section!).toLowerCase()).toBe(group.toLowerCase());
      });
    }

    it('when the catalog renders, it has exactly one h1', async () => {
      const el = await render();
      const h1s = el.querySelectorAll('h1');
      expect(h1s).toHaveLength(1);
      expect(h1s[0].textContent?.trim()).toBe('Component catalog');
    });

    it('when the catalog renders, no heading level is skipped', async () => {
      const el = await render();
      const levels = Array.from(el.querySelectorAll('h1, h2, h3, h4, h5, h6')).map((h) =>
        Number(h.tagName.slice(1)),
      );

      expect(levels[0]).toBe(1);
      levels.forEach((level, i) => {
        if (i > 0) expect(level).toBeLessThanOrEqual(levels[i - 1] + 1);
      });
    });

    it('when the catalog renders, the section region names are distinct', async () => {
      const el = await render();
      const names = Array.from(el.querySelectorAll('section[aria-labelledby]')).map(labelledByText);
      expect(new Set(names).size).toBe(names.length);
    });
  });

  describe('light and dark regions', () => {
    it('when the catalog renders, at least one dark-scoped container is present per section', async () => {
      const el = await render();
      const darkContainers = el.querySelectorAll('.dark');
      // Every demo in every section renders one dark region.
      expect(darkContainers.length).toBeGreaterThanOrEqual(GROUPS.length);
    });

    it('when the catalog renders, a light region (without dark class on outer wrapper) exists', async () => {
      const el = await render();
      // The host does not carry the dark class; the light regions sit beside the dark ones.
      expect(el.classList.contains('dark')).toBe(false);
      expect(el.querySelector('.light')).toBeTruthy();
    });

    it('when the catalog renders, a dark-classed container element is present', async () => {
      const el = await render();
      expect(el.querySelector('.dark')).toBeTruthy();
    });

    for (const group of GROUPS) {
      it(`when the catalog renders, '${group}' pairs every light region with a dark region`, async () => {
        const el = await render();
        const section = el.querySelector(`section[data-section="${group}"]`)!;
        const light = section.querySelectorAll('.light');
        const dark = section.querySelectorAll('.dark');

        expect(light.length).toBeGreaterThan(0);
        expect(dark.length).toBe(light.length);
      });
    }

    it('when the catalog renders, every region is a group named Light or Dark after its scheme', async () => {
      const el = await render();
      const regions = Array.from(el.querySelectorAll('.light, .dark'));

      expect(regions.length).toBeGreaterThan(0);
      for (const region of regions) {
        expect(region.getAttribute('role')).toBe('group');
        expect(labelledByText(region)).toBe(region.classList.contains('dark') ? 'Dark' : 'Light');
      }
    });

    it('when the catalog renders, each overlay demo group renders once in the light and once in the dark region', async () => {
      const el = await render();
      const section = el.querySelector('section[data-section="Overlays"]')!;

      // Mounted once: the section stamps each group into its own light and dark region.
      expect(section.querySelectorAll('app-overlays-section')).toHaveLength(1);
      for (const demo of ['overlay-triggers', 'snackbars', 'tooltips']) {
        const regions = Array.from(section.querySelectorAll(`[data-demo="${demo}"] .preview-region`));
        expect(regions.map((region) => (region.classList.contains('dark') ? 'dark' : 'light'))).toEqual([
          'light',
          'dark',
        ]);
      }
    });

    it('when the catalog renders, the overlay demo groups are h3 headings under the Overlays h2', async () => {
      const el = await render();
      const section = el.querySelector('section[data-section="Overlays"]')!;
      const headings = Array.from(section.querySelectorAll('h2, h3')).map(
        (heading) => `${heading.tagName}: ${heading.textContent?.trim()}`,
      );

      // Each heading sits outside the stamped template, so it appears once, not once per region.
      expect(headings).toEqual(['H2: Overlays', 'H3: Modal, slide-over, and drawer', 'H3: Snackbar', 'H3: Tooltip']);
    });

    it('when the catalog renders, the overlay trigger regions paint their own surface from tokens', async () => {
      const el = await render();
      const regions = el.querySelectorAll('[data-section="Overlays"] .preview-region');

      expect(regions).toHaveLength(6);
      for (const region of Array.from(regions)) {
        const style = getComputedStyle(region);
        expect(style.backgroundColor).toContain('--mat-sys-surface');
        expect(style.color).toContain('--mat-sys-on-surface');
      }
    });

    for (const group of ['Navigation', 'Data Display']) {
      it(`when the catalog renders, every landmark and tablist in '${group}' is named after its region`, async () => {
        const el = await render();
        const section = el.querySelector(`section[data-section="${group}"]`)!;
        const named = Array.from(section.querySelectorAll(NAMED_ROLES));
        const names = named.map(accessibleName);

        expect(named.length).toBeGreaterThan(0);
        // Two copies sharing a name (two "Breadcrumb" navs, two "Project views" tablists) can't be told apart.
        expect(new Set(names).size).toBe(names.length);
        for (const element of named) {
          const scheme = element.closest('.light, .dark')?.classList.contains('dark') ? 'dark' : 'light';
          expect(accessibleName(element).toLowerCase()).toMatch(new RegExp(`${scheme} preview$`));
        }
      });
    }

    it('when the catalog renders, the navigation demos sit directly in the region, with no second painted frame', async () => {
      const el = await render();
      const section = el.querySelector('section[data-section="Navigation"]')!;
      const trails = Array.from(section.querySelectorAll('ui-breadcrumbs nav')).map(accessibleName);

      expect(trails).toEqual(['Breadcrumb, light preview', 'Breadcrumb, dark preview']);
      expect(el.querySelectorAll('.demo-surface')).toHaveLength(0);
    });
  });

  describe('overlays', () => {
    let loader: HarnessLoader;
    let documentLoader: HarnessLoader;

    beforeEach(async () => {
      await render();
      loader = TestbedHarnessEnvironment.loader(fixture);
      documentLoader = TestbedHarnessEnvironment.documentRootLoader(fixture);
    });

    function trigger(text: string, scheme: 'light' | 'dark'): Promise<MatButtonHarness> {
      return loader.getHarness(
        MatButtonHarness.with({ text, ancestor: `[data-section="Overlays"] .${scheme}` }),
      );
    }

    it('when the catalog renders, no overlay is open', async () => {
      expect(document.querySelectorAll('.cdk-overlay-container [role="dialog"]')).toHaveLength(0);
    });

    it('when the catalog renders, every dialog trigger in both regions announces a dialog and no expanded state', async () => {
      const triggers = await loader.getAllHarnesses(
        MatButtonHarness.with({ ancestor: '[data-section="Overlays"] [data-demo="overlay-triggers"]' }),
      );

      expect(triggers).toHaveLength(6);
      for (const button of triggers) {
        const host = await button.host();
        expect(await host.getAttribute('aria-haspopup')).toBe('dialog');
        expect(await host.getAttribute('aria-expanded')).toBeNull();
      }
    });

    it('when a snackbar trigger is clicked, ToastService shows that snackbar', async () => {
      const show = vi.spyOn(TestBed.inject(ToastService), 'show');

      await (await trigger('Show snackbar', 'light')).click();
      expect(show).toHaveBeenLastCalledWith('success', 'Changes saved');
      const [snackBar] = await documentLoader.getAllHarnesses(MatSnackBarHarness);
      expect(await snackBar.getMessage()).toContain('Changes saved');

      await (await trigger('Show error snackbar', 'dark')).click();
      expect(show).toHaveBeenLastCalledWith('error', "Couldn't save changes");

      TestBed.inject(MatSnackBar).dismiss();
      show.mockRestore();
    });

    it('when an overlay is opened, at most one overlay panel is rendered in the DOM', async () => {
      fixture.componentInstance.activeOverlay.set('modal');
      fixture.detectChanges();
      await fixture.whenStable();
      // MatDialog renders the modal in document.body's overlay container, not in the fixture.
      const overlayPanels = document.querySelectorAll('.cdk-overlay-container [role="dialog"]');
      expect(overlayPanels).toHaveLength(1);

      // Switching overlays closes the previous one rather than stacking a second focus trap.
      fixture.componentInstance.activeOverlay.set('drawer');
      fixture.detectChanges();
      await fixture.whenStable();
      expect(document.querySelectorAll('.cdk-overlay-container [role="dialog"]')).toHaveLength(1);
      const [dialog] = await documentLoader.getAllHarnesses(MatDialogHarness);
      expect(await dialog.getTitleText()).toBe('Notifications');
    });

    it('when the dark region modal trigger is clicked, the modal opens and Cancel closes it', async () => {
      const openModal = await trigger('Open modal', 'dark');
      await openModal.click();

      const dialog = await documentLoader.getHarness(MatDialogHarness);
      expect(await dialog.getTitleText()).toBe('Publish changes?');
      expect(await dialog.getContentText()).toContain('Everyone with access to this project will see your changes');
      expect(fixture.componentInstance.activeOverlay()).toBe('modal');
      expect(await (await openModal.host()).getAttribute('aria-expanded')).toBeNull();

      const cancel = await documentLoader.getHarness(
        MatButtonHarness.with({ text: 'Cancel', ancestor: '.cdk-overlay-container' }),
      );
      await cancel.click();
      await fixture.whenStable();

      expect(await documentLoader.getAllHarnesses(MatDialogHarness)).toHaveLength(0);
      expect(fixture.componentInstance.activeOverlay()).toBeNull();
    });

    it('when a closed overlay is opened again, it reopens', async () => {
      const openModal = await trigger('Open modal', 'light');
      await openModal.click();
      await (await documentLoader.getHarness(MatDialogHarness)).close();
      await fixture.whenStable();
      expect(fixture.componentInstance.activeOverlay()).toBeNull();

      await openModal.click();

      expect(await documentLoader.getAllHarnesses(MatDialogHarness)).toHaveLength(1);
      expect(fixture.componentInstance.activeOverlay()).toBe('modal');
    });

    it('when Esc dismisses the slide-over, the state clears and focus returns to its trigger', async () => {
      const openSlideOver = await trigger('Open slide-over', 'light');
      const triggerElement = TestbedHarnessEnvironment.getNativeElement(await openSlideOver.host()) as HTMLElement;
      triggerElement.focus();
      await openSlideOver.click();

      const dialog = await documentLoader.getHarness(MatDialogHarness);
      expect(await dialog.getTitleText()).toBe('Project details');
      expect(fixture.componentInstance.activeOverlay()).toBe('slide-over');

      await dialog.close();
      await fixture.whenStable();

      expect(await documentLoader.getAllHarnesses(MatDialogHarness)).toHaveLength(0);
      expect(fixture.componentInstance.activeOverlay()).toBeNull();
      expect(document.activeElement).toBe(triggerElement);
    });

    it('when the drawer trigger is clicked, a named side sheet opens', async () => {
      await (await trigger('Open drawer', 'dark')).click();

      const dialog = await documentLoader.getHarness(MatDialogHarness);
      expect(await dialog.getTitleText()).toBe('Notifications');
      expect(fixture.componentInstance.activeOverlay()).toBe('drawer');
    });

    it('when the modal opens, Cancel comes first as a text button and Publish is the filled confirming action', async () => {
      await (await trigger('Open modal', 'light')).click();

      const actions = await documentLoader.getAllHarnesses(
        MatButtonHarness.with({ ancestor: '.cdk-overlay-container .mat-mdc-dialog-actions' }),
      );
      const summary = await Promise.all(
        actions.map(async (button) => [await button.getText(), await button.getAppearance()]),
      );

      expect(summary).toEqual([
        ['Cancel', 'text'],
        ['Publish', 'filled'],
      ]);
    });

    for (const [previous, surfaceTitle] of [
      ['drawer', 'Notifications'],
      ['slide-over', 'Project details'],
    ] as const) {
      it(`when the ${previous} dismissal lands after the modal trigger but before change detection, the modal still opens`, async () => {
        const component = fixture.componentInstance;
        component.openOverlay(previous);
        fixture.detectChanges();
        await fixture.whenStable();
        const [sheet] = TestBed.inject(MatDialog).openDialogs;
        expect(await (await documentLoader.getHarness(MatDialogHarness)).getTitleText()).toBe(surfaceTitle);

        // The user dismisses the sheet and activates the modal trigger in the same task. With animations
        // disabled, MatDialog reports the close in a microtask, which runs before the scheduled change
        // detection, so the sheet still holds its dialog ref and reports the dismissal.
        sheet.close();
        component.openOverlay('modal');
        await Promise.resolve();
        await Promise.resolve();

        expect(component.activeOverlay()).toBe('modal');

        fixture.detectChanges();
        await fixture.whenStable();
        const dialogs = await documentLoader.getAllHarnesses(MatDialogHarness);
        expect(dialogs).toHaveLength(1);
        expect(await dialogs[0].getTitleText()).toBe('Publish changes?');
      });
    }

    it('when a dismissal names an overlay that is not the active one, the active overlay stays open', async () => {
      const component = fixture.componentInstance;
      component.openOverlay('modal');

      component.closeOverlay('drawer');
      expect(component.activeOverlay()).toBe('modal');

      component.closeOverlay('modal');
      expect(component.activeOverlay()).toBeNull();
    });

    it('when closeOverlay is called without a name, whatever is open is cleared', () => {
      const component = fixture.componentInstance;
      component.openOverlay('slide-over');

      component.closeOverlay();

      expect(component.activeOverlay()).toBeNull();
    });
  });

  describe('navigation toggles', () => {
    let el: HTMLElement;

    beforeEach(async () => {
      el = await render();
    });

    function buttons(selector: string): HTMLElement[] {
      return Array.from(el.querySelectorAll<HTMLElement>(`[data-section="Navigation"] ${selector}`));
    }

    /** The element a toggle's aria-controls names, or null while it has none. */
    function controlled(button: HTMLElement): HTMLElement | null {
      const id = button.getAttribute('aria-controls');
      return id ? document.getElementById(id) : null;
    }

    async function click(button: HTMLElement): Promise<void> {
      button.click();
      fixture.detectChanges();
      await fixture.whenStable();
    }

    it('when the navbar toggle opens, each copy shows its own destination preview and aria-controls names it', async () => {
      const toggles = buttons('[data-demo="navbar"] app-hamburger button');
      expect(toggles).toHaveLength(2);
      for (const toggle of toggles) {
        expect(toggle.getAttribute('aria-expanded')).toBe('false');
        expect(toggle.hasAttribute('aria-controls')).toBe(false);
      }
      expect(el.querySelectorAll('[data-demo="navbar"] .nav-preview')).toHaveLength(0);

      await click(toggles[0]);

      const ids = toggles.map((toggle) => {
        const preview = controlled(toggle);
        expect(toggle.getAttribute('aria-expanded')).toBe('true');
        expect(preview?.getAttribute('role')).toBe('list');
        expect(preview?.closest('.preview-region')).toBe(toggle.closest('.preview-region'));
        expect(preview?.querySelectorAll('li')).toHaveLength(3);
        expect(preview?.querySelectorAll('lucide-icon[aria-hidden="true"]')).toHaveLength(3);
        return preview?.id;
      });
      expect(new Set(ids).size).toBe(2);
    });

    it('when the modal rail toggle closes, its preview and aria-controls are removed', async () => {
      const toggles = buttons('[data-demo="hamburger"] app-hamburger:not([variant]) button');
      expect(toggles).toHaveLength(2);
      for (const toggle of toggles) {
        expect(toggle.getAttribute('aria-expanded')).toBe('true');
        expect(controlled(toggle)?.closest('.toggle-demo')).toBe(toggle.closest('.toggle-demo'));
      }

      await click(toggles[1]);

      for (const toggle of toggles) {
        expect(toggle.getAttribute('aria-expanded')).toBe('false');
        expect(toggle.hasAttribute('aria-controls')).toBe(false);
        expect(toggle.closest('.toggle-demo')?.querySelector('.nav-preview')).toBeNull();
      }
    });

    it('when the docked rail toggle collapses, its preview stays and switches to the collapsed layout', async () => {
      const toggles = buttons('[data-demo="hamburger"] app-hamburger[variant="rail"] button');
      expect(toggles).toHaveLength(2);
      for (const toggle of toggles) {
        expect(toggle.getAttribute('aria-expanded')).toBe('true');
        expect(controlled(toggle)?.classList.contains('nav-preview-collapsed')).toBe(false);
      }

      await click(toggles[0]);

      for (const toggle of toggles) {
        const preview = controlled(toggle);
        expect(toggle.getAttribute('aria-expanded')).toBe('false');
        expect(preview?.closest('.toggle-demo')).toBe(toggle.closest('.toggle-demo'));
        expect(preview?.classList.contains('nav-preview-collapsed')).toBe(true);
      }
    });
  });

  describe('forms', () => {
    let loader: HarnessLoader;

    beforeEach(async () => {
      await render();
      loader = TestbedHarnessEnvironment.loader(fixture);
    });

    function statusField(scheme: 'light' | 'dark'): Promise<MatFormFieldHarness> {
      return loader.getHarness(
        MatFormFieldHarness.with({ floatingLabelText: 'Status', ancestor: `[data-demo="fields"] .${scheme}` }),
      );
    }

    it('when the catalog renders, neither copy of the required Status field shows an error yet', async () => {
      for (const scheme of ['light', 'dark'] as const) {
        const field = await statusField(scheme);
        const select = await field.getControl(MatSelectHarness);

        expect(await field.hasErrors()).toBe(false);
        expect(await (await select!.host()).getAttribute('aria-invalid')).not.toBe('true');
      }
    });

    it('when the Status field closes without a choice, that copy shows the error until a status is chosen', async () => {
      const field = await statusField('light');
      const select = (await field.getControl(MatSelectHarness))!;

      await select.open();
      await select.close();

      expect(await field.getTextErrors()).toEqual(['Choose a status']);
      expect(await (await select.host()).getAttribute('aria-invalid')).toBe('true');
      expect(await (await statusField('dark')).hasErrors()).toBe(false);

      await select.open();
      await select.clickOptions({ text: 'Active' });

      expect(await field.hasErrors()).toBe(false);
    });
  });

  describe('loading demos', () => {
    it('when the catalog renders, each copy of the skeleton demo names its loading state outside the busy region', async () => {
      const el = await render();
      const regions = Array.from(el.querySelectorAll('[data-demo="loading"] .preview-region'));

      expect(regions).toHaveLength(2);
      for (const region of regions) {
        const status = Array.from(region.querySelectorAll('[role="status"]')).find(
          (node) => node.textContent?.trim() === 'Loading profile…',
        );
        expect(region.querySelector('[aria-busy="true"] app-skeleton')).toBeTruthy();
        expect(status).toBeTruthy();
        expect(status!.closest('[aria-busy]')).toBeNull();
      }
    });
  });

  describe('stat card demo', () => {
    it('when the catalog renders, each copy formats its numbers with locale pipes and names direction without a sign', async () => {
      const el = await render();
      const regions = Array.from(el.querySelectorAll('[data-demo="stat-cards"] .preview-region'));

      expect(regions).toHaveLength(2);
      for (const region of regions) {
        const cards = Array.from(region.querySelectorAll('app-stat-card')).map((card) => [
          card.querySelector('.stat-card-metric')?.textContent?.trim(),
          card.querySelector('.stat-card-delta')?.textContent?.replace(/\s+/g, ' ').trim() ?? null,
        ]);
        // Default en-US locale. The hidden Up / Down label reads before the delta, so a sign would say "Down -3%".
        expect(cards).toEqual([
          ['1,284', 'Up 12%'],
          ['8,932', 'Down 3%'],
          ['342', null],
        ]);
      }
    });
  });
});

@Component({
  imports: [ThemePreviewComponent],
  template: `
    <app-theme-preview [label]="label()">
      <ng-template>
        <button type="button" class="stamped">Save changes</button>
      </ng-template>
    </app-theme-preview>
  `,
})
class PreviewHostComponent {
  readonly label = signal('');
}

describe('ThemePreviewComponent', () => {
  let fixture: ComponentFixture<PreviewHostComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [PreviewHostComponent] }).compileComponents();
    fixture = TestBed.createComponent(PreviewHostComponent);
    await fixture.whenStable();
  });

  it('stamps the template once in the light region and once in the dark region', () => {
    const el: HTMLElement = fixture.nativeElement;
    const light = el.querySelector('.preview-region.light');
    const dark = el.querySelector('.preview-region.dark');

    expect(light?.querySelectorAll('.stamped')).toHaveLength(1);
    expect(dark?.querySelectorAll('.stamped')).toHaveLength(1);
  });

  it('names each region with its visible caption, with ids unique per preview', () => {
    const el: HTMLElement = fixture.nativeElement;
    const light = el.querySelector('.light')!;
    const dark = el.querySelector('.dark')!;

    expect(light.getAttribute('role')).toBe('group');
    expect(labelledByText(light)).toBe('Light');
    expect(labelledByText(dark)).toBe('Dark');
    expect(light.getAttribute('aria-labelledby')).not.toBe(dark.getAttribute('aria-labelledby'));
  });

  it('omits the label row while the label is empty', () => {
    expect(fixture.nativeElement.querySelector('.preview-label')).toBeNull();
  });

  it('shows the label above both regions when one is set', async () => {
    fixture.componentInstance.label.set('Buttons');
    await fixture.whenStable();

    expect(fixture.nativeElement.querySelector('.preview-label')?.textContent?.trim()).toBe('Buttons');
  });
});
