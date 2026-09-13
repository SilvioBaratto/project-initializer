# Cross-Browser / Device QA Checklist

> **Instructions for the developer:** fill in each TBD field after completing a
> manual pass on real hardware. Do not mark a row ✅ based on assumption — use an
> actual device or BrowserStack session and record the device name + OS version.

The template is styled with Angular Material 3. `mat.theme()` in `src/styles.scss`
emits every color as a `--mat-sys-*` token with a light and a dark value, and the
shell follows the M3 window size classes: a navigation bar below 600px, a
navigation rail from 600px.

## Tested by

| Field           | Value |
|-----------------|-------|
| Tester          | TBD   |
| Date            | TBD   |

---

## Test matrix

Each cell: ✅ pass · ❌ fail · ⚠️ partial · — skipped

### iOS Safari

| Scenario                                     | Mobile | Desktop |
|----------------------------------------------|--------|---------|
| Notch clearance (safe-area-inset-top/bottom) | TBD    | n/a     |
| dvh full-height — toolbar show/hide          | TBD    | n/a     |
| Sticky-footer + safe-area                    | TBD    | n/a     |
| Dark-mode toggle                             | TBD    | TBD     |
| Focus trap (dialogs, side and bottom sheets) | TBD    | TBD     |
| Navigation bar and rail at 600px             | TBD    | n/a     |

**Device tested:** TBD (for example iPhone 15 Pro, iOS 18.4)

---

### Chrome

| Scenario                                     | Mobile | Desktop |
|----------------------------------------------|--------|---------|
| Notch clearance (safe-area-inset-top/bottom) | TBD    | n/a     |
| dvh full-height — toolbar show/hide          | TBD    | n/a     |
| Sticky-footer + safe-area                    | TBD    | TBD     |
| Dark-mode toggle                             | TBD    | TBD     |
| Focus trap (dialogs, side and bottom sheets) | TBD    | TBD     |
| Navigation bar and rail at 600px             | TBD    | TBD     |

**Device tested:** TBD (for example Pixel 8 / Android 15; macOS desktop)

---

### Edge

| Scenario                                     | Mobile | Desktop |
|----------------------------------------------|--------|---------|
| Notch clearance (safe-area-inset-top/bottom) | TBD    | n/a     |
| dvh full-height — toolbar show/hide          | TBD    | n/a     |
| Sticky-footer + safe-area                    | TBD    | TBD     |
| Dark-mode toggle                             | TBD    | TBD     |
| Focus trap (dialogs, side and bottom sheets) | TBD    | TBD     |
| Navigation bar and rail at 600px             | TBD    | TBD     |

**Device tested:** TBD (for example Surface Pro / Windows 11; Android mobile)

---

## Validation areas

### Notch clearance

Verify that the top app bar's `<header>` (`app-navbar`, shown below 600px), padded
by `env(safe-area-inset-top)`, and the navigation bar (`app-bottom-tab-bar`), padded
by `env(safe-area-inset-bottom)`, clear the device notch and home indicator on all
tested browsers. Both also pad by the side insets. In landscape, the navigation rail
adds `env(safe-area-inset-left)` / `env(safe-area-inset-right)` to its width.

- [ ] Top app bar title and icons aren't clipped by the notch
- [ ] Navigation bar destinations clear the home indicator
- [ ] In landscape, rail destinations clear the notch

### dvh full-height under toolbar show/hide

Verify that the shell root (`layout.css`, `block-size: 100dvh`) tracks the visible
viewport when the browser toolbar slides in and out (iOS Safari address bar,
Chrome/Edge compact mode), and that only `<main>` scrolls.

- [ ] No content is cut off when the toolbar is hidden
- [ ] Layout doesn't jump when the toolbar reappears

### Sticky-footer + safe-area

Verify that bottom-anchored elements stay visible and respect
`env(safe-area-inset-bottom)` when the toolbar hides: the navigation bar
(64px + `env(safe-area-inset-bottom)`) and snackbars, which sit 8px above the
navigation bar below 600px and 8px above the bottom edge from 600px.

- [ ] Navigation bar stays above the home indicator
- [ ] Snackbars don't overlap the navigation bar or OS chrome

### Dark-mode toggle

Verify that choosing System, Light or Dark (from the rail's Change theme menu, the
compact actions sheet or the Settings page, all through `ThemeService.setTheme`) puts
exactly one of `.light` / `.dark` on `<html>`. Those classes set `color-scheme`,
which picks the light or dark value of every `--mat-sys-*` token. Check the shell,
the shared components, Material overlay panels (dialogs, snackbars, tooltips in
`.cdk-overlay-container`) and the `/components` catalog, including its forced
light and dark preview regions.

- [ ] All surfaces switch scheme, overlay panels included
- [ ] System follows an OS appearance change while the app is open
- [ ] No unthemed white flash on toggle
- [ ] With Light or Dark chosen against the OS appearance, a reload paints the chosen scheme from the first frame

### Focus trap (dialogs, side and bottom sheets)

Verify that Tab and Shift-Tab cycle only inside an open dialog (`app-modal`) or side
sheet (`app-drawer`, `app-slide-over`), all built on `MatDialog`, and inside the
compact actions bottom sheet (`ShellActionsSheetComponent`), which the top app bar
button opens through `MatBottomSheet` below 600px. Escape or a click on the scrim
closes each of them, and focus returns to the trigger element.

- [ ] Tab wraps at the last focusable element
- [ ] Shift-Tab wraps at the first focusable element
- [ ] Escape closes and returns focus
- [ ] A click on the scrim closes and returns focus

### Navigation bar and rail at 600px

Verify both sides of each M3 window size class boundary: 599/600px, 839/840px,
1199/1200px and 1599/1600px. Below 600px the top app bar and navigation bar show,
and a top app bar button opens the theme and account actions. From 600px a collapsed
navigation rail replaces both, from 840px a toggle expands it, and from 1600px the
rail starts expanded. Those are defaults: once the rail is toggled, the choice is
stored in localStorage (`app-rail-expanded`) and wins at every width from 840px,
across reloads. Delete that key in the browser's dev tools before checking the
defaults. On a phone, rotating between portrait and landscape usually crosses 600px.

- [ ] Exactly one navigation surface shows at every width
- [ ] The current destination keeps its active indicator across the switch
- [ ] Expanding and collapsing the rail (840px and up) doesn't clip content
- [ ] With `app-rail-expanded` deleted, the rail starts expanded from 1600px and collapsed below 1600px
- [ ] After a toggle, the rail keeps that state across a reload and at every width from 840px

---

## Known-fragile patterns to re-check

- Sticky-footer + `env(safe-area-inset-bottom)` when the iOS toolbar hides: check
  that the navigation bar doesn't jump or leave a gap while the toolbar animates
- `aria-modal` + VoiceOver on recent Safari may not inert background content.
  Material dialogs also set `aria-hidden` on the overlay container's siblings, so
  check that VoiceOver can't reach the page behind any modal surface
- `dvh` inside in-app WKWebView browsers (Instagram, Gmail) may behave as `svh`
- Compact snackbars assume a 64px navigation bar. At a large text-size setting the
  bar can grow taller, so check that snackbars still clear it
