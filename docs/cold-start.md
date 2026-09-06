# What a cold start costs, and what it would take to remove one

Connectris runs on Cloud Run at `min-instances=0`. Nobody plays it at 3am, so most real
sessions begin by waiting for a container to boot. This measures that wait, takes it apart,
and prices the ways of getting rid of it.

Twelve services were deployed side by side in `europe-north1` — same Firestore collection,
same service account, same code except where the row says otherwise. Each container reports
its own boot in an `x-boot` header (first JS line, listen, request arrival, response) so the
client-side wait can be split into the part Cloud Run owns and the part the app owns.
Measurements: 204 samples on 2026-09-05 17:22–19:40 UTC (all twelve hit at once), then 96
samples on 2026-09-06 06:54–08:34 UTC (one service at a time, 25s apart). Nothing here ever
touched the `connectris` service.

## The number

**A cold start costs a real first player about 1.8 seconds today.** Of that, roughly 0.3s is
Cloud Run finding a host and starting the container, and **1.4s is Node** — reaching the
first line of JavaScript, loading the server bundle, and answering.

Warm, the same page comes back in **24 ms**. The cold start is not a slow app; it is a
99%-idle app paying to exist.

## Where the 1.8 seconds goes

Cold after ~16 minutes idle, one service at a time. Median, with the range across 5 rounds.

| configuration                                         | n   | client total        | Cloud Run + container | Node runtime | app modules | listen→request | request work |
| ----------------------------------------------------- | --- | ------------------- | --------------------- | ------------ | ----------- | -------------- | ------------ |
| Node, gen2, 1 vCPU, boost (baseline)                  | 5   | 1764 (1581–6241) ms | 526 (225–1887) ms     | 141 ms       | 690 ms      | 247 ms         | 131 ms       |
| Node, **gen1**, 1 vCPU, boost                         | 5   | 1528 (1347–1615) ms | 173 (149–290) ms      | 47 ms        | 704 ms      | 282 ms         | 133 ms       |
| Node, gen2, 1 vCPU, **no boost**                      | 5   | 1821 (1571–3771) ms | 345 (303–2573) ms     | 76 ms        | 607 ms      | 330 ms         | 151 ms       |
| Node, gen2, **2 vCPU**, boost                         | 5   | 1776 (1475–2177) ms | 317 (240–403) ms      | 206 ms       | 784 ms      | 239 ms         | 153 ms       |
| Node, gen2, 1 vCPU, **1 GiB**, boost                  | 5   | 1617 (1367–4158) ms | 428 (286–3034) ms     | 61 ms        | 578 ms      | 218 ms         | 125 ms       |
| Node on **alpine**, gen2, 1 vCPU, boost               | 5   | 2959 (2374–3980) ms | 887 (486–1126) ms     | 180 ms       | 1268 ms     | 456 ms         | 178 ms       |
| Node **bundled + compile cache**, gen2, 1 vCPU, boost | 5   | 1116 (1073–1197) ms | 389 (274–444) ms      | 61 ms        | 330 ms      | 114 ms         | 148 ms       |
| **Go**, gen2, 1 vCPU, boost                           | 5   | 361 (310–2204) ms   | 172 (154–1817) ms     | 0 ms         | 4 ms        | 95 ms          | 0 ms         |

Same services after 11 hours idle — the first start of the day, which is the one a real
player is most likely to hit. One sample each, so read these as anecdotes with a direction,
not as medians.

| configuration                                         | client total | Cloud Run + container | in-process to response |
| ----------------------------------------------------- | ------------ | --------------------- | ---------------------- |
| Node, gen2, 1 vCPU, boost (baseline)                  | 1762 ms      | 236 ms                | 1359 ms                |
| Node, **gen1**, 1 vCPU, boost                         | 2239 ms      | 362 ms                | 1576 ms                |
| Node, gen2, 1 vCPU, **no boost**                      | 1999 ms      | 299 ms                | 1643 ms                |
| Node, gen2, **2 vCPU**, boost                         | 3246 ms      | 1589 ms               | 1547 ms                |
| Node, gen2, 1 vCPU, **1 GiB**, boost                  | 3355 ms      | 2074 ms               | 1161 ms                |
| Node on **alpine**, gen2, 1 vCPU, boost               | 4624 ms      | 1918 ms               | 2600 ms                |
| Node **bundled + compile cache**, gen2, 1 vCPU, boost | 1302 ms      | 412 ms                | 823 ms                 |
| **Go**, gen2, 1 vCPU, boost                           | 757 ms       | 615 ms                | 89 ms                  |

