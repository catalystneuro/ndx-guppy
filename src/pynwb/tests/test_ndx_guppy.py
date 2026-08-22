"""Unit and roundtrip tests for the ndx-guppy neurodata types.

The tests are organized one ``Test<ClassName>`` class per neurodata type. Shared setup
(an NWBFile, the two registry tables, a roundtrip helper) lives in module-level fixtures.
"""

import numpy as np
import pytest

from pynwb import NWBHDF5IO, TimeSeries
from pynwb.event import EventsTable
from pynwb.testing.mock.file import mock_NWBFile
from hdmf.common import DynamicTable, VectorData
from hdmf.common.table import DynamicTableRegion

from ndx_guppy import (
    GuppyRecordingSitesTable,
    GuppyEventsTable,
    GuppyDerivedResponseSeries,
    GuppyTransientsTable,
    GuppyTransientSummaryTable,
    GuppyPSTH,
    GuppyCrossCorrelation,
    GuppyPeakAUC,
    GuppyValidSignalIntervals,
    GuppyTonicEpochs,
    GuppyBinnedMetrics,
    GuppyBinnedCovariates,
    GuppyCovariateCorrelations,
    GuppyParameters,
)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture
def nwbfile():
    return mock_NWBFile()


@pytest.fixture
def guppy_module(nwbfile):
    return nwbfile.create_processing_module(name="guppy", description="GuPPy-derived outputs")


def build_recording_sites_table():
    table = GuppyRecordingSitesTable(name="recording_sites", description="GuPPy recording sites")
    table.add_row(recording_site="dms")
    table.add_row(recording_site="dls")
    return table


def build_events_table():
    table = GuppyEventsTable(name="events", description="GuPPy behavioral events")
    table.add_row(event_name="port_entries")
    return table


def build_multi_events_table():
    """A two-event registry for the event-bearing products, which concatenate across events."""
    table = GuppyEventsTable(name="events", description="GuPPy behavioral events")
    table.add_row(event_name="port_entries")
    table.add_row(event_name="rewarded_nose_pokes")
    return table


@pytest.fixture
def recording_sites_table():
    return build_recording_sites_table()


@pytest.fixture
def events_table():
    return build_events_table()


@pytest.fixture
def multi_events_table():
    return build_multi_events_table()


@pytest.fixture
def covariate_series():
    """The TimeSeries a behavioral covariate's scores live in, which the covariate products reference."""
    return TimeSeries(
        name="akinesia",
        description="Akinesia severity, scored every two minutes.",
        data=[2.0, 3.0, 4.0],
        unit="a.u.",
        timestamps=[0.0, 120.0, 240.0],
    )


@pytest.fixture
def roundtrip(tmp_path):
    """Write an NWBFile, read it back, and return the read file. Open IO handles are closed at teardown."""
    open_ios = []

    def _roundtrip(nwbfile):
        path = str(tmp_path / "test.nwb")
        with NWBHDF5IO(path, mode="w") as io:
            io.write(nwbfile)
        read_io = NWBHDF5IO(path, mode="r", load_namespaces=True)
        open_ios.append(read_io)
        return read_io.read()

    yield _roundtrip
    for io in open_ios:
        io.close()


def build_dynamic_table_region(name, indices, table, description="dynamic table region reference"):
    return DynamicTableRegion(name=name, data=list(indices), description=description, table=table)


# --------------------------------------------------------------------------- #
# Registries
# --------------------------------------------------------------------------- #
class TestGuppyRecordingSitesTable:
    def test_constructor(self, recording_sites_table):
        assert list(recording_sites_table["recording_site"].data) == ["dms", "dls"]
        assert "fiber_photometry_table_region" not in recording_sites_table.colnames

    def test_roundtrip(self, nwbfile, guppy_module, recording_sites_table, roundtrip):
        guppy_module.add(recording_sites_table)
        read = roundtrip(nwbfile)
        read_table = read.processing["guppy"]["recording_sites"]
        assert list(read_table["recording_site"].data) == ["dms", "dls"]

    def test_optional_fiber_link_roundtrip(self, nwbfile, guppy_module, roundtrip):
        """The optional ragged fiber_photometry_table_region column roundtrips (stand-in target table)."""
        fiber_stand_in = DynamicTable(
            name="fiber_photometry_table",
            description="stand-in for the acquisition FiberPhotometryTable",
            columns=[VectorData(name="location", description="loc", data=["DMS", "DMS"])],
        )
        table = GuppyRecordingSitesTable(
            name="recording_sites",
            description="GuPPy recording sites",
            target_tables={"fiber_photometry_table_region": fiber_stand_in},
        )
        table.add_row(recording_site="dms", fiber_photometry_table_region=[0, 1])
        guppy_module.add(fiber_stand_in)
        guppy_module.add(table)

        read = roundtrip(nwbfile)
        read_table = read.processing["guppy"]["recording_sites"]
        # The ragged column is a VectorIndex over a DynamicTableRegion; check the stored target indices.
        column = read_table["fiber_photometry_table_region"]
        target_indices = column.target.data[:] if hasattr(column, "target") else column.data[:]
        assert list(target_indices) == [0, 1]


class TestGuppyEventsTable:
    def test_constructor(self, events_table):
        assert list(events_table["event_name"].data) == ["port_entries"]
        assert "events" not in events_table.colnames

    def test_roundtrip(self, nwbfile, guppy_module, events_table, roundtrip):
        guppy_module.add(events_table)
        read = roundtrip(nwbfile)
        read_table = read.processing["guppy"]["events"]
        assert list(read_table["event_name"].data) == ["port_entries"]

    def test_optional_events_link_roundtrip(self, nwbfile, guppy_module, roundtrip):
        """The optional ragged events DTR selects this type's occurrence rows in a merged EventsTable."""
        merged = EventsTable(name="BehavioralEvents", description="all behavioral events, one merged table")
        for timestamp in (10.0, 12.0, 20.0):  # rows 0, 1 are port_entries; row 2 is another type
            merged.add_row(timestamp=timestamp)
        nwbfile.add_events_table(merged)

        table = GuppyEventsTable(
            name="events",
            description="GuPPy behavioral events",
            target_tables={"events": merged},
        )
        table.add_row(event_name="port_entries", events=[0, 1])
        guppy_module.add(table)

        read = roundtrip(nwbfile)
        read_table = read.processing["guppy"]["events"]
        # The ragged column is a VectorIndex over a DynamicTableRegion; check the stored target indices.
        column = read_table["events"]
        target_indices = column.target.data[:] if hasattr(column, "target") else column.data[:]
        assert list(target_indices) == [0, 1]


class TestGuppyValidSignalIntervals:
    def test_roundtrip(self, nwbfile, guppy_module, recording_sites_table, roundtrip):
        """Each valid interval is a row referencing its recording site via a DynamicTableRegion."""
        guppy_module.add(recording_sites_table)
        intervals = GuppyValidSignalIntervals(
            name="valid_signal_intervals",
            description="Valid (artifact-free) signal intervals per recording site.",
            target_tables={"recording_site": recording_sites_table},
        )
        intervals.add_interval(start_time=0.0, stop_time=5.0, recording_site=0)
        intervals.add_interval(start_time=7.0, stop_time=12.0, recording_site=0)
        intervals.add_interval(start_time=1.0, stop_time=4.0, recording_site=1)
        guppy_module.add(intervals)

        read = roundtrip(nwbfile)
        read_intervals = read.processing["guppy"]["valid_signal_intervals"]
        np.testing.assert_array_equal(read_intervals["start_time"].data, [0.0, 7.0, 1.0])
        np.testing.assert_array_equal(read_intervals["stop_time"].data, [5.0, 12.0, 4.0])
        assert list(read_intervals["recording_site"].data) == [0, 0, 1]


