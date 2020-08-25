# -*- coding: utf-8 -*-
#
# Copyright 2020 Google LLC
#
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd


from __future__ import absolute_import

import nox
import os


def default(session):
    # Install all test dependencies, then install this package in-place.
    session.install("mock", "pytest", "pytest-cov")
    session.install("-e", ".")

    # Run py.test against the unit tests.
    session.run(
        "py.test",
        "--quiet",
        os.path.join("tests", "spanner_dbapi"),
        *session.posargs,
    )


@nox.session(python=["3.5", "3.6", "3.7", "3.8"])
def unit(session):
    """Run the unit test suite."""
    default(session)