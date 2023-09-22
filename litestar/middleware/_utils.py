from __future__ import annotations

import re
from typing import TYPE_CHECKING, Pattern

from litestar.exceptions import ImproperlyConfiguredException

__all__ = ("build_exclude_path_pattern", "should_bypass_middleware")


if TYPE_CHECKING:
    from litestar.types import Scope, Scopes


def build_exclude_path_pattern(*, exclude: str | list[str] | None = None) -> Pattern | None:
    """Build single path pattern from list of patterns to opt-out from middleware processing.

    Args:
        exclude: A pattern or a list of patterns.

    Returns:
        An optional pattern to match against scope["path"] to opt-out from middleware processing.
    """
    if exclude is None:
        return None

    try:
        return re.compile("|".join(exclude)) if isinstance(exclude, list) else re.compile(exclude)
    except re.error as e:  # pragma: no cover
        raise ImproperlyConfiguredException(
            "Unable to compile exclude patterns for middleware. Please make sure you passed a valid regular expression."
        ) from e


def should_bypass_middleware(
    *,
    scope: Scope,
    scopes: Scopes,
    exclude_opt_key: str | None = None,
    exclude_path_pattern: Pattern | None = None,
) -> bool:
    """Determine weather a middleware should be bypassed.

    Args:
        scope: The ASGI scope.
        scopes: A set with the ASGI scope types that are supported by the middleware.
        exclude_opt_key: Key in ``opt`` with which a route handler can "opt-out" of a middleware.
        exclude_path_pattern: If this pattern matches scope["path"], the middleware should
            be bypassed.

    Returns:
        A boolean indicating if a middleware should be bypassed
    """
    if scope["type"] not in scopes:
        return True

    if exclude_opt_key and scope["route_handler"].opt.get(exclude_opt_key):
        return True

    return bool(
        exclude_path_pattern
        and exclude_path_pattern.findall(
            scope["raw_path"].decode() if getattr(scope.get("route_handler", {}), "is_mount", False) else scope["path"]
        )
    )
