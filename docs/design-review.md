# Design review — UI and UX

**Revision 2**, re-done at `87b6a88` on `main` with the app actually rendering in Chrome at four
phone viewports. Revision 1 was written at `dee588e` without a screen; where the two disagree,
this one wins and says so. `pnpm check`, `pnpm lint` and `pnpm test` are green; nothing here is a
build failure.

## How this was done, and what it is worth

**This time I could see the screen.** The app ran on `localhost` and was driven through Chrome —
real clicks, real keyboard focus, real network. Chrome clamps its own window to ~544px wide, so
phone widths were reached by hosting the app in a same-origin iframe sized exactly 360×640,
375×667, 390×844 and 414×896; `dvh`, `cqw` and container queries all resolve against an iframe
viewport, so layout is faithful. Every claim is now one of:

- **Confirmed** — predicted in revision 1 and observed rendering. Most items.
- **Corrected** — revision 1 had it wrong, or right for the wrong reason, or right only at
  some viewports.
- **New** — only visible with pixels. Four of these, and one of them retracts something
  revision 1 called untouchable.

Where a number appears it was measured, not estimated. Three techniques did most of the work and
are worth reusing:

- **A per-frame `requestAnimationFrame` sampler** over the DOM, to catch animation classes that
  exist for less than one paint. This is what settled §1.2 (1205 frames, zero hits).
- **Reconstructing exact game states.** The answer key is server-side, so it was learned from one
  loss reveal, then boards were arranged tile by tile through the real tap-to-swap path to produce
  a specific `correctCount`. This is how §1.8 was rendered rather than reasoned.
- **Driving the server, not just the browser.** `SIGSTOP` on the dev server reproduces a Cloud Run
  cold start; `SIGTERM` mid-request reproduces a transport failure. §1.6 and §1.7 were measured
  this way.

---

## What is already good, and should not be touched

Revision 1's list survives intact **except its last item, which I now have to withdraw** — see
§1.10. Still good, still verified, now with pixels behind it:

- **The board never resizing.** Five slots for the whole game, solved rows keeping full row
  height, cleared rows converting in place. Confirmed rendering: `.row` bands measure 87px against
  an 87px tile row at 375×667, so solved and unsolved land on one rhythm, and the loss path holds
  it too. Do not let anything in this document be read as a reason to reopen it.
- **One verb, two input paths.** Drag and tap-to-swap share `Session.swap`. Confirmed the hard
  way: synthetic clicks drove ~40 consecutive swaps to build exact board states without a single
  missed or doubled swap. The `draggedAt` timestamp rather than a flag is why. This is the
  fiddliest code in the repo and the part I would change least.
- **The check budget on the button that spends it**, counting down, neutral, never red.
- **The verdict's restraint.** A check that clears cleanly and leaves nothing else right says
  nothing at all. Confirmed: a three-row clear rendered no verdict.
- **The anticipation sweep doubling as the latency budget.** Still the best idea on the branch. My
  complaints in §1.6 are about what happens when the round trip _doesn't_ fit inside it.
- **The type-shrink rule on tiles.** `font-size: min(--fs-md, (100cqw - 12px) / (len * 0.62))`.
  Confirmed at 360px: SAXOPHONE and WEDNESDAY shrink, everything else holds one size. Correct, and
  cheaper than a JS fitter.
- **Colour never leaking into the board's own chrome.** Selection, drag target, drop shadow, jolt
  and tier are all neutral. Holds everywhere except the end card (§1.4).

---

## 1. Incoherent, and cheap to fix

Ordered by value. These are defects against the design's own stated intent, not taste.

### 1.1 There is no visible focus ring on any primary control — Confirmed

Revision 1 derived this from specificity arithmetic. Now measured directly in the browser: a
focused tile **matches `:focus-visible` and still computes the decorative outline**.

```
tile.focus()  → matches(':focus-visible') = true
              → computed outline: rgb(44,54,70) solid 1px, offset -1px   ← --tile-edge
check.focus() → matches(':focus-visible') = true
              → computed outline: rgb(44,54,70) solid 1px, offset -1px   ← --tile-edge
help.focus()  → computed outline: rgb(238,243,250) solid 2px, offset 2px ← --accent ✓
```

`.help` is the only control in the app that gets a ring, and only because it happens not to set a
decorative outline. Tabbing onto BASSOON and screenshotting produces a tile visually identical to
its neighbours.

**Why it matters.** DESIGN.md keeps tap-to-swap specifically because "it is what keeps the board
reachable from a keyboard". The keyboard path works — the tiles are real buttons, `Enter` fires
`onpick`, tile ids key the `each` so focus follows a tile through a swap. It is invisible, which
is the same as not existing. Highest value item in the document and the cheapest.