class TestGuppyTonicEpochs:
    @staticmethod
    def _build(recording_sites_table):
        """Two epochs on 'dms' and one on 'dls', each with a z-score and a dF/F mean."""
        epochs = GuppyTonicEpochs(
            name="tonic_epochs",
            description="Mean trace level within each tonic epoch window.",
            target_tables={"recording_site": recording_sites_table},
        )
        epochs.add_interval(
            start_time=0.0, stop_time=600.0, label="baseline", trace_type="z_score", mean=-0.12, recording_site=0
        )
        epochs.add_interval(
            start_time=0.0, stop_time=600.0, label="baseline", trace_type="dff", mean=0.004, recording_site=0
        )
        epochs.add_interval(
            start_time=600.0,
            stop_time=1800.0,
            label="post_injection",
            trace_type="z_score",
            mean=1.83,
            recording_site=0,
        )
        epochs.add_interval(
            start_time=600.0, stop_time=1800.0, label="post_injection", trace_type="dff", mean=0.061, recording_site=0
        )
        epochs.add_interval(
            start_time=0.0, stop_time=900.0, label="baseline", trace_type="z_score", mean=-0.05, recording_site=1
        )
        return epochs

    def test_constructor(self, recording_sites_table):
        epochs = self._build(recording_sites_table)
        assert list(epochs["label"].data) == ["baseline", "baseline", "post_injection", "post_injection", "baseline"]
        assert list(epochs["trace_type"].data) == ["z_score", "dff", "z_score", "dff", "z_score"]
        np.testing.assert_allclose(epochs["mean"].data, [-0.12, 0.004, 1.83, 0.061, -0.05])

    def test_roundtrip(self, nwbfile, guppy_module, recording_sites_table, roundtrip):
        """Each row is one (recording_site, epoch, trace_type) mean over its window."""
        guppy_module.add(recording_sites_table)
        guppy_module.add(self._build(recording_sites_table))

        read = roundtrip(nwbfile)
        read_epochs = read.processing["guppy"]["tonic_epochs"]
        np.testing.assert_array_equal(read_epochs["start_time"].data, [0.0, 0.0, 600.0, 600.0, 0.0])
        np.testing.assert_array_equal(read_epochs["stop_time"].data, [600.0, 600.0, 1800.0, 1800.0, 900.0])
        assert list(read_epochs["label"].data) == [
            "baseline",
            "baseline",
            "post_injection",
            "post_injection",
            "baseline",
        ]
        assert list(read_epochs["trace_type"].data) == ["z_score", "dff", "z_score", "dff", "z_score"]
        np.testing.assert_allclose(read_epochs["mean"].data, [-0.12, 0.004, 1.83, 0.061, -0.05])
        assert list(read_epochs["recording_site"].data) == [0, 0, 0, 0, 1]
        # The reference resolves back to the recording sites registry.
        assert read_epochs["recording_site"].table["recording_site"].data[1] == "dls"


class TestGuppyBinnedMetrics:
    @staticmethod
    def _build(recording_sites_table):
        """Two bins on 'dms', each reduced to a z-score and a dF/F row."""
        binned = GuppyBinnedMetrics(
            name="binned_metrics",
            description="GuPPy metrics reduced to fixed-width time bins.",
            target_tables={"recording_site": recording_sites_table},
        )
        binned.add_interval(
            start_time=0.0,
            stop_time=60.0,
            trace_type="z_score",
            mean=0.4,
            transient_count=3.0,
            n_samples=600,
            recording_site=0,
        )
        # The detector did not run on dF/F, so that trace has no count.
        binned.add_interval(
            start_time=0.0,
            stop_time=60.0,
            trace_type="dff",
            mean=0.02,
            transient_count=float("nan"),
            n_samples=600,
            recording_site=0,
        )
        binned.add_interval(
            start_time=60.0,
            stop_time=95.0,
            trace_type="z_score",
            mean=-0.7,
            transient_count=1.0,
            n_samples=350,
            recording_site=0,
        )
        return binned

    def test_constructor(self, recording_sites_table):
        binned = self._build(recording_sites_table)
        assert list(binned["trace_type"].data) == ["z_score", "dff", "z_score"]
        np.testing.assert_allclose(binned["mean"].data, [0.4, 0.02, -0.7])

    def test_roundtrip(self, nwbfile, guppy_module, recording_sites_table, roundtrip):
        """Each row is one (recording_site, bin, trace_type); the short final bin keeps its true bounds."""
        guppy_module.add(recording_sites_table)
        guppy_module.add(self._build(recording_sites_table))

        read = roundtrip(nwbfile)
        read_binned = read.processing["guppy"]["binned_metrics"]
        np.testing.assert_array_equal(read_binned["start_time"].data, [0.0, 0.0, 60.0])
        np.testing.assert_array_equal(read_binned["stop_time"].data, [60.0, 60.0, 95.0])
        assert list(read_binned["trace_type"].data) == ["z_score", "dff", "z_score"]
        np.testing.assert_allclose(read_binned["mean"].data, [0.4, 0.02, -0.7])
        np.testing.assert_allclose(read_binned["transient_count"].data, [3.0, np.nan, 1.0])
        assert list(read_binned["n_samples"].data) == [600, 600, 350]
        assert list(read_binned["recording_site"].data) == [0, 0, 0]