The first measurement pass hit all twelve services in the same instant, and it is kept here
only as a caution: contention between co-starting containers inflated every row and
reordered several of them.

| configuration                                         | n   | client total, contended |
| ----------------------------------------------------- | --- | ----------------------- |
| Node, gen2, 1 vCPU, boost (baseline)                  | 8   | 2623 (2301–3356) ms     |
| Node, **gen1**, 1 vCPU, boost                         | 8   | 1872 (1557–2112) ms     |
| Node, gen2, 1 vCPU, **no boost**                      | 8   | 1762 (1621–3756) ms     |
| Node, gen2, **2 vCPU**, boost                         | 8   | 2616 (2303–4394) ms     |
| Node, gen2, 1 vCPU, **1 GiB**, boost                  | 8   | 1801 (1466–2114) ms     |
| Node on **alpine**, gen2, 1 vCPU, boost               | 8   | 3352 (2892–6594) ms     |
| Node **bundled + compile cache**, gen2, 1 vCPU, boost | 8   | 1442 (1005–2872) ms     |
| **Go**, gen2, 1 vCPU, boost                           | 8   | 444 (372–2430) ms       |

Twelve simultaneous cold starts is not a situation Connectris will ever be in. Every
conclusion below comes from the staggered pass.

## What does not work

**The knobs do nothing.** gen1 vs gen2, CPU boost on or off, 1 vCPU vs 2, 512 MiB vs 1 GiB —
every one of these lands inside the run-to-run spread of the baseline. The largest honest
effect is gen1 being ~240 ms quicker to hand over a container, and even that is inside the
tail. **There is no configuration change that meaningfully improves this.** Worth knowing
before anyone spends an afternoon on it.

**Smaller images do not start faster.** Image size and cold start are unrelated here:

| image             | compressed | cold start                |
| ----------------- | ---------- | ------------------------- |
| `node-base`       | 88.9 MB    | 1764 ms                   |
| `node-alpine`     | 65.7 MB    | 2959 ms                   |
| `node-lean`       | 83.1 MB    | **1116 ms**               |
| `node-distroless` | 55.8 MB    | not in the staggered pass |
| `go-app`          | **7.6 MB** | **361 ms**                |

Alpine is 26% smaller than the base image and **68% slower** — musl's allocator and dynamic
linker punish Node badly, and it shows up as 1268 ms of module loading against the baseline's
690 ms. The fastest Node image is _larger_ than the Alpine one. Cloud Run streams image
layers lazily, so bytes that are never read cost nothing; what matters is what is on the
critical path, not what is in the image. **Do not optimise the Dockerfile for size.**

(Distroless was dropped before the staggered pass and only has a contended number, 1722 ms
against the baseline's 2623 ms in that same pass. It looked promising and is the one row here
worth re-measuring if anyone revisits this.)

## What does work

**Bundle the server and ship V8's compile cache.** One esbuild pass turning `build/index.js`
and its `node_modules` tree into a single file, plus `enableCompileCache()` pointed at a
directory warmed during the image build, so a cold instance parses bytecode instead of
source:

```dockerfile
RUN npx esbuild build/index.js --bundle --platform=node --format=esm \
      --target=node24 --outfile=/out/index.js
# then, in a build stage that runs once:
RUN node --import ./cache.mjs --import ./boot.mjs warm.mjs
```

Module loading falls from 690 ms to **330 ms**, listen→request from 247 ms to 114 ms, and the
whole cold start from 1764 ms to **1116 ms — a 37% cut, for about 20 lines of Dockerfile.**
It is also the tightest distribution measured: 1073–1197 ms across five rounds, against the
baseline's 1581–6241 ms. The one wrinkle is that `google-gax` reads `__dirname` at module
scope, so the ESM bundle needs the CJS shims banner back.

**Rewriting in Go removes the problem rather than shrinking it.** 361 ms cold, of which 172
ms is Cloud Run and **4 ms is the application**. A Go binary has no module graph to load.

**Firestore's first query is 300–400 ms of the wait**, and it is not the client library being
slow so much as the connection being new — Go pays 88 ms for the same query. The baseline
already warms this on boot, concurrently with `listen`, which is why it does not appear as a
separate line in the tables.

## The Go prototype

