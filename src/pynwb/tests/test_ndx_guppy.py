"""Unit and roundtrip tests for the ndx-guppy neurodata types.

The tests are organized one ``Test<ClassName>`` class per neurodata type. Shared setup
(an NWBFile, the two registry tables, a roundtrip helper) lives in module-level fixtures.
"""

import numpy as np
import pytest

from pynwb import NWBHDF5IO
from pynwb.event import EventsTable
from pynwb.testing.mock.file import mock_NWBFile
from hdmf.common import DynamicTable, VectorData
from hdmf.common.table import DynamicTableRegion

from ndx_guppy import (
    GuppyRegionsTable,
    GuppyEventsTable,
    GuppyDerivedResponseSeries,
    GuppyTransientsTable,
    GuppyTransientSummaryTable,
    GuppyPSTH,
    GuppyCrossCorrelation,
    GuppyPeakAUC,
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


def build_regions_table():
    table = GuppyRegionsTable(name="regions", description="GuPPy logical regions")
    table.add_row(region="dms", raw_store_name="Dv2A")
    table.add_row(region="dls", raw_store_name="Dv1A")
    return table


def build_events_table():
    table = GuppyEventsTable(name="events", description="GuPPy behavioral events")
    table.add_row(event_name="port_entries", event_description="Port entry events", raw_store_name="PrtN")
    return table


def build_multi_events_table():
    """A two-event registry for the event-bearing products, which concatenate across events."""
    table = GuppyEventsTable(name="events", description="GuPPy behavioral events")
    table.add_row(event_name="port_entries", event_description="Port entry events", raw_store_name="PrtN")
    table.add_row(event_name="rewarded_nose_pokes", event_description="Rewarded nose pokes", raw_store_name="LNRW")
    return table


@pytest.fixture
def regions_table():
    return build_regions_table()


@pytest.fixture
def events_table():
    return build_events_table()


@pytest.fixture
def multi_events_table():
    return build_multi_events_table()


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


def region_ref(name, indices, table, description="region reference"):
    return DynamicTableRegion(name=name, data=list(indices), description=description, table=table)


# --------------------------------------------------------------------------- #
# Registries
# --------------------------------------------------------------------------- #
class TestGuppyRegionsTable:
    def test_constructor(self, regions_table):
        assert list(regions_table["region"].data) == ["dms", "dls"]
        assert list(regions_table["raw_store_name"].data) == ["Dv2A", "Dv1A"]
        assert "fiber_photometry_table_region" not in regions_table.colnames

    def test_roundtrip(self, nwbfile, guppy_module, regions_table, roundtrip):
        guppy_module.add(regions_table)
        read = roundtrip(nwbfile)
        read_table = read.processing["guppy"]["regions"]
        assert list(read_table["region"].data) == ["dms", "dls"]
        assert list(read_table["raw_store_name"].data) == ["Dv2A", "Dv1A"]

    def test_optional_fiber_link_roundtrip(self, nwbfile, guppy_module, roundtrip):
        """The optional ragged fiber_photometry_table_region column roundtrips (stand-in target table)."""
        fiber_stand_in = DynamicTable(
            name="fiber_photometry_table",
            description="stand-in for the acquisition FiberPhotometryTable",
            columns=[VectorData(name="location", description="loc", data=["DMS", "DMS"])],
        )
        table = GuppyRegionsTable(
            name="regions",
            description="GuPPy logical regions",
            target_tables={"fiber_photometry_table_region": fiber_stand_in},
        )
        table.add_row(region="dms", fiber_photometry_table_region=[0, 1])
        guppy_module.add(fiber_stand_in)
        guppy_module.add(table)

        read = roundtrip(nwbfile)
        read_table = read.processing["guppy"]["regions"]
        # The ragged column is a VectorIndex over a DynamicTableRegion; check the stored target indices.
        column = read_table["fiber_photometry_table_region"]
        target_indices = column.target.data[:] if hasattr(column, "target") else column.data[:]
        assert list(target_indices) == [0, 1]

    def test_valid_signal_intervals_roundtrip(self, nwbfile, guppy_module, roundtrip):
        """The optional obs_intervals-style ragged valid_signal_intervals column roundtrips per region."""
        table = GuppyRegionsTable(name="regions", description="GuPPy logical regions")
        # One region carries two valid intervals, the other carries none (empty ragged entry).
        table.add_row(region="dms", valid_signal_intervals=[[0.0, 5.0], [7.0, 12.0]])
        table.add_row(region="dls", valid_signal_intervals=[])
        guppy_module.add(table)

        read = roundtrip(nwbfile)
        read_table = read.processing["guppy"]["regions"]
        np.testing.assert_array_equal(read_table["valid_signal_intervals"][0], [[0.0, 5.0], [7.0, 12.0]])
        np.testing.assert_array_equal(read_table["valid_signal_intervals"][1], np.empty((0, 2)))


class TestGuppyEventsTable:
    def test_constructor(self, events_table):
        assert list(events_table["event_name"].data) == ["port_entries"]
        assert list(events_table["event_description"].data) == ["Port entry events"]

    def test_roundtrip(self, nwbfile, guppy_module, events_table, roundtrip):
        guppy_module.add(events_table)
        read = roundtrip(nwbfile)
        read_table = read.processing["guppy"]["events"]
        assert list(read_table["event_name"].data) == ["port_entries"]
        assert list(read_table["raw_store_name"].data) == ["PrtN"]

    def test_optional_event_reference_roundtrip(self, nwbfile, guppy_module, roundtrip):
        """The optional reference roundtrips, pointing at a core pynwb.event.EventsTable."""
        events_table = EventsTable(name="PortEntries", description="port entry events")
        events_table.add_row(timestamp=10.0)
        events_table.add_row(timestamp=20.0)
        nwbfile.add_events_table(events_table)

        table = GuppyEventsTable(name="events", description="GuPPy behavioral events")
        table.add_row(event_name="port_entries", event_description="Port entry events", events=events_table)
        guppy_module.add(table)

        read = roundtrip(nwbfile)
        read_table = read.processing["guppy"]["events"]
        assert read_table["events"][0].name == "PortEntries"


# --------------------------------------------------------------------------- #
# Derived traces
# --------------------------------------------------------------------------- #
class TestGuppyDerivedResponseSeries:
    def test_constructor(self, regions_table):
        data = np.arange(100, dtype="float64")
        series = GuppyDerivedResponseSeries(
            name="z_score_dms",
            data=data,
            unit="a.u.",
            trace_type="z_score",
            region=region_ref("region", [0], regions_table),
            timestamps=np.linspace(0, 10, 100),
        )
        assert series.trace_type == "z_score"
        assert series.region.table is regions_table
        np.testing.assert_array_equal(series.data, data)

    def test_roundtrip(self, nwbfile, guppy_module, regions_table, roundtrip):
        guppy_module.add(regions_table)
        data = np.arange(100, dtype="float64")
        series = GuppyDerivedResponseSeries(
            name="z_score_dms",
            data=data,
            unit="a.u.",
            trace_type="z_score",
            region=region_ref("region", [0], regions_table),
            timestamps=np.linspace(0, 10, 100),
        )
        guppy_module.add(series)
        read = roundtrip(nwbfile)
        read_series = read.processing["guppy"]["z_score_dms"]
        assert read_series.trace_type == "z_score"
        np.testing.assert_array_equal(read_series.data[:], data)
        assert read_series.region.data[0] == 0


# --------------------------------------------------------------------------- #
# Analysis products
# --------------------------------------------------------------------------- #
class TestGuppyTransientsTable:
    def test_constructor(self, regions_table):
        table = GuppyTransientsTable(
            name="transients_dms_z_score",
            description="z_score transients in dms",
            trace_type="z_score",
            unit="a.u.",
            target_tables={"region": regions_table},
        )
        table.add_row(region=0, timestamp=1.5, amplitude=2.3)
        table.add_row(region=0, timestamp=2.5, amplitude=1.1)
        assert table.trace_type == "z_score"
        np.testing.assert_array_equal(table["timestamp"].data, [1.5, 2.5])
        np.testing.assert_array_equal(table["amplitude"].data, [2.3, 1.1])
        assert table["region"].table is regions_table

    def test_roundtrip(self, nwbfile, guppy_module, regions_table, roundtrip):
        guppy_module.add(regions_table)
        table = GuppyTransientsTable(
            name="transients_dms_z_score",
            description="z_score transients in dms",
            trace_type="z_score",
            unit="a.u.",
            target_tables={"region": regions_table},
        )
        table.add_row(region=0, timestamp=1.5, amplitude=2.3)
        guppy_module.add(table)
        read = roundtrip(nwbfile)
        read_table = read.processing["guppy"]["transients_dms_z_score"]
        assert read_table.trace_type == "z_score"
        np.testing.assert_array_equal(read_table["timestamp"].data, [1.5])
        assert read_table["region"].data[0] == 0


class TestGuppyTransientSummaryTable:
    def test_constructor(self, regions_table):
        table = GuppyTransientSummaryTable(
            name="transient_summary",
            description="per (region, trace_type) summary",
            target_tables={"region": regions_table},
        )
        table.add_row(region=0, trace_type="z_score", frequency_per_min=12.0, mean_amplitude=2.1)
        table.add_row(region=1, trace_type="dff", frequency_per_min=8.0, mean_amplitude=0.05)
        np.testing.assert_array_equal(table["frequency_per_min"].data, [12.0, 8.0])
        assert list(table["trace_type"].data) == ["z_score", "dff"]

    def test_roundtrip(self, nwbfile, guppy_module, regions_table, roundtrip):
        guppy_module.add(regions_table)
        table = GuppyTransientSummaryTable(
            name="transient_summary",
            description="per (region, trace_type) summary",
            target_tables={"region": regions_table},
        )
        table.add_row(region=0, trace_type="z_score", frequency_per_min=12.0, mean_amplitude=2.1)
        table.add_row(region=1, trace_type="dff", frequency_per_min=8.0, mean_amplitude=0.05)
        guppy_module.add(table)
        read = roundtrip(nwbfile)
        read_table = read.processing["guppy"]["transient_summary"]
        np.testing.assert_array_equal(read_table["mean_amplitude"].data, [2.1, 0.05])
        assert list(read_table["region"].data) == [0, 1]


class TestGuppyPSTH:
    # One PSTH per (region, trace_type, baseline) condition, concatenated across events.
    # Event 0 contributes 2 trials, event 1 contributes 1 trial -> 3 trials total; bins are 2 + 1.
    def _build(self, regions_table, events_table, binned=False):
        kwargs = dict(
            name="psth_dms_z_score",
            trace_type="z_score",
            baseline_corrected=True,
            unit="a.u.",
            region=region_ref("region", [0], regions_table),
            event=region_ref("event", [0, 0, 1], events_table),  # per-trial
            summary_event=region_ref("summary_event", [0, 1], events_table),  # per-event-column
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
                bin_event=region_ref("bin_event", [0, 0, 1], events_table),
                binned_mean=np.zeros((4, 3)),
                binned_error=np.zeros((4, 3)),
            )
        return GuppyPSTH(**kwargs)

    def test_constructor(self, regions_table, multi_events_table):
        psth = self._build(regions_table, multi_events_table)
        assert psth.traces.shape == (4, 3)  # time-first
        assert psth.trace_type == "z_score"
        assert psth.baseline_corrected is True
        assert psth.event.table is multi_events_table
        assert list(psth.event.data) == [0, 0, 1]  # per-trial event membership
        assert list(psth.summary_event.data) == [0, 1]
        assert psth.mean.shape == (4, 2)  # one column per event

    def test_roundtrip(self, nwbfile, guppy_module, regions_table, multi_events_table, roundtrip):
        guppy_module.add(regions_table)
        guppy_module.add(multi_events_table)
        guppy_module.add(self._build(regions_table, multi_events_table, binned=True))
        read = roundtrip(nwbfile)
        read_psth = read.processing["guppy"]["psth_dms_z_score"]
        np.testing.assert_array_equal(read_psth.traces[:], np.arange(12).reshape(4, 3))
        np.testing.assert_array_equal(read_psth.mean[:], np.arange(8).reshape(4, 2))
        assert read_psth.traces.shape[0] == read_psth.peri_event_time.shape[0]
        assert read_psth.traces.shape[1] == read_psth.trial_onset_times.shape[0]
        assert list(read_psth.summary_event.data) == [0, 1]
        assert read_psth.bin_edges.attrs["bin_basis"] == "trials"
        assert read_psth.binned_mean.shape == (4, 3)
        assert list(read_psth.bin_event.data) == [0, 0, 1]


class TestGuppyCrossCorrelation:
    # One cross-correlation per (trace_type, region-pair) condition, concatenated across events.
    def _build(self, regions_table, events_table, binned=False):
        kwargs = dict(
            name="xcorr_z_score_dms_dls",
            trace_type="z_score",
            unit="a.u.",
            region=region_ref("region", [0, 1], regions_table),  # region_1, region_2
            event=region_ref("event", [0, 0, 1], events_table),  # per-trial
            summary_event=region_ref("summary_event", [0, 1], events_table),
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
                bin_event=region_ref("bin_event", [0, 0, 1], events_table),
                binned_mean=np.zeros((5, 3)),
                binned_error=np.zeros((5, 3)),
            )
        return GuppyCrossCorrelation(**kwargs)

    def test_constructor(self, regions_table, multi_events_table):
        xcorr = self._build(regions_table, multi_events_table)
        assert xcorr.trials.shape == (5, 3)  # lag-first
        assert list(xcorr.region.data) == [0, 1]
        assert list(xcorr.event.data) == [0, 0, 1]
        assert xcorr.mean.shape == (5, 2)
        np.testing.assert_array_equal(xcorr.trial_onset_times, [10.0, 20.0, 30.0])

    def test_roundtrip(self, nwbfile, guppy_module, regions_table, multi_events_table, roundtrip):
        guppy_module.add(regions_table)
        guppy_module.add(multi_events_table)
        guppy_module.add(self._build(regions_table, multi_events_table, binned=True))
        read = roundtrip(nwbfile)
        read_xcorr = read.processing["guppy"]["xcorr_z_score_dms_dls"]
        np.testing.assert_array_equal(read_xcorr.trials[:], np.arange(15).reshape(5, 3))
        np.testing.assert_array_equal(read_xcorr.mean[:], np.arange(10).reshape(5, 2))
        assert read_xcorr.trials.shape[0] == read_xcorr.lag.shape[0]
        assert read_xcorr.trials.shape[1] == read_xcorr.trial_onset_times.shape[0]
        assert list(read_xcorr.region.data) == [0, 1]
        assert list(read_xcorr.bin_event.data) == [0, 0, 1]


class TestGuppyPeakAUC:
    # One peak/AUC per (region, trace_type) condition, concatenated across events.
    # 2 windows; event 0 contributes 2 trials, event 1 contributes 1 trial -> 3 trials; bins 2 + 1.
    def _build(self, regions_table, events_table, binned=False):
        kwargs = dict(
            name="peak_auc_dms_z_score",
            trace_type="z_score",
            unit="a.u.",
            region=region_ref("region", [0], regions_table),
            event=region_ref("event", [0, 0, 1], events_table),  # per-trial
            summary_event=region_ref("summary_event", [0, 1], events_table),
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
                bin_event=region_ref("bin_event", [0, 0, 1], events_table),
                binned_peak_positive=np.zeros((2, 3)),
                binned_peak_negative=np.zeros((2, 3)),
                binned_area_under_curve=np.zeros((2, 3)),
            )
        return GuppyPeakAUC(**kwargs)

    def test_constructor(self, regions_table, multi_events_table):
        peak_auc = self._build(regions_table, multi_events_table)
        assert peak_auc.trace_type == "z_score"
        assert peak_auc.peak_positive.shape == (2, 3)  # (num_windows, num_trials)
        assert peak_auc.mean_peak_positive.shape == (2, 2)  # (num_windows, num_events)
        np.testing.assert_array_equal(peak_auc.mean_peak_positive, [[2.0, 4.0], [3.0, 5.0]])
        assert list(peak_auc.event.data) == [0, 0, 1]
        assert peak_auc.event.table is multi_events_table

    def test_roundtrip(self, nwbfile, guppy_module, regions_table, multi_events_table, roundtrip):
        guppy_module.add(regions_table)
        guppy_module.add(multi_events_table)
        guppy_module.add(self._build(regions_table, multi_events_table, binned=True))
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
