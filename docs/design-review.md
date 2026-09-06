# Design review — UI and UX

Reviewed at `dee588e` on `give-connectris-a-backend`. `pnpm check`, `pnpm lint` and `pnpm test`
are all green; nothing here is a build failure.

## How this was done, and what it is worth

**I could not see the screen.** The Chrome extension was not connected, so no screenshot was
taken and no rendered pixel was observed. Everything below is one of three things, and each
finding says which:

- **Verified** — read out of the source, the compiled CSS, or the server-rendered HTML from
  `pnpm dev` on `localhost`. Specificity, token usage counts, DOM structure, ARIA attributes
  and contrast arithmetic are all in this category.
- **Derived** — a consequence of code that follows necessarily, e.g. "this animation cannot
  render because the element is removed in the same tick". High confidence, but worth one
  real play to confirm.
- **Estimated** — layout arithmetic from the CSS against a stated viewport. Directionally
  right, exact numbers not to be trusted.

Nothing here is "it looks wrong" from imagination.

---

## What is already good, and should not be touched

This codebase has an unusually high ratio of reasoning to code, and a review is a machine for
recommending good things away. So, explicitly:

- **The board never resizing.** Five slots for the whole game, solved rows keeping full row
  height, cleared rows converting in place. `SolvedRow.svelte:32` matching `--row-h + 2 *
--row-bleed` so solved and unsolved rows land on one rhythm is exactly right, and the loss
  path holds it too (`Board.svelte:42-51` swaps tiles for bands rather than showing both).
  Do not let anything in this document be read as a reason to reopen it.
- **One verb, two input paths.** Drag and tap-to-swap share `Session.swap`, and the drag
  layer (`Board.svelte:84-156`) is genuinely careful: pointer capture, a slop threshold, a
  `draggedAt` timestamp rather than a flag so a drag ending off-target cannot eat the next
  tap, and `elementsFromPoint` walking past the tile in hand. This is the fiddliest code in
  the repo and it is the part I would change least.
- **The check budget on the button that spends it**, counting down, neutral, never red. The
  comment at `Budget.svelte:83` — spending a check is the cost of playing, not a punishment —
  is the right call and the pips are the right shape for it.
- **The verdict's restraint.** A check that clears cleanly and leaves nothing else right says
  nothing at all (`session.svelte.ts:262`). That is hard to hold and it is held.
- **Pin 8 is intact on the end card.** `mm:ss · N left`, one line, no grid, no move count.
  `EndCard.svelte:15-19` states why and the code matches.
- **The anticipation sweep doubling as the latency budget** (`session.svelte.ts:216-221`).
  Hiding a network round trip inside an animation beat you were going to play anyway is the
  best idea on the branch. My complaints below are about what happens when it _doesn't_ fit,
  not about the idea.
- **The type-shrink rule on tiles.** `font-size: min(--fs-md, (100cqw - 12px) / (len * 0.62))`
  with `container-type: inline-size` on the slot — one size for everything that fits,
  shrinking only as far as the column demands. Correct, and cheaper than a JS fitter.
- **Colour never leaking into the board's own chrome.** Selection, drag target, drop shadow,
  jolt and tier are all neutral. The rule holds everywhere except the end card, which is item
  4 below.

---

## 1. Incoherent, and cheap to fix

Ordered by value. These are defects against the design's own stated intent, not taste.

### 1.1 There is no visible focus ring on any primary control — Verified

`src/lib/styles/app.css:103` defines the only focus style in the repo:

```css
:focus-visible {
	outline: 2px solid var(--accent);
	outline-offset: 2px;
}
```

Specificity `(0,1,0)`. Every focusable control that matters sets `outline` for _decoration_
inside a scoped component block, which Svelte compiles to `(0,2,0)`. From the compiled CSS
served by `pnpm dev`:

```css
.tile.svelte-4lsiak { … outline: 1px solid var(--tile-edge); outline-offset: -1px; }
```

Higher specificity wins regardless of source order, so `:focus-visible` never applies to:

| Control                                                | File                 |
| ------------------------------------------------------ | -------------------- |
| all 20 tiles                                           | `Tile.svelte:92`     |
| the Check button                                       | `Game.svelte:308`    |
| the three difficulty buttons and both fairness buttons | `EndCard.svelte:188` |
| the comment textarea                                   | `EndCard.svelte:215` |

`grep -rn "focus" src/` returns exactly one hit, in `app.css`. There is no `:focus-visible`
rule anywhere in any component.

**Why it matters.** DESIGN.md keeps tap-to-swap specifically because "it is what keeps the
board reachable from a keyboard". The keyboard path exists and works — the tiles are real
buttons, `Enter` fires `onpick`, the tile ids key the `each` so focus follows a tile through
a swap. It is invisible, which is the same as not existing. This is the highest-value item in
the document and the cheapest.

**Do this.** Give each of the four controls its own focus rule, and move the decorative
outline to an inset box-shadow so the two never compete again:

```css
.tile:focus-visible {
	outline: 2px solid var(--accent);
	outline-offset: 2px;
}
```

Four rules, four files. Then add a lint guard, because this will regress: the global reset at
`app.css:93` strips every button to bare text, so every new control has to redraw itself, and
redrawing itself is exactly what kills the ring.

### 1.2 The crash never plays on the last check of a lost run — Derived

`session.svelte.ts:238-245` fires `impact()`, then `:261` calls `finish('lost', …)` — with no
`await` between them, so both land in one synchronous block. `Board.svelte:51`:

```ts
let active = $derived(session.status === 'lost' ? [] : session.rows);
```

By the time Svelte flushes, `status` is `'lost'` and `active` is `[]`. The tiles that were
given `class:crashing` and `class:impact` are removed before a frame is painted with them.

**Why it matters.** DESIGN.md is emphatic that this is not decoration: _"the crash **is** the
feedback, pointing at where the run broke, and it's information the top-down rule otherwise
has to state in words."_ On the final check, the run ends with no crash, no verdict
(`:260-268` sets neither on a loss), and the board simply emptying under a rising card. The
one moment the game most owes the player an explanation is the one moment it gives none. That
is pin 5 territory — losing should feel like the puzzle beat you, not like the interface
closed.

**Do this.** Hold the reveal until the impact has landed. `impact()` already knows its own
duration; make it return a promise, and `await` it before `finish('lost', …)` on the losing
branch only. The win branch is fine as it is — there is nothing left to crash into.

### 1.3 The end card covers the loss reveal at the instant it lands — Derived / Estimated

`EndCard.svelte:37` opens with `asking = true`. `Game.svelte:123` mounts the card as soon as
`session.over && !session.combo`. On a losing check that cleared nothing — the common loss —
`combo` is 0, so the card rises immediately, while `SolvedRow`'s missed rows are still
staggering in at `order * 90ms` (`Board.svelte:170`), finishing around 660ms.

Estimated on a 375×667 viewport from the CSS: the well spans roughly y≈50–576, each row band
about 87px; the card with questions up is about 318px tall, so its top edge sits near y≈333.
That covers rows 4 and 5 entirely and part of row 3 — **about half the categories the player
just lost to, hidden at the moment they appear.**

**Why it matters.** The card's own comment (`EndCard.svelte:26-36`) already identified this
and chose questions-first because "an unseen question is an unanswered one". That trade is
right on a **win**, where everything under the card was revealed row by row and watched. It
is wrong on a **loss**, which is the only ending that shows the player something new. Asking
"was it fair?" over the top of the answer is the same self-defeating shape the revision was
meant to fix, just moved.

**Do this — one of:**

- `let asking = $state(won)`. Questions up on a win, board first on a loss, one tap either
  way. Two characters, and it uses the distinction the card already computes.
- Or reuse the machinery that already exists: `Game.svelte:123` holds the card behind a
  combo; hold it behind the loss stagger too.

I would do both.

### 1.4 Colour has stopped meaning only category — Verified

Three separate breaches, all recent:

1. **`--danger` and `--g5` are the same colour.** `app.css:21` is `#e8596c`; `app.css:32` is
   `#e8596c`. So the miss jolt, the network-fault text and "Out of checks" are painted in
   category five. `SolvedRow`'s chip for a fifth row is `background: var(--colour)`, i.e.
   pure `--g5` — so on a lost board the failure heading and a revealed category's chip are
   byte-identical.
2. **`EndCard.svelte:320`: `.outcome { color: var(--g4) }`.** "Solved" is painted in category
   four, a literal category token used as card chrome — twenty lines above `.choice`'s
   comment, "Unhued. Colour on this board means category, and an answer about the board is
   not one." The card contradicts itself within one stylesheet.
3. `ComboFlash`'s five-colour sweep is the one sanctioned exception and it is well argued
   (`ComboFlash.svelte:203-205`). Leave it.

**Why it matters.** This is the rule the Feel section spends a paragraph on, and it is the
one an end card full of buttons was always going to erode. It is also the cheapest to
restore.

**Do this.** Give `--danger` its own value that is visibly not `--g5` (nudge hue or
lightness — it only has to be distinguishable next to a chip), and repaint `.outcome`
neutrally: `--text` for won, `--muted` for lost, with the _word_ carrying the outcome. If a
won card must feel like a win, it can do it with weight and the score line, not with a hue
the board has already spent.

### 1.5 The survey's own questions are the least legible text on screen — Verified

`EndCard.svelte:166-174`, `legend { color: var(--dim) }` at `--fs-xs` (11.2px), uppercase,
0.06em tracking, on the card gradient `#161d27`.

Computed contrast ratios on the card:

| Element                                    | Colour               | Ratio       | AA (4.5) |
| ------------------------------------------ | -------------------- | ----------- | -------- |
| `legend` — "HOW WAS THAT?", "WAS IT FAIR?" | `--dim`              | **2.21**    | fail     |
| `.comment::placeholder` — "Anything else?" | `--dim`              | **2.06**    | fail     |
| `.best` — "best 2:14"                      | `--dim`              | **2.21**    | fail     |
| `.score`, `.choice`, `.next`               | `--muted` / `--text` | 4.97 – 16.7 | pass     |

**Why it matters.** This phase exists to collect these two answers. Both question labels fail
AA by a factor of two, in the smallest size in the scale, in caps. The buttons under them are
perfectly legible, so the player sees "Too easy / Just right / Too hard" with no readable
question above it. `--dim` is fine as a hairline colour on the near-black body
(`#090b0f`); it stops working the moment it is put on a raised surface, and the card is the
only raised surface in the app.

**Do this.** Use `--muted` for `legend` and `.best` (4.97 on the card, passes), and something
between `--dim` and `--muted` for the placeholder. Or define `--muted-on-raised` and stop
guessing. This is a two-line change.

### 1.6 The Check button and the tiles stay live-looking while nothing can happen — Verified

`Game.svelte:114` is `disabled={session.over}`. `Board.svelte:208` is the same.
`session.check()` guards on `this.busy` and `swap()` guards on `this.live`, so presses during
a check are correctly ignored — but nothing on screen says so. Both controls keep
`cursor: pointer` and keep their `:active { transform: scale(…) }` press feedback.

Two windows where this bites:

- **A slow grade.** `sweeping` is cleared by a fixed `setTimeout(SWEEP_MS)` at
  `session.svelte.ts:214`, not by the grading promise. If the network takes longer than the
  260ms sweep — a scaled-to-zero Cloud Run cold start will — the rails run up, the button
  flash ends, and then there is _dead air with a fully live-looking Check button_ until the
  wave starts. The player will press it again. Nothing will happen.
- **The roll.** A five-row clear runs `4 × ROW_STEP + LOCK_MS` ≈ 1.9s during which every
  remaining tile presses and does nothing.

**Why it matters.** The task brief notes that the global `button` reset has already caused one
bug where a control was invisible as a control. This is the mirror image: controls that are
visible as controls and are not live. It is also the most likely thing a real tester hits on
the deployed instance, because cold starts are where the latency actually is.

**Do this.** Add a `busy` gate to both `disabled` bindings, and hold `sweeping` until the
grade resolves rather than on a fixed timer — the rails can loop or hold at the top. A pending
state does not count anything, so pin 11 is untouched; this is the button reporting its own
state, not the game reporting a score.

### 1.7 The network-failure path contradicts itself in three small ways — Verified

`session.svelte.ts:204` increments `checks` _before_ awaiting the grade; `:226` decrements it
on failure. In between, Svelte has rendered: `left` dropped, the pip got `class:spending` and
ran its 560ms flash. **On every failed check the player watches a check get spent and then
un-spend itself.** The refund is the right call — the comment at `:224` argues it correctly
from pin 5 — but showing the charge first undoes the argument.

Two more, same area:

- `Game.svelte:99` renders `.fault` in `var(--danger)` inside `.callout`, which is `align-items:
end` — so a network error appears in exactly the slot, at exactly the size, and in exactly
  the colour that a missed check uses. The design says a check "says one thing, and only when
  it has something to say"; a transport failure is not a thing the check said.
- The copy is _"Could not reach the scorer. Try again."_ "Scorer" appears nowhere else in the
  UI — the button says Check, the rules say check, DESIGN.md says grader. And it does not say
  the check was refunded, which is the one fact that would stop the player panicking.

**Do this.** Spend the pip when the grade lands, not when the request leaves. Move the fault
next to the Check button — it is a "your press did not land" message, which is a button state
— and rewrite it as _"Couldn't check — no connection. That one's free, try again."_ Keep it
out of `--danger` so red still only means the board bit back.

### 1.8 "1 rows right" — Verified

`session.svelte.ts:265-268`:

```ts
this.verdict = {
	count: result.correctCount,
	note: result.correctCount > 0 ? 'rows right · none at the top' : 'rows right'
};
```

`correctCount === 1` renders **"1 ROWS RIGHT · NONE AT THE TOP"**. This is a reachable and
common state: exactly one row correct, not at the top. The verdict is the single sentence the
game writes in words, set at `--fs-lg` and described in DESIGN.md as "the only thing written
in words" — it should not have a grammar error in it.

While in there: the three note strings are three different sentence shapes for one fact —
`N more right · wrong order`, `N rows right · none at the top`, `N rows right`. Worth a pass
for one voice.

### 1.9 The only door to the rules and the picker is an 11px text link — Verified

`Game.svelte:46` and `:174-180`. `.help` is `--fs-xs` (11.2px), underlined, `--muted`, with
the global `padding: 0` from the button reset and no padding of its own. Its tap target is
about 13px tall — under a third of the 44px guideline — and it is the sole route to the rules
_and_ to every other board (§5.1).

**Why it matters.** Phone is the target "by roughly a factor of ten". This is the one control
on the screen with no size at all. Contrast is fine (5.78 on the body ground); the problem is
purely the target.

**Do this.** `padding: 8px 4px; margin: -8px -4px;` — target grows to ~29px with no visual
change and no layout shift. Better still, `min-height: 44px` with a negative block margin.
Same fix applies to `.picker button` (~23px) and `.choice` (~37px).

---

## 2. The visual system has drifted

None of this is broken. All of it is why the app "feels a bit messy", and it is the kind of
mess that compounds.

### 2.1 There is a raised-surface gradient concept, used five times, tokenised zero times — Verified

`--tile` and `--tile-hi` are referenced exactly **twice** in the whole repo (both in the base
tile gradient). Every other raised surface hardcodes its own pair:

| Surface               | Value                         | File                 |
| --------------------- | ----------------------------- | -------------------- |
| tile (base)           | `var(--tile-hi), var(--tile)` | `Tile.svelte:88`     |
| tile (selected)       | `#2a3442, #202836`            | `Tile.svelte:116`    |
| tile (drop target)    | `#33405180, #26303f`          | `Tile.svelte:132`    |
| Check button          | `#232c39, #19212c`            | `Game.svelte:307`    |
| Check button (firing) | `#39465a, #2a3547`            | `Game.svelte:328`    |
| end card              | `#161d27, #10151d`            | `EndCard.svelte:264` |

Six variants of one idea, each hand-mixed. Change the tile colour and five of these go stale
silently. `#33405180` also carries an alpha in a hex-8 in the middle of a set that does not,
which reads as an accident.

**Do this.** Two tokens — `--surface` / `--surface-hi` — plus a `--surface-raise` step
expressed with `color-mix`, and derive all six.

### 2.2 `--accent` is spelled out as a literal in four files — Verified

`rgb(238 243 250 / …)` — the exact channels of `--accent: #eef3fa` — appears 8 times across
`Tile.svelte`, `Game.svelte`, `Budget.svelte` and `ComboFlash.svelte`, at six different
alphas (8, 10, 12, 22, 30, 35, 42, 55%). It is a literal only because `box-shadow` and
`text-shadow` need a colour with alpha, which is now a solved problem:

```css
box-shadow: 0 0 0 4px color-mix(in oklab, var(--accent) 10%, transparent);
```

The file already uses `color-mix(in oklab, …)` in seven places, so this is house style, not a
new dependency. Same for `#0d131c` — "text on accent" — hardcoded twice (`Game.svelte:219`,
`EndCard.svelte:351`) and equal to neither `--ink` nor `--bg`.

### 2.3 Seven radii, one token — Verified

`--radius: 13px` is used twice (the tile, and the lifted-slot ghost). Everything else picks a
number: 10 (`.choice`, `.comment`), 12 (`.next`), 14 (`.rules`, `.check`), 17 (`.frame`,
`SolvedRow .row`), 18 (`.well`), 20 (`.card`), 999 (pills). Concentric radii are the thing the
eye notices when they are wrong: `.tile` at 13 sits inside `.frame` at 17 inside `.well` at
18, and 17-inside-18 with 10px of padding between them is not a concentric pair.

**Do this.** `--r-sm: 10px; --r-md: 13px; --r-lg: 18px; --r-xl: 20px; --r-pill: 999px`, and
make `.frame` derive from the tile radius plus its bleed rather than hardcoding 17.

### 2.4 The white-veil scale has seven undocumented steps — Verified

`rgb(255 255 255 / X%)` with X ∈ {3, 5, 6, 10, 18, 20, 42} across `.rules`, `.picker button`,
`.choice`, `.choice.picked`, `.comment`, `.toggle`, `.head:active`. Three of these (5, 6, 10)
are visually indistinguishable and are being used for _different_ semantic jobs — a picker
pill, a survey button, a toggle. Collapse to three steps and name them.

### 2.5 The row tier fades to invisible — the failure the design note says it avoids — Verified

`Board.svelte:68`: `const tier = (rank) => 26 - rank * 5;` → 26, 21, 16, 11, 6% white, with
`--fill` at a quarter of that. Contrast of each frame's edge against the well `#0c1016`:

| Row | edge alpha | edge vs well | fill vs well |
| --- | ---------- | ------------ | ------------ |
| 1   | 26%        | 2.28         | 1.16         |
| 2   | 21%        | 1.89         | 1.13         |
| 3   | 16%        | 1.57         | 1.09         |
| 4   | 11%        | **1.33**     | 1.06         |
| 5   | 6%         | **1.14**     | 1.03         |

DESIGN.md picked "a linear ramp with a floor rather than a decay, because a bottom row faded
to nothing stops reading as a container at all — which would win the argument about order at
the cost of the one about rows." The reasoning is right; the floor is set too low to deliver
it. At 1.14:1 the bottom frame is invisible on anything but a good screen in a dark room, so
the argument about rows is being lost anyway.

**This does not touch a pin** — the shape (linear, floored, neutral) is unchanged. I would try
`38 - rank * 6` (38→14%, i.e. ~3.0 down to ~1.5) and check it on a phone in daylight. The
18px row-gap versus the 7px column gap is doing most of the row-as-unit work regardless, so
this is reinforcement, not rescue.

### 2.6 Motion timing ignores reduced motion in three places — Verified