class TestGuppyBinnedCovariates:
    @staticmethod
    def _build(recording_sites_table, covariate_series):
        """One covariate averaged onto two bins of 'dms'."""
        binned = GuppyBinnedCovariates(
            name="binned_covariates",
            description="A behavioral covariate averaged onto the binned-metrics bins.",
            target_tables={"recording_site": recording_sites_table},
        )
        binned.add_interval(
            start_time=0.0, stop_time=60.0, covariate=covariate_series, mean=2.5, n_samples=2, recording_site=0
        )
        # A bin holding no score reads NaN with a count of 0.
        binned.add_interval(
            start_time=60.0,
            stop_time=95.0,
            covariate=covariate_series,
            mean=float("nan"),
            n_samples=0,
            recording_site=0,
        )
        return binned

    def test_roundtrip(self, nwbfile, guppy_module, recording_sites_table, covariate_series, roundtrip):
        """The covariate column references the TimeSeries holding its scores, which is its identity."""
        guppy_module.add(recording_sites_table)
        guppy_module.add(covariate_series)
        guppy_module.add(self._build(recording_sites_table, covariate_series))

        read = roundtrip(nwbfile)
        read_binned = read.processing["guppy"]["binned_covariates"]
        np.testing.assert_array_equal(read_binned["start_time"].data, [0.0, 60.0])
        np.testing.assert_allclose(read_binned["mean"].data, [2.5, np.nan])
        assert list(read_binned["n_samples"].data) == [2, 0]
        assert [reference.name for reference in read_binned["covariate"].data] == ["akinesia", "akinesia"]
        np.testing.assert_allclose(read_binned["covariate"].data[0].data[:], [2.0, 3.0, 4.0])


class TestGuppyCovariateCorrelations:
    @staticmethod
    def _build(recording_sites_table, covariate_series):
        """One covariate correlated against the two metrics of one trace type."""
        correlations = GuppyCovariateCorrelations(
            name="covariate_correlations",
            description="Descriptive correlations of a covariate against the per-bin metrics.",
            target_tables={"recording_site": recording_sites_table},
        )
        for metric, pearson_r, spearman_rho, n_bins in (("mean", 0.62, 0.5, 12), ("transient_count", -0.31, -0.4, 12)):
            correlations.add_row(
                recording_site=0,
                trace_type="z_score",
                metric=metric,
                covariate=covariate_series,
                pearson_r=pearson_r,
                spearman_rho=spearman_rho,
                n_bins=n_bins,
            )
        return correlations

    def test_roundtrip(self, nwbfile, guppy_module, recording_sites_table, covariate_series, roundtrip):
        """Each row names the (trace_type, metric) whose bins the coefficients were computed over."""
        guppy_module.add(recording_sites_table)
        guppy_module.add(covariate_series)
        guppy_module.add(self._build(recording_sites_table, covariate_series))

        read = roundtrip(nwbfile)
        read_correlations = read.processing["guppy"]["covariate_correlations"]
        assert list(read_correlations["trace_type"].data) == ["z_score", "z_score"]
        assert list(read_correlations["metric"].data) == ["mean", "transient_count"]
        np.testing.assert_allclose(read_correlations["pearson_r"].data, [0.62, -0.31])
        np.testing.assert_allclose(read_correlations["spearman_rho"].data, [0.5, -0.4])
        assert list(read_correlations["n_bins"].data) == [12, 12]
        assert [reference.name for reference in read_correlations["covariate"].data] == ["akinesia", "akinesia"]
        # No p-value is reported, by design.
        assert "p_value" not in read_correlations.colnames


