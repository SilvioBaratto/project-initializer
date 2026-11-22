"""Facts about the NestJS API image that more than one guard compares against.

Kept out of the test modules so that a Node bump has one place to be read from,
and so that no test module imports another.
"""

import re
from pathlib import Path

NESTJS_DOCKERFILE = (
    Path(__file__).resolve().parent.parent
    / "project_initializer"
    / "templates-api-nestjs"
    / "api"
    / "Dockerfile"
)


def nestjs_dockerfile_node_majors() -> set[int]:
    """Return the Node major of every ``FROM node:`` line of the NestJS API Dockerfile.

    A stage that inherits another (``FROM dev AS builder``) has no Node line and
    is not counted.
    """
    dockerfile = NESTJS_DOCKERFILE.read_text(encoding="utf-8")
    return {int(major) for major in re.findall(r"^FROM node:(\d+)", dockerfile, re.M)}
