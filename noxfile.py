# -*- coding: utf-8 -*-
#
# Copyright 2020 Google LLC
#
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd


from __future__ import absolute_import

import os
import pathlib
import shutil

import nox

BLACK_VERSION = "black==22.3.0"
BLACK_PATHS = [
    "docs",
    "django_spanner",
    "tests",
    "noxfile.py",
    "setup.py",
]

MOCKSERVER_TEST_PYTHON_VERSION = "3.12"
DEFAULT_PYTHON_VERSION = "3.8"
SYSTEM_TEST_PYTHON_VERSIONS = ["3.8"]
UNIT_TEST_PYTHON_VERSIONS = ["3.8", "3.9", "3.10"]

CURRENT_DIRECTORY = pathlib.Path(__file__).parent.absolute()


@nox.session(python=DEFAULT_PYTHON_VERSION)
def lint(session):
    """Run linters.

    Returns a failure if the linters find linting errors or sufficiently
    serious code quality issues.
    """
    session.install("flake8", BLACK_VERSION)
    session.run("black", "--check", *BLACK_PATHS)
    session.run("flake8", "django_spanner", "tests")


@nox.session(python=DEFAULT_PYTHON_VERSION)
def blacken(session):
    """Run black.

    Format code to uniform standard.

    This currently uses Python 3.6 due to the automated Kokoro run of synthtool.
    That run uses an image that doesn't have 3.6 installed. Before updating this
    check the state of the `gcp_ubuntu_config` we use for that Kokoro run.
    """
    session.install(BLACK_VERSION)
    session.run("black", *BLACK_PATHS)


@nox.session(python=DEFAULT_PYTHON_VERSION)
def lint_setup_py(session):
    """Verify that setup.py is valid (including RST check)."""
    session.install("docutils", "pygments")
    session.run(
        "python", "setup.py", "check", "--restructuredtext", "--strict"
    )


def default(session, django_version="3.2"):
    # Install all test dependencies, then install this package in-place.
    session.install(
        "setuptools",
        "django~={}".format(django_version),
        "mock",
        "mock-import",
        "pytest",
        "pytest-cov",
        "coverage",
        "sqlparse==0.3.1",
        "google-cloud-spanner>=3.13.0",
        "opentelemetry-api==1.1.0",
        "opentelemetry-sdk==1.1.0",
        "opentelemetry-instrumentation==0.20b0",
    )
    session.install("-e", ".")

    # Run py.test against the unit tests.
    session.run(
        "py.test",
        "--quiet",
        "--cov=django_spanner",
        "--cov=tests.unit",
        "--cov-append",
        "--cov-config=.coveragerc",
        "--cov-report=",
        "--cov-fail-under=75",
        os.path.join("tests", "unit"),
        *session.posargs,
    )


@nox.session(python=UNIT_TEST_PYTHON_VERSIONS)
def unit(session):
    """Run the unit test suite."""
    print("Unit tests with django 3.2")
    default(session)
    print("Unit tests with django 4.2")
    default(session, django_version="4.2")


@nox.session(python=MOCKSERVER_TEST_PYTHON_VERSION)
def mockserver(session):
    # Install all test dependencies, then install this package in-place.
    session.install(
        "setuptools",
        "django~=4.2",
        "mock",
        "mock-import",
        "pytest",
        "pytest-cov",
        "coverage",
        "sqlparse>=0.4.4",
        "google-cloud-spanner>=3.55.0",
        "opentelemetry-api==1.1.0",
        "opentelemetry-sdk==1.1.0",
        "opentelemetry-instrumentation==0.20b0",
    )
    session.install("-e", ".")
    session.run(
        "py.test",
        "--quiet",
        os.path.join("tests", "mockserver_tests"),
        *session.posargs,
    )


