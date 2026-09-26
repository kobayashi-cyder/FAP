from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional, Sequence

from fap_visual.loop import VisualCognitiveLoop
from fap_visual.render import RasterFrame, RendererPort
from fap_visual.vision import CallableVisionAdapter, PrimitiveVision
from fap_visual.visual_ir import VisualIR, VisualPrimitive


class VisionBackendUnavailable(RuntimeError):
    """Raised when a production visual loop has no verified production Vision backend."""


@dataclass(frozen=True)
class VisionBackend:
    backend_id: str
    observe_fn: Callable[[RasterFrame], Any]
    mapper: Optional[Callable[[Any, RasterFrame], VisualIR]] = None
    kind: str = "production"

    def validate(self) -> None:
        if not isinstance(self.backend_id, str) or not self.backend_id.strip():
            raise ValueError("vision backend_id is required")
        if not callable(self.observe_fn):
            raise TypeError("vision observe_fn must be callable")
        if self.mapper is not None and not callable(self.mapper):
            raise TypeError("vision mapper must be callable")
        if self.kind not in {"production", "bootstrap"}:
            raise ValueError("unsupported vision backend kind")


class ObjectListVisionMapper:
    """Normalize a bounded existing-Vision object list into VisualIR.

    Expected raw shape:
      {"objects": [{"id": "...", "kind": "rect|circle", ...}], "background": [r,g,b]}

    Rectangles use x/y + w/h (or width/height).
    Circles use center x/y + r (or radius). Width/height are derived as 2*r+1.
    """

    def __call__(self, raw: Any, frame: RasterFrame) -> VisualIR:
        if not isinstance(raw, Mapping):
            raise TypeError("vision output must be a mapping")
        objects = raw.get("objects")
        if not isinstance(objects, Sequence) or isinstance(objects, (str, bytes, bytearray)):
            raise ValueError("vision output objects must be a sequence")

        background = raw.get("background", frame.background)
        bg = self._rgb(background, "background")
        primitives: list[VisualPrimitive] = []
        for index, obj in enumerate(objects):
            if not isinstance(obj, Mapping):
                raise ValueError("vision object must be a mapping")
            kind = str(obj.get("kind", "")).strip().lower()
            primitive_id = str(obj.get("id") or f"vision:{index}")
            color = self._rgb(obj.get("rgb", obj.get("color")), "object color")
            x = self._integer(obj.get("x"), "x")
            y = self._integer(obj.get("y"), "y")
            if kind == "rect":
                width = self._integer(obj.get("w", obj.get("width")), "width")
                height = self._integer(obj.get("h", obj.get("height")), "height")
                primitive = VisualPrimitive(
                    primitive_id, "rect", x, y, width, height, 0, color
                )
            elif kind == "circle":
                radius = self._integer(obj.get("r", obj.get("radius")), "radius")
                primitive = VisualPrimitive(
                    primitive_id,
                    "circle",
                    x,
                    y,
                    radius * 2 + 1,
                    radius * 2 + 1,
                    radius,
                    color,
                )
            else:
                raise ValueError(f"unsupported production vision object: {kind}")
            primitives.append(primitive)

        observed = VisualIR(
            frame.width,
            frame.height,
            tuple(primitives),
            bg,
        )
        observed.validate()
        return observed

    @staticmethod
    def _integer(value: Any, name: str) -> int:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"vision {name} must be numeric")
        ivalue = int(value)
        if float(value) != float(ivalue):
            raise ValueError(f"vision {name} must be integral")
        return ivalue

    @staticmethod
    def _rgb(value: Any, name: str) -> tuple[int, int, int]:
        if (
            not isinstance(value, Sequence)
            or isinstance(value, (str, bytes, bytearray))
            or len(value) != 3
        ):
            raise ValueError(f"vision {name} must be RGB")
        out = []
        for channel in value:
            if isinstance(channel, bool) or not isinstance(channel, (int, float)):
                raise ValueError(f"vision {name} must contain numeric RGB")
            ivalue = int(channel)
            if float(channel) != float(ivalue) or not 0 <= ivalue <= 255:
                raise ValueError(f"vision {name} channel out of range")
            out.append(ivalue)
        return tuple(out)  # type: ignore[return-value]


class StrictProductionVisionAdapter:
    """CallableVisionAdapter plus production frame-space invariants."""

    def __init__(self, backend: VisionBackend):
        backend.validate()
        self.backend = backend
        self.inner = CallableVisionAdapter(
            backend.observe_fn,
            mapper=backend.mapper,
        )

    def observe(self, frame: RasterFrame) -> VisualIR:
        observed = self.inner.observe(frame)
        if observed.width != frame.width or observed.height != frame.height:
            raise ValueError("production Vision changed frame dimensions")
        for primitive in observed.primitives:
            if primitive.kind == "rect":
                if (
                    primitive.x < 0
                    or primitive.y < 0
                    or primitive.x + primitive.width > frame.width
                    or primitive.y + primitive.height > frame.height
                ):
                    raise ValueError("production Vision rect is outside frame")
            elif primitive.kind == "circle":
                if (
                    primitive.x - primitive.radius < 0
                    or primitive.y - primitive.radius < 0
                    or primitive.x + primitive.radius >= frame.width
                    or primitive.y + primitive.radius >= frame.height
                ):
                    raise ValueError("production Vision circle is outside frame")
        return observed


class ProductionVisionHost:
    """Canonical production entry point for V83 visual cognition.

    Unlike VisualCognitiveLoop's dependency-free bootstrap constructor, this
    host refuses to start without an explicit production backend.
    """

    def __init__(self, backend: VisionBackend):
        backend.validate()
        if backend.kind != "production":
            raise VisionBackendUnavailable(
                "production visual host requires a production Vision backend"
            )
        owner = getattr(backend.observe_fn, "__self__", None)
        if isinstance(owner, PrimitiveVision):
            raise VisionBackendUnavailable(
                "PrimitiveVision is bootstrap-only and cannot be a production backend"
            )
        self.backend = backend
        self.adapter = StrictProductionVisionAdapter(backend)

    def build_loop(
        self,
        *,
        renderer: RendererPort | None = None,
    ) -> VisualCognitiveLoop:
        return VisualCognitiveLoop(
            renderer=renderer,
            vision=self.adapter,
        )

    def probe(self, frame: RasterFrame) -> VisualIR:
        return self.adapter.observe(frame)

    def manifest(self) -> dict:
        return {
            "schema": "fap.vision-host.v1",
            "backend_id": self.backend.backend_id,
            "backend_kind": self.backend.kind,
            "production_vision_required": True,
            "bootstrap_default": False,
            "vision_feedback_required": True,
            "state_space": "VisualIR",
        }


def build_production_visual_loop(
    backend: VisionBackend | None,
    *,
    renderer: RendererPort | None = None,
) -> VisualCognitiveLoop:
    if backend is None:
        raise VisionBackendUnavailable(
            "production Vision backend must be explicitly configured"
        )
    return ProductionVisionHost(backend).build_loop(renderer=renderer)


def build_bootstrap_visual_loop(
    *,
    renderer: RendererPort | None = None,
) -> VisualCognitiveLoop:
    """Explicit test/bootstrap path; never selected by the production builder."""
    return VisualCognitiveLoop(
        renderer=renderer,
        vision=PrimitiveVision(),
    )