# --------------------------------------------------------------------------- #
# Derived traces
# --------------------------------------------------------------------------- #
class TestGuppyDerivedResponseSeries:
    def test_constructor(self, recording_sites_table):
        data = np.arange(100, dtype="float64")
        series = GuppyDerivedResponseSeries(
            name="z_score_dms",
            data=data,
            unit="a.u.",
            trace_type="z_score",
            recording_site=build_dynamic_table_region("recording_site", [0], recording_sites_table),
            timestamps=np.linspace(0, 10, 100),
        )
        assert series.trace_type == "z_score"
        assert series.recording_site.table is recording_sites_table
        np.testing.assert_array_equal(series.data, data)

    def test_roundtrip(self, nwbfile, guppy_module, recording_sites_table, roundtrip):
        guppy_module.add(recording_sites_table)
        data = np.arange(100, dtype="float64")
        series = GuppyDerivedResponseSeries(
            name="z_score_dms",
            data=data,
            unit="a.u.",
            trace_type="z_score",
            recording_site=build_dynamic_table_region("recording_site", [0], recording_sites_table),
            timestamps=np.linspace(0, 10, 100),
        )
        guppy_module.add(series)
        read = roundtrip(nwbfile)
        read_series = read.processing["guppy"]["z_score_dms"]
        assert read_series.trace_type == "z_score"
        np.testing.assert_array_equal(read_series.data[:], data)
        assert read_series.recording_site.data[0] == 0


# --------------------------------------------------------------------------- #
# Analysis products
# --------------------------------------------------------------------------- #
class TestGuppyTransientsTable:
    def test_constructor(self, recording_sites_table):
        table = GuppyTransientsTable(
            name="transients_dms_z_score",
            description="z_score transients in dms",
            trace_type="z_score",
            unit="a.u.",
            target_tables={"recording_site": recording_sites_table},
        )
        table.add_row(recording_site=0, timestamp=1.5, amplitude=2.3)
        table.add_row(recording_site=0, timestamp=2.5, amplitude=1.1)
        assert table.trace_type == "z_score"
        np.testing.assert_array_equal(table["timestamp"].data, [1.5, 2.5])
        np.testing.assert_array_equal(table["amplitude"].data, [2.3, 1.1])
        assert table["recording_site"].table is recording_sites_table

    def test_roundtrip(self, nwbfile, guppy_module, recording_sites_table, roundtrip):
        guppy_module.add(recording_sites_table)
        table = GuppyTransientsTable(
            name="transients_dms_z_score",
            description="z_score transients in dms",
            trace_type="z_score",
            unit="a.u.",
            target_tables={"recording_site": recording_sites_table},
        )
        table.add_row(recording_site=0, timestamp=1.5, amplitude=2.3)
        guppy_module.add(table)
        read = roundtrip(nwbfile)
        read_table = read.processing["guppy"]["transients_dms_z_score"]
        assert read_table.trace_type == "z_score"
        np.testing.assert_array_equal(read_table["timestamp"].data, [1.5])
        assert read_table["recording_site"].data[0] == 0


class TestGuppyTransientSummaryTable:
    def test_constructor(self, recording_sites_table):
        table = GuppyTransientSummaryTable(
            name="transient_summary",
            description="per (recording_site, trace_type) summary",
            target_tables={"recording_site": recording_sites_table},
        )
        table.add_row(recording_site=0, trace_type="z_score", frequency_per_min=12.0, mean_amplitude=2.1)
        table.add_row(recording_site=1, trace_type="dff", frequency_per_min=8.0, mean_amplitude=0.05)
        np.testing.assert_array_equal(table["frequency_per_min"].data, [12.0, 8.0])
        assert list(table["trace_type"].data) == ["z_score", "dff"]

    def test_roundtrip(self, nwbfile, guppy_module, recording_sites_table, roundtrip):
        guppy_module.add(recording_sites_table)
        table = GuppyTransientSummaryTable(
            name="transient_summary",
            description="per (recording_site, trace_type) summary",
            target_tables={"recording_site": recording_sites_table},
        )
        table.add_row(recording_site=0, trace_type="z_score", frequency_per_min=12.0, mean_amplitude=2.1)
        table.add_row(recording_site=1, trace_type="dff", frequency_per_min=8.0, mean_amplitude=0.05)
        guppy_module.add(table)
        read = roundtrip(nwbfile)
        read_table = read.processing["guppy"]["transient_summary"]
        np.testing.assert_array_equal(read_table["mean_amplitude"].data, [2.1, 0.05])
        assert list(read_table["recording_site"].data) == [0, 1]


