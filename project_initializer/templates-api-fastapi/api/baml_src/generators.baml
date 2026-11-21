generator target {
  output_type "python/pydantic"
  output_dir "../"

  // Must equal the baml-py pin in requirements.txt and the baml-cli that runs
  // `baml-cli generate`; a mismatched runtime rejects the generated client.
  version "0.223.0"

  default_client_mode sync
}
