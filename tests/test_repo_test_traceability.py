"""Traceability guard for the repo's own test suite.

Code standard 6.6 asks each test to cite its requirement ID and the code it
validates. This repo has no requirement tracker, so the written-down adaptation
(standard 1.4, see CLAUDE.md and CONTRIBUTING.md) is: repo tests carry no
requirement IDs, and each one ends its docstring with a ``Validates <path or
symbol>.`` line that names the template file, generator function or document it
inspects. The change itself is traced through the ``CHANGELOG.md`` entry.

Two lists define where the convention is enforced:

* ``NEW_MODULES`` holds the modules in which every test is checked: the modules
  that are new or were rewritten, and an older module once all its tests carry the
  line. A new test module is added to it in the same change that creates the module.
* ``TRACED_FUNCTIONS`` holds, per older module, only the test functions that a
  change wrote or rewrote (a new test, or one whose body or target it changed).
  The other tests of those modules predate the convention and stay unchecked until
  a change touches them; that change annotates them and lists them here.
"""

import ast
from collections.abc import Collection, Iterator
from pathlib import Path

import pytest

NEW_MODULES = (
    "test_asyncdb_overlay.py",
    "test_docs_compliance_sync.py",
    "test_docs_nestjs_compliance.py",
    "test_entra_fastapi_integration_matrix.py",
    "test_entra_fastapi_overlay.py",
    "test_env_generator_runtime_defaults.py",
    "test_env_generator_secrets.py",
    "test_fastapi_dependencies.py",
    "test_fastapi_migrations.py",
    "test_frontend_dependency_upgrade.py",
    "test_nestjs_auth_seam.py",
    "test_nestjs_migrations.py",
    "test_no_ai_framework_in_templates.py",
    "test_python_metadata_single_source.py",
    "test_template_packaging_complete.py",
    "test_repo_test_traceability.py",
)

