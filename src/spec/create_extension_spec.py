# -*- coding: utf-8 -*-
"""Create the ndx-guppy extension spec.

ndx-guppy provides dedicated neurodata types for the derived outputs of the GuPPy
fiber-photometry processing tool. The design turns GuPPy's organizing features --
``region``, ``trace_type``, and ``event`` -- into structured, queryable NWB features:

- *region* and *event* are entities, so they live as rows in registry tables
  (``GuppyRegionsTable``, ``GuppyEventsTable``) and are referenced via ``DynamicTableRegion``.
- *trace_type* is a closed category, so it is a plain enumerated text attribute stamped
  directly on each object (values: ``control_fit`` / ``dff`` / ``z_score``).

Cross-extension dependencies are quarantined: products reference ndx-guppy's own registry
tables, and any outward link (to the acquisition ``FiberPhotometryTable`` or to an
``ndx_events.Events`` object) is an optional column on a registry.
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


def region_region(doc, quantity=1):
    """A ``DynamicTableRegion`` referencing rows of the ``GuppyRegionsTable``."""
    return NWBDatasetSpec(name="region", neurodata_type_inc="DynamicTableRegion", doc=doc, quantity=quantity)


def event_region(doc, quantity=1):
    """A ``DynamicTableRegion`` referencing a row of the ``GuppyEventsTable``."""
    return NWBDatasetSpec(name="event", neurodata_type_inc="DynamicTableRegion", doc=doc, quantity=quantity)


def main():
    ns_builder = NWBNamespaceBuilder(
        name="""ndx-guppy""",
        version="""0.1.0""",
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
    guppy_regions_table = NWBGroupSpec(
        neurodata_type_def="GuppyRegionsTable",
        neurodata_type_inc="DynamicTable",
        doc=(
            "Registry of GuPPy logical regions (one row per region, e.g. 'dms'). A GuPPy region is a "
            "processing-level entity -- a signal+isosbestic pair collapsed into one derived signal -- "
            "so it is the canonical region identity that GuPPy products reference."
        ),
        datasets=[
            NWBDatasetSpec(
                name="region",
                neurodata_type_inc="VectorData",
                doc="The semantic region name from storesList.csv (e.g. 'dms'). The region's identity.",
                dtype="text",
            ),
            NWBDatasetSpec(
                name="raw_store_name",
                neurodata_type_inc="VectorData",
                doc="Optional raw acquisition channel/store name from storesList.csv (e.g. 'Dv2A').",
                dtype="text",
                quantity="?",
            ),
            NWBDatasetSpec(
                name="fiber_photometry_table_region",
                neurodata_type_inc="DynamicTableRegion",
                doc=(
                    "Optional ragged reference into the acquisition FiberPhotometryTable (the signal + "
                    "isosbestic fiber rows for this region). Absorbs the signal/control many-to-one mapping "
                    "once, here, so products reference a single region row. Anatomical location is reached "
                    "through this link (the fiber's 'location'), not duplicated."
                ),
                quantity="?",
            ),
            NWBDatasetSpec(
                name="fiber_photometry_table_region_index",
                neurodata_type_inc="VectorIndex",
                doc="Ragged index for fiber_photometry_table_region (multiple fiber rows per region).",
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
                name="event_description",
                neurodata_type_inc="VectorData",
                doc="Human-readable description of the event.",
                dtype="text",
            ),
            NWBDatasetSpec(
                name="raw_store_name",
                neurodata_type_inc="VectorData",
                doc="Optional raw acquisition channel/store name from storesList.csv (e.g. 'PrtN').",
                dtype="text",
                quantity="?",
            ),
            NWBDatasetSpec(
                name="events",
                neurodata_type_inc="VectorData",
                doc=(
                    "Optional object reference to the behavioral-event object holding this event's onset "
                    "timestamps (e.g. an ndx_events.Events object in the behavior module). Kept as a generic "
                    "object reference so ndx-guppy takes no hard dependency on ndx-events."
                ),
                dtype=NWBRefSpec(target_type="NWBDataInterface", reftype="object"),
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
            "A GuPPy-derived continuous trace (control_fit, dff, or z_score) for one region. Extends "
            "FiberPhotometryResponseSeries to stamp the trace_type and to reference the GuPPy regions "
            "registry; the inherited fiber_photometry_table_region still carries the physical "
            "signal+isosbestic fiber provenance."
        ),
        attributes=[trace_type_attr()],
        datasets=[
            region_region(
                doc="Reference to the GuppyRegionsTable row for this trace's region (single row).",
            ),
        ],
    )

    # ------------------------------------------------------------------ #
    # Analysis products
    # ------------------------------------------------------------------ #
    guppy_transients_table = NWBGroupSpec(
        neurodata_type_def="GuppyTransientsTable",
        neurodata_type_inc="DynamicTable",
        doc="GuPPy-detected transient peaks for one (region, trace_type).",
        attributes=[
            trace_type_attr(),
            NWBAttributeSpec(name="unit", doc="Unit of the amplitude (matches the trace_type).", dtype="text"),
        ],
        datasets=[
            region_region(doc="Reference to the GuppyRegionsTable row for this table's region (single row)."),
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
            "Per-session GuPPy transient summary: one row per (region, trace_type) with event frequency and "
            "mean peak amplitude. region and trace_type vary per row, so they are columns."
        ),
        datasets=[
            NWBDatasetSpec(
                name="region",
                neurodata_type_inc="DynamicTableRegion",
                doc="Reference to the GuppyRegionsTable row for this summary row's region.",
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
            "Peri-event PSTH for one (event, region, trace_type), stored as a natural samples-by-trials "
            "matrix. The baseline-uncorrected variant is a second GuppyPSTH with baseline_corrected=False."
        ),
        attributes=[
            trace_type_attr(),
            NWBAttributeSpec(
                name="baseline_corrected",
                doc="Whether per-trial baseline correction was applied.",
                dtype="bool",
            ),
            NWBAttributeSpec(
                name="unit", doc="Unit of the PSTH values (matches the trace_type).", dtype="text"
            ),
        ],
        datasets=[
            region_region(doc="Reference to the GuppyRegionsTable row for this PSTH's region (single row)."),
            event_region(doc="Reference to the GuppyEventsTable row for this PSTH's event (single row)."),
            NWBDatasetSpec(
                name="peri_event_time",
                doc="Peri-event time axis in seconds (relative to event onset), shape (num_samples,).",
                dtype="float64",
                shape=(None,),
                dims=("num_samples",),
            ),
            NWBDatasetSpec(
                name="trial_onset_times",
                doc="Absolute onset time of each trial in seconds (session clock), shape (num_trials,).",
                dtype="float64",
                shape=(None,),
                dims=("num_trials",),
            ),
            NWBDatasetSpec(
                name="traces",
                doc="Per-trial response, shape (num_samples, num_trials). Time is the first axis.",
                dtype="float64",
                shape=(None, None),
                dims=("num_samples", "num_trials"),
            ),
            NWBDatasetSpec(
                name="mean",
                doc="Across-trial mean at each peri-event time, shape (num_samples,).",
                dtype="float64",
                shape=(None,),
                dims=("num_samples",),
            ),
            NWBDatasetSpec(
                name="error",
                doc="Across-trial error (e.g. SEM) at each peri-event time, shape (num_samples,).",
                dtype="float64",
                shape=(None,),
                dims=("num_samples",),
            ),
            NWBDatasetSpec(
                name="bin_edges",
                doc=(
                    "Optional bin definitions, shape (num_bins, 2). Each row is [start, stop); interpreted as "
                    "trial-index ranges or time ranges according to the bin_basis attribute."
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
            NWBDatasetSpec(
                name="binned_mean",
                doc="Optional per-bin mean, shape (num_samples, num_bins).",
                dtype="float64",
                shape=(None, None),
                dims=("num_samples", "num_bins"),
                quantity="?",
            ),
            NWBDatasetSpec(
                name="binned_error",
                doc="Optional per-bin error, shape (num_samples, num_bins).",
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
            "Peri-event cross-correlation for one (event, trace_type, region-pair), stored as a "
            "samples-by-trials matrix over a lag axis. The region reference points at two rows "
            "(region_1, region_2)."
        ),
        attributes=[
            trace_type_attr(),
            NWBAttributeSpec(
                name="unit", doc="Unit of the cross-correlation values (normalized; typically 'a.u.').", dtype="text"
            ),
        ],
        datasets=[
            region_region(
                doc="Reference to the two GuppyRegionsTable rows (region_1, region_2) for this cross-correlation.",
            ),
            event_region(doc="Reference to the GuppyEventsTable row for this cross-correlation's event (single row)."),
            NWBDatasetSpec(
                name="lag",
                doc="Lag axis in seconds (symmetric around zero), shape (num_lags,).",
                dtype="float64",
                shape=(None,),
                dims=("num_lags",),
            ),
            NWBDatasetSpec(
                name="trials",
                doc="Per-trial cross-correlation, shape (num_lags, num_trials). Lag is the first axis.",
                dtype="float64",
                shape=(None, None),
                dims=("num_lags", "num_trials"),
            ),
            NWBDatasetSpec(
                name="mean",
                doc="Across-trial mean cross-correlation at each lag, shape (num_lags,).",
                dtype="float64",
                shape=(None,),
                dims=("num_lags",),
            ),
            NWBDatasetSpec(
                name="error",
                doc="Across-trial error at each lag, shape (num_lags,).",
                dtype="float64",
                shape=(None,),
                dims=("num_lags",),
            ),
            NWBDatasetSpec(
                name="bin_edges",
                doc=(
                    "Optional bin definitions, shape (num_bins, 2). Each row is [start, stop); interpreted as "
                    "trial-index ranges or time ranges according to the bin_basis attribute."
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
            NWBDatasetSpec(
                name="binned_mean",
                doc="Optional per-bin mean, shape (num_lags, num_bins).",
                dtype="float64",
                shape=(None, None),
                dims=("num_lags", "num_bins"),
                quantity="?",
            ),
            NWBDatasetSpec(
                name="binned_error",
                doc="Optional per-bin error, shape (num_lags, num_bins).",
                dtype="float64",
                shape=(None, None),
                dims=("num_lags", "num_bins"),
                quantity="?",
            ),
        ],
    )

    guppy_peak_auc = NWBGroupSpec(
        neurodata_type_def="GuppyPeakAUC",
        neurodata_type_inc="DynamicTable",
        doc=(
            "Peak and area-under-curve summary of a peri-event PSTH for one (event, region, trace_type); "
            "one row per peak window."
        ),
        attributes=[
            trace_type_attr(),
            NWBAttributeSpec(
                name="unit", doc="Unit of the peak/area values (matches the trace_type).", dtype="text"
            ),
        ],
        datasets=[
            region_region(doc="Reference to the GuppyRegionsTable row for this summary's region (single row)."),
            event_region(doc="Reference to the GuppyEventsTable row for this summary's event (single row)."),
            NWBDatasetSpec(
                name="window_start",
                neurodata_type_inc="VectorData",
                doc="Start of the peak window in seconds (relative to event onset).",
                dtype="float64",
            ),
            NWBDatasetSpec(
                name="window_stop",
                neurodata_type_inc="VectorData",
                doc="Stop of the peak window in seconds (relative to event onset).",
                dtype="float64",
            ),
            NWBDatasetSpec(
                name="peak_positive",
                neurodata_type_inc="VectorData",
                doc="Maximum value of the PSTH mean within the window.",
                dtype="float64",
            ),
            NWBDatasetSpec(
                name="peak_negative",
                neurodata_type_inc="VectorData",
                doc="Minimum value of the PSTH mean within the window.",
                dtype="float64",
            ),
            NWBDatasetSpec(
                name="area_under_curve",
                neurodata_type_inc="VectorData",
                doc="Area under the PSTH mean within the window (trapezoidal).",
                dtype="float64",
            ),
        ],
    )

    guppy_valid_signal_intervals = NWBGroupSpec(
        neurodata_type_def="GuppyValidSignalIntervals",
        neurodata_type_inc="TimeIntervals",
        doc=(
            "Time intervals retained as valid signal (not removed as artifacts) during GuPPy preprocessing, "
            "with a structured region reference per interval."
        ),
        datasets=[
            NWBDatasetSpec(
                name="region",
                neurodata_type_inc="DynamicTableRegion",
                doc="Reference to the GuppyRegionsTable row the interval applies to.",
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
        ],
    )

    new_data_types = [
        guppy_regions_table,
        guppy_events_table,
        guppy_derived_response_series,
        guppy_transients_table,
        guppy_transient_summary_table,
        guppy_psth,
        guppy_cross_correlation,
        guppy_peak_auc,
        guppy_valid_signal_intervals,
        guppy_parameters,
    ]

    # export the spec to yaml files in the root spec folder
    output_dir = str((Path(__file__).parent.parent.parent / "spec").absolute())
    export_spec(ns_builder, new_data_types, output_dir)


if __name__ == "__main__":
    # usage: python create_extension_spec.py
    main()
