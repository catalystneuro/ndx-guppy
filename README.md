# ndx-guppy Extension for NWB

This is an NWB extension for storing the derived outputs of the [GuPPy](https://github.com/LernerLab/GuPPy)
(Guided Photometry Analysis in Python) fiber-photometry processing tool.

GuPPy is a *processing* tool, not an acquisition system. This extension represents only the products GuPPy
computes — normalized traces, detected transients, peri-event PSTHs, cross-correlations, and the parameters
used — for a single session. Raw signal/control traces and behavioral events remain owned by the acquisition
and events interfaces (e.g. [ndx-fiber-photometry](https://github.com/catalystneuro/ndx-fiber-photometry) and
[ndx-events](https://github.com/rly/ndx-events)).

The design turns GuPPy's organizing features into structured, queryable NWB features:

- **region** and **event** are *entities*, so they live as rows in registry tables (`GuppyRegionsTable`,
  `GuppyEventsTable`) and are referenced by `DynamicTableRegion`. Region/event identity is defined once and
  referenced everywhere — no free-text strings to keep in sync.
- **trace_type** is a closed *category* (`control_fit` / `dff` / `z_score`), so it is a plain enumerated text
  attribute stamped directly on each object.

Cross-extension dependencies are quarantined: products reference ndx-guppy's own registry tables, and any
outward link to the acquisition `FiberPhotometryTable` or to a behavioral-events object is an **optional**
column on a registry. A GuPPy file can therefore stand alone or be fully wired to acquisition/events.

## Neurodata Types

### Registries

- **`GuppyRegionsTable`** (extends `DynamicTable`) — one row per GuPPy logical region (e.g. `dms`). Columns:
  `region` (the semantic name), optional `raw_store_name` (from `storesList.csv`), and an optional ragged
  `fiber_photometry_table_region` linking each region to its signal + isosbestic fiber rows in the acquisition
  `FiberPhotometryTable` (anatomy is reached through this link, not duplicated).
- **`GuppyEventsTable`** (extends `DynamicTable`) — one row per behavioral event GuPPy aligned to (e.g.
  `port_entries`). Columns: `event_name`, `event_description`, optional `raw_store_name`, and an optional
  generic object reference `events` to the behavioral-event object (e.g. an `ndx_events.Events`).

### Derived traces

- **`GuppyDerivedResponseSeries`** (extends `ndx_fiber_photometry.FiberPhotometryResponseSeries`) — a derived
  continuous trace (`control_fit`, `dff`, or `z_score`) for one region. Adds a `trace_type` attribute and a
  `region` reference into `GuppyRegionsTable`; the inherited `fiber_photometry_table_region` still carries the
  physical fiber provenance.

### Analysis products

- **`GuppyTransientsTable`** (extends `DynamicTable`) — detected transient peaks for one (region, trace_type);
  columns `timestamp`, `amplitude`; attributes `trace_type`, `unit`.
- **`GuppyTransientSummaryTable`** (extends `DynamicTable`) — per-session summary, one row per
  (region, trace_type); columns `region`, `trace_type`, `frequency_per_min`, `mean_amplitude`.
- **`GuppyPSTH`** (extends `NWBDataInterface`) — peri-event PSTH for one (event, region, trace_type), stored as
  a natural `(num_samples, num_trials)` matrix with across-trial `mean`/`error` and optional trial- or
  time-based binning.
- **`GuppyCrossCorrelation`** (extends `NWBDataInterface`) — peri-event cross-correlation for one
  (event, trace_type, region-pair), stored as a `(num_lags, num_trials)` matrix with `mean`/`error` and
  optional binning.
- **`GuppyPeakAUC`** (extends `NWBDataInterface`) — peak/area summary of a PSTH for one
  (event, region, trace_type). GuPPy computes `peak_positive`/`peak_negative`/`area_under_curve`
  for every trial, every bin, and the across-trial mean within each peak window, so each metric is
  a `(num_windows, num_trials)` matrix plus a per-window mean (and optional per-bin) value.
- **`GuppyValidSignalIntervals`** (extends `TimeIntervals`) — artifact-free valid-signal windows with a
  structured `region` reference per interval.

### Parameters

- **`GuppyParameters`** (extends `LabMetaData`) — one per session: typed GuPPy processing parameters
  (version, z-score method, baseline windows, transient thresholds, PSTH windows, etc.) from
  `GuPPyParamtersUsed.json`.

## Installation

```
pip install ndx-guppy
```

Or, for development, from a clone of this repository:

```
pip install -e .
```

## Usage

```python
import numpy as np
from datetime import datetime
from dateutil.tz import tzlocal
from hdmf.common.table import DynamicTableRegion
from pynwb import NWBFile, NWBHDF5IO

from ndx_guppy import (
    GuppyRegionsTable,
    GuppyEventsTable,
    GuppyParameters,
    GuppyDerivedResponseSeries,
    GuppyTransientsTable,
    GuppyPSTH,
    GuppyCrossCorrelation,
)

nwbfile = NWBFile(
    session_description="A GuPPy-processed fiber photometry session.",
    identifier="guppy-session-0",
    session_start_time=datetime.now(tzlocal()),
)

# Typed session parameters live in /general.
nwbfile.add_lab_meta_data(
    GuppyParameters(
        name="guppy_parameters",
        guppy_version="2.0.0a7",
        zscore_method="standard",
        baseline_window_start=0.0,
        baseline_window_end=30.0,
        transients_thresh=2.0,
    )
)

# A processing module holds the registries and all derived products.
module = nwbfile.create_processing_module(name="guppy", description="GuPPy-derived outputs")

# Registries: region and event identity, defined once.
regions = GuppyRegionsTable(name="regions", description="GuPPy logical regions")
regions.add_row(region="dms", raw_store_name="Dv2A")
regions.add_row(region="dls", raw_store_name="Dv1A")

events = GuppyEventsTable(name="events", description="GuPPy behavioral events")
events.add_row(event_name="port_entries", event_description="Port entry events", raw_store_name="PrtN")

module.add(regions)
module.add(events)

# A derived trace: trace_type stamped, region referenced.
z_score_dms = GuppyDerivedResponseSeries(
    name="z_score_dms",
    data=np.random.randn(1000),
    unit="a.u.",
    trace_type="z_score",
    region=DynamicTableRegion(name="region", data=[0], description="dms", table=regions),
    rate=30.0,
)
module.add(z_score_dms)

# Transient peaks for one (region, trace_type). region is a per-row DynamicTableRegion column.
transients = GuppyTransientsTable(
    name="transients_dms_z_score",
    description="GuPPy-detected z_score transients in dms",
    trace_type="z_score",
    unit="a.u.",
    target_tables={"region": regions},
)
transients.add_row(region=0, timestamp=1.5, amplitude=2.3)
transients.add_row(region=0, timestamp=4.2, amplitude=1.8)
module.add(transients)

# A peri-event PSTH as a (num_samples, num_trials) matrix.
psth = GuppyPSTH(
    name="psth_port_entries_dms_z_score",
    trace_type="z_score",
    baseline_corrected=True,
    unit="a.u.",
    region=DynamicTableRegion(name="region", data=[0], description="dms", table=regions),
    event=DynamicTableRegion(name="event", data=[0], description="port_entries", table=events),
    peri_event_time=np.linspace(-1.0, 2.0, 90),
    trial_onset_times=np.array([10.0, 20.0, 30.0]),
    traces=np.random.randn(90, 3),
    mean=np.zeros(90),
    error=np.zeros(90),
)
module.add(psth)

# A cross-correlation between two regions, aligned to an event: region references two rows.
cross_correlation = GuppyCrossCorrelation(
    name="xcorr_port_entries_z_score_dms_dls",
    trace_type="z_score",
    unit="a.u.",
    region=DynamicTableRegion(name="region", data=[0, 1], description="dms, dls", table=regions),
    event=DynamicTableRegion(name="event", data=[0], description="port_entries", table=events),
    lag=np.linspace(-1.0, 1.0, 101),
    trials=np.random.randn(101, 3),
    mean=np.zeros(101),
    error=np.zeros(101),
)
module.add(cross_correlation)

with NWBHDF5IO("guppy_session.nwb", mode="w") as io:
    io.write(nwbfile)

with NWBHDF5IO("guppy_session.nwb", mode="r", load_namespaces=True) as io:
    read_nwbfile = io.read()
    guppy = read_nwbfile.processing["guppy"]
    print(guppy["z_score_dms"].trace_type)                          # "z_score"
    print(guppy["psth_port_entries_dms_z_score"].traces.shape)      # (90, 3) -> (num_samples, num_trials)
    print(read_nwbfile.lab_meta_data["guppy_parameters"].zscore_method)  # "standard"
```

## Extension Diagram

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#ffffff', 'lineColor': '#333'}}}%%
classDiagram
    direction LR

    class FiberPhotometryResponseSeries {
        <<ndx-fiber-photometry>>
    }
    class FiberPhotometryTable {
        <<ndx-fiber-photometry>>
    }
    class GuppyDerivedResponseSeries {
        <<ndx-guppy>>
        --
        attribute trace_type : text
        DynamicTableRegion region
    }
    FiberPhotometryResponseSeries <|-- GuppyDerivedResponseSeries

    class GuppyRegionsTable {
        <<ndx-guppy>>
        --
        VectorData region
        VectorData raw_store_name [optional]
        DynamicTableRegion fiber_photometry_table_region [optional, ragged]
    }
    class GuppyEventsTable {
        <<ndx-guppy>>
        --
        VectorData event_name
        VectorData event_description
        VectorData raw_store_name [optional]
        object reference events [optional]
    }

    class GuppyTransientsTable {
        <<ndx-guppy>>
        --
        attribute trace_type, unit : text
        DynamicTableRegion region
        VectorData timestamp, amplitude
    }
    class GuppyTransientSummaryTable {
        <<ndx-guppy>>
        --
        DynamicTableRegion region
        VectorData trace_type, frequency_per_min, mean_amplitude
    }
    class GuppyPSTH {
        <<ndx-guppy>>
        --
        attribute trace_type, unit : text
        attribute baseline_corrected : bool
        DynamicTableRegion region, event
        dataset traces (num_samples, num_trials)
    }
    class GuppyCrossCorrelation {
        <<ndx-guppy>>
        --
        attribute trace_type, unit : text
        DynamicTableRegion region, event
        dataset trials (num_lags, num_trials)
        dataset trial_onset_times (num_trials)
    }
    class GuppyPeakAUC {
        <<ndx-guppy>>
        --
        attribute trace_type, unit : text
        DynamicTableRegion region, event
        dataset peak_positive (num_windows, num_trials)
        dataset mean_peak_positive (num_windows)
    }
    class GuppyValidSignalIntervals {
        <<ndx-guppy>>
        --
        DynamicTableRegion region
    }
    class GuppyParameters {
        <<ndx-guppy>>
        LabMetaData
    }

    GuppyDerivedResponseSeries ..> GuppyRegionsTable : region
    GuppyTransientsTable ..> GuppyRegionsTable : region
    GuppyTransientSummaryTable ..> GuppyRegionsTable : region
    GuppyValidSignalIntervals ..> GuppyRegionsTable : region
    GuppyPSTH ..> GuppyRegionsTable : region
    GuppyPSTH ..> GuppyEventsTable : event
    GuppyCrossCorrelation ..> GuppyRegionsTable : region (2)
    GuppyCrossCorrelation ..> GuppyEventsTable : event
    GuppyPeakAUC ..> GuppyRegionsTable : region
    GuppyPeakAUC ..> GuppyEventsTable : event
    GuppyRegionsTable ..> FiberPhotometryTable : optional outward link (ragged)
```

---
This extension was created using [ndx-template](https://github.com/nwb-extensions/ndx-template).
