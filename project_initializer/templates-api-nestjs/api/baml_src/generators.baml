generator target {
    output_type "typescript"
    output_dir "../"

    // Must equal the @boundaryml/baml pin in package.json and the baml-cli that runs
    // `baml-cli generate`; a mismatched runtime rejects the generated client.
    version "0.223.0"

    default_client_mode async
}
