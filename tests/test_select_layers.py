"""Unit tests for the pure scope -> layer routing helper."""

import pytest

from project_initializer.cli import (
    get_api_templates_dir,
    get_auth_frontend_overlay_dir,
    get_auth_overlay_dir,
    get_templates_dir,
    select_layers,
)


def _srcs(layers):
    return [src for src, _skip, _transform in layers]


def test_when_fullstack_no_auth_only_base_and_api_layers_are_returned():
    layers = select_layers("fullstack", "fastapi", None)
    assert _srcs(layers) == [get_templates_dir(), get_api_templates_dir("fastapi")]


def test_when_fullstack_with_auth_both_overlays_follow_in_merge_order():
    layers = select_layers("fullstack", "nestjs", "token")
    assert _srcs(layers) == [
        get_templates_dir(),
        get_api_templates_dir("nestjs"),
        get_auth_overlay_dir("token", "nestjs"),
        get_auth_frontend_overlay_dir("token"),
    ]


@pytest.mark.parametrize("framework", ["fastapi", "nestjs"])
@pytest.mark.parametrize("auth", [None, "token", "supabase"])
def test_when_fullstack_every_layer_has_empty_skip_and_no_transform(framework, auth):
    for _src, skip, transform in select_layers("fullstack", framework, auth):
        assert skip == frozenset()
        assert transform is None


def test_when_api_scope_base_and_api_layers_skip_frontend_subdir():
    layers = select_layers("api", "fastapi", None)
    assert _srcs(layers) == [get_templates_dir(), get_api_templates_dir("fastapi")]
    assert all(skip == frozenset({"frontend"}) for _s, skip, _t in layers)


def test_when_api_scope_with_auth_applies_api_overlay_but_not_frontend_overlay():
    layers = select_layers("api", "fastapi", "token")
    srcs = _srcs(layers)
    assert get_auth_overlay_dir("token", "fastapi") in srcs
    assert get_auth_frontend_overlay_dir("token") not in srcs


def test_when_frontend_scope_only_base_layer_is_returned():
    layers = select_layers("frontend", "fastapi", None)
    assert _srcs(layers) == [get_templates_dir()]
    assert all(skip == frozenset() for _s, skip, _t in layers)


def test_when_frontend_scope_no_api_layer_is_present():
    srcs = _srcs(select_layers("frontend", "fastapi", None))
    assert get_api_templates_dir("fastapi") not in srcs
