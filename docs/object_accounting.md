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
| `n_recording_sites` | Recording sites (fiber locations) | `signal_<R>` entries in `storesList.csv` | **2** — `dms`, `dls` |
| `n_events` | Behavioral events GuPPy aligned to | non-fiber stores in `storesList.csv` | **3** — `port_entries`, `rewarded_nose_pokes`, `unrewarded_nose_pokes` |
| `n_traces` | Derived trace channels per recording site | `_DERIVED_TRACE_PREFIXES` | **3** — `control_fit`, `dff`, `z_score` |
| `n_features` | Trace types the *downstream analyses* run on | `_TRANSIENT_FEATURES` | **2** — `dff`, `z_score` |
| `n_recording_site_pairs` | Recording-site pairs with a cross-correlation | `corr_*.h5` files | **1** — `(dls, dms)` |
| `n_baselines` | PSTH baseline variants | corrected always; uncorrected optional | **2** — corrected + uncorrected |

Two subtleties worth calling out, because they explain otherwise-surprising counts:

- **`n_traces` (3) vs `n_features` (2).** GuPPy emits three derived channels per recording site,
  but one of them — `control_fit` — is the *fitted isosbestic control*, an intermediate, not a
  signal of interest. Transients, PSTHs, cross-correlations, and peak/AUC are computed only on
  the real signals (`dff`, `z_score`). So products split on `n_features = 2`, while the raw
  traces split on `n_traces = 3`.
- **`n_recording_site_pairs` is not `n_recording_sites²`.** GuPPy emits one cross-correlation per
  *ordered pair it was asked to compute*, here just `(dls, dms)`. It is its own axis, not derived
  from `n_recording_sites`.

---

## 2. How many of each object

Two rules set the layout. The first decides whether an axis becomes rows or objects; the
second decides which axis is absorbed into the *data* rather than spawning objects at all:

- **Scalar-per-combination → table rows; array-per-combination → objects.** A scalar result
  per combination collapses the axis into one table's rows; an array result (a timeseries, or
  a `(time × trials)` matrix) makes each combination its own object.
- **The unbounded axis is concatenated into the data, not multiplied into objects.** Of the
  axes, only `n_events` grows without bound (you can align to arbitrarily many behavioral
  events). So the event-bearing products — PSTH, peak/AUC, cross-correlation — emit **one
  object per condition** (the bounded axes) and stack every event's trials *inside* that object
  (see §5). The object count is therefore **invariant to `n_events`.**

### Session singletons — axes collapsed into rows

These hold scalar-per-combination data, so the axis becomes a row index inside one object.

| Object | Rows | Count |
|---|---|---|
| `GuppyParameters` (LabMetaData) | — (one parameter set/session) | **1** |
| `GuppyRecordingSitesTable` | `n_recording_sites` | **1** |
| `GuppyEventsTable` | `n_events` | **1** |
| `GuppyTransientSummaryTable` | `n_recording_sites × n_features` (= 4 rows) | **1** |

Valid-signal intervals (the artifact-free windows GuPPy keeps during preprocessing) are a
per-recording-site fact, so they are **not** a separate object: they ride on
`GuppyRecordingSitesTable` as an optional `obs_intervals`-style ragged column
(`valid_signal_intervals`, a per-row list of `[start, stop]` pairs, indexed by
`valid_signal_intervals_index`), exactly as the core `Units` table carries per-unit
`obs_intervals`. The removal method is recorded once on
`GuppyParameters.artifacts_removal_method`, not re-embedded here.

### Per-condition objects — axes that carry arrays

These hold an array per condition, so each condition is a separate object. Note the absence of
`n_events` from every multiplicity — it lives *inside* the objects, along the trials axis.

| Object | Multiplicity | Fixture count |
|---|---|---|
| `GuppyDerivedResponseSeries` | `n_recording_sites × n_traces` | 2 × 3 = **6** |
| `GuppyTransientsTable` | `n_recording_sites × n_features` | 2 × 2 = **4** |
| `GuppyCrossCorrelation` | `n_features × n_recording_site_pairs` | 2 × 1 = **2** |
| `GuppyPSTH` | `n_recording_sites × n_features × n_baselines` | 2 × 2 × 2 = **8** |
| `GuppyPeakAUC` | `n_recording_sites × n_features` | 2 × 2 = **4** |

---

## 3. The total

