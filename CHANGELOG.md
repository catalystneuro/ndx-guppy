# Changelog for ndx-guppy

# v0.2.1 (Upcoming)

### Features
* Added `GuppyPSTHSignificance`, holding the bootstrap significance of a baseline-corrected PSTH for one (recording_site, trace_type) condition, concatenated across comparisons. An object holds either the tests against zero or the event-versus-event comparisons, the latter adding `event_b` and `num_trials_b`. `GuppyParameters` gained `compute_psth_significance`, `psth_significance_alpha`, `psth_bootstrap_resamples` and the requested comparison pairs [PR #9](https://github.com/catalystneuro/ndx-guppy/pull/9).

### Fixes


# v0.2.0 (August 24th, 2026)

### Features
* `GuppyParameters` gained `use_transients_as_events`, recording that GuPPy stood each recording site's own detected transients in for external TTLs. Such an event needs no new type: it contributes one `GuppyEventsTable` row per (metric, recording site), each selecting its own site's occurrences [PR #6](https://github.com/catalystneuro/ndx-guppy/pull/6).
* Added `GuppyBinnedMetrics` and `GuppyBinnedCovariates`, extending `TimeIntervals` to hold GuPPy's whole-session time-binned metrics and the behavioral covariates binned onto them, and `GuppyCovariateCorrelations` for the coefficients relating the two. `GuppyParameters` gained `compute_binned_metrics` and `binned_metrics_width` [PR #5](https://github.com/catalystneuro/ndx-guppy/pull/5).
* Added `GuppyTonicEpochs`, extending `TimeIntervals` to hold the mean level of each normalized trace within each of GuPPy's tonic epoch windows, one row per (recording_site, epoch, trace_type) [PR #4](https://github.com/catalystneuro/ndx-guppy/pull/4).

### Fixes


# v0.1.0 (July 16th, 2026)

### Features
Initial release of 10 new neurodata types representing the derived outputs of the GuPPy fiber-photometry tool (one NWB file per session):
* `GuppyParameters` extends `LabMetaData` to hold the session-level GuPPy processing parameters.
* `GuppyRecordingSitesTable` extends `DynamicTable` as the canonical registry of recording sites (one row per site, e.g. `dms`) that the derived products reference.
* `GuppyEventsTable` extends `DynamicTable` as the registry of behavioral events GuPPy aligned to, with an optional ragged `DynamicTableRegion` into a merged core `EventsTable`.
* `GuppyValidSignalIntervals` extends `TimeIntervals` to hold the valid (artifact-free) signal intervals per recording site.
* `GuppyDerivedResponseSeries` extends `FiberPhotometryResponseSeries` to hold a derived trace (`control_fit`/`dff`/`z_score`), stamped with its `trace_type` and referencing its recording site.
* `GuppyTransientsTable` extends `DynamicTable` to hold the detected transients.
* `GuppyTransientSummaryTable` extends `DynamicTable` to hold per-condition transient summary statistics.
* `GuppyPSTH` holds the peri-event PSTH for one (recording_site, trace_type, baseline) condition, concatenated across events.
* `GuppyCrossCorrelation` holds the cross-correlation between a recording-site pair for one trace_type, concatenated across events.
* `GuppyPeakAUC` holds the peak and area-under-the-curve metrics for one (recording_site, trace_type) condition, concatenated across events.

### Fixes
* Fixed the ruff and Sphinx CI jobs (import ordering and doc-autogen namespace registration; no schema changes) [PR #1](https://github.com/catalystneuro/ndx-guppy/pull/1).