`wait()` (`session.svelte.ts:58`) collapses to 0 under `prefers-reduced-motion`. Three timers
in the same file use bare `setTimeout` and do not:

- `:214` — `sweeping` held 260ms
- `:311` — `crash` held `CRASH_MS + n * RIPPLE_STEP` (460–700ms)
- `:304` — `comboTimer` at `COMBO_HOLD` = 1100ms

So a reduced-motion player who wins with a triple clear gets: the whole clear resolving
instantly, a `TRIPLE` that never animates in, and then **1.1 seconds of a finished board**
before the end card appears, because `Game.svelte:123` is still holding it behind `combo`.
There is a real question underneath this (§5.4), but the inconsistency is a bug either way:
one clock respects the preference and three do not.

**Do this.** Route all four through one helper. Whether that helper zeroes them or merely
shortens them is §5.4.

### 2.7 Two tokens in `app.css` are dead, three are used once — Verified

`--boost` and `--jolt` are declared at `app.css:48` and `:50` but `Board.svelte:161-162`
always sets both on `.grid`, so the `:root` values never apply — they are documentation
wearing a declaration. `--fs-md`, `--well-edge` and `--bg-glow` each have exactly one
consumer. That is fine for the last three; the first two make the token file misleading to
read, which matters because it is meant to be the one place to look.

**Do this.** Move `--boost` / `--jolt` to a commented "set at runtime by Board" block, or drop
the `:root` declarations and document them where they are set.

### 2.8 Three disclosure idioms for three panels — Verified

- **Rules**: an inline `<section>` in normal flow (`Game.svelte:56-79`), pushing the layout
  down. `.app` is `min-height: 100dvh` and `.well` is `flex: 0 0 auto`, so on a short phone
  opening the rules mid-game pushes the Check button below the fold and makes the page
  scroll.
- **End card**: a fixed sheet with a scrim, z-index 10/11, collapsible.
- **Callout**: a transient absolute/flow hybrid inside a reserved 44px slack.

Three patterns is defensible — they do different jobs — but the rules panel is the odd one,
because it is the only one that moves the board. Making it a sheet like the end card would
unify the two things that are actually the same shape (a panel over the board that goes away
in a tap) and would fix the scroll.

---

## 3. Accessibility

Honestly: the keyboard _path_ is there and works, the reduced-motion hook is there, and the
contrast is mostly fine. What is missing is that none of it is finished.

### 3.1 §1.1 — no visible focus ring. The single most important item in this section.

### 3.2 The ordering mechanic is invisible to a screen reader — Verified

The board renders as a flat sequence of 20 buttons whose only accessible name is their word.
There is no `role`, no row grouping, and no position information. Verified in the SSR HTML:

```html
<button class="tile" data-row="0" data-col="0" aria-pressed="false">BLOODHOUND</button>
```

`data-row` is not exposed to assistive tech. So a screen-reader user can select and swap
tiles — the mechanics work — but cannot tell which row anything is in, and the entire game
("the order of your rows is part of the answer") is unavailable.

**This brushes a dropped feature, so, explicitly:** DESIGN.md dropped the rank column because
"the numbers were redundant — the top row is visibly the top row". That reasoning is about a
_visible_ column of numbers, and it holds. An accessible name is not visible and does not
resurrect it. Nothing goes back on screen.

**Do this.** Wrap each active row's tiles in `role="group"` with `aria-label="Row 1 of 5"`, or
put the row into the tile's accessible name via `aria-label={`${word}, row ${row + 1}`}`.
Then announce the swap in the existing live region.

### 3.3 The end card is a modal that is not a dialog — Verified

`EndCard.svelte:89` is a plain `<div class="sheet">`. No `role="dialog"`, no `aria-modal`, no
focus move on open, no `Escape` handler, no focus containment. When the run ends, the Check
button becomes `disabled` while focused, which drops focus to `<body>` — so a keyboard user's
next Tab starts from the top of the document. Nothing announces that the run ended at all:
`Game.svelte:91`'s `aria-live="polite"` covers the callout, and the callout is empty on both
a win and a loss.