```
singletons          4   (recording sites + events + parameters + transient summary)
derived traces      6   = n_recording_sites · n_traces
transients          4   = n_recording_sites · n_features
cross-correlation   2   = n_features · n_recording_site_pairs
PSTH                8   = n_recording_sites · n_features · n_baselines
peak / AUC          4   = n_recording_sites · n_features
                  ───
total              28
```

No multiplicity carries `n_events`, so adding behavioral events does not add objects — it adds
*columns* to the existing PSTH/peak-AUC/cross-correlation objects. Before the events axis was
concatenated this same fixture produced **56** objects (PSTH alone was 24); the event-bearing
products were 64% of the file and grew linearly with `n_events`. They are now 14 of 28, fixed.

---

## 4. Why this shape (the design principle to present)

Three rules, applied consistently, produce the layout above. When justifying it to others,
these are the load-bearing ideas:

**(a) Identity lives once, in registries.** `recording_site` and `dms`, `event` and
`port_entries`, are *entities*. They are defined exactly once — as rows in
`GuppyRecordingSitesTable` and `GuppyEventsTable` — and every product points back at them with a
`DynamicTableRegion`. Recording site and event are never re-spelled as free text on each product.
So the proliferation of products does **not** proliferate identity: there are still only
`n_recording_sites + n_events` identity rows in the whole file.

**(b) Scalar-per-combination collapses to rows; array-per-combination becomes an object.**
- The transient *summary* is one frequency + one mean amplitude per `(recording_site, feature)` —
  scalars — so all `n_recording_sites · n_features` combinations live as **rows in one table**.
- A PSTH is a `(time × trials)` **matrix** per condition — an array — so each condition is
  **its own object**.

The 28 objects are not 28 modelling decisions; they are the count of array-valued results GuPPy
computed (with the event axis folded inside), plus a handful of tables that absorb everything
scalar.

**(c) Bounded axes split objects; the unbounded axis is concatenated.** `trace_type` is a
closed category (`control_fit`/`dff`/`z_score`) stamped as an **attribute**; `recording_site` and
the baseline flag are likewise bounded and stay attributes/refs on the object. Splitting objects
along these *bounded* axes keeps `trace_type`/`recording_site`/`baseline` as attributes and every
array rectangular. The **event** axis is different — it is unbounded, so splitting on it would let
the file grow without limit. Instead it is concatenated into the trials axis *inside* each object,
and `event` (which genuinely varies trial-to-trial) becomes a per-trial `DynamicTableRegion`
into `GuppyEventsTable`. That is the rule working as intended, not a violation of it: bounded
categories stay attributes; the one unbounded entity becomes data.

---

## 5. Concatenating the unbounded axis (how an event-bearing object is shaped)

Concatenating events works — without duplication or ragged storage — because of two facts about
GuPPy's data:

- **Different event types are genuinely different trials.** `port_entries` occurrence #3 and
  `rewarded_nose_pokes` occurrence #1 are two distinct alignment windows, so stacking them along
  the trials axis adds real trials, not copies. "Trials stay trials."
- **The peri-event window is one parameter**, so `num_samples` (the time axis) is identical
  across every event. Concatenating along trials keeps the matrix rectangular; only the trial
  *count* differed per event, and concatenation sums that count out.

Each event-bearing object is therefore a **three-grain structure**, every axis flat-concatenated
across events with its own event `DynamicTableRegion` (the CSR-style way to hold ragged groups):

| Grain | Size | Holds | Event label |
|---|---|---|---|
| trials | `num_trials` = Σ over events | `traces` `(num_samples, num_trials)`, `trial_onset_times` | `event` (per trial) |
| per-event summary | `num_events` | `mean`/`error` `(num_samples, num_events)` | `summary_event` |
| bins | `num_bins` = Σ over events | `binned_mean`/`binned_error` `(num_samples, num_bins)` | `bin_event` |

The bins need their own grain because GuPPy bins trials in fixed groups, so bin counts differ
per event (fixture: 2 / 1 / 6) — ragged, handled by the same concatenate-plus-event-ref trick as
the trials. `recording_site`, `trace_type`, `baseline_corrected`, and `unit` stay object-level
attributes/refs because they are constant within a condition.

### The remaining lever

If the count ever needs to fall further, the bounded axes are the only remaining knob, and they
are cheap to consolidate because they produce **identically-shaped** arrays (no raggedness). For
example, the `n_baselines` axis (corrected/uncorrected) could fold into a dimension rather than
doubling PSTH objects. We have **not** done this — the bounded axes are small and splitting on
them keeps each object semantically homogeneous and self-describing — but it is the lever that
remains, now that the unbounded one is already handled.
