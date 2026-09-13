"""Content-Security-Policy of the scaffolded frontend's nginx.conf.

``src/index.html`` puts a ``CSP_NONCE`` placeholder on ``<app-root>``, and the production build
copies it onto every inline ``<script>`` and ``<style>`` (the theme script, the critical CSS and
its loader, the main bundle tag). nginx must swap the placeholder for a fresh per-request nonce and
allow that nonce in ``script-src`` and ``style-src``; otherwise the policy blocks Angular's inline
styles and scripts and the container serves an unstyled app.

The base layer and both api layers ship one identical ``frontend/nginx.conf``. The supabase and
entra frontend overlays ship their own, whose policy also allows the provider their SDK calls;
apart from that header (and its comment) they must match the base file.
"""

import re

import pytest

from project_initializer.cli import copy_template, get_templates_dir

_TEMPLATES = get_templates_dir()
_PACKAGE = _TEMPLATES.parent
_BASE_CONF = _TEMPLATES / "frontend" / "nginx.conf"
_API_CONFS = [_PACKAGE / f"templates-api-{framework}" / "frontend" / "nginx.conf" for framework in ("fastapi", "nestjs")]

# Hosts each auth overlay adds, by directive.
_PROVIDER_SOURCES = {
    "supabase": {"connect-src": ["https://*.supabase.co", "wss://*.supabase.co"]},
    "entra": {
        "connect-src": ["https://login.microsoftonline.com"],
        "frame-src": ["https://login.microsoftonline.com"],
    },
}

_VARIANTS = [
    (None, "fastapi"),
    (None, "nestjs"),
    ("token", "fastapi"),
    ("supabase", "fastapi"),
    ("supabase", "nestjs"),
    ("entra", "fastapi"),
    ("entra", "nestjs"),
]

_CSP_RE = re.compile(r'add_header Content-Security-Policy "([^"]*)" always;')


def _policy(conf_text):
    """Directive name -> source list of the Content-Security-Policy header."""
    match = _CSP_RE.search(conf_text)
    assert match, "nginx.conf must send a Content-Security-Policy header"
    directives = {}
    for part in match.group(1).split(";"):
        tokens = part.split()
        if tokens:
            directives[tokens[0]] = tokens[1:]
    return directives


def _spa_location(conf_text):
    """Body of the `location / { ... }` block that serves index.html."""
    match = re.search(r"\n    location / \{\n(.*?)\n    \}\n", conf_text, re.S)
    assert match, "nginx.conf must serve the app from `location /`"
    return match.group(1)


def _scaffold(dest, auth=None, framework="fastapi", scope="fullstack"):
    copy_template(dest, "app", auth=auth, framework=framework, scope=scope)
    return (dest / "frontend" / "nginx.conf").read_text(encoding="utf-8")


def _without_policy(conf_text):
    """The config minus the CSP header and comment lines, which overlays may change."""
    return [
        line
        for line in conf_text.splitlines()
        if "Content-Security-Policy" not in line and not line.lstrip().startswith("#")
    ]


@pytest.mark.parametrize("auth,framework", _VARIANTS)
def test_when_frontend_is_scaffolded_then_script_and_style_src_allow_only_the_request_nonce(tmp_path, auth, framework):
    policy = _policy(_scaffold(tmp_path, auth, framework))
    for directive in ("script-src", "style-src"):
        assert "'nonce-$request_id'" in policy[directive], f"{directive} must allow the per-request nonce"
        assert "'unsafe-inline'" not in policy[directive], f"{directive} must not fall back to 'unsafe-inline'"


@pytest.mark.parametrize("auth,framework", _VARIANTS)
def test_when_frontend_is_scaffolded_then_index_html_gets_the_nonce_swapped_in(tmp_path, auth, framework):
    location = _spa_location(_scaffold(tmp_path, auth, framework))
    assert re.search(r"^\s*sub_filter\s+CSP_NONCE\s+\$request_id;", location, re.M)
    # The placeholder sits on several tags, so every occurrence must be replaced.
    assert re.search(r"^\s*sub_filter_once\s+off;", location, re.M)
    index_html = (tmp_path / "frontend" / "src" / "index.html").read_text(encoding="utf-8")
    assert 'ngCspNonce="CSP_NONCE"' in index_html


def test_when_frontend_only_scope_is_scaffolded_then_the_nonce_policy_survives_the_proxy_strip(tmp_path):
    conf = _scaffold(tmp_path, scope="frontend")
    assert "location /api/" not in conf
    assert "'nonce-$request_id'" in _policy(conf)["script-src"]
    assert re.search(r"sub_filter\s+CSP_NONCE\s+\$request_id;", _spa_location(conf))


@pytest.mark.parametrize("auth,framework", _VARIANTS)
def test_when_frontend_is_scaffolded_then_the_web_font_host_in_index_html_is_allowed(tmp_path, auth, framework):
    policy = _policy(_scaffold(tmp_path, auth, framework))
    index_html = (tmp_path / "frontend" / "src" / "index.html").read_text(encoding="utf-8")
    for host in sorted(set(re.findall(r'href="(https://[^/"]+)/css', index_html))):
        assert host in policy["style-src"], f"style-src must allow the stylesheet host {host}"
        assert host in policy["font-src"], f"font-src must allow the font host {host}"


@pytest.mark.parametrize("auth", sorted(_PROVIDER_SOURCES))
@pytest.mark.parametrize("framework", ["fastapi", "nestjs"])
def test_when_auth_variant_is_scaffolded_then_its_provider_is_allowed(tmp_path, auth, framework):
    policy = _policy(_scaffold(tmp_path, auth, framework))
    assert "'self'" in policy["connect-src"], "the app must still reach its own /api/ proxy"
    for directive, hosts in _PROVIDER_SOURCES[auth].items():
        for host in hosts:
            assert host in policy[directive], f"{auth}: {directive} must allow {host}"


@pytest.mark.parametrize("auth", [None, "token"])
def test_when_no_identity_provider_is_used_then_connections_stay_same_origin(tmp_path, auth):
    policy = _policy(_scaffold(tmp_path, auth))
    assert policy.get("connect-src", ["'self'"]) == ["'self'"]
    assert "frame-src" not in policy


def test_when_api_layers_are_read_then_their_nginx_conf_is_the_base_file():
    base = _BASE_CONF.read_text(encoding="utf-8")
    for conf in _API_CONFS:
        assert conf.read_text(encoding="utf-8") == base, f"{conf} drifted from {_BASE_CONF}"


@pytest.mark.parametrize("auth", sorted(_PROVIDER_SOURCES))
def test_when_overlay_nginx_conf_is_read_then_only_its_policy_differs_from_the_base(auth):
    base_text = _BASE_CONF.read_text(encoding="utf-8")
    overlay_text = (_PACKAGE / f"templates-{auth}-frontend" / "frontend" / "nginx.conf").read_text(encoding="utf-8")
    assert _without_policy(overlay_text) == _without_policy(base_text)

    base_policy, overlay_policy = _policy(base_text), _policy(overlay_text)
    changed = {name for name in set(base_policy) | set(overlay_policy) if base_policy.get(name) != overlay_policy.get(name)}
    assert changed <= set(_PROVIDER_SOURCES[auth]), f"{auth} overlay may only add {sorted(_PROVIDER_SOURCES[auth])}"
