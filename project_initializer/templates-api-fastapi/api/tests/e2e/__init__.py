"""End-to-end smoke tests of the assembled application.

They check that the application boots, which routes it mounts, what its
OpenAPI document publishes and whether the interactive docs follow the
configured policy. They run in-process: no server, database or provider is
contacted. Mark each test ``e2e``.
"""