**Do this.** `role="dialog" aria-modal="true" aria-labelledby` pointing at the outcome span;
move focus to the card on mount; `Escape` collapses the questions (matching the scrim, which
already does exactly that). The scrim is already a real `<button>` with a real label, which is
the hard part and is done right.

### 3.4 `Budget`'s label is on a role-less div — Verified

`Budget.svelte:7`: `<div class="budget" aria-label="4 of 4 checks left">`. `aria-label` on a
generic element with no role is not reliably exposed by assistive tech, and the div is not in
the tab order, so nothing will ever read it. Give it `role="status"` (or `role="img"` if it
should be read on demand rather than announced) — `role="status"` also means the count is read
when it changes, which is what a player would want.

### 3.5 The survey buttons are toggles pretending to be a radio group — Verified

`EndCard.svelte:108-142`. `<fieldset><legend>` around plain `<button aria-pressed>` gives the
legend no programmatic relationship to the buttons — `fieldset`/`legend` only names _form
controls_, and these are not. A screen reader announces "Too easy, toggle button, not
pressed", with no question attached. And `aria-pressed` is the wrong role shape: these are
mutually exclusive.

**Do this.** `role="radiogroup"` with `aria-label` on `.choices`, `role="radio"` +
`aria-checked` on each button, plus arrow-key handling. Or use real `<input type="radio">`
styled as the pills, which makes the `fieldset`/`legend` correct as written and gets arrow
keys for free. The second is less code.

### 3.6 Two toggles, two different contracts — Verified

`EndCard.svelte:95` gets `aria-expanded={asking}` — correct. `Game.svelte:46`'s help button
gets none, and instead changes its own _label_ between "How to play" and "Close" (which also
reads as "close the page"). Two disclosure buttons in one app should behave the same way.
Give the help button `aria-expanded` + `aria-controls`, and keep the label stable.

### 3.7 Contrast — mostly fine, three failures

All in §1.5 (`--dim` on the card, three uses). Everything else computed clears AA: `--muted`
on the body ground is 5.78, on the rules panel 5.50, on a picker pill 4.90; tile words 13.19;
solved-row labels 4.62–5.38 across all five categories; revealed (missed) rows 5.19–6.55 for
labels and 7.33 for words even at `opacity: 0.65`. The category palette is well chosen for
this ground and I would not touch it.

Non-text: the row frames (§2.5) and the 1px tile edge (1.25:1 against the tile fill) are both
below the 3:1 UI-component guideline. The tile edge does not matter — the tile's own fill is
13:1 against the well, so the shape is unmissable without its edge. The frames do.

---

## 4. Taste calls

Reasonable people differ; I would not spend a day on any of these.

- **`--fs-sm` (12.8px) is carrying all body copy.** The rules list, the survey buttons, the
  score line, the Check button, the solved-row word lists. `--fs-md` (15.2px) has exactly one
  consumer, the tile. Four sizes declared, two doing all the work, and the one doing most of
  it is small for a phone. I would try promoting the rules list and the solved-row words to
  `--fs-md` and see whether "one type size" still reads as deliberate.
- **The survey gives almost no acknowledgement.** Tapping "Just right" moves the button fill
  from 6% white to 18% and the outline from `--tile-edge` to 42% white. It posts immediately
  and fails silently by design (`report.ts:113`). The silent failure is right; the silent
  _success_ is the part I would strengthen — a checkmark, or the question label going from
  `--muted` to `--text`.
- **Selected, primary and current are all `--accent`.** A held tile, the sweep rails, the
  neutral jolt, "Next puzzle" and the picker's current pill are one paint. Correct under the
  colour rule (they are all neutral) and probably fine in practice, since they never co-occur
  — but it is why the picker's current pill reads as a button you should press.
- **`.head`'s label pair is "See the board" / "Questions"** — a verb phrase and a noun for one
  control. Pick a grammar: "See the board" / "See the questions".
- **Hit targets under 44px**, in order of exposure: `.help` ~13 (§1.9), `.picker button` ~23,
  `.choice` ~37, `.head` ~38, `.next` ~43. Only the first is urgent.