**Do this.** Give each of the four controls (tiles, Check, the five card buttons, the textarea)
its own `:focus-visible` rule, and move the decorative outline to an inset `box-shadow` so the two
never compete again. Then add a lint guard: the global reset at `app.css:93` strips every button
to bare text, so every new control has to redraw itself, and redrawing itself is what kills the
ring.

### 1.2 The crash never plays on the last check of a lost run — Confirmed, conclusively

Revision 1 derived this. A per-frame sampler across a full losing run settles it:

```
frames sampled: 1205
frames carrying .crashing or .impact: 0
t=3577ms  tiles=20  rows=0  card=false
t=3625ms  tiles=0   rows=5  card=true     ← one frame later
```

The tiles that were given `class:crashing` and `class:impact` are removed before a single frame is
painted with them. Not "probably too fast to see" — never painted at all.

**Why it matters.** DESIGN.md is emphatic that this is not decoration: _"the crash **is** the
feedback, pointing at where the run broke, and it's information the top-down rule otherwise has to
state in words."_ On the final check the run ends with no crash, no verdict, and the board simply
emptying under a rising card. The one moment the game most owes the player an explanation is the
one moment it gives none. Pin 5 territory — losing should feel like the puzzle beat you, not like
the interface closed.

**Do this.** `impact()` already knows its own duration; make it return a promise and `await` it
before `finish('lost', …)` on the losing branch only. The win branch is fine — nothing left to
crash into.

### 1.3 The end card covers the loss reveal — Corrected: true, and viewport-dependent

Revision 1 estimated the card top at y≈333 on a 375×667 viewport. Measured, it is **y=282** — so
the coverage is worse than estimated. But the finding does not generalise the way revision 1
implied. Losing runs at four viewports, measuring the `.card` box against each `.row`:

| Viewport | Card top | Rows fully hidden | Row coverage (1→5)     |
| -------- | -------- | ----------------- | ---------------------- |
| 360×640  | 237      | **3**             | 0 · 7 · 100 · 100 ·100 |
| 375×667  | 282      | **2**             | 0 · 0 · 72 · 100 · 100 |
| 390×844  | 477      | 0                 | 0 · 0 · 0 · 0 · 81     |
| 414×896  | 565      | 0                 | 0 · 0 · 0 · 0 · 0      |