`goapp/` (540 lines, in the scratchpad, not committed): one page, one check endpoint, the same
Firestore collection, the same warm-up-on-boot, the same instrumentation header.

The hard requirement is that Go must deal byte-identical boards, or every existing puzzle id
changes meaning. Measured, not assumed:

- `deal()` ported to Go — xmur3, mulberry32, Fisher-Yates, the re-seed loop. Diffed against
  the TypeScript over 412 puzzles: the 3 real boards plus 409 synthetic ids, including the
  empty string, `åäö`, `日本語のボード`, an emoji with a skin-tone modifier, a 200-character
  id, and 400 random ids. **Byte-identical on all 412.**
- The grader diffed against `localChecker` over 6 arrangements — as dealt, one right row in
  the wrong place, two right on top, solved, a short board, first check vs last check.
  **Identical JSON on all 6**, including which categories are named at the end and in what
  order.
- End to end: the board the Go service dealt from Firestore matched the board `deal()`
  produces from `puzzles.json`, tile id for tile id.

So "it must produce identical boards" is not a theoretical risk. It is about 60 lines of
careful uint32 arithmetic, and a differential test proves it. The cost is real all the same:
two implementations of the game rules, kept in step forever, for 750 ms.

## What it costs to never cold start

Prices pulled live from the Cloud Billing Catalog API for `europe-north1` on 2026-09-06, not
from memory: min-instance CPU $0.0000025/vCPU-s, min-instance memory $0.0000025/GiB-s,
request-based CPU $0.000024/vCPU-s.

**`min-instances=1`, at the deployed 1 vCPU / 512 MiB, is $9.86/month** ($6.57 CPU + $3.29
memory) — **$118/year to remove a 1.8-second wait.**

The alternative is a scheduled ping. Under request-based billing you are charged only while a
request is in flight, so holding an instance open costs almost nothing — and it works: a
service pinged every 10 minutes served **30 consecutive requests over 4 hours 51 minutes from
one process that was never recycled** (same start epoch, request counter 1→30, no gap).

| approach                          | cost/month | cold starts removed  |
| --------------------------------- | ---------- | -------------------- |
| `min-instances=1`                 | $9.86      | all of them          |
| Cloud Scheduler ping every 5 min  | $0.022     | one instance's worth |
| Cloud Scheduler ping every 10 min | $0.011     | one instance's worth |
| do nothing                        | $0.00      | none                 |

Cloud Scheduler's first 3 jobs/month are free, so the ping is **~900× cheaper** than
`min-instances`. It buys less: it holds one instance, so a second concurrent player during a
scale-out still waits, and nothing keeps the instance alive if Cloud Run recycles it. For a
game with this much traffic, that distinction is theoretical.

## Recommendation

1. **Do the bundle + compile cache.** 1764 ms → 1116 ms, ~20 lines of Dockerfile, no second
   implementation of anything, and it tightens the tail as much as it moves the median. This
   is the only change here with an obviously good ratio.
2. **Then ping it every 10 minutes** if the remaining second still bothers anyone. At $0.011
   a month it is cheaper than thinking about it, and it stacks with the bundle: an instance
   that is already warm serves in 24 ms.
3. **Do not pay for `min-instances`** at this traffic level, and **do not tune the knobs or
   shrink the image** — measured, neither does anything.
4. **Do not rewrite in Go for this reason alone.** It works, it is provably faithful, and it
   is 750 ms better than the best Node option. It is also a second copy of the game rules.
   Revisit only if something else independently argues for Go.

One thing this measurement caught in passing: the live service had been running **2 vCPU**
while `deploy.yml` asks for **1**, so merging the backend branch halved it (revision
`connectris-00009`). On this evidence that is the right way round — 1 vCPU measured no worse
than 2 and costs less — but it happened as a side effect of a deploy rather than as a
decision, which is worth knowing.

## Reproducing

Scripts are in the investigation scratchpad, not the repo:
`deploy.sh` (deploy the twelve), `measure.py` (one round, all at once), `stagger.py` and
`staggered_rounds.sh` (one at a time, the pass that matters), `analyze_stag.py` and
`tables.py` (the tables above), `warmbench.py` (warm latency), `skus.py` (live prices), and
`cleanup.sh`, which deletes every `csx-*` service and the `cold-start` Artifact Registry repo
and never names `connectris`. Raw samples are in `data/samples.tsv`, `data/staggered.tsv` and
`data/keepwarm.tsv`.