---

## 5. Needs a decision from the owner

### 5.1 Where does the puzzle picker live?

Today it is an unlabelled row of pills at the bottom of the rules panel
(`Game.svelte:71-77`), reachable only through an 11px "How to play" link, and choosing a board
closes the rules. Three things are wrong at once: the door is tiny, the room is the wrong one,
and the control has no heading.

**The constraint that makes this a decision rather than a fix:** the Feel section says the
header carries "the wordmark and a way to the rules. Nothing else earns a place up here."
Putting the picker in the header is the obvious move and it is the one the design has
pre-emptively refused. So, options that respect it:

1. **Split the panel.** Keep it where it is, but give it two headed sections — "How to play"
   and "Boards" — and rename the trigger to something that covers both. Cheapest; still hides
   navigation inside help.
2. **Put it on the end card, beside "Next puzzle."** Choosing a board is a between-runs
   action, and the end card is the between-runs screen. This is where I would put it. It also
   turns "Next puzzle" from a guess into a choice (see §5.3).
3. **A `/boards` route**, linked from the end card. Most room, most navigation.

Whichever wins, the trigger needs a real target (§1.9).

### 5.2 Two URLs render the same board

`/` serves `live[0]` (`+page.server.ts`); the picker links every board including `live[0]` to
`/p/<id>`. So today's board has two addresses, and the picker's "current" pill navigates you
off the canonical one. Harmless now, a share-link problem later. Either redirect `/p/<live[0]>`
to `/`, or make `/` a redirect to `/p/<live[0]>` and have one address per board.

### 5.3 "Next puzzle" is a guess, and nothing shows what you have played

`Game.svelte:36` takes `backlog[(index + 1) % length]`, which from the last board wraps to
today's — a board you have probably just played. `log.ts` already records every run locally,
so completion state is available for free.

**This needs a pin ruling.** Marking finished boards in the picker is a status display, not a
counter, and it appears between runs rather than during one — so I read it as outside pin 11,
which is explicitly about "anything that counts upward while you think". But it is the first
step onto a streak/progress ladder, which is exactly the kind of thing pin 11 was written to
refuse. Your call, and worth making it explicitly rather than by accretion.

### 5.4 Should reduced motion remove pacing, or only motion?

`wait()` currently returns 0 under `prefers-reduced-motion`, so a five-row clear resolves in
one frame and all five categories appear simultaneously. The preference asks for less
_motion_; sequence is information here — "one row's whole life, then the next" is how the
player reads which row cleared when.

I would keep `ROW_STEP` (or shorten it) while zeroing the transforms, so a reduced-motion
player still sees rows land one at a time. That is a change to what the accommodation means,
so it should be a decision rather than a patch.

### 5.5 Should the survey appear after a loss at all — and in that order?

Separate from §1.3's timing. A player who just lost is being asked "was it fair?" — which is
the answer you most want from them, per `EndCard.svelte:44-47` — but they are being asked
before they have read the categories they missed, which is the only evidence they have for
answering. Ordering the loss card as _reveal → read → then ask_ would get better data, not
just a better feeling. Whether that is worth the extra tap is a judgement about response
rates that I cannot make from the code.

---

## If you only do five things

1. **§1.1** — focus rings. Four rules, four files. It is the only item here that makes the
   game unplayable for someone.
2. **§1.2 + §1.3** — the loss ending. The crash does not render and the card covers the
   reveal, so the ending the design cares most about (pin 5) currently has no feedback and a
   hidden answer.
3. **§1.4** — repaint `--danger` and `.outcome`. Restores a Feel rule the end card broke, in
   about six lines.
4. **§1.6 + §1.7** — busy states and the refund flicker. This is where a real tester on a
   cold Cloud Run instance will first think the app is broken.
5. **§1.5 + §1.8** — `--dim` on the card, and "1 rows right". Both are two-line fixes to text
   the whole phase depends on being read.

Everything in §2 is one focused afternoon of tokenising, and would remove most of what "feels
a bit messy" without changing a single design decision.
