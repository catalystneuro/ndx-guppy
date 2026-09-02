# -*- coding: utf-8 -*-
"""Create the ndx-guppy extension spec.

ndx-guppy provides dedicated neurodata types for the derived outputs of the GuPPy
fiber-photometry processing tool. The design turns GuPPy's organizing features --
``recording_site``, ``trace_type``, and ``event`` -- into structured, queryable NWB features:

- *recording_site* and *event* are entities, so they live as rows in registry tables
  (``GuppyRecordingSitesTable``, ``GuppyEventsTable``) and are referenced via ``DynamicTableRegion``.
- *trace_type* is a closed category, so it is a plain enumerated text attribute stamped
  directly on each object (values: ``control_fit`` / ``dff`` / ``z_score``).

Cross-extension dependencies are quarantined: products reference ndx-guppy's own registry
tables, and any outward link (to the acquisition ``FiberPhotometryTable`` or to a
``pynwb.event.EventsTable``) is an optional column on a registry.
"""
from pathlib import Path

from pynwb.spec import (
    NWBNamespaceBuilder,
    export_spec,
    NWBGroupSpec,
    NWBDatasetSpec,
    NWBAttributeSpec,
    NWBRefSpec,
)

# Controlled vocabulary for the ``trace_type`` attribute, documented (not hard-enforced) so a
# future GuPPy trace type does not break reading.
TRACE_TYPE_DOC = (
    "The GuPPy normalized trace this object was computed from. Controlled vocabulary: "
    "'control_fit', 'dff', or 'z_score'."
)


def trace_type_attr():
    """The enumerated ``trace_type`` attribute stamped on objects that are about one trace type."""
    return NWBAttributeSpec(name="trace_type", doc=TRACE_TYPE_DOC, dtype="text")


def recording_site_region(doc, quantity=1):
    """A ``DynamicTableRegion`` referencing rows of the ``GuppyRecordingSitesTable``."""
    return NWBDatasetSpec(name="recording_site", neurodata_type_inc="DynamicTableRegion", doc=doc, quantity=quantity)


def covariate_reference(doc):
    """A column of object references to the ``TimeSeries`` holding a covariate's scored values.

    The series the interface writes is the covariate's identity, so the covariate products point at it
    rather than re-spelling its name.
    """
    return NWBDatasetSpec(
        name="covariate",
        neurodata_type_inc="VectorData",
        doc=doc,
        dtype=NWBRefSpec(target_type="TimeSeries", reftype="object"),
    )


def event_region(doc, quantity=1, name="event"):
    """A ``DynamicTableRegion`` referencing rows of the ``GuppyEventsTable``.

    The same helper builds the per-trial ``event`` reference, the per-summary-column
    ``summary_event`` reference, and the per-bin ``bin_event`` reference.
    """
    return NWBDatasetSpec(name=name, neurodata_type_inc="DynamicTableRegion", doc=doc, quantity=quantity)