class TestGuppyPSTH:
    # One PSTH per (recording_site, trace_type, baseline) condition, concatenated across events.
    # Event 0 contributes 2 trials, event 1 contributes 1 trial -> 3 trials total; bins are 2 + 1.
    def _build(self, recording_sites_table, events_table, binned=False):
        kwargs = dict(
            name="psth_dms_z_score",
            description="PSTH of z_score for dms.",
            trace_type="z_score",
            baseline_corrected=True,
            unit="a.u.",
            recording_site=build_dynamic_table_region("recording_site", [0], recording_sites_table),
            event=build_dynamic_table_region("event", [0, 0, 1], events_table),  # per-trial
            summary_event=build_dynamic_table_region("summary_event", [0, 1], events_table),  # per-event-column
            peri_event_time=np.linspace(-1.0, 2.0, 4),
            trial_onset_times=np.array([10.0, 20.0, 30.0]),
            traces=np.arange(12, dtype="float64").reshape(4, 3),  # (num_samples, num_trials)
            mean=np.arange(8, dtype="float64").reshape(4, 2),  # (num_samples, num_events)
            error=np.zeros((4, 2)),
        )
        if binned:
            kwargs.update(
                bin_edges=np.array([[0.0, 3.0], [3.0, 4.0], [0.0, 2.0]]),  # 2 bins from event 0, 1 from event 1
                bin_edges__bin_basis="trials",
                bin_event=build_dynamic_table_region("bin_event", [0, 0, 1], events_table),
                binned_mean=np.zeros((4, 3)),
                binned_error=np.zeros((4, 3)),
            )
        return GuppyPSTH(**kwargs)

    def test_constructor(self, recording_sites_table, multi_events_table):
        psth = self._build(recording_sites_table, multi_events_table)
        assert psth.traces.shape == (4, 3)  # time-first
        assert psth.trace_type == "z_score"
        assert psth.baseline_corrected is True
        assert psth.event.table is multi_events_table
        assert list(psth.event.data) == [0, 0, 1]  # per-trial event membership
        assert list(psth.summary_event.data) == [0, 1]
        assert psth.mean.shape == (4, 2)  # one column per event

    def test_roundtrip(self, nwbfile, guppy_module, recording_sites_table, multi_events_table, roundtrip):
        guppy_module.add(recording_sites_table)
        guppy_module.add(multi_events_table)
        guppy_module.add(self._build(recording_sites_table, multi_events_table, binned=True))
        read = roundtrip(nwbfile)
        read_psth = read.processing["guppy"]["psth_dms_z_score"]
        assert read_psth.description == "PSTH of z_score for dms."
        np.testing.assert_array_equal(read_psth.traces[:], np.arange(12).reshape(4, 3))
        np.testing.assert_array_equal(read_psth.mean[:], np.arange(8).reshape(4, 2))
        assert read_psth.traces.shape[0] == read_psth.peri_event_time.shape[0]
        assert read_psth.traces.shape[1] == read_psth.trial_onset_times.shape[0]
        assert list(read_psth.summary_event.data) == [0, 1]
        assert read_psth.bin_edges.attrs["bin_basis"] == "trials"
        assert read_psth.binned_mean.shape == (4, 3)
        assert list(read_psth.bin_event.data) == [0, 0, 1]