Note also that the card mounts in the **same frame** the board converts (§1.2's trace), so there
is no window in which the reveal is unobstructed on the short viewports — the stagger runs
entirely underneath the card.

So: on a 360×640 Android, three of the five categories the player just lost to are completely
hidden at the moment they appear. On a 414×896 iPhone, none are. This is a short-phone bug, not a
universal one — which changes the fix, because the questions-first default is defensible on the
tall half of the fleet.

**Why it matters.** The card's own comment already identified this tension and chose
questions-first because "an unseen question is an unanswered one". That trade is right on a
**win**, where everything under the card was revealed row by row and watched. It is wrong on a
**loss**, which is the only ending that shows the player something new.

**Do this — one of:**

- `let asking = $state(won)`. Questions up on a win, board first on a loss, one tap either way.
  Two characters, uses a distinction the card already computes, and fixes every viewport at once.
- Or hold the card behind the loss stagger the way `Game.svelte:123` already holds it behind a
  combo.

I would do both. Given the table, I would not bother making this viewport-conditional.

### 1.4 Colour has stopped meaning only category — Confirmed

Read off the live computed styles:

1. **`--danger` and `--g5` are byte-identical.** Both `#e8596c`. Rendered on a lost board, the
   "Out of checks" heading and a fifth row's category chip are the same paint. Also confirmed:
   `.fault` renders in that same red (screenshot below), so a transport failure looks like the
   board bit back.
2. **`.outcome` on a win computes `rgb(76,190,128)` — exactly `--g4` (`#4cbe80`).** "Solved" is
   painted in category four, a literal category token used as card chrome, twenty lines above
   `.choice`'s comment: "Unhued. Colour on this board means category, and an answer about the
   board is not one." The card contradicts itself within one stylesheet, and on screen the green
   word sits directly above green-family category rows.
3. `ComboFlash`'s five-colour sweep is the one sanctioned exception and it is well argued. Leave
   it.

**Do this.** Give `--danger` its own value visibly distinct from `--g5`, and repaint `.outcome`
neutrally — `--text` for won, `--muted` for lost, with the _word_ carrying the outcome. A won card
can feel like a win through weight and the score line, not a hue the board has already spent.

### 1.5 The survey's own questions are the least legible text on screen — Confirmed

Recomputed independently, compositing the card's gradient and every translucent layer above it
rather than assuming a flat ground:

| Element                        | Colour     | Composited ground  | Ratio    | AA (4.5) |
| ------------------------------ | ---------- | ------------------ | -------- | -------- |
| `legend` — "HOW WAS THAT?" etc | `--dim`    | `rgb(20,27,36)`    | **2.26** | fail     |
| `.outcome`                     | `--danger` | `rgb(22,28,38)`    | 4.95     | pass     |
| `.score`                       | `--muted`  | `rgb(21,28,38)`    | 5.03     | pass     |
| `.choice`                      | `--text`   | `rgb(34,40,49)`    | 12.85    | pass     |
| `.next`                        | `--ink`    | `rgb(238,243,250)` | 16.71    | pass     |

Revision 1 said 2.21 for the legend; 2.26 with proper compositing. Same conclusion: the two
question labels fail AA by a factor of two, at 11.2px, in caps. The buttons under them are at
12.85, so the player reads "Too easy / Just right / Too hard" with no legible question above it.
Visible in the win-card screenshot — the legends are plainly the faintest thing on screen.

`--dim` is fine as a hairline colour on the near-black body; it stops working the moment it is put
on a raised surface, and the card is the only raised surface in the app.

**Do this.** `--muted` for `legend` (5.03 on the card, passes), something between `--dim` and
`--muted` for the placeholder. Or define `--muted-on-raised` and stop guessing.

### 1.6 The Check button and the tiles stay live-looking while nothing can happen — Confirmed, measured

Two windows, both now measured rather than argued.

**The roll.** A 3-row clear, sampled every frame:

```
182 frames across the full check + roll
frames where check.disabled === true : 0
cursor on .check, every frame        : pointer
cursor on remaining .tile, every frame: pointer
t=0     tiles=20 rows=0
t=1501  tiles=8  rows=3   ← ~1.5s of live-looking, inert controls
```

**A slow grade.** `SIGSTOP` on the dev server, then press Check. `sweeping` is cleared by a fixed
`setTimeout(SWEEP_MS)`, not by the grading promise, so the rails run up, the button's `firing`
class comes and goes, and then the screen sits **completely inert with a fully bright Check
button** — no spinner, no pending state, nothing — while a check has already been visibly spent.
Screenshot below; this is the single most misleading frame in the app, and cold starts are exactly
where the latency actually is.

**Do this.** Add a `busy` gate to both `disabled` bindings, and hold `sweeping` until the grade
resolves rather than on a fixed timer — the rails can loop or hold at the top. A pending state
does not count anything, so pin 11 is untouched; this is the button reporting its own state.

### 1.7 The network-failure path contradicts itself in three small ways — Confirmed, and the window is unbounded

`this.checks++` happens before the await; `this.checks--` on failure. Measured across one real
failure (server suspended, then killed mid-request):

```
t=13782ms  pip → spent + spending (the 560ms flash runs)
t=42765ms  pip → un-spent, fault appears
           ── 28,983 ms of a visibly spent check ──
```

Revision 1 said "the player watches a check get spent and then un-spend itself". Correct, and the
window is bounded only by the browser's timeout, not by anything in the app. The refund is the
right call — the comment argues it correctly from pin 5 — but showing the charge first undoes the
argument, and showing it for half a minute inverts it.

Two more, same area, both confirmed on screen:

- `.fault` renders in `var(--danger)` inside `.callout`, which is `align-items: end` — so a
  network error appears in exactly the slot, at exactly the size, and in exactly the colour a
  missed check uses. The design says a check "says one thing, and only when it has something to
  say"; a transport failure is not a thing the check said.
- The copy is _"Could not reach the scorer. Try again."_ "Scorer" appears nowhere else in the UI —
  the button says Check, the rules say check, DESIGN.md says grader. And it does not say the check
  was refunded, which is the one fact that would stop the player panicking.

**Do this.** Spend the pip when the grade lands, not when the request leaves. Move the fault next
to the Check button — it is a "your press did not land" message, which is a button state — and
rewrite it as _"Couldn't check — no connection. That one's free, try again."_ Keep it out of
`--danger` so red still only means the board bit back.

### 1.8 "1 rows right" — Confirmed, rendered

Reconstructed the state rather than reasoning about it: learned the answer key from a loss reveal,
then arranged one correct row at position 3 (so nothing locks) through the real swap path. The
verdict rendered:

> **1** ROWS RIGHT · NONE AT THE TOP

Reachable, common, and it is the single sentence the game writes in words, set at `--fs-lg` and
described in DESIGN.md as "the only thing written in words".

While in there: the three note strings are three different sentence shapes for one fact — `N more
right · wrong order`, `N rows right · none at the top`, `N rows right`. Worth a pass for one
voice.

### 1.9 The only door to the rules and the picker is a 15px text link — Confirmed

Measured tap targets on a live board, smallest first:

| Control                     | Measured   | vs 44px guideline |
| --------------------------- | ---------- | ----------------- |
| `.help` ("How to play")     | **62×15**  | 34%               |
| `.picker button`            | **~95×25** | 57%               |
| `.toggle` ("See the board") | **105×25** | 57%               |
| `.choice` (survey pills)    | 95×40      | 91%               |
| `.next`                     | 296×46     | pass              |
| `.check`                    | 336×48     | pass              |
| `.tile`                     | 76×77      | pass              |

`.help` is 15px tall and is the sole route to the rules _and_ to every other board (§5.1). Phone is
the target "by roughly a factor of ten". Contrast is fine (5.78 on the body ground); the problem is
purely the target.

**Do this.** `padding: 8px 4px; margin: -8px -4px;` grows it to ~31px with no visual change and no
layout shift. Better, `min-height: 44px` with a negative block margin. Same fix for `.picker
button` and `.toggle`.

### 1.10 NEW — The score line breaks to four lines on the loss card, and Pin 8 is not intact

**This retracts an item revision 1 listed as untouchable.** It said: _"Pin 8 is intact on the end
card. `mm:ss · N left`, one line, no grid, no move count."_ The code says one line. The screen
does not.

`.head` is a flex row holding `.outcome`, `.score` and `.toggle`. Computed flex:

```
.outcome  flex: 0 1 auto   min-width: auto   ← will not shrink below its text
.toggle   flex: 0 0 auto   min-width: auto   ← fixed
.score    flex: 1 1 0%     min-width: 0px    ← absorbs 100% of the squeeze
```

So `.score` is the only item that can give, and on a loss `.outcome` is the long string "Out of
checks" rather than "Solved". Measured on the loss card:

| Viewport | `.score` width | Line boxes  |
| -------- | -------------- | ----------- |
| 360×640  | **12px**       | **4 lines** |
| 375×667  | **27px**       | **3 lines** |
| 390×844  | 57px           | **2 lines** |
| 414×896  | 81px           | 1 line      |

Swapping the text to "Solved" in place at 375×667 restores it to 101px on one line, which isolates
the cause exactly. So `mm:ss · N left` is one line **on a win at any phone width, and on a loss
only at 414px and above** — i.e. it is broken on a loss for most of the fleet, stacked into a
narrow column beside a red heading. The 375×667 loss screenshot below shows `0:06` / `· 0` / `left`
on three lines.

Pin 8 is about what the end card is allowed to _say_, and the card still says only the two facts —
so this is a layout bug, not a pin breach. But the reason revision 1 praised it (one calm line, no
grid) is not what renders.

**Do this.** `.score { flex: 0 0 auto; white-space: nowrap }` and let `.outcome` be the item that
shrinks or wraps — it is the one with a natural break. Or drop `.toggle` to a second line on a
loss. One line either way.

---

## 2. The visual system has drifted

None of this is broken. All of it is why the app "feels a bit messy", and it is the kind of mess
that compounds.

### 2.1 There is a raised-surface gradient concept, used six times, tokenised once — Confirmed

`var(--tile)` / `var(--tile-hi)` appear in exactly two rules, both the tile gradient
(`Tile.svelte:88` and `:160`). Every other raised surface hardcodes its own pair:

| Surface               | Value                         | File                 |
| --------------------- | ----------------------------- | -------------------- |
| tile (base, ghost)    | `var(--tile-hi), var(--tile)` | `Tile.svelte:88,160` |
| tile (selected)       | `#2a3442, #202836`            | `Tile.svelte:116`    |
| tile (drop target)    | `#33405180, #26303f`          | `Tile.svelte:132`    |
| Check button          | `#232c39, #19212c`            | `Game.svelte:307`    |
| Check button (firing) | `#39465a, #2a3547`            | `Game.svelte:328`    |
| Check button (repeat) | `#232c39, #19212c`            | `Game.svelte:332`    |
| end card              | `#161d27, #10151d`            | `EndCard.svelte:264` |

Change the tile colour and five of these go stale silently. Two details revision 1 missed:
`Game.svelte:332` repeats `:307`'s literal pair verbatim, so that one value is written twice; and
`#33405180` carries an alpha in a hex-8 in the middle of a set that does not, which reads as an
accident.

**Do this.** Two tokens — `--surface` / `--surface-hi` — plus a `--surface-raise` step expressed
with `color-mix`, and derive all of them.

### 2.2 `--accent` is spelled out as a literal in four files — Confirmed

`rgb(238 243 250 / …)` — the exact channels of `--accent: #eef3fa` — appears **8 times** across
`Tile.svelte`, `Game.svelte`, `Budget.svelte` and `ComboFlash.svelte`, at six alphas. It is a
literal only because `box-shadow` and `text-shadow` need a colour with alpha, which is a solved
problem:

```css
box-shadow: 0 0 0 4px color-mix(in oklab, var(--accent) 10%, transparent);
```

`color-mix(in oklab, …)` already appears **14 times** in the repo, so this is house style, not a
new dependency. Same for `#0d131c` — "text on accent" — hardcoded twice and equal to neither
`--ink` nor `--bg`.

### 2.3 Nine radii, one token — Confirmed

`--radius: 13px` is used twice. Everything else picks a number. Actual distinct values in
`src/lib`: 2, 3, 10, 12, 14, 17, 18, 20, 999. Concentric radii are what the eye notices when they
are wrong: `.tile` at 13 sits inside `.frame` at 17 inside `.well` at 18, and 17-inside-18 with
10px of padding between them is not a concentric pair.

**Do this.** `--r-sm: 10px; --r-md: 13px; --r-lg: 18px; --r-xl: 20px; --r-pill: 999px`, and make
`.frame` derive from the tile radius plus its bleed rather than hardcoding 17.

### 2.4 The white-veil scale has seven undocumented steps — Confirmed

`rgb(255 255 255 / X%)` with X ∈ {3, 5, 6, 10, 18, 20, 42}; 5% is used four times and 6% twice.
Three of these (5, 6, 10) are visually indistinguishable and are doing _different_ semantic jobs —
a picker pill, a survey button, a toggle. Collapse to three steps and name them.

### 2.5 The row tier fades to invisible — the failure the design note says it avoids — Confirmed

Live computed values off the five `.frame` elements, edge alphas 26/21/16/11/6% exactly as
`26 - rank * 5` predicts, with `--fill` at a quarter of each:

| Row | edge alpha | fill vs well |
| --- | ---------- | ------------ |
| 1   | 26%        | 1.17         |
| 2   | 21%        | 1.13         |
| 3   | 16%        | 1.09         |
| 4   | 11%        | 1.06         |
| 5   | 6%         | **1.03**     |

DESIGN.md picked "a linear ramp with a floor rather than a decay, because a bottom row faded to
nothing stops reading as a container at all — which would win the argument about order at the cost
of the one about rows." The reasoning is right; the floor is set too low to deliver it. Rendering
confirms it: on screen row 1's frame reads clearly, row 4's is marginal and row 5's is essentially
absent on anything but a good screen in a dark room.

**This does not touch a pin** — the shape (linear, floored, neutral) is unchanged. I would try
`38 - rank * 6` and check it on a phone in daylight. The 18px row-gap versus the 7px column gap is
doing most of the row-as-unit work regardless, so this is reinforcement, not rescue.

### 2.6 Motion timing ignores reduced motion in three places — Confirmed, measured

`wait()` collapses to 0 under `prefers-reduced-motion`; three bare `setTimeout`s in the same file
do not (`sweeping` 260ms, `crash` 460–700ms, `comboTimer` 1100ms). Exercised by overriding
`matchMedia` in the frame — `reducedMotion()` reads the global at call time — then winning with a
full clear:

```
board fully resolved at   t = 94ms     ← all five rows at once, wait() zeroed
end card appeared at      t = 1190ms
                          ── 1096ms of a finished, motionless board ──
```

Revision 1 predicted "1.1 seconds". Measured 1096ms, which is `COMBO_HOLD` to within a frame. So a
reduced-motion player who wins gets the whole clear in one frame, a `TRIPLE` that never animates
in, and then a second of nothing. There is a real question underneath this (§5.4), but the
inconsistency is a bug either way: one clock respects the preference and three do not.

**Do this.** Route all four through one helper. Whether that helper zeroes them or merely shortens
them is §5.4.

### 2.7 Two tokens in `app.css` are dead — Confirmed

Read off the live `.grid`: `--boost: 1` and `--jolt: #eef3fa` are always set inline by
`Board.svelte:161-162`, so the `:root` declarations never apply — they are documentation wearing a
declaration. `--fs-md`, `--well-edge` and `--bg-glow` each have one consumer, which is fine.

**Do this.** Move `--boost` / `--jolt` to a commented "set at runtime by Board" block, or drop the
`:root` declarations and document them where they are set.

### 2.8 Three disclosure idioms for three panels — Confirmed, and the rules panel is worse than described

Revision 1 said opening the rules "pushes the Check button below the fold". Measured at 375×667:

```
rules closed:  document 685px in a 667px viewport
rules open:    document 986px in a 667px viewport
               .check top moves to y=926 — 307px below the fold
```

So opening the rules pushes the primary action nearly a full screen down. The end card is a fixed
sheet with a scrim; the callout is a transient hybrid in reserved slack; the rules are an inline
`<section>` in normal flow. Three patterns is defensible — they do different jobs — but the rules
panel is the odd one, because it is the only one that moves the board. Making it a sheet like the
end card would unify the two things that are actually the same shape and would fix the scroll.

> **Decided: make it a sheet. Shipped.** The owner's answer was "yes make it a sheet".
>
> Rather than write a second sheet beside the end card's — which is the drift this section is
> about — the shape moved into `Sheet.svelte`: fixed position, graded scrim, `role="dialog"`,
> focus on open, dismiss on scrim press or Escape. Both panels use it, so there is one sheet in
> the app and not two. `EndCard` keeps what goes _on_ the card; `Game` keeps what goes on the
> rules panel.
>
> Measured at 375×667 with the rules open: the document stays **667px** and the Check button
> moves **0px**, against 986px and 307px before. The picker came along with the move and gained
> a "Boards" heading, `role="group"` and `aria-current` (§5.1). The callout stays as it is — it
> genuinely does a different job.

### 2.9 NEW — The app overflows a short phone, and the Check button is cut off

Fresh board, rules closed, nothing open:

| Viewport | Document height | Overflow  | Check button        |
| -------- | --------------- | --------- | ------------------- |
| 360×640  | 669             | **+29px** | **cut off by 17px** |
| 375×667  | 685             | **+18px** | **cut off by 6px**  |
| 390×844  | 844             | 0         | fully visible       |
| 414×896  | 896             | 0         | fully visible       |

`.app` is `min-height: 100dvh` but its content is taller than that on short viewports, so the page
scrolls in its resting state and the primary action is clipped. This is before any browser URL bar
is accounted for — on real iOS Safari the usable height is smaller still, so it is worse than the
table.

This compounds §1.9: the app's most important control is partly off-screen on the same phones
where its only navigation control is 15px tall. Given "phone by roughly a factor of ten", the
resting layout not fitting an iPhone SE or a 640-tall Android is the kind of thing that reads as
"feels a bit messy" without ever being articulated.

**Do this.** Find the ~30px. The candidates, in the order I would try them: the reserved 44px
callout slack (it only needs to reserve one line of `--fs-lg`), the gap between the well and the
budget, and the header's vertical padding. Worth also checking whether `.well` should be `flex: 1
1 auto` with the grid absorbing the slack, since the board is fixed-height by design and the
leftover space is currently all dead air below it — at 390×844 there is a visible ~280px void
between the board and the budget, which is the same bug in the opposite direction.

---

## 3. Accessibility

The keyboard _path_ is there and works, the reduced-motion hook is there, and the contrast is
mostly fine. What is missing is that none of it is finished. All items below re-confirmed against
the live DOM.

### 3.1 §1.1 — no visible focus ring. The single most important item in this section.

### 3.2 The ordering mechanic is invisible to a screen reader — Confirmed

Live DOM, first tile:

```
tag=BUTTON  role=null  aria-label=null  aria-pressed="false"  data-row="0"  text="BASSOON"
elements with role="group" on the page: 0
elements with role="row" / "grid" / "listitem": 0
```

The board is a flat sequence of 20 buttons whose only accessible name is their word. `data-row` is
not exposed to assistive tech. A screen-reader user can select and swap — the mechanics work — but
cannot tell which row anything is in, so the entire game ("the order of your rows is part of the
answer") is unavailable.

**This brushes a dropped feature, so, explicitly:** DESIGN.md dropped the rank column because "the
numbers were redundant — the top row is visibly the top row". That reasoning is about a _visible_
column of numbers and it holds. An accessible name is not visible and does not resurrect it.
Nothing goes back on screen.

**Do this.** Wrap each active row's tiles in `role="group"` with `aria-label="Row 1 of 5"`, or put
the row into the tile's accessible name. Then announce the swap in the existing live region.

### 3.3 The end card is a modal that is not a dialog — Confirmed

Measured on a real win:

```
.sheet  role=null   aria-modal=null
document.activeElement after the run ends: BODY
```

No `role="dialog"`, no `aria-modal`, no focus move on open, no `Escape` handler, no containment.
The Check button becomes `disabled` while focused, which drops focus to `<body>` — exactly as
predicted — so a keyboard user's next Tab starts from the top of the document. Nothing announces
that the run ended: the `aria-live="polite"` callout is empty on both a win and a loss. (There is a
second `aria-live="assertive"` region in the DOM, but it is SvelteKit's route announcer, not the
game's.)

**Do this.** `role="dialog" aria-modal="true" aria-labelledby` pointing at the outcome span; move
focus to the card on mount; `Escape` collapses the questions, matching the scrim, which already
does exactly that. The scrim is already a real `<button>` with a real label, which is the hard part
and is done right.

### 3.4 `Budget`'s label is on a role-less div — Confirmed

Live: `tag=DIV, role=null, aria-label="4 of 4 checks left", tabIndex=-1`. `aria-label` on a generic
element with no role is not reliably exposed, and the div is not in the tab order, so nothing will
ever read it. Give it `role="status"` — which also means the count is read when it changes, which
is what a player would want.

### 3.5 The survey buttons are toggles pretending to be a radio group — Confirmed

Live: two `<fieldset>`s with `<legend>`s, five plain `<button aria-pressed="false">`, `role=null`
on every one, **zero** `role="radiogroup"`, **zero** real radios. `fieldset`/`legend` only names
_form controls_, and these are not, so the legend has no programmatic relationship to the buttons:
a screen reader announces "Too easy, toggle button, not pressed" with no question attached. And
`aria-pressed` is the wrong role shape — these are mutually exclusive.

**Do this.** Real `<input type="radio">` styled as the pills. That makes the `fieldset`/`legend`
correct as written and gets arrow keys for free. It is less code than the `role="radiogroup"`
route.

### 3.6 Two toggles, two different contracts — Confirmed

`EndCard`'s `.head` gets `aria-expanded` — correct. `Game`'s help button: `aria-expanded=null`,
`aria-controls=null`, and it changes its own _label_ from "How to play" to "Close" (which also
reads as "close the page"). Two disclosure buttons in one app should behave the same way. Give the
help button `aria-expanded` + `aria-controls` and keep the label stable.

### 3.7 Contrast — one real failure

`legend` at 2.26 (§1.5) is the only text failure; everything else on the card composites to 4.95
or better, and `--muted` on the body ground is 5.78. The category palette is well chosen for this
ground and I would not touch it.

Non-text: the row frames (§2.5, bottom row at 1.03 fill contrast) and the 1px tile edge are both
below the 3:1 UI-component guideline. The tile edge does not matter — the tile's own fill is 13:1
against the well, so the shape is unmissable without its edge. The frames do.

---

## 4. Taste calls

Reasonable people differ; I would not spend a day on any of these.

- **`--fs-sm` (12.8px) is carrying all body copy** — the rules list, survey buttons, score line,
  Check button, solved-row word lists. `--fs-md` (15.2px) has exactly one consumer, the tile. Four
  sizes declared, two doing all the work, and the one doing most of it is small for a phone. Seeing
  it rendered, I am more convinced than revision 1 was: promote the rules list and the solved-row
  words to `--fs-md`.
- **The survey gives almost no acknowledgement.** Tapping "Just right" moves the button fill from
  6% white to 18% and the outline from `--tile-edge` to 42% white — rendered, this is a very quiet
  change for the one interaction the phase exists to collect. It posts immediately and fails
  silently by design. The silent failure is right; the silent _success_ is what I would strengthen.
- **Selected, primary and current are all `--accent`.** Correct under the colour rule (all
  neutral) and fine in practice since they never co-occur — but it is why the picker's current
  pill reads as a button you should press. Worth noting the picker sets no `aria-current` either,
  so the current board is unmarked both visually and programmatically.
- **`.head`'s label pair is "See the board" / "Questions"** — a verb phrase and a noun for one
  control. Pick a grammar.
- **Board names are inconsistently cased** — "Second Look", "FITTING NAMES", "Natural Order" in
  the picker. Pick one.

---

## 5. Decided by the owner, 2026-09-07

All five were put to the owner as a table with the UI questions illustrated, and all five came
back. Each section below keeps the argument and records the ruling; §2.8 and §5.4 shipped with
the decision, §5.1 and §5.3 are deferred together by design, and §5.5 was already satisfied.

### 5.1 Where does the puzzle picker live?

> **Decided: option 3 — a `/boards` page of its own, "down the line".** Not the end card, which
> is where I would have put it. The owner wants a page that shows every puzzle and which ones
> you have completed, which is a bigger surface than the end card can carry — and it takes
> §5.3 with it.
>
> **Shipped in the meantime:** the picker is still in the rules, but the rules are now a sheet
> (§2.8) with a real "Boards" heading, `role="group"`, and `aria-current` on the board you are
> on. That is option 1 as a holding position, not as the answer. The `/boards` page is the
> answer and is not built.

Today it is an unlabelled row of 25px pills at the bottom of the rules panel, reachable only
through a 15px "How to play" link, and choosing a board closes the rules. Confirmed rendering: the
picker has no heading, no `aria-label`, and no `aria-current`. Three things are wrong at once — the
door is tiny, the room is the wrong one, and the control has no heading.

**The constraint that makes this a decision:** the Feel section says the header carries "the
wordmark and a way to the rules. Nothing else earns a place up here." Putting the picker in the
header is the obvious move and the design has pre-emptively refused it. So:

1. **Split the panel** into headed "How to play" and "Boards" sections, and rename the trigger.
   Cheapest; still hides navigation inside help.
2. **Put it on the end card, beside "Next puzzle."** Choosing a board is a between-runs action and
   the end card is the between-runs screen. This is where I would put it. It also turns "Next
   puzzle" from a guess into a choice (§5.3).
3. **A `/boards` route**, linked from the end card. Most room, most navigation.

Whichever wins, the trigger needs a real target (§1.9).

### 5.2 Two URLs render the same board

`/` serves `live[0]`; the picker links every board including `live[0]` to `/p/<id>`. Today's board
has two addresses, and the picker's "current" pill navigates you off the canonical one. Harmless
now, a share-link problem later. Either redirect `/p/<live[0]>` to `/`, or make `/` a redirect and
have one address per board.

### 5.3 "Next puzzle" is a guess, and nothing shows what you have played

> **Decided: it belongs with §5.1.** The owner's read is that this is the same piece of work —
> a boards page is where "which ones you completed" is worth showing, and marking completion
> inside an in-game picker is solving it in the wrong room.
>
> That also settles the pin-11 question by scoping it: completion is a property of a
> between-runs _page_, not a badge on a control you meet mid-game. The ruling on how far it
> goes — played, or solved, or streaks — comes with that page, and my recommendation stands at
> "played, and stop there".

`Game.svelte:36` takes `backlog[(index + 1) % length]`, which from the last board wraps to today's
— a board you have probably just played. `log.ts` already records every run locally, so completion
state is available for free.

**This needs a pin ruling.** Marking finished boards in the picker is a status display, not a
counter, and it appears between runs rather than during one — so I read it as outside pin 11,
which is explicitly about "anything that counts upward while you think". But it is the first step
onto a streak/progress ladder, which is exactly what pin 11 was written to refuse. Your call, and
worth making explicitly rather than by accretion.

### 5.4 Should reduced motion remove pacing, or only motion?

Now measured (§2.6): a five-row clear resolves in 94ms and all five categories appear at once. The
preference asks for less _motion_; sequence is information here — "one row's whole life, then the
next" is how the player reads which row cleared when.

I would keep `ROW_STEP` (or shorten it) while zeroing the transforms, so a reduced-motion player
still sees rows land one at a time. That is a change to what the accommodation means, so it should
be a decision rather than a patch. Note that fixing §2.6's inconsistency does not require settling
this — routing all four clocks through one helper is right either way.

> **Decided: my judgement, and shipped.** The owner's answer was "I don't really know about
> accessibility best practice, use your judgement", so: reduced motion removes motion, not
> sequence.
>
> The clocks now split in two. A **hold** is time reserved for a flourish to play, and since
> `app.css` already collapses every CSS animation under the preference, a hold has nothing left
> to show and goes to zero — the sweep, the crash, the combo callout. A **gap** is what makes
> two events read as two events, and it is shortened to 60% with a 90ms floor rather than
> removed. Only `roll()`'s two waits are gaps.
>
> Measured under the preference, a five-row clear: rows land at **163, 427, 683, 942 and
> 1202ms** — five distinct events — and the end card follows at 1202ms with no dead air. For
> comparison, before any of this work the same clear resolved in 94ms and then held a finished,
> motionless board for 1096ms before the card appeared. It is the same second of the player's
> time; it now buys five legible row events instead of a freeze.

### 5.5 Should the survey appear after a loss at all — and in that order?

Separate from §1.3's timing. A player who just lost is being asked "was it fair?" — the answer you
most want from them — before they have read the categories they missed, which is the only evidence
they have for answering. On a 360×640 phone they are being asked it _on top of_ three of those five
categories. Ordering the loss card as _reveal → read → then ask_ would get better data, not just a
better feeling. Whether that is worth the extra tap is a judgement about response rates I cannot
make from the code.

> **Decided: reveal → read → then ask, which is what already ships.** The owner asked for the
> loss card to "show the reveal and get to read first then can open the survey" — and §1.3's fix
> put it exactly there: a loss now lands on the collapsed card, all five categories readable,
> the survey one tap behind "Questions". Nothing further to build.
>
> The win path deliberately stays questions-first: everything under that card was revealed row
> by row and watched as it cleared, so the player has already read it, and an unseen question is
> an unanswered one. If response rates on the loss path turn out to suffer, that asymmetry is
> the first thing to revisit.

---

## If you only do five things

Re-ranked with rendering in hand. §1.10 and §2.9 are new; §1.3 moved down slightly because it is
short-phone-only, and §1.6 moved up because the suspended-server screenshot is genuinely alarming.

1. **§1.1 — focus rings.** Four rules, four files. The only item here that makes the game
   unplayable for someone, and now proven to fail at runtime rather than inferred from
   specificity.
2. **§1.2 + §1.3 — the loss ending.** The crash provably never paints (0 of 1205 frames), and on a
   short phone the card hides three of five categories in the same frame they appear. The ending
   the design cares most about (pin 5) has no feedback and a hidden answer.
3. **§1.6 + §1.7 — busy states and the refund flicker.** Where a real tester on a cold Cloud Run
   instance will first think the app is broken: an inert screen with a bright Check button, and a
   check that reads as spent for as long as the network takes to give up.
4. **§2.9 + §1.9 + §1.10 — the short-phone pass.** The Check button is clipped at 375×667 and
   360×640, the only navigation control is 15px tall, and the loss card's score line stacks into
   four lines. Three separate bugs with one cause: nobody has run this at 360–375px.
5. **§1.4 + §1.5 + §1.8 — the card's own text.** Repaint `--danger` and `.outcome`, lift `legend`
   to `--muted`, and fix "1 rows right". About ten lines, all of it text the whole end phase
   depends on being read.

Everything in §2 is one focused afternoon of tokenising and would remove most of what "feels a bit
messy" without changing a single design decision.