TRACED_FUNCTIONS: dict[str, frozenset[str]] = {
    "test_async_db_flag.py": frozenset(
        {
            "test_when_pyproject_transformed_then_async_runtime_deps_join_dependencies",
            "test_when_pyproject_transformed_then_aiosqlite_joins_dev_extra",
            "test_when_pyproject_transformed_then_existing_dependencies_survive",
            "test_when_pyproject_transformed_twice_then_second_pass_changes_nothing",
            "test_when_pyproject_already_has_asyncpg_then_transform_returns_it_unchanged",
            "test_when_pyproject_lacks_an_array_then_transform_raises_value_error",
            "test_when_scaffolded_with_async_db_then_pyproject_declares_async_deps",
            "test_when_scaffolded_with_async_db_then_no_requirements_txt_exists",
            "test_when_supabase_scaffolded_with_async_db_then_pyproject_gains_async_deps",
            "test_when_scaffolded_with_async_db_async_files_exist",
            "test_when_async_db_false_scaffold_is_byte_identical_to_default",
        }
    ),
    "test_ci_workflow_scope.py": frozenset(
        {
            "test_when_api_only_steps_are_gated_against_frontend_scope",
        }
    ),
    "test_docker_runtime_invariants.py": frozenset(
        {
            "test_fastapi_server_does_not_write_the_unstructured_access_log",
            "test_fastapi_image_keeps_the_application_code_root_owned",
            "test_fastapi_entrypoint_waits_on_the_database_the_application_will_use",
            "test_fastapi_dockerfile_installs_the_client_the_entrypoint_needs",
            "test_nestjs_entrypoint_waits_on_the_database_the_application_will_use",
            "test_nestjs_production_image_ships_the_prisma_config_the_entrypoint_needs",
            "test_no_compose_file_hardcodes_container_names",
            "test_every_published_host_port_is_parametrized",
        }
    ),
    "test_docs_frontend_material.py": frozenset(
        {
            "test_when_frontend_claude_generated_then_material_convention_is_documented_and_real",
        }
    ),
    "test_docs_sync_async.py": frozenset(
        {
            "test_when_api_claude_md_read_async_reserved_for_real_async_io_documented",
            "test_when_api_claude_md_read_canonical_sync_example_cited",
        }
    ),
    "test_entra_nestjs_overlay.py": frozenset(
        {
            "test_when_overlay_is_present_then_inherited_file_is_not_duplicated",
            "test_when_overlay_is_present_then_per_variant_guard_file_is_gone",
            "test_when_env_validation_is_read_then_it_extends_the_base_schema",
            "test_when_env_validation_is_read_then_unused_postgres_var_is_not_required",
            "test_when_auth_guard_is_read_then_class_is_named_access_token_guard",
            "test_when_auth_guard_is_read_then_public_decorator_is_honoured",
            "test_when_auth_module_is_read_then_entra_verifier_is_provided_as_access_token_verifier",
            "test_when_auth_module_is_read_then_access_token_verifier_is_exported",
            "test_when_app_auth_is_read_then_access_token_guard_is_registered_as_app_guard",
            "test_when_app_auth_is_read_then_access_token_guard_appears_exactly_once_as_app_guard",
            "test_when_app_module_is_read_then_throttler_guard_precedes_the_auth_guards",
            "test_when_auth_guard_is_read_then_401_status_code_is_used_for_auth_failure",
            "test_when_base_layer_is_present_then_shared_parity_test_file_exists",
            "test_when_verifier_spec_is_read_then_it_exercises_the_entra_checks",
            "test_when_overlay_is_present_then_required_file_exists",
            "test_when_overlay_is_present_then_parity_test_file_exists",
            "test_when_overlay_is_scanned_then_no_client_secret_is_present",
        }
    ),
    "test_issue5_nestjs_global_criteria.py": frozenset(
        {
            "test_when_auth_overlay_app_auth_is_read_then_app_guard_provider_is_present",
            "test_when_auth_overlay_app_auth_is_read_then_auth_guard_class_is_provided_as_app_guard",
            "test_when_app_module_is_read_then_database_url_is_required_in_env_validation",
            "test_when_supabase_env_validation_is_read_then_supabase_secrets_are_required",
            "test_when_app_module_is_read_then_config_module_uses_validate_option",
            "test_when_app_setup_and_main_ts_are_read_then_global_prefix_api_v1_is_set",
        }
    ),
    "test_issue_003_zod_serialization.py": frozenset(
        {
            "test_when_auth_overlay_app_auth_is_read_then_app_guard_is_registered",
            "test_when_base_env_validation_is_read_then_database_url_is_required",
            "test_when_overlay_is_listed_then_it_does_not_replace_the_shared_app_module",
            "test_when_app_module_is_read_then_zod_validation_pipe_is_registered_as_app_pipe",
            "test_when_app_module_is_read_then_zod_serializer_interceptor_is_registered_as_app_interceptor",
            "test_when_all_controller_files_are_read_then_data_handlers_carry_zod_serializer_dto",
            "test_when_all_dto_files_are_read_then_no_schema_calls_passthrough",
            "test_when_serialization_spec_is_searched_then_it_exists",
            "test_when_serialization_spec_is_read_then_it_asserts_password_is_stripped",
        }
    ),
    "test_issue_11_packaging.py": frozenset(
        {
            "test_when_fastapi_pyproject_checked_then_pyjwt_crypto_is_declared",
            "test_when_fastapi_entra_overlay_checked_then_auth_seam_and_verifier_exist",
            "test_when_entra_env_example_generated_then_no_client_secret_is_present",
        }
    ),
    "test_issue_12_global_criteria.py": frozenset(
        {
            "test_when_fastapi_overlay_present_then_pyjwt_crypto_in_pyproject",
            "test_when_fastapi_env_example_present_then_no_client_secret_key",
            "test_when_fastapi_overlay_present_then_pyjwks_client_used",
            "test_when_fastapi_verifier_present_then_rs256_algorithm_is_enforced",
            "test_when_fastapi_verifier_present_then_audience_is_validated",
            "test_when_fastapi_verifier_present_then_issuer_is_validated",
            "test_when_fastapi_verifier_present_then_tid_pinning_present",
            "test_when_fastapi_verifier_present_then_scp_scope_enforced",
            "test_when_fastapi_verifier_and_handlers_present_then_401_on_auth_failure",
            "test_when_fastapi_verifier_and_handlers_present_then_403_on_insufficient_scope",
            "test_when_any_entra_overlay_dir_checked_then_it_contains_at_least_one_file",
            "test_when_fastapi_overlay_present_then_no_hard_coded_refresh_schedule",
            "test_when_nestjs_overlay_present_then_no_hard_coded_refresh_schedule",
        }
    ),
    "test_issue_12_toast.py": frozenset(
        {
            "test_when_toast_service_parsed_then_it_is_a_root_singleton",
        }
    ),
    "test_issue_13_jwks_auto_refresh.py": frozenset(
        {
            "test_when_fastapi_verifier_is_read_then_pyjwkclient_is_used_for_key_fetching",
            "test_when_fastapi_verifier_is_read_then_no_hard_coded_refresh_interval_is_present",
        }
    ),
    "test_issue_13_jwt_validation.py": frozenset(
        {
            "test_when_fastapi_overlay_dependencies_are_read_then_pyjwt_crypto_is_declared",
            "test_when_fastapi_verifier_is_read_then_jwks_client_is_used",
            "test_when_fastapi_verifier_is_read_then_tid_pinning_is_present",
            "test_when_fastapi_verifier_is_read_then_scp_scope_is_enforced",
            "test_when_fastapi_verifier_and_handlers_are_read_then_401_is_raised_on_auth_failure",
            "test_when_fastapi_verifier_and_handlers_are_read_then_403_is_raised_on_insufficient_scope",
            "test_when_fastapi_overlay_dependencies_are_read_then_rs256_algorithm_is_enforced",
            "test_when_fastapi_overlay_dependencies_are_read_then_aud_is_validated",
            "test_when_fastapi_overlay_dependencies_are_read_then_iss_is_validated",
        }
    ),
    "test_issue_13_nestjs_production_readiness.py": frozenset(
        {
            "test_when_token_overlay_app_auth_is_read_then_access_token_guard_is_wired_as_app_guard",
            "test_when_supabase_overlay_app_auth_is_read_then_access_token_guard_is_wired_as_app_guard",
            "test_when_base_env_validation_is_read_then_database_url_is_a_required_field",
            "test_when_supabase_env_validation_is_read_then_supabase_url_is_a_required_field",
            "test_when_serialization_spec_is_read_then_it_asserts_secret_field_is_absent_from_response",
            "test_when_claude_md_is_read_then_it_references_all_five_global_acceptance_criteria",
        }
    ),
    "test_issue_13_no_client_secret.py": frozenset(
        {
            "test_when_fastapi_env_example_is_read_then_no_client_secret_key_is_present",
            "test_when_fastapi_entra_auth_modules_are_read_then_no_client_secret_usage_is_present",
        }
    ),
    "test_issue_14.py": frozenset(
        {
            "test_when_token_app_auth_is_read_then_app_guard_is_registered",
            "test_when_supabase_app_auth_is_read_then_app_guard_is_registered",
            "test_when_config_module_setup_is_read_then_validate_option_is_present",
            "test_when_env_validation_schema_is_read_then_required_secrets_are_declared",
            "test_when_user_response_schema_is_read_then_password_field_is_not_exposed",
            "test_when_any_response_schema_is_sampled_then_no_password_field_is_exposed",
        }
    ),
    "test_issue_15_app_filter_docs.py": frozenset(
        {
            "test_when_token_overlay_app_auth_is_read_then_access_token_guard_is_wired_as_app_guard",
            "test_when_supabase_overlay_app_auth_is_read_then_access_token_guard_is_wired_as_app_guard",
            "test_when_env_validation_module_is_read_then_database_url_is_required",
            "test_when_response_schema_exists_then_password_field_is_absent",
            "test_when_token_overlay_app_module_is_read_then_app_guard_is_imported",
            "test_when_supabase_overlay_app_module_is_read_then_app_guard_is_imported",
        }
    ),
    "test_issue_15_ci_matrix_entra.py": frozenset(
        {
            "test_when_fastapi_entra_row_install_cmd_is_pip_install_of_the_api_extras",
        }
    ),
    "test_issue_15_entra_global_criteria.py": frozenset(
        {
            "test_when_fastapi_overlay_read_pyjwt_crypto_is_declared_as_dependency",
            "test_when_fastapi_verifier_read_rs256_algorithm_is_referenced",
            "test_when_fastapi_verifier_read_aud_claim_is_validated",
            "test_when_fastapi_verifier_read_iss_claim_is_validated",
            "test_when_fastapi_verifier_read_tid_claim_is_validated",
            "test_when_fastapi_verifier_read_scp_scope_is_enforced",
            "test_when_fastapi_verifier_and_handlers_read_401_is_returned_on_auth_failure",
            "test_when_fastapi_verifier_and_handlers_read_403_is_returned_on_insufficient_scope",
            "test_when_fastapi_verifier_read_pyjwkclient_is_used",
            "test_when_fastapi_verifier_read_no_hard_coded_refresh_interval",
            "test_when_nestjs_auth_guard_read_401_is_returned_on_auth_failure",
            "test_when_nestjs_auth_guard_read_403_is_returned_on_insufficient_scope",
            "test_when_fastapi_overlay_files_read_client_secret_is_absent",
            "test_when_nestjs_overlay_files_read_client_secret_is_absent",
        }
    ),
    "test_issue_19_avatar_stat_card.py": frozenset(
        {
            "test_when_stat_card_read_then_delta_direction_is_not_signaled_by_color_alone",
        }
    ),
    "test_issue_1_tailwind_bump.py": frozenset(
        {
            "test_when_package_json_read_then_material_package_is_a_22_3_runtime_dependency",
            "test_when_package_lock_read_then_angular_material_resolves_to_22_3",
        }
    ),
    "test_issue_20_pagination_accordion.py": frozenset(
        {
            "test_when_accordion_css_is_generated_then_expanded_headers_get_a_hover_state_layer",
        }
    ),
    "test_issue_2_nestjs_guard_wiring.py": frozenset(
        {
            "test_when_token_app_auth_is_read_then_AccessTokenGuard_is_registered_as_APP_GUARD",
            "test_when_supabase_app_auth_is_read_then_AccessTokenGuard_is_registered_as_APP_GUARD",
            "test_when_token_app_module_providers_are_listed_then_ThrottlerGuard_appears_before_AuthGuard",
            "test_when_supabase_app_module_providers_are_listed_then_ThrottlerGuard_appears_before_AuthGuard",
            "test_when_token_auth_guard_source_is_read_then_it_checks_Public_metadata_to_allow",
            "test_when_supabase_auth_guard_source_is_read_then_it_checks_Public_metadata_to_allow",
            "test_when_Authorization_header_is_absent_then_token_auth_guard_rejects",
            "test_when_Authorization_header_is_absent_then_supabase_auth_guard_rejects",
            "test_when_token_app_module_is_read_then_ConfigModule_has_env_validation_for_DATABASE_URL",
            "test_when_supabase_app_module_is_read_then_ConfigModule_has_env_validation_for_SUPABASE_vars",
            "test_when_token_overlay_is_listed_then_app_module_spec_file_exists",
            "test_when_supabase_overlay_is_listed_then_app_module_spec_file_exists",
            "test_when_token_overlay_is_listed_then_auth_guard_spec_file_exists",
            "test_when_supabase_overlay_is_listed_then_supabase_auth_guard_spec_file_exists",
            "test_when_token_overlay_source_is_read_then_no_response_schema_uses_passthrough",
            "test_when_supabase_overlay_source_is_read_then_no_response_schema_uses_passthrough",
            "test_when_base_nestjs_template_source_is_read_then_no_response_schema_uses_passthrough",
        }
    ),
    "test_issue_6_nestjs_hardening.py": frozenset(
        {
            "test_when_token_auth_scaffolded_auth_guard_is_registered_as_app_guard",
            "test_when_supabase_auth_scaffolded_auth_guard_is_registered_as_app_guard",
            "test_when_nestjs_base_scaffolded_logger_config_has_a_companion_spec",
        }
    ),
    "test_issue_7_entra_auth_service.py": frozenset(
        {
            "test_when_fastapi_pyproject_is_read_then_pyjwt_crypto_is_declared",
            "test_when_fastapi_verifier_is_read_then_tid_pinning_is_enforced",
            "test_when_fastapi_verifier_is_read_then_scp_scope_is_checked",
            "test_when_fastapi_verifier_and_handlers_are_read_then_401_is_returned_on_auth_failure",
            "test_when_fastapi_verifier_and_handlers_are_read_then_403_is_returned_on_insufficient_scope",
            "test_when_fastapi_env_example_is_read_then_client_secret_key_is_absent",
            "test_when_fastapi_verifier_is_read_then_pyjwkclient_is_used_for_auto_refresh",
            "test_when_auth_service_template_is_read_then_it_is_a_root_singleton",
        }
    ),
    "test_issue_9_backend_jwt_validation.py": frozenset(
        {
            "test_when_fastapi_overlay_present_then_401_status_is_returned_on_auth_failure",
            "test_when_fastapi_overlay_present_then_403_status_is_returned_on_insufficient_scope",
            "test_when_fastapi_overlay_present_then_claim_is_validated",
            "test_when_fastapi_overlay_present_then_no_hard_coded_refresh_interval_is_present",
            "test_when_fastapi_overlay_present_then_pyjwkclient_is_used_for_jwks",
            "test_when_fastapi_overlay_present_then_rs256_algorithm_is_declared",
            "test_when_nestjs_overlay_present_then_401_status_is_returned_on_auth_failure",
            "test_when_nestjs_overlay_present_then_403_status_is_returned_on_insufficient_scope",
            "test_when_nestjs_overlay_present_then_claim_is_validated",
            "test_when_nestjs_overlay_present_then_jwks_rsa_cache_is_enabled",
            "test_when_nestjs_overlay_present_then_jwks_rsa_rate_limit_is_enabled",
            "test_when_nestjs_overlay_present_then_rs256_algorithm_is_declared",
        }
    ),
    "test_issue_9_feedback_atoms.py": frozenset(
        {
            "test_when_alert_source_read_then_each_variant_has_a_leading_icon",
        }
    ),
    "test_issue_9_nestjs_acceptance.py": frozenset(
        {
            "test_when_token_app_auth_is_inspected_auth_guard_is_registered_as_app_guard",
            "test_when_supabase_app_auth_is_inspected_auth_guard_is_registered_as_app_guard",
            "test_when_item_dto_is_inspected_response_schema_does_not_include_sensitive_field_names",
        }
    ),
    "test_issue_9_no_client_secret.py": frozenset(
        {
            "test_when_fastapi_overlay_env_example_present_then_no_client_secret_is_listed",
            "test_when_fastapi_overlay_present_then_no_client_secret_is_in_source",
            "test_when_nestjs_overlay_present_then_no_client_secret_is_in_source",
        }
    ),
    "test_nestjs_build_config.py": frozenset(
        {
            "test_when_both_packages_compared_only_supabase_js_differs",
            "test_when_package_read_lint_and_format_scripts_fail_on_findings",
            "test_when_package_read_coverage_threshold_is_enforced",
            "test_when_package_read_jest_loads_the_test_environment_first",
            "test_when_package_read_lint_tooling_is_pinned_exactly",
        }
    ),
    "test_nestjs_issue8_acceptance.py": frozenset(
        {
            "test_when_token_overlay_app_auth_is_read_then_APP_GUARD_is_registered",
            "test_when_supabase_overlay_app_auth_is_read_then_APP_GUARD_is_registered",
            "test_when_config_validation_is_read_then_DATABASE_URL_is_a_required_key",
            "test_when_response_schema_files_are_read_then_password_is_not_a_whitelisted_field",
            "test_when_src_tree_is_searched_then_at_least_one_provider_spec_uses_TestingModule",
        }
    ),
    "test_nestjs_lockfile_sync.py": frozenset(
        {
            "test_nestjs_layer_owns_a_lock_exactly_when_it_ships_a_package_json",
        }
    ),
    "test_scope_scaffold.py": frozenset(
        {
            "test_when_fullstack_scaffolded_twice_trees_are_identical",
        }
    ),
}