class TestGuppyCrossCorrelation:
    # One cross-correlation per (trace_type, recording-site-pair) condition, concatenated across events.
    def _build(self, recording_sites_table, events_table, binned=False):
        kwargs = dict(
            name="xcorr_z_score_dms_dls",
            description="Cross-correlation of z_score between dms and dls.",
            trace_type="z_score",
            unit="a.u.",
            recording_site=build_dynamic_table_region(
                "recording_site", [0, 1], recording_sites_table
            ),  # recording_site_1, recording_site_2
            event=build_dynamic_table_region("event", [0, 0, 1], events_table),  # per-trial
            summary_event=build_dynamic_table_region("summary_event", [0, 1], events_table),
            lag=np.linspace(-1.0, 1.0, 5),
            trial_onset_times=np.array([10.0, 20.0, 30.0]),
            trials=np.arange(15, dtype="float64").reshape(5, 3),  # (num_lags, num_trials)
            mean=np.arange(10, dtype="float64").reshape(5, 2),  # (num_lags, num_events)
            error=np.zeros((5, 2)),
        )
        if binned:
            kwargs.update(
                bin_edges=np.array([[0.0, 3.0], [3.0, 4.0], [0.0, 2.0]]),
                bin_edges__bin_basis="trials",
                bin_event=build_dynamic_table_region("bin_event", [0, 0, 1], events_table),
                binned_mean=np.zeros((5, 3)),
                binned_error=np.zeros((5, 3)),
            )
        return GuppyCrossCorrelation(**kwargs)

    def test_constructor(self, recording_sites_table, multi_events_table):
        xcorr = self._build(recording_sites_table, multi_events_table)
        assert xcorr.trials.shape == (5, 3)  # lag-first
        assert list(xcorr.recording_site.data) == [0, 1]
        assert list(xcorr.event.data) == [0, 0, 1]
        assert xcorr.mean.shape == (5, 2)
        np.testing.assert_array_equal(xcorr.trial_onset_times, [10.0, 20.0, 30.0])

    def test_roundtrip(self, nwbfile, guppy_module, recording_sites_table, multi_events_table, roundtrip):
        guppy_module.add(recording_sites_table)
        guppy_module.add(multi_events_table)
        guppy_module.add(self._build(recording_sites_table, multi_events_table, binned=True))
        read = roundtrip(nwbfile)
        read_xcorr = read.processing["guppy"]["xcorr_z_score_dms_dls"]
        np.testing.assert_array_equal(read_xcorr.trials[:], np.arange(15).reshape(5, 3))
        np.testing.assert_array_equal(read_xcorr.mean[:], np.arange(10).reshape(5, 2))
        assert read_xcorr.trials.shape[0] == read_xcorr.lag.shape[0]
        assert read_xcorr.trials.shape[1] == read_xcorr.trial_onset_times.shape[0]
        assert list(read_xcorr.recording_site.data) == [0, 1]
        assert list(read_xcorr.bin_event.data) == [0, 0, 1]