def system_test(session, django_version="3.2"):
    """Run the system test suite."""
    constraints_path = str(
        CURRENT_DIRECTORY / "testing" / f"constraints-{session.python}.txt"
    )
    system_test_path = os.path.join("tests", "system.py")
    system_test_folder_path = os.path.join("tests", "system")

    # Check the value of `RUN_SYSTEM_TESTS` env var. It defaults to true.
    if os.environ.get("RUN_SYSTEM_TESTS", "true") == "false":
        session.skip("RUN_SYSTEM_TESTS is set to false, skipping")
    # Sanity check: Only run tests if the environment variable is set.
    if not os.environ.get(
        "GOOGLE_APPLICATION_CREDENTIALS", ""
    ) and not os.environ.get("SPANNER_EMULATOR_HOST", ""):
        session.skip(
            "Credentials or emulator host must be set via environment variable"
        )

    system_test_exists = os.path.exists(system_test_path)
    system_test_folder_exists = os.path.exists(system_test_folder_path)
    # Sanity check: only run tests if found.
    if not system_test_exists and not system_test_folder_exists:
        session.skip("System tests were not found")

    # Use pre-release gRPC for system tests.
    session.install("--pre", "grpcio")

    # Install all test dependencies, then install this package into the
    # virtualenv's dist-packages.
    session.install(
        "django~={}".format(django_version),
        "mock",
        "pytest",
        "google-cloud-testutils",
        "-c",
        constraints_path,
    )
    session.install("-e", ".[tracing]", "-c", constraints_path)
    # Run py.test against the system tests.
    if system_test_exists:
        session.run("py.test", "--quiet", system_test_path, *session.posargs)
    if system_test_folder_exists:
        session.run(
            "py.test", "--quiet", system_test_folder_path, *session.posargs
        )


@nox.session(python=SYSTEM_TEST_PYTHON_VERSIONS)
def system(session):
    print("System tests with django 3.2")
    system_test(session)
    print("System tests with django 4.2")
    system_test(session, django_version="4.2")


@nox.session(python=DEFAULT_PYTHON_VERSION)
def cover(session):
    """Run the final coverage report.

    This outputs the coverage report aggregating coverage from the unit
    test runs (not system test runs), and then erases coverage data.
    """
    session.install("coverage", "pytest-cov")
    session.run("coverage", "report", "--show-missing", "--fail-under=80")

    session.run("coverage", "erase")


@nox.session(python="3.9")
def docs(session):
    """Build the docs for this library."""

    session.install("-e", ".[tracing]")
    session.install(
        # We need to pin to specific versions of the `sphinxcontrib-*` packages
        # which still support sphinx 4.x.
        # See https://github.com/googleapis/sphinx-docfx-yaml/issues/344
        # and https://github.com/googleapis/sphinx-docfx-yaml/issues/345.
        "sphinxcontrib-applehelp==1.0.4",
        "sphinxcontrib-devhelp==1.0.2",
        "sphinxcontrib-htmlhelp==2.0.1",
        "sphinxcontrib-qthelp==1.0.3",
        "sphinxcontrib-serializinghtml==1.1.5",
        "sphinx==4.5.0",
        "alabaster",
        "recommonmark",
        "django==3.2",
    )

    shutil.rmtree(os.path.join("docs", "_build"), ignore_errors=True)
    # Warnings as errors is disabled for `sphinx-build` because django module
    # has warnings.
    session.run(
        "sphinx-build",
        "-T",  # show full traceback on exception
        "-N",  # no colors
        "-b",
        "html",
        "-d",
        os.path.join("docs", "_build", "doctrees", ""),
        os.path.join("docs", ""),
        os.path.join("docs", "_build", "html", ""),
    )


@nox.session(python="3.10")
def docfx(session):
    """Build the docfx yaml files for this library."""

    session.install("-e", ".[tracing]")
    session.install(
        # We need to pin to specific versions of the `sphinxcontrib-*` packages
        # which still support sphinx 4.x.
        # See https://github.com/googleapis/sphinx-docfx-yaml/issues/344
        # and https://github.com/googleapis/sphinx-docfx-yaml/issues/345.
        "sphinxcontrib-applehelp==1.0.4",
        "sphinxcontrib-devhelp==1.0.2",
        "sphinxcontrib-htmlhelp==2.0.1",
        "sphinxcontrib-qthelp==1.0.3",
        "sphinxcontrib-serializinghtml==1.1.5",
        "gcp-sphinx-docfx-yaml",
        "alabaster",
        "recommonmark",
        "django==3.2",
    )

    shutil.rmtree(os.path.join("docs", "_build"), ignore_errors=True)
    session.run(
        "sphinx-build",
        "-T",  # show full traceback on exception
        "-N",  # no colors
        "-D",
        (
            "extensions=sphinx.ext.autodoc,"
            "sphinx.ext.autosummary,"
            "docfx_yaml.extension,"
            "sphinx.ext.intersphinx,"
            "sphinx.ext.coverage,"
            "sphinx.ext.napoleon,"
            "sphinx.ext.todo,"
            "sphinx.ext.viewcode,"
            "recommonmark"
        ),
        "-b",
        "html",
        "-d",
        os.path.join("docs", "_build", "doctrees", ""),
        os.path.join("docs", ""),
        os.path.join("docs", "_build", "html", ""),
    )