VALIDATES_PREFIX = "Validates "
_TESTS_DIR = Path(__file__).resolve().parent


def _test_functions(source: str) -> Iterator[ast.FunctionDef | ast.AsyncFunctionDef]:
    """Yield every ``test_*`` function or method defined in ``source``."""
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            if node.name.startswith("test_"):
                yield node


def _names_the_code_it_validates(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Tell whether the last docstring line of ``node`` is a non-empty Validates line."""
    docstring = ast.get_docstring(node) or ""
    lines = [line for line in docstring.splitlines() if line.strip()]
    if not lines or not lines[-1].startswith(VALIDATES_PREFIX):
        return False
    return bool(lines[-1].removeprefix(VALIDATES_PREFIX).strip())


def untraced_tests(source: str, only: Collection[str] | None = None) -> list[str]:
    """List the test functions of ``source`` that do not name the code they validate.

    A test function is any ``test_*`` function or method. It is traced when the
    last non-blank line of its docstring starts with ``Validates `` and names
    something after it.

    Args:
        source: Python source text of one test module.
        only: When given, only the test functions with these names are checked;
            the others are ignored. ``None`` checks every test function.

    Returns:
        The sorted names of the checked test functions that lack the line; empty
        when every checked test is traced.
    """
    offenders = [
        node.name
        for node in _test_functions(source)
        if (only is None or node.name in only)
        and not _names_the_code_it_validates(node)
    ]
    return sorted(offenders)


def _read_module(module: str) -> str:
    return (_TESTS_DIR / module).read_text(encoding="utf-8")


@pytest.mark.parametrize("module", NEW_MODULES)
def test_when_a_listed_module_is_parsed_then_every_test_names_the_code_it_validates(
    module: str,
):
    """Every test function of a listed module ends its docstring with a Validates line.

    Validates tests/test_repo_test_traceability.py untraced_tests().
    """
    assert untraced_tests(_read_module(module)) == [], (
        f"{module}: add a final 'Validates <path or symbol>.' docstring line to these tests"
    )


@pytest.mark.parametrize("module", sorted(TRACED_FUNCTIONS))
def test_when_a_module_lists_traced_functions_then_each_names_the_code_it_validates(
    module: str,
):
    """Each function listed for an older module ends its docstring with a Validates line.

    Validates tests/test_repo_test_traceability.py untraced_tests() with only=TRACED_FUNCTIONS.
    """
    offenders = untraced_tests(_read_module(module), only=TRACED_FUNCTIONS[module])

    assert offenders == [], (
        f"{module}: add a final 'Validates <path or symbol>.' docstring line to these tests"
    )


@pytest.mark.parametrize("module", sorted(TRACED_FUNCTIONS))
def test_when_a_module_lists_traced_functions_then_each_is_still_defined_there(
    module: str,
):
    """A renamed or deleted function must leave the list, or its check silently lapses.

    Validates tests/test_repo_test_traceability.py TRACED_FUNCTIONS.
    """
    defined = {node.name for node in _test_functions(_read_module(module))}

    assert sorted(TRACED_FUNCTIONS[module] - defined) == []


@pytest.mark.parametrize(
    ("source", "only", "expected"),
    [
        pytest.param("def test_a():\n    pass\n", None, ["test_a"], id="no-docstring"),
        pytest.param(
            "def test_a():\n    '''Says what it checks.'''\n",
            None,
            ["test_a"],
            id="plain-docstring",
        ),
        pytest.param(
            "def test_a():\n    '''Validates cli.py.\n\n    Trailing prose.\n    '''\n",
            None,
            ["test_a"],
            id="validates-not-last",
        ),
        pytest.param(
            "def test_a():\n    '''Says what it checks.\n\n    Validates\n    '''\n",
            None,
            ["test_a"],
            id="empty-target",
        ),
        pytest.param(
            "class TestGroup:\n    def test_a(self):\n        '''Says it.'''\n",
            None,
            ["test_a"],
            id="method",
        ),
        pytest.param("def helper():\n    pass\n", None, [], id="not-a-test"),
        pytest.param(
            "def test_a():\n    '''Says it.\n\n    Validates cli.py copy_template().\n    '''\n",
            None,
            [],
            id="traced",
        ),
        pytest.param(
            "def test_old():\n    pass\n\ndef test_new():\n    pass\n",
            {"test_new"},
            ["test_new"],
            id="only-checks-the-named-function",
        ),
        pytest.param(
            "def test_old():\n    pass\n",
            {"test_new"},
            [],
            id="only-ignores-an-unnamed-function",
        ),
    ],
)
def test_when_a_test_lacks_a_validates_line_then_it_is_reported(
    source: str, only: set[str] | None, expected: list[str]
):
    """A missing docstring, a Validates line that is not last or an empty target fails.

    Validates tests/test_repo_test_traceability.py untraced_tests().
    """
    assert untraced_tests(source, only=only) == expected


def test_when_new_modules_are_listed_then_each_exists_and_this_module_is_one():
    """A renamed or deleted module must leave the list, and this guard guards itself.

    Validates tests/test_repo_test_traceability.py NEW_MODULES.
    """
    missing = [name for name in NEW_MODULES if not (_TESTS_DIR / name).is_file()]

    assert missing == []
    assert Path(__file__).name in NEW_MODULES


def test_when_a_module_is_fully_checked_then_it_is_not_also_listed_per_function():
    """A module in NEW_MODULES is checked whole, so a per-function entry would be dead weight.

    Validates tests/test_repo_test_traceability.py NEW_MODULES and TRACED_FUNCTIONS.
    """
    assert sorted(set(NEW_MODULES) & set(TRACED_FUNCTIONS)) == []
