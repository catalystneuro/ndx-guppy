from importlib.resources import files
from pynwb import load_namespaces, get_class

# ndx-fiber-photometry must be imported so its types are registered before loading ndx-guppy,
# since GuppyDerivedResponseSeries extends FiberPhotometryResponseSeries.
import ndx_fiber_photometry  # noqa: F401

# Get path to the namespace.yaml file with the expected location when installed not in editable mode
__location_of_this_file = files(__name__)
__spec_path = __location_of_this_file / "spec" / "ndx-guppy.namespace.yaml"

# If that path does not exist, we are likely running in editable mode. Use the local path instead
if not __spec_path.exists():
    __spec_path = __location_of_this_file.parent.parent.parent / "spec" / "ndx-guppy.namespace.yaml"

# Load the namespace
load_namespaces(str(__spec_path))

# Registries
GuppyRecordingSitesTable = get_class("GuppyRecordingSitesTable", "ndx-guppy")
GuppyEventsTable = get_class("GuppyEventsTable", "ndx-guppy")

# Derived traces
GuppyDerivedResponseSeries = get_class("GuppyDerivedResponseSeries", "ndx-guppy")

# Analysis products
GuppyTransientsTable = get_class("GuppyTransientsTable", "ndx-guppy")
GuppyTransientSummaryTable = get_class("GuppyTransientSummaryTable", "ndx-guppy")
GuppyPSTH = get_class("GuppyPSTH", "ndx-guppy")
GuppyCrossCorrelation = get_class("GuppyCrossCorrelation", "ndx-guppy")
GuppyPeakAUC = get_class("GuppyPeakAUC", "ndx-guppy")
GuppyValidSignalIntervals = get_class("GuppyValidSignalIntervals", "ndx-guppy")

# Parameters
GuppyParameters = get_class("GuppyParameters", "ndx-guppy")

__all__ = [
    "GuppyRecordingSitesTable",
    "GuppyEventsTable",
    "GuppyDerivedResponseSeries",
    "GuppyTransientsTable",
    "GuppyTransientSummaryTable",
    "GuppyPSTH",
    "GuppyCrossCorrelation",
    "GuppyPeakAUC",
    "GuppyValidSignalIntervals",
    "GuppyParameters",
]

# Remove these functions/modules from the package
del load_namespaces, get_class, files, __location_of_this_file, __spec_path
