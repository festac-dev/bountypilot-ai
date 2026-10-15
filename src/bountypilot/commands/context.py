"""Shared CLI context: builds AppServices once per invocation from global options."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from bountypilot.output import set_json_mode
from bountypilot.settings import Settings, load_settings

_state: dict[str, Any] = {}

if TYPE_CHECKING:
    from bountypilot.services.container import AppServices


class CliContext:
    def __init__(
        self,
        verbose: bool = False,
        quiet: bool = False,
        json_mode: bool = False,
        no_color: bool = False,
        debug: bool = False,
        data_dir: Optional[str] = None,
    ) -> None:
        self.verbose = verbose
        self.quiet = quiet
        self.json_mode = json_mode
        self.no_color = no_color
        self.debug = debug
        self.data_dir = data_dir
        self._services: Optional[AppServices] = None

    def settings(self) -> Settings:
        overrides: dict[str, Any] = {}
        if self.data_dir:
            overrides["DATA_DIRECTORY"] = self.data_dir
        if self.json_mode:
            overrides["OUTPUT_FORMAT"] = "json"
        return load_settings(overrides=overrides or None)

    def services(self) -> AppServices:
        if self._services is None:
            from bountypilot.services.container import AppServices

            self._services = AppServices(self.settings())
        return self._services


def set_context(ctx: CliContext) -> None:
    _state["ctx"] = ctx
    if ctx.json_mode:
        set_json_mode(True)


def get_context() -> CliContext:
    ctx = _state.get("ctx")
    if ctx is None:
        ctx = CliContext()
        _state["ctx"] = ctx
    return ctx


def get_services() -> AppServices:
    return get_context().services()
