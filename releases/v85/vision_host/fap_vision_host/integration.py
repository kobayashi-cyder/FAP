from __future__ import annotations

from .host import ObjectListVisionMapper, VisionBackend
from .raster_backend import BoundedRasterVision


def build_bounded_raster_backend(
    *,
    backend_id: str = "bounded-raster-vision.v1",
) -> tuple[VisionBackend, BoundedRasterVision]:
    """Create a concrete production Vision backend for bounded raster scenes."""
    observer = BoundedRasterVision()
    backend = VisionBackend(
        backend_id,
        observer.observe,
        mapper=ObjectListVisionMapper(),
        kind="production",
    )
    return backend, observer
