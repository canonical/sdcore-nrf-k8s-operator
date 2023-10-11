#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.


import logging
from pathlib import Path

import pytest
import yaml
from pytest_operator.plugin import OpsTest

logger = logging.getLogger(__name__)

METADATA = yaml.safe_load(Path("./metadata.yaml").read_text())
APP_NAME = METADATA["name"]
DB_APPLICATION_NAME = "mongodb"
TLS_APPLICATION_NAME = "self-signed-certificates"


@pytest.fixture(scope="module")
@pytest.mark.abort_on_fail
async def deploy_mongodb(ops_test):
    await ops_test.model.deploy(
        "mongodb-k8s", application_name=DB_APPLICATION_NAME, channel="5/edge", trust=True
    )


@pytest.fixture(scope="module")
@pytest.mark.abort_on_fail
async def deploy_self_signed_certificates(ops_test):
    await ops_test.model.deploy(
        TLS_APPLICATION_NAME,
        application_name=TLS_APPLICATION_NAME,
        channel="beta",
    )


@pytest.fixture(scope="module")
@pytest.mark.abort_on_fail
async def build_and_deploy(ops_test):
    """Build the charm-under-test and deploy it together with related charms.

    Assert on the unit status before any relations/configurations take place.
    """
    charm = await ops_test.build_charm(".")
    resources = {"nrf-image": METADATA["resources"]["nrf-image"]["upstream-source"]}
    await ops_test.model.deploy(
        charm,
        resources=resources,
        application_name=APP_NAME,
        series="jammy",
    )


@pytest.mark.abort_on_fail
async def test_given_charm_is_built_when_deployed_then_status_is_blocked(
    ops_test, build_and_deploy, deploy_mongodb, deploy_self_signed_certificates
):
    await ops_test.model.wait_for_idle(
        apps=[APP_NAME],
        status="blocked",
        timeout=1000,
    )


async def test_given_charm_is_deployed_when_relate_to_mongo_and_certificates_then_status_is_active(
    ops_test: OpsTest, build_and_deploy
):
    assert ops_test.model
    await ops_test.model.integrate(
        relation1=f"{APP_NAME}:database", relation2=f"{DB_APPLICATION_NAME}:database"
    )
    await ops_test.model.integrate(
        relation1=f"{APP_NAME}:certificates", relation2=f"{TLS_APPLICATION_NAME}:certificates"
    )
    await ops_test.model.wait_for_idle(apps=[APP_NAME], status="active", timeout=1000)


@pytest.mark.abort_on_fail
async def test_remove_tls_and_wait_for_blocked_status(ops_test, build_and_deploy):
    await ops_test.model.remove_application(TLS_APPLICATION_NAME, block_until_done=True)  # type: ignore[union-attr]  # noqa: E501
    await ops_test.model.wait_for_idle(apps=[APP_NAME], status="blocked", timeout=60)  # type: ignore[union-attr]  # noqa: E501


@pytest.mark.abort_on_fail
async def test_restore_tls_and_wait_for_active_status(ops_test: OpsTest, build_and_deploy):
    assert ops_test.model
    await ops_test.model.deploy(
        TLS_APPLICATION_NAME,
        application_name=TLS_APPLICATION_NAME,
        channel="beta",
        trust=True,
    )
    await ops_test.model.add_relation(relation1=APP_NAME, relation2=TLS_APPLICATION_NAME)
    await ops_test.model.wait_for_idle(apps=[APP_NAME], status="active", timeout=1000)
