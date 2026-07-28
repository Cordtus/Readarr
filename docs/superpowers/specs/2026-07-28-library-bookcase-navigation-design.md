# Library of Bex Bookcase Navigation Design

## Goal

Replace the landing page's square navigation cards with one responsive,
environmental bookcase that contains the library identity, shelf previews, and
the complete request flow. Preserve the existing reading-room atmosphere while
making late-model iPhones and iOS Safari the primary interaction target.

## Visual Composition

The desktop page places a narrow, built-in dark-wood bookcase along the left
side of the reading-room scene. The identity plaque is integrated into its top:
`A private collection` above `The Library of Bex`. There is no floating room
tagline, including the rejected copy `A room to browse, listen, and ask for the
next book`.

Three horizontal shelf fronts sit below the plaque:

- `Books` - `Open the shelves and see what is ready to read.`
- `Audiobooks` - `Settle in with something worth hearing.`
- `Request a book` - `Search by title, author, or ISBN without leaving the room.`

The shelves use wood grain, inset shadow, and restrained brass detail to read
as furniture, not cards or conventional buttons. The passive archives notice
becomes a quiet inscription at the foot of the bookcase rather than a separate
card. The existing warm reading-room image, walnut, copper, paper, serif type,
and calligraphic identity remain the visual foundation.

On narrow screens, the scene retains a shallow atmospheric area above a
full-width cabinet. Labels become horizontal touch targets; no vertical spine
text is used. The cabinet stays in normal document flow so the page can scroll
correctly around the iOS software keyboard.

## Shelf Interaction

Only one shelf is pinned open at a time. On pointer-accurate desktop devices,
hover may reveal a temporary preview; click pins it. Keyboard focus and
activation provide the same states. Touch devices never depend on hover: one
tap expands a shelf, and another shelf tap transfers the open state.

Books and Audiobooks show server-rendered item counts, an honest empty state,
and up to three recent entries. An `Open shelf` link navigates to the existing
catalog route. Previews must reuse the catalog's path-safety filtering and
never expose escaping symlinks.

Request a book expands into the search form in place. Search results,
confirmation, errors, expired-token recovery, and success all render inside
the same bookcase and reading-room shell. Existing request URLs and POST
semantics remain valid for browser history, refreshes, direct links, and
no-JavaScript operation. JavaScript enhances accordion state only; it is not a
requirement for searching or confirming.

## Motion

Motion is occasional state feedback, weighted toward subtle production polish.
Shelf content enters with opacity and a small translate over 220-320 ms using a
strong decelerating curve and no bounce. Exits are shorter and quieter. There
is no looping, pulsing, parallax, cursor-following, or decorative ambient
motion. Layout remains stable while inner content transitions.

`prefers-reduced-motion: reduce` makes all shelf state changes immediate.
Touch press, hover, keyboard focus, loading, error, and success states remain
clear without animation.

## iPhone and iOS Safari Requirements

- Add `viewport-fit=cover`; pad interactive content with
  `env(safe-area-inset-*)` and normal spacing fallbacks.
- Use stable and dynamic viewport units only as progressive enhancements.
  Avoid root overflow locks, fixed page heights, and fixed backgrounds.
- Make every control at least 44 by 44 CSS pixels with adequate separation.
- Keep form controls at 16 CSS pixels or larger to prevent focus zoom.
- Use `type="search"`, `enterkeyhint="search"`, and visible labels.
- Keep the focused field and submit action scrollable above the software
  keyboard and Home indicator.
- Restrict hover behavior to `(hover: hover) and (pointer: fine)`.
- Preserve pinch zoom, text resizing, VoiceOver landmarks, visible focus,
  browser Back, and iOS edge-swipe navigation.
- Prevent horizontal overflow in portrait and landscape.
- Support increased contrast, reduced motion, and reduced transparency without
  losing hierarchy or functionality.

## Accessibility and Failure States

Shelf triggers are buttons with `aria-expanded` and `aria-controls`; catalog
destinations remain anchors. The open panel is associated with its trigger and
receives logical focus after server-rendered request-state transitions.
Headings and landmarks remain semantic. Color is never the only state signal.

Empty shelves state that nothing is catalogued yet. Metadata, Readarr, and
network failures appear within the request shelf with a retry path. Expired or
reused confirmation tokens cannot repeat a request. Disabled or unavailable
request configuration leaves Books and Audiobooks fully usable.

## Verification

Behavior tests cover dynamic previews, safe entry filtering, all request states
inside the shared shell, no-JavaScript forms, single-use confirmation, and
semantic accordion attributes. Existing traversal, symlink, file download, and
Readarr credential tests remain green.

Browser verification covers keyboard and pointer operation, reduced motion,
increased contrast, and WebKit viewports of 393 by 852 and 430 by 932 in both
orientations. It also checks form focus with the software keyboard represented,
44-pixel targets, safe-area padding, no horizontal overflow, and usable text at
200 percent zoom. A real late-model iPhone Safari pass is the final acceptance
check when the device is available.