def main():
    ns_builder = NWBNamespaceBuilder(
        name="""ndx-guppy""",
        version="""0.2.1""",
        doc="""NWB extension for the Guppy fiber photometry processing tool""",
        author=[
            "Paul Adkisson-Floro",
        ],
        contact=[
            "paul.wesley.adkisson@gmail.com",
        ],
    )
    ns_builder.include_namespace("core")
    # GuppyDerivedResponseSeries extends FiberPhotometryResponseSeries.
    ns_builder.include_namespace("ndx-fiber-photometry")

    # ------------------------------------------------------------------ #
    # Registries (the structural backbone)
    # ------------------------------------------------------------------ #
    guppy_recording_sites_table = NWBGroupSpec(
        neurodata_type_def="GuppyRecordingSitesTable",
        neurodata_type_inc="DynamicTable",
        doc=(
            "Registry of GuPPy recording sites (one row per recording site, e.g. 'dms'). A GuPPy recording "
            "site is a processing-level entity -- a signal+isosbestic pair collapsed into one derived "
            "signal -- so it is the canonical recording-site identity that GuPPy products reference."
        ),
        datasets=[
            NWBDatasetSpec(
                name="recording_site",
                neurodata_type_inc="VectorData",
                doc=(
                    "The semantic recording-site name from storesList.csv (e.g. 'dms'). The recording "
                    "site's identity."
                ),
                dtype="text",
            ),
            NWBDatasetSpec(
                name="fiber_photometry_table_region",
                neurodata_type_inc="DynamicTableRegion",
                doc=(
                    "Optional ragged reference into the acquisition FiberPhotometryTable (the signal + "
                    "isosbestic fiber rows for this recording site). Absorbs the signal/control "
                    "many-to-one mapping once, here, so products reference a single recording-site row "
                    "and reach the physical fiber provenance through it. Populated at conversion time "
                    "by a converter that owns the acquisition side (see the neuroconv GuppyInterface)."
                ),
                quantity="?",
            ),
            NWBDatasetSpec(
                name="fiber_photometry_table_region_index",
                neurodata_type_inc="VectorIndex",
                doc="Ragged index for fiber_photometry_table_region (multiple fiber rows per recording site).",
                quantity="?",
            ),
        ],
    )

    guppy_events_table = NWBGroupSpec(
        neurodata_type_def="GuppyEventsTable",
        neurodata_type_inc="DynamicTable",
        doc=(
            "Registry of behavioral events GuPPy aligned to (one row per event, e.g. 'port_entries'). The "
            "canonical event identity that GuPPy peri-event products reference."
        ),
        datasets=[
            NWBDatasetSpec(
                name="event_name",
                neurodata_type_inc="VectorData",
                doc="The semantic event name from storesList.csv (e.g. 'port_entries').",
                dtype="text",
            ),
            NWBDatasetSpec(
                name="events",
                neurodata_type_inc="DynamicTableRegion",
                doc=(
                    "Optional ragged reference into the merged pynwb EventsTable (in nwbfile.events) "
                    "selecting this event type's occurrence rows. Populated at conversion time by a "
                    "converter that merges every event type into one EventsTable (see the neuroconv "
                    "GuppyInterface)."
                ),
                quantity="?",
            ),
            NWBDatasetSpec(
                name="events_index",
                neurodata_type_inc="VectorIndex",
                doc="Ragged index for events (multiple occurrence rows per event type).",
                quantity="?",
            ),
        ],
    )

    # ------------------------------------------------------------------ #
    # Derived traces
    # ------------------------------------------------------------------ #
    guppy_derived_response_series = NWBGroupSpec(
        neurodata_type_def="GuppyDerivedResponseSeries",
        neurodata_type_inc="FiberPhotometryResponseSeries",
        doc=(
            "A GuPPy-derived continuous trace (control_fit, dff, or z_score) for one recording site. "
            "Extends FiberPhotometryResponseSeries to stamp the trace_type and to reference the GuPPy "
            "recording sites registry; the inherited fiber_photometry_table_region still carries the "
            "physical signal+isosbestic fiber provenance."
        ),
        attributes=[trace_type_attr()],
        datasets=[
            recording_site_region(
                doc="Reference to the GuppyRecordingSitesTable row for this trace's recording site (single row).",
            ),
        ],
    )

    # ------------------------------------------------------------------ #
    # Analysis products
    # ------------------------------------------------------------------ #
    guppy_transients_table = NWBGroupSpec(
        neurodata_type_def="GuppyTransientsTable",
        neurodata_type_inc="DynamicTable",
        doc="GuPPy-detected transient peaks for one (recording_site, trace_type).",
        attributes=[
            trace_type_attr(),
            NWBAttributeSpec(name="unit", doc="Unit of the amplitude (matches the trace_type).", dtype="text"),
        ],
        datasets=[
            recording_site_region(
                doc="Reference to the GuppyRecordingSitesTable row for this table's recording site (single row)."
            ),
            NWBDatasetSpec(
                name="timestamp",
                neurodata_type_inc="VectorData",
                doc="Timestamp of the detected transient peak (seconds, session clock).",
                dtype="float64",
            ),
            NWBDatasetSpec(
                name="amplitude",
                neurodata_type_inc="VectorData",
                doc="Trace value at the detected transient peak.",
                dtype="float64",
            ),
        ],
    )

    guppy_transient_summary_table = NWBGroupSpec(
        neurodata_type_def="GuppyTransientSummaryTable",
        neurodata_type_inc="DynamicTable",
        doc=(
            "Per-session GuPPy transient summary: one row per (recording_site, trace_type) with event "
            "frequency and mean peak amplitude. recording_site and trace_type vary per row, so they are columns."
        ),
        datasets=[
            NWBDatasetSpec(
                name="recording_site",
                neurodata_type_inc="DynamicTableRegion",
                doc="Reference to the GuppyRecordingSitesTable row for this summary row's recording site.",
            ),
            NWBDatasetSpec(
                name="trace_type",
                neurodata_type_inc="VectorData",
                doc=TRACE_TYPE_DOC,
                dtype="text",
            ),
            NWBDatasetSpec(
                name="frequency_per_min",
                neurodata_type_inc="VectorData",
                doc="Transient frequency in events per minute.",
                dtype="float64",
            ),
            NWBDatasetSpec(
                name="mean_amplitude",
                neurodata_type_inc="VectorData",
                doc="Mean amplitude of the detected transient peaks.",
                dtype="float64",
            ),
        ],
    )

    guppy_psth = NWBGroupSpec(
        neurodata_type_def="GuppyPSTH",
        neurodata_type_inc="NWBDataInterface",
        doc=(
            "Peri-event PSTH for one (recording_site, trace_type) condition, concatenated across events. "
            "The per-trial 'traces' matrix stacks every event's trials along the trials axis (each trial "
            "labeled by the per-trial 'event' reference); 'mean'/'error' hold GuPPy's across-trial "
            "summary, one column per event ('summary_event'). The baseline-uncorrected variant is a "
            "second GuppyPSTH with baseline_corrected=False."
        ),
        attributes=[
            NWBAttributeSpec(name="description", doc="Human-readable description of this PSTH.", dtype="text"),
            trace_type_attr(),
            NWBAttributeSpec(
                name="baseline_corrected",
                doc="Whether per-trial baseline correction was applied.",
                dtype="bool",
            ),
            NWBAttributeSpec(name="unit", doc="Unit of the PSTH values (matches the trace_type).", dtype="text"),
        ],
        datasets=[
            recording_site_region(
                doc="Reference to the GuppyRecordingSitesTable row for this PSTH's recording site (single row)."
            ),
            event_region(
                doc=(
                    "Per-trial reference into GuppyEventsTable: one row per trial (shape (num_trials,)), "
                    "labeling which event each column of 'traces' was aligned to."
                ),
            ),
            event_region(
                name="summary_event",
                doc=(
                    "Per-summary-column reference into GuppyEventsTable: one row per event type "
                    "(shape (num_events,)), labeling the columns of 'mean'/'error'."
                ),
            ),
            NWBDatasetSpec(
                name="peri_event_time",
                doc="Peri-event time axis in seconds (relative to event onset), shape (num_samples,).",
                dtype="float64",
                shape=(None,),
                dims=("num_samples",),
            ),
            NWBDatasetSpec(
                name="trial_onset_times",
                doc=(
                    "Absolute onset time of each trial in seconds (session clock), shape (num_trials,), "
                    "concatenated across events in the same order as the 'traces' columns."
                ),
                dtype="float64",
                shape=(None,),
                dims=("num_trials",),
            ),
            NWBDatasetSpec(
                name="traces",
                doc=(
                    "Per-trial response, shape (num_samples, num_trials). Time is the first axis. Trials "
                    "from every event are concatenated along the second axis; see the 'event' reference."
                ),
                dtype="float64",
                shape=(None, None),
                dims=("num_samples", "num_trials"),
            ),
            NWBDatasetSpec(
                name="mean",
                doc="Across-trial mean at each peri-event time, one column per event, shape (num_samples, num_events).",
                dtype="float64",
                shape=(None, None),
                dims=("num_samples", "num_events"),
            ),
            NWBDatasetSpec(
                name="error",
                doc=(
                    "Across-trial error (e.g. SEM) at each peri-event time, one column per event, "
                    "shape (num_samples, num_events)."
                ),
                dtype="float64",
                shape=(None, None),
                dims=("num_samples", "num_events"),
            ),
            NWBDatasetSpec(
                name="bin_edges",
                doc=(
                    "Optional bin definitions, shape (num_bins, 2), concatenated across events. Each row is "
                    "[start, stop); interpreted as trial-index ranges or time ranges according to the "
                    "bin_basis attribute. See the 'bin_event' reference for each bin's event."
                ),
                dtype="float64",
                shape=(None, 2),
                dims=("num_bins", "start_stop"),
                quantity="?",
                attributes=[
                    NWBAttributeSpec(
                        name="bin_basis",
                        doc="Whether bins are defined over 'trials' or 'time'.",
                        dtype="text",
                    )
                ],
            ),
            event_region(
                name="bin_event",
                quantity="?",
                doc=(
                    "Per-bin reference into GuppyEventsTable: one row per bin (shape (num_bins,)), labeling "
                    "the columns of 'binned_mean'/'binned_error'."
                ),
            ),
            NWBDatasetSpec(
                name="binned_mean",
                doc="Optional per-bin mean, shape (num_samples, num_bins), concatenated across events.",
                dtype="float64",
                shape=(None, None),
                dims=("num_samples", "num_bins"),
                quantity="?",
            ),
            NWBDatasetSpec(
                name="binned_error",
                doc="Optional per-bin error, shape (num_samples, num_bins), concatenated across events.",
                dtype="float64",
                shape=(None, None),
                dims=("num_samples", "num_bins"),
                quantity="?",
            ),
        ],
    )

    guppy_cross_correlation = NWBGroupSpec(
        neurodata_type_def="GuppyCrossCorrelation",
        neurodata_type_inc="NWBDataInterface",
        doc=(
            "Peri-event cross-correlation for one (trace_type, recording-site-pair) condition, concatenated "
            "across events, stored as a lags-by-trials matrix over a lag axis. The recording_site reference "
            "points at two rows (recording_site_1, recording_site_2); the per-trial 'event' reference labels "
            "each trials column and 'mean'/'error' hold the across-trial summary, one column per event "
            "('summary_event')."
        ),
        attributes=[
            NWBAttributeSpec(
                name="description", doc="Human-readable description of this cross-correlation.", dtype="text"
            ),
            trace_type_attr(),
            NWBAttributeSpec(
                name="unit", doc="Unit of the cross-correlation values (normalized; typically 'a.u.').", dtype="text"
            ),
        ],
        datasets=[
            recording_site_region(
                doc=(
                    "Reference to the two GuppyRecordingSitesTable rows (recording_site_1, recording_site_2) "
                    "for this cross-correlation."
                ),
            ),
            event_region(
                doc=(
                    "Per-trial reference into GuppyEventsTable: one row per trial (shape (num_trials,)), "
                    "labeling which event each column of 'trials' was aligned to."
                ),
            ),
            event_region(
                name="summary_event",
                doc=(
                    "Per-summary-column reference into GuppyEventsTable: one row per event type "
                    "(shape (num_events,)), labeling the columns of 'mean'/'error'."
                ),
            ),
            NWBDatasetSpec(
                name="lag",
                doc="Lag axis in seconds (symmetric around zero), shape (num_lags,).",
                dtype="float64",
                shape=(None,),
                dims=("num_lags",),
            ),
            NWBDatasetSpec(
                name="trial_onset_times",
                doc=(
                    "Absolute onset time of each trial in seconds (session clock), shape (num_trials,), "
                    "concatenated across events in the same order as the 'trials' columns."
                ),
                dtype="float64",
                shape=(None,),
                dims=("num_trials",),
            ),
            NWBDatasetSpec(
                name="trials",
                doc=(
                    "Per-trial cross-correlation, shape (num_lags, num_trials). Lag is the first axis. Trials "
                    "from every event are concatenated along the second axis; see the 'event' reference."
                ),
                dtype="float64",
                shape=(None, None),
                dims=("num_lags", "num_trials"),
            ),
            NWBDatasetSpec(
                name="mean",
                doc=(
                    "Across-trial mean cross-correlation at each lag, one column per event, "
                    "shape (num_lags, num_events)."
                ),
                dtype="float64",
                shape=(None, None),
                dims=("num_lags", "num_events"),
            ),
            NWBDatasetSpec(
                name="error",
                doc="Across-trial error at each lag, one column per event, shape (num_lags, num_events).",
                dtype="float64",
                shape=(None, None),
                dims=("num_lags", "num_events"),
            ),
            NWBDatasetSpec(
                name="bin_edges",
                doc=(
                    "Optional bin definitions, shape (num_bins, 2), concatenated across events. Each row is "
                    "[start, stop); interpreted as trial-index ranges or time ranges according to the "
                    "bin_basis attribute. See the 'bin_event' reference for each bin's event."
                ),
                dtype="float64",
                shape=(None, 2),
                dims=("num_bins", "start_stop"),
                quantity="?",
                attributes=[
                    NWBAttributeSpec(
                        name="bin_basis",
                        doc="Whether bins are defined over 'trials' or 'time'.",
                        dtype="text",
                    )
                ],
            ),
            event_region(
                name="bin_event",
                quantity="?",
                doc=(
                    "Per-bin reference into GuppyEventsTable: one row per bin (shape (num_bins,)), labeling "
                    "the columns of 'binned_mean'/'binned_error'."
                ),
            ),
            NWBDatasetSpec(
                name="binned_mean",
                doc="Optional per-bin mean, shape (num_lags, num_bins), concatenated across events.",
                dtype="float64",
                shape=(None, None),
                dims=("num_lags", "num_bins"),
                quantity="?",
            ),
            NWBDatasetSpec(
                name="binned_error",
                doc="Optional per-bin error, shape (num_lags, num_bins), concatenated across events.",
                dtype="float64",
                shape=(None, None),
                dims=("num_lags", "num_bins"),
                quantity="?",
            ),
        ],
    )

    guppy_peak_auc = NWBGroupSpec(
        neurodata_type_def="GuppyPeakAUC",
        neurodata_type_inc="NWBDataInterface",
        doc=(
            "Peak and area-under-curve summary of a peri-event PSTH for one (recording_site, trace_type) "
            "condition, concatenated across events. GuPPy computes peak_positive, peak_negative, and area "
            "for every trial, every bin, and the across-trial mean within each peak window. The per-trial "
            "metric matrices stack every event's trials along the trials axis (labeled by the per-trial "
            "'event' reference); the mean_* metrics hold one column per event ('summary_event')."
        ),
        attributes=[
            NWBAttributeSpec(
                name="description", doc="Human-readable description of this peak/AUC summary.", dtype="text"
            ),
            trace_type_attr(),
            NWBAttributeSpec(name="unit", doc="Unit of the peak/area values (matches the trace_type).", dtype="text"),
        ],
        datasets=[
            recording_site_region(
                doc="Reference to the GuppyRecordingSitesTable row for this summary's recording site (single row)."
            ),
            event_region(
                doc=(
                    "Per-trial reference into GuppyEventsTable: one row per trial (shape (num_trials,)), "
                    "labeling which event each column of the per-trial metric matrices was aligned to."
                ),
            ),
            event_region(
                name="summary_event",
                doc=(
                    "Per-summary-column reference into GuppyEventsTable: one row per event type "
                    "(shape (num_events,)), labeling the columns of the mean_* metrics."
                ),
            ),
            NWBDatasetSpec(
                name="window_start",
                doc="Start of each peak window in seconds (relative to event onset), shape (num_windows,).",
                dtype="float64",
                shape=(None,),
                dims=("num_windows",),
            ),
            NWBDatasetSpec(
                name="window_stop",
                doc="Stop of each peak window in seconds (relative to event onset), shape (num_windows,).",
                dtype="float64",
                shape=(None,),
                dims=("num_windows",),
            ),
            NWBDatasetSpec(
                name="trial_onset_times",
                doc=(
                    "Absolute onset time of each trial in seconds (session clock), shape (num_trials,), "
                    "concatenated across events in the same order as the per-trial metric columns."
                ),
                dtype="float64",
                shape=(None,),
                dims=("num_trials",),
            ),
            NWBDatasetSpec(
                name="peak_positive",
                doc=(
                    "Per-trial maximum within each window, shape (num_windows, num_trials), "
                    "concatenated across events."
                ),
                dtype="float64",
                shape=(None, None),
                dims=("num_windows", "num_trials"),
            ),
            NWBDatasetSpec(
                name="peak_negative",
                doc=(
                    "Per-trial minimum within each window, shape (num_windows, num_trials), "
                    "concatenated across events."
                ),
                dtype="float64",
                shape=(None, None),
                dims=("num_windows", "num_trials"),
            ),
            NWBDatasetSpec(
                name="area_under_curve",
                doc=(
                    "Per-trial area within each window (trapezoidal), shape (num_windows, num_trials), "
                    "concatenated across events."
                ),
                dtype="float64",
                shape=(None, None),
                dims=("num_windows", "num_trials"),
            ),
            NWBDatasetSpec(
                name="mean_peak_positive",
                doc=(
                    "Across-trial-mean trace maximum within each window, one column per event, "
                    "shape (num_windows, num_events)."
                ),
                dtype="float64",
                shape=(None, None),
                dims=("num_windows", "num_events"),
            ),
            NWBDatasetSpec(
                name="mean_peak_negative",
                doc=(
                    "Across-trial-mean trace minimum within each window, one column per event, "
                    "shape (num_windows, num_events)."
                ),
                dtype="float64",
                shape=(None, None),
                dims=("num_windows", "num_events"),
            ),
            NWBDatasetSpec(
                name="mean_area_under_curve",
                doc=(
                    "Across-trial-mean trace area within each window (trapezoidal), one column per event, "
                    "shape (num_windows, num_events)."
                ),
                dtype="float64",
                shape=(None, None),
                dims=("num_windows", "num_events"),
            ),
            NWBDatasetSpec(
                name="bin_edges",
                doc=(
                    "Optional bin definitions, shape (num_bins, 2), concatenated across events. Each row is "
                    "[start, stop); interpreted as trial-index ranges or time ranges according to the "
                    "bin_basis attribute. See the 'bin_event' reference for each bin's event."
                ),
                dtype="float64",
                shape=(None, 2),
                dims=("num_bins", "start_stop"),
                quantity="?",
                attributes=[
                    NWBAttributeSpec(
                        name="bin_basis", doc="Whether bins are defined over 'trials' or 'time'.", dtype="text"
                    )
                ],
            ),
            event_region(
                name="bin_event",
                quantity="?",
                doc=(
                    "Per-bin reference into GuppyEventsTable: one row per bin (shape (num_bins,)), labeling "
                    "the columns of the binned_* metrics."
                ),
            ),
            NWBDatasetSpec(
                name="binned_peak_positive",
                doc=(
                    "Optional per-bin (binned-mean trace) maximum within each window, shape "
                    "(num_windows, num_bins), concatenated across events."
                ),
                dtype="float64",
                shape=(None, None),
                dims=("num_windows", "num_bins"),
                quantity="?",
            ),
            NWBDatasetSpec(
                name="binned_peak_negative",
                doc=(
                    "Optional per-bin (binned-mean trace) minimum within each window, shape "
                    "(num_windows, num_bins), concatenated across events."
                ),
                dtype="float64",
                shape=(None, None),
                dims=("num_windows", "num_bins"),
                quantity="?",
            ),
            NWBDatasetSpec(
                name="binned_area_under_curve",
                doc=(
                    "Optional per-bin (binned-mean trace) area within each window, shape "
                    "(num_windows, num_bins), concatenated across events."
                ),
                dtype="float64",
                shape=(None, None),
                dims=("num_windows", "num_bins"),
                quantity="?",
            ),
        ],
    )

    guppy_psth_significance = NWBGroupSpec(
        neurodata_type_def="GuppyPSTHSignificance",
        neurodata_type_inc="NWBDataInterface",
        doc=(
            "Bootstrap significance of a baseline-corrected PSTH for one (recording_site, trace_type) "
            "condition, concatenated across comparisons, stored as samples-by-comparisons matrices over "
            "the peri-event time axis. Each comparison tests one event's mean PSTH against zero, or -- "
            "when the 'event_b' reference is present -- one event's mean PSTH against another's. The "
            "interval is a bias-corrected and accelerated (BCa) bootstrap over trials at each timepoint, "
            "and 'significant' marks a timepoint only when its interval excludes zero as part of a run "
            "longer than twice the moving-average filter window, which is what controls the many "
            "comparisons along the time axis. Timepoints where too few trials overlap to resample carry "
            "a NaN interval and are reported as not significant. The events tested here are a subset of "
            "the matching GuppyPSTH's: GuPPy skips a comparison whose event has fewer than three trials "
            "rather than writing an unreliable one. Sourced from "
            "psth_significance_output/significance_<comparison>.h5."
        ),
        attributes=[
            NWBAttributeSpec(
                name="description", doc="Human-readable description of this significance result.", dtype="text"
            ),
            trace_type_attr(),
            NWBAttributeSpec(
                name="unit", doc="Unit of the estimate and its interval bounds (typically 'a.u.').", dtype="text"
            ),
        ],
        datasets=[
            recording_site_region(
                doc="Reference to the GuppyRecordingSitesTable row these comparisons were computed on.",
            ),
            event_region(
                doc=(
                    "Per-comparison reference into GuppyEventsTable: one row per comparison "
                    "(shape (num_comparisons,)), labeling the event each column was computed for. For a "
                    "two-event comparison this is event A, the one 'estimate' is positive for."
                ),
            ),
            event_region(
                name="event_b",
                quantity="?",
                doc=(
                    "Per-comparison reference into GuppyEventsTable for the second event of a two-event "
                    "comparison (shape (num_comparisons,)). Present only on an object holding event-versus-"
                    "event comparisons; its absence means every column was tested against zero."
                ),
            ),
            NWBDatasetSpec(
                name="peri_event_time",
                doc=(
                    "Peri-event time axis in seconds relative to event onset, shape (num_samples,). The same "
                    "axis as the matching GuppyPSTH's."
                ),
                dtype="float64",
                shape=(None,),
                dims=("num_samples",),
            ),
            NWBDatasetSpec(
                name="estimate",
                doc=(
                    "The quantity the interval was computed on, shape (num_samples, num_comparisons). Time is "
                    "the first axis. For a test against zero this is the across-trial mean PSTH; for a "
                    "two-event comparison it is event A's mean minus event B's."
                ),
                dtype="float64",
                shape=(None, None),
                dims=("num_samples", "num_comparisons"),
            ),
            NWBDatasetSpec(
                name="confidence_interval_lower",
                doc=(
                    "Lower BCa bootstrap bound on 'estimate', shape (num_samples, num_comparisons). NaN where "
                    "too few trials overlap to resample, which happens at the window edges and wherever "
                    "artifact removal blanked a stretch."
                ),
                dtype="float64",
                shape=(None, None),
                dims=("num_samples", "num_comparisons"),
            ),
            NWBDatasetSpec(
                name="confidence_interval_upper",
                doc=(
                    "Upper BCa bootstrap bound on 'estimate', shape (num_samples, num_comparisons). NaN "
                    "wherever the lower bound is."
                ),
                dtype="float64",
                shape=(None, None),
                dims=("num_samples", "num_comparisons"),
            ),
            NWBDatasetSpec(
                name="significant",
                doc=(
                    "Whether each timepoint fell inside a significant stretch, shape "
                    "(num_samples, num_comparisons). True requires both that the interval excludes zero and "
                    "that the run of such timepoints is longer than twice the moving-average filter window; "
                    "a shorter run is discarded along with the chance hits it cannot be told apart from. A "
                    "stretch says the effect lies somewhere within it, not that it begins at its left edge."
                ),
                dtype="bool",
                shape=(None, None),
                dims=("num_samples", "num_comparisons"),
            ),
            NWBDatasetSpec(
                name="num_trials",
                doc=(
                    "Number of trials resampled for each comparison, shape (num_comparisons,). For a "
                    "two-event comparison this is event A's trial count. Between three and five the interval "
                    "is driven by a handful of distinct resamples and is unreliable."
                ),
                dtype="int32",
                shape=(None,),
                dims=("num_comparisons",),
            ),
            NWBDatasetSpec(
                name="num_trials_b",
                doc=(
                    "Number of event B trials resampled for each comparison, shape (num_comparisons,). "
                    "Present only alongside 'event_b'."
                ),
                dtype="int32",
                shape=(None,),
                dims=("num_comparisons",),
                quantity="?",
            ),
        ],
    )

    guppy_valid_signal_intervals = NWBGroupSpec(
        neurodata_type_def="GuppyValidSignalIntervals",
        neurodata_type_inc="TimeIntervals",
        doc=(
            "Time intervals retained as valid signal (not removed as artifacts) during GuPPy "
            "preprocessing, one row per interval with a structured recording-site reference. Sourced "
            "from coordsForPreProcessing_<recording_site>.npy; the removal method is recorded once on "
            "GuppyParameters.artifacts_removal_method."
        ),
        datasets=[
            NWBDatasetSpec(
                name="recording_site",
                neurodata_type_inc="DynamicTableRegion",
                doc="Reference to the GuppyRecordingSitesTable row this interval applies to.",
            ),
        ],
    )

    guppy_tonic_epochs = NWBGroupSpec(
        neurodata_type_def="GuppyTonicEpochs",
        neurodata_type_inc="TimeIntervals",
        doc=(
            "Mean level of a GuPPy normalized trace within each user-defined tonic epoch window, for "
            "pharmacological experiments that care about slow shifts in the overall fluorescence level "
            "rather than event-triggered transients. One row per (recording_site, epoch, trace_type): "
            "the windows are defined per recording site, and recording_site and trace_type vary per row, "
            "so they are columns. Sourced from tonic_epochs_<recording_site>.csv and "
            "tonic_<recording_site>.h5."
        ),
        datasets=[
            NWBDatasetSpec(
                name="recording_site",
                neurodata_type_inc="DynamicTableRegion",
                doc="Reference to the GuppyRecordingSitesTable row this epoch window applies to.",
            ),
            NWBDatasetSpec(
                name="label",
                neurodata_type_inc="VectorData",
                doc="The epoch's GuPPy label (e.g. 'baseline').",
                dtype="text",
            ),
            NWBDatasetSpec(
                name="trace_type",
                neurodata_type_inc="VectorData",
                doc=TRACE_TYPE_DOC,
                dtype="text",
            ),
            NWBDatasetSpec(
                name="mean",
                neurodata_type_inc="VectorData",
                doc="Mean of the trace over the epoch window.",
                dtype="float64",
            ),
        ],
    )

    guppy_binned_metrics = NWBGroupSpec(
        neurodata_type_def="GuppyBinnedMetrics",
        neurodata_type_inc="TimeIntervals",
        doc=(
            "Whole-session GuPPy metrics reduced to fixed-width time bins, for asking how the signal "
            "tracks a slowly varying quantity rather than how it responds to an event. One row per "
            "(recording_site, bin, trace_type): the bins are tiled per recording site, and "
            "recording_site and trace_type vary per row, so they are columns. Sourced from "
            "binned_metrics_<recording_site>.h5; the bin width is recorded once on "
            "GuppyParameters.binned_metrics_width."
        ),
        datasets=[
            NWBDatasetSpec(
                name="recording_site",
                neurodata_type_inc="DynamicTableRegion",
                doc="Reference to the GuppyRecordingSitesTable row this bin applies to.",
            ),
            NWBDatasetSpec(
                name="trace_type",
                neurodata_type_inc="VectorData",
                doc=TRACE_TYPE_DOC,
                dtype="text",
            ),
            NWBDatasetSpec(
                name="mean",
                neurodata_type_inc="VectorData",
                doc="Mean of the trace over the bin, NaN for a bin holding no sample.",
                dtype="float64",
            ),
            NWBDatasetSpec(
                name="transient_count",
                neurodata_type_inc="VectorData",
                doc=(
                    "Number of transients detected in the bin, NaN for a trace the transient detector "
                    "did not run on."
                ),
                dtype="float64",
            ),
            NWBDatasetSpec(
                name="n_samples",
                neurodata_type_inc="VectorData",
                doc=(
                    "Number of finite samples behind the mean. A property of the bin, so it repeats "
                    "across that bin's rows; 0 for a bin lost to artifact removal."
                ),
                dtype="int32",
            ),
        ],
    )

    guppy_binned_covariates = NWBGroupSpec(
        neurodata_type_def="GuppyBinnedCovariates",
        neurodata_type_inc="TimeIntervals",
        doc=(
            "A behavioral covariate -- a continuous variable scored outside the rig -- averaged onto the "
            "same bins as GuppyBinnedMetrics. One row per (recording_site, bin, covariate). Sourced from "
            "binned_covariates_<recording_site>.h5."
        ),
        datasets=[
            NWBDatasetSpec(
                name="recording_site",
                neurodata_type_inc="DynamicTableRegion",
                doc="Reference to the GuppyRecordingSitesTable row whose bins this row is on.",
            ),
            covariate_reference(
                "Reference to the TimeSeries holding this covariate's scored values, which is its identity."
            ),
            NWBDatasetSpec(
                name="mean",
                neurodata_type_inc="VectorData",
                doc="Mean of the covariate's scores over the bin, NaN for a bin holding no score.",
                dtype="float64",
            ),
            NWBDatasetSpec(
                name="n_samples",
                neurodata_type_inc="VectorData",
                doc="Number of the covariate's scores that fell in the bin.",
                dtype="int32",
            ),
        ],
    )

    guppy_covariate_correlations = NWBGroupSpec(
        neurodata_type_def="GuppyCovariateCorrelations",
        neurodata_type_inc="DynamicTable",
        doc=(
            "Correlation of each behavioral covariate against each per-bin GuPPy metric, one row per "
            "(recording_site, trace_type, metric, covariate) -- naming exactly the GuppyBinnedMetrics "
            "rows the coefficients were computed over. The coefficients are descriptive: successive "
            "bins of both series are autocorrelated, which the standard significance tests assume they "
            "are not, so GuPPy reports no p-value and one must not be derived from these columns. "
            "Sourced from covariate_correlations_<recording_site>.h5."
        ),
        datasets=[
            NWBDatasetSpec(
                name="recording_site",
                neurodata_type_inc="DynamicTableRegion",
                doc="Reference to the GuppyRecordingSitesTable row this correlation was computed on.",
            ),
            NWBDatasetSpec(
                name="trace_type",
                neurodata_type_inc="VectorData",
                doc=TRACE_TYPE_DOC,
                dtype="text",
            ),
            NWBDatasetSpec(
                name="metric",
                neurodata_type_inc="VectorData",
                doc=(
                    "The GuppyBinnedMetrics column the covariate was correlated against. Controlled "
                    "vocabulary: 'mean' or 'transient_count'."
                ),
                dtype="text",
            ),
            covariate_reference("Reference to the TimeSeries holding the correlated covariate's scored values."),
            NWBDatasetSpec(
                name="pearson_r",
                neurodata_type_inc="VectorData",
                doc="Pearson correlation coefficient, NaN when either series is constant.",
                dtype="float64",
            ),
            NWBDatasetSpec(
                name="spearman_rho",
                neurodata_type_inc="VectorData",
                doc="Spearman rank correlation coefficient, NaN when either series is constant.",
                dtype="float64",
            ),
            NWBDatasetSpec(
                name="n_bins",
                neurodata_type_inc="VectorData",
                doc=(
                    "Number of bins where both the metric and the covariate are present -- the sample "
                    "size behind the two coefficients."
                ),
                dtype="int32",
            ),
        ],
    )

    # ------------------------------------------------------------------ #
    # Parameters
    # ------------------------------------------------------------------ #
    def opt_float(name, doc):
        return NWBAttributeSpec(name=name, doc=doc, dtype="float64", required=False)

    guppy_parameters = NWBGroupSpec(
        neurodata_type_def="GuppyParameters",
        neurodata_type_inc="LabMetaData",
        doc=(
            "Typed GuPPy processing parameters for the session (from GuPPyParamtersUsed.json). One per "
            "session; applies to the co-located GuPPy products."
        ),
        attributes=[
            NWBAttributeSpec(name="guppy_version", doc="GuPPy version string.", dtype="text", required=False),
            NWBAttributeSpec(name="zscore_method", doc="Z-score computation method.", dtype="text", required=False),
            opt_float("baseline_window_start", "Baseline window start (seconds) for normalization."),
            opt_float("baseline_window_end", "Baseline window end (seconds) for normalization."),
            opt_float("filter_window", "Filtering window used for the control fit."),
            NWBAttributeSpec(
                name="isosbestic_control",
                doc="Whether an isosbestic control channel was used (vs a synthetic fit).",
                dtype="bool",
                required=False,
            ),
            NWBAttributeSpec(
                name="remove_artifacts", doc="Whether artifact removal was performed.", dtype="bool", required=False
            ),
            NWBAttributeSpec(
                name="artifacts_removal_method",
                doc="Artifact removal method (e.g. 'concatenate' or 'replace with NaN').",
                dtype="text",
                required=False,
            ),
            opt_float("transients_thresh", "Transient detection threshold."),
            opt_float("high_amp_filt", "High-amplitude filter for transient detection."),
            opt_float("moving_window", "Moving window for transient detection."),
            opt_float("n_sec_prev", "Seconds before event onset for PSTH windows."),
            opt_float("n_sec_post", "Seconds after event onset for PSTH windows."),
            opt_float("time_interval", "Minimum inter-event interval for PSTH trial inclusion (seconds)."),
            NWBAttributeSpec(
                name="bin_psth_trials",
                doc="Number of trials per PSTH bin (0 if unbinned).",
                dtype="int32",
                required=False,
            ),
            opt_float("baseline_correction_start", "PSTH baseline-correction window start (seconds)."),
            opt_float("baseline_correction_end", "PSTH baseline-correction window end (seconds)."),
            NWBAttributeSpec(
                name="compute_binned_metrics",
                doc="Whether whole-session time-binned metrics were computed.",
                dtype="bool",
                required=False,
            ),
            opt_float("binned_metrics_width", "Width of the whole-session time bins (seconds)."),
            NWBAttributeSpec(
                name="use_transients_as_events",
                doc="Whether detected transients stood in for behavioral events (spontaneous mode).",
                dtype="bool",
                required=False,
            ),
            NWBAttributeSpec(
                name="compute_psth_significance",
                doc="Whether bootstrap significance testing was run on the PSTHs.",
                dtype="bool",
                required=False,
            ),
            opt_float(
                "psth_significance_alpha",
                "Two-sided threshold the PSTH significance intervals were computed at.",
            ),
            NWBAttributeSpec(
                name="psth_bootstrap_resamples",
                doc="Number of resamples each PSTH significance interval was built from.",
                dtype="int32",
                required=False,
            ),
        ],
        datasets=[
            NWBDatasetSpec(
                name="peak_start_points",
                doc="Optional peak/AUC window start points (seconds), shape (num_windows,).",
                dtype="float64",
                shape=(None,),
                dims=("num_windows",),
                quantity="?",
            ),
            NWBDatasetSpec(
                name="peak_end_points",
                doc="Optional peak/AUC window end points (seconds), shape (num_windows,).",
                dtype="float64",
                shape=(None,),
                dims=("num_windows",),
                quantity="?",
            ),
            NWBDatasetSpec(
                name="psth_comparison_events_a",
                doc=(
                    "Optional first event of each event-versus-event PSTH comparison that was requested, "
                    "shape (num_comparisons,). Paired elementwise with psth_comparison_events_b. This is "
                    "what was asked for rather than what was produced: a pair whose event had fewer than "
                    "three trials is skipped, so it appears here but in no GuppyPSTHSignificance object."
                ),
                dtype="text",
                shape=(None,),
                dims=("num_comparisons",),
                quantity="?",
            ),
            NWBDatasetSpec(
                name="psth_comparison_events_b",
                doc=(
                    "Optional second event of each event-versus-event PSTH comparison that was requested, "
                    "shape (num_comparisons,)."
                ),
                dtype="text",
                shape=(None,),
                dims=("num_comparisons",),
                quantity="?",
            ),
        ],
    )

    new_data_types = [
        guppy_recording_sites_table,
        guppy_events_table,
        guppy_derived_response_series,
        guppy_transients_table,
        guppy_transient_summary_table,
        guppy_psth,
        guppy_cross_correlation,
        guppy_peak_auc,
        guppy_psth_significance,
        guppy_valid_signal_intervals,
        guppy_tonic_epochs,
        guppy_binned_metrics,
        guppy_binned_covariates,
        guppy_covariate_correlations,
        guppy_parameters,
    ]

    # export the spec to yaml files in the root spec folder
    output_dir = str((Path(__file__).parent.parent.parent / "spec").absolute())
    export_spec(ns_builder, new_data_types, output_dir)


if __name__ == "__main__":
    # usage: python create_extension_spec.py
    main()
