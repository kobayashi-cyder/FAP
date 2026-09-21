from .routing import LazyOrganPool, OrganRoute, SparseOrganRouter

_RENDER_EXPORTS = {
    "activate_sparse_renderers",
    "background_cache_info",
    "last_render_stats",
    "render_scientific_fast_png",
    "render_sparse_photo_look_png",
}


def __getattr__(name):
    if name in _RENDER_EXPORTS:
        from . import renderer
        return getattr(renderer, name)
    raise AttributeError(name)


__all__ = [
    "LazyOrganPool",
    "OrganRoute",
    "SparseOrganRouter",
    *_RENDER_EXPORTS,
]
