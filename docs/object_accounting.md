# ndx-guppy object accounting

How many NWB objects a single GuPPy session produces, and *why* that number is what it
is. The point of this document is to make the object count **predictable from the data**:
every object can be traced back to a physical axis of variation in GuPPy's output, so the
count is a consequence of the analysis GuPPy ran, not of an arbitrary modelling choice.

Concrete numbers below use the `Photo_63_207-181030-103332` fixture.

---

## 1. The axes of variation

A GuPPy session varies along a handful of independent axes. Everything ndx-guppy writes is
indexed by some subset of these.

| Symbol | Meaning | Ranges over | Fixture value |
|---|---|---|---|
| `n_regions` | Recording sites (fiber locations) | `signal_<R>` entries in `storesList.csv` | **2** — `dms`, `dls` |
| `n_events` | Behavioral events GuPPy aligned to | non-fiber stores in `storesList.csv` | **3** — `port_entries`, `rewarded_nose_pokes`, `unrewarded_nose_pokes` |
| `n_traces` | Derived trace channels per region | `_DERIVED_TRACE_PREFIXES` | **3** — `control_fit`, `dff`, `z_score` |
| `n_features` | Trace types the *downstream analyses* run on | `_TRANSIENT_FEATURES` | **2** — `dff`, `z_score` |
| `n_region_pairs` | Region pairs with a cross-correlation | `corr_*.h5` files | **1** — `(dls, dms)` |
| `n_baselines` | PSTH baseline variants | corrected always; uncorrected optional | **2** — corrected + uncorrected |

Two subtleties worth calling out, because they explain otherwise-surprising counts:

- **`n_traces` (3) vs `n_features` (2).** GuPPy emits three derived channels per region, but
  one of them — `control_fit` — is the *fitted isosbestic control*, an intermediate, not a
  signal of interest. Transients, PSTHs, cross-correlations, and peak/AUC are computed only on
  the real signals (`dff`, `z_score`). So products split on `n_features = 2`, while the raw
  traces split on `n_traces = 3`.
- **`n_region_pairs` is not `n_regions²`.** GuPPy emits one cross-correlation per *ordered pair
  it was asked to compute*, here just `(dls, dms)`. It is its own axis, not derived from
  `n_regions`.

---

## 2. How many of each object

The key distinction is **what GuPPy produces per combination of axes**:

- A **scalar (or fixed small tuple) per combination** → the axis collapses into **table rows**.
  One object, `n` rows.
- An **array per combination** (a timeseries, or a `(time × trials)` matrix) → each combination
  is its **own object**. `n` objects.

That single rule explains the entire layout.

### Session singletons — axes collapsed into rows

These hold scalar-per-combination data, so the axis becomes a row index inside one object.

| Object | Rows | Count |
|---|---|---|
| `GuppyParameters` (LabMetaData) | — (one parameter set/session) | **1** |
| `GuppyRegionsTable` | `n_regions` | **1** |
| `GuppyEventsTable` | `n_events` | **1** |
| `GuppyTransientSummaryTable` | `n_regions × n_features` (= 4 rows) | **1** |
| `GuppyValidSignalIntervals` | `n_regions` (only if artifact coords exist) | **0** here |

### Per-combination objects — axes that carry arrays

These hold an array per combination, so each combination is a separate object.

| Object | Multiplicity | Fixture count |
|---|---|---|
| `GuppyDerivedResponseSeries` | `n_regions × n_traces` | 2 × 3 = **6** |
| `GuppyTransientsTable` | `n_regions × n_features` | 2 × 2 = **4** |
| `GuppyCrossCorrelation` | `n_events × n_features × n_region_pairs` | 3 × 2 × 1 = **6** |
| `GuppyPSTH` | `n_events × n_regions × n_features × n_baselines` | 3 × 2 × 2 × 2 = **24** |
| `GuppyPeakAUC` | `n_events × n_regions × n_features` | 3 × 2 × 2 = **12** |

---

## 3. The total, and what dominates

```
singletons          4   (regions + events + parameters + transient summary)
derived traces      6   = n_regions · n_traces
transients          4   = n_regions · n_features
cross-correlation   6   = n_events · n_features · n_region_pairs
PSTH               24   = n_events · n_regions · n_features · n_baselines
peak / AUC         12   = n_events · n_regions · n_features
                  ───
total              56
```

**The PSTH count dominates because it is the only product that multiplies *all four* of the
big axes** — events, regions, features, and baseline variants. PSTH (24) and peak/AUC (12)
together are the two products carrying the `n_events` factor, and they are **36 of 56 objects
(64%)**. This is the "~20 PSTH objects" you noticed: it is `n_events · n_regions · n_features ·
n_baselines`, and there is no smaller honest number for it *as separate objects*.

---

## 4. Why this shape (the design principle to present)

Three rules, applied consistently, produce the layout above. When justifying it to others,
these are the load-bearing ideas:

**(a) Identity lives once, in registries.** `region` and `dms`, `event` and `port_entries`,
are *entities*. They are defined exactly once — as rows in `GuppyRegionsTable` and
`GuppyEventsTable` — and every product points back at them with a `DynamicTableRegion`. Region
and event are never re-spelled as free text on each product. So the proliferation of products
does **not** proliferate identity: there are still only `n_regions + n_events` identity rows in
the whole file.

**(b) Scalar-per-combination collapses to rows; array-per-combination becomes an object.**
This is the rule that sets the object count.
- The transient *summary* is one frequency + one mean amplitude per `(region, feature)` — scalars
  — so all `n_regions · n_features` combinations live as **rows in one table**.
- A PSTH is a `(time × trials)` **matrix** per `(event, region, feature, baseline)` — an array —
  so each combination is **its own object**.

The 56 objects are not 56 modelling decisions; they are the count of array-valued results GuPPy
actually computed, plus a handful of tables that absorb everything scalar.

**(c) Categories are attributes, entities are references — and that is *why* we don't merge the
matrices into one mega-table.** `trace_type` is a closed category (`control_fit`/`dff`/`z_score`),
so it is stamped as an **attribute** on each object. Keeping each PSTH/transient/peak-AUC as a
separate object is exactly what lets `trace_type`, `region`, and `event` stay
attributes-and-references *on the object*. The moment you consolidate, say, all PSTHs into one
table with rows = `(event, region, feature)`, those axes are forced to become **data columns**,
and the per-trial matrices become a doubly-ragged column (trials vary by event) — the one storage
shape HDMF handles worst. Splitting by combination is what keeps every array rectangular and every
category an attribute rather than a column.

### The shape-boundary corollary

If the object count ever *does* need to come down, the principled lever is visible in the
formulas: only **`n_events`** changes the *shape* of a PSTH/peak-AUC array (different events have
different trial counts). `n_regions`, `n_features`, and `n_baselines` produce
**identically-shaped** arrays. So the only consolidation that doesn't fight HDMF is collapsing
those same-shape axes into extra array dimensions *within* an object, splitting solely on
`n_events` — turning `n_events · n_regions · n_features · n_baselines` objects into `n_events`
objects. We have **not** done this (it trades 24 self-describing objects for 3 objects with
internal index bookkeeping), but it is the one consolidation the data structure permits, and it
is worth knowing it exists.