class TestGuppyPeakAUC:
    # One peak/AUC per (recording_site, trace_type) condition, concatenated across events.
    # 2 windows; event 0 contributes 2 trials, event 1 contributes 1 trial -> 3 trials; bins 2 + 1.
    def _build(self, recording_sites_table, events_table, binned=False):
        kwargs = dict(
            name="peak_auc_dms_z_score",
            description="Peak/AUC summary of z_score for dms.",
            trace_type="z_score",
            unit="a.u.",
            recording_site=build_dynamic_table_region("recording_site", [0], recording_sites_table),
            event=build_dynamic_table_region("event", [0, 0, 1], events_table),  # per-trial
            summary_event=build_dynamic_table_region("summary_event", [0, 1], events_table),
            window_start=np.array([-5.0, 0.0]),
            window_stop=np.array([0.0, 3.0]),
            trial_onset_times=np.array([10.0, 20.0, 30.0]),
            peak_positive=np.arange(6, dtype="float64").reshape(2, 3),  # (num_windows, num_trials)
            peak_negative=-np.arange(6, dtype="float64").reshape(2, 3),
            area_under_curve=np.arange(6, dtype="float64").reshape(2, 3) * 0.5,
            mean_peak_positive=np.array([[2.0, 4.0], [3.0, 5.0]]),  # (num_windows, num_events)
            mean_peak_negative=np.array([[-1.0, -2.0], [-0.5, -1.5]]),
            mean_area_under_curve=np.array([[1.0, 2.0], [1.5, 2.5]]),
        )
        if binned:
            kwargs.update(
                bin_edges=np.array([[0.0, 3.0], [3.0, 4.0], [0.0, 2.0]]),
                bin_edges__bin_basis="trials",
                bin_event=build_dynamic_table_region("bin_event", [0, 0, 1], events_table),
                binned_peak_positive=np.zeros((2, 3)),
                binned_peak_negative=np.zeros((2, 3)),
                binned_area_under_curve=np.zeros((2, 3)),
            )
        return GuppyPeakAUC(**kwargs)

    def test_constructor(self, recording_sites_table, multi_events_table):
        peak_auc = self._build(recording_sites_table, multi_events_table)
        assert peak_auc.trace_type == "z_score"
        assert peak_auc.peak_positive.shape == (2, 3)  # (num_windows, num_trials)
        assert peak_auc.mean_peak_positive.shape == (2, 2)  # (num_windows, num_events)
        np.testing.assert_array_equal(peak_auc.mean_peak_positive, [[2.0, 4.0], [3.0, 5.0]])
        assert list(peak_auc.event.data) == [0, 0, 1]
        assert peak_auc.event.table is multi_events_table

    def test_roundtrip(self, nwbfile, guppy_module, recording_sites_table, multi_events_table, roundtrip):
        guppy_module.add(recording_sites_table)
        guppy_module.add(multi_events_table)
        guppy_module.add(self._build(recording_sites_table, multi_events_table, binned=True))
        read = roundtrip(nwbfile)
        read_peak_auc = read.processing["guppy"]["peak_auc_dms_z_score"]
        np.testing.assert_array_equal(read_peak_auc.peak_positive[:], np.arange(6).reshape(2, 3))
        assert read_peak_auc.peak_positive.shape[0] == read_peak_auc.window_start.shape[0]
        assert read_peak_auc.peak_positive.shape[1] == read_peak_auc.trial_onset_times.shape[0]
        np.testing.assert_array_equal(read_peak_auc.mean_area_under_curve[:], [[1.0, 2.0], [1.5, 2.5]])
        assert list(read_peak_auc.summary_event.data) == [0, 1]
        assert read_peak_auc.bin_edges.attrs["bin_basis"] == "trials"
        assert read_peak_auc.binned_peak_positive.shape == (2, 3)
        assert list(read_peak_auc.bin_event.data) == [0, 0, 1]


# --------------------------------------------------------------------------- #
# Parameters
# --------------------------------------------------------------------------- #
class TestGuppyParameters:
    def test_constructor(self):
        params = GuppyParameters(
            name="guppy_parameters",
            guppy_version="2.0.0a7",
            zscore_method="standard",
            baseline_window_start=0.0,
            baseline_window_end=30.0,
            isosbestic_control=True,
            remove_artifacts=False,
            transients_thresh=2.0,
            peak_start_points=np.array([0.0, 1.0]),
            peak_end_points=np.array([1.0, 2.0]),
        )
        assert params.guppy_version == "2.0.0a7"
        assert params.isosbestic_control is True
        np.testing.assert_array_equal(params.peak_start_points, [0.0, 1.0])

    def test_roundtrip(self, nwbfile, roundtrip):
        params = GuppyParameters(
            name="guppy_parameters",
            guppy_version="2.0.0a7",
            zscore_method="standard",
            baseline_window_start=0.0,
            baseline_window_end=30.0,
            isosbestic_control=True,
            remove_artifacts=False,
            transients_thresh=2.0,
            peak_start_points=np.array([0.0, 1.0]),
            peak_end_points=np.array([1.0, 2.0]),
        )
        nwbfile.add_lab_meta_data(params)
        read = roundtrip(nwbfile)
        read_params = read.lab_meta_data["guppy_parameters"]
        assert read_params.guppy_version == "2.0.0a7"
        assert read_params.zscore_method == "standard"
        np.testing.assert_array_equal(read_params.peak_end_points[:], [1.0, 2.0])
