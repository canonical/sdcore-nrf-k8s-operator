#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.


import logging
from collections import Counter
from pathlib import Path

import pytest
import yaml
from juju.application import Application
from pytest_operator.plugin import OpsTest

logger = logging.getLogger(__name__)

METADATA = yaml.safe_load(Path("./charmcraft.yaml").read_text())
APP_NAME = METADATA["name"]
DB_CHARM_NAME = "mongodb-k8s"
DB_CHARM_CHANNEL = "6/stable"
NMS_CHARM_NAME = "sdcore-nms-k8s"
NMS_CHARM_CHANNEL = "1.6/edge"
TLS_CHARM_NAME = "self-signed-certificates"
TLS_CHARM_CHANNEL = "latest/stable"
GRAFANA_AGENT_CHARM_NAME = "grafana-agent-k8s"
GRAFANA_AGENT_CHARM_CHANNEL = "1/stable"
SDCORE_CHARMS_BASE = "ubuntu@24.04"
TIMEOUT = 15 * 60


@pytest.fixture(scope="module")
async def deploy(ops_test: OpsTest, request):
    """Deploy the charm-under-test together with related charms.

    Assert on the unit status before any relations/configurations take place.
    """
    assert ops_test.model
    charm = Path(request.config.getoption("--charm_path")).resolve()
    resources = {"nrf-image": METADATA["resources"]["nrf-image"]["upstream-source"]}
    await ops_test.model.deploy(
        charm,
        resources=resources,
        application_name=APP_NAME,
        base=SDCORE_CHARMS_BASE,
    )


@pytest.mark.abort_on_fail
async def test_given_charm_is_built_when_deployed_then_status_is_blocked(
    ops_test: OpsTest,
    deploy,
):
    assert ops_test.model
    await _deploy_mongodb(ops_test)
    await _deploy_self_signed_certificates(ops_test)
    await _deploy_nms(ops_test)
    await _deploy_grafana_agent(ops_test)
    await ops_test.model.wait_for_idle(
        apps=[APP_NAME],
        status="blocked",
        timeout=TIMEOUT,
    )


async def test_given_charm_is_deployed_when_relate_to_mongo_nms_and_certificates_then_status_is_active(  # noqa: E501
    ops_test: OpsTest, deploy
):
    assert ops_test.model
    await ops_test.model.integrate(
        relation1=f"{APP_NAME}:database", relation2=f"{DB_CHARM_NAME}:database"
    )
    await ops_test.model.integrate(relation1=APP_NAME, relation2=NMS_CHARM_NAME)
    await ops_test.model.integrate(
        relation1=f"{APP_NAME}:certificates", relation2=f"{TLS_CHARM_NAME}:certificates"
    )
    await ops_test.model.integrate(
        relation1=f"{APP_NAME}:logging",
        relation2=f"{GRAFANA_AGENT_CHARM_NAME}:logging-provider",
    )
    await ops_test.model.integrate(
        relation1=f"{APP_NAME}:metrics-endpoint",
        relation2=f"{GRAFANA_AGENT_CHARM_NAME}:metrics-endpoint",
    )
    await ops_test.model.wait_for_idle(apps=[APP_NAME], status="active", timeout=TIMEOUT)


@pytest.mark.abort_on_fail
async def test_remove_tls_and_wait_for_blocked_status(ops_test: OpsTest, deploy):
    assert ops_test.model
    await ops_test.model.remove_application(TLS_CHARM_NAME, block_until_done=True)
    await ops_test.model.wait_for_idle(apps=[APP_NAME], status="blocked", timeout=TIMEOUT)


@pytest.mark.abort_on_fail
async def test_restore_tls_and_wait_for_active_status(ops_test: OpsTest, deploy):
    assert ops_test.model
    await _deploy_self_signed_certificates(ops_test)
    await ops_test.model.integrate(relation1=APP_NAME, relation2=TLS_CHARM_NAME)
    await ops_test.model.integrate(relation1=NMS_CHARM_NAME, relation2=TLS_CHARM_NAME)
    await ops_test.model.wait_for_idle(apps=[APP_NAME], status="active", timeout=TIMEOUT)


@pytest.mark.abort_on_fail
async def test_remove_database_and_wait_for_blocked_status(ops_test: OpsTest, deploy):
    assert ops_test.model
    await ops_test.model.remove_application(DB_CHARM_NAME, block_until_done=True)
    await ops_test.model.wait_for_idle(apps=[APP_NAME], status="blocked", timeout=TIMEOUT)


@pytest.mark.abort_on_fail
async def test_restore_database_and_wait_for_active_status(ops_test: OpsTest, deploy):
    assert ops_test.model
    await _deploy_mongodb(ops_test)
    await ops_test.model.integrate(relation1=APP_NAME, relation2=DB_CHARM_NAME)
    await ops_test.model.wait_for_idle(apps=[APP_NAME], status="active", timeout=TIMEOUT)


@pytest.mark.abort_on_fail
async def test_remove_nms_and_wait_for_blocked_status(ops_test: OpsTest, deploy):
    assert ops_test.model
    await ops_test.model.remove_application(NMS_CHARM_NAME, block_until_done=True)
    await ops_test.model.wait_for_idle(apps=[APP_NAME], status="blocked", timeout=TIMEOUT)


@pytest.mark.abort_on_fail
async def test_restore_nms_and_wait_for_active_status(ops_test: OpsTest, deploy):
    assert ops_test.model
    await _deploy_nms(ops_test)
    await ops_test.model.integrate(relation1=APP_NAME, relation2=NMS_CHARM_NAME)
    await ops_test.model.wait_for_idle(apps=[APP_NAME], status="active", timeout=TIMEOUT)


@pytest.mark.abort_on_fail
async def test_when_scale_nrf_beyond_1_then_only_one_unit_is_active(ops_test: OpsTest, deploy):
    assert ops_test.model
    assert isinstance(app := ops_test.model.applications[APP_NAME], Application)
    await app.scale(3)
    await ops_test.model.wait_for_idle(apps=[APP_NAME], timeout=TIMEOUT, wait_for_at_least_units=3)
    unit_statuses = Counter(unit.workload_status for unit in app.units)
    assert unit_statuses.get("active") == 1
    assert unit_statuses.get("blocked") == 2


async def test_remove_nrf(ops_test: OpsTest, deploy):
    assert ops_test.model
    await ops_test.model.remove_application(APP_NAME, block_until_done=True)


async def _deploy_mongodb(ops_test: OpsTest):
    assert ops_test.model
    await ops_test.model.deploy(
        DB_CHARM_NAME,
        application_name=DB_CHARM_NAME,
        channel=DB_CHARM_CHANNEL,
        trust=True,
    )


async def _deploy_nms(ops_test: OpsTest):
    assert ops_test.model
    await ops_test.model.deploy(
        NMS_CHARM_NAME,
        application_name=NMS_CHARM_NAME,
        channel=NMS_CHARM_CHANNEL,
        base=SDCORE_CHARMS_BASE,
    )
    await ops_test.model.integrate(
        relation1=f"{NMS_CHARM_NAME}:common_database", relation2=DB_CHARM_NAME
    )
    await ops_test.model.integrate(
        relation1=f"{NMS_CHARM_NAME}:auth_database", relation2=DB_CHARM_NAME
    )
    await ops_test.model.integrate(
        relation1=f"{NMS_CHARM_NAME}:webui_database", relation2=DB_CHARM_NAME
    )
    await ops_test.model.integrate(relation1=NMS_CHARM_NAME, relation2=TLS_CHARM_NAME)


async def _deploy_grafana_agent(ops_test: OpsTest):
    assert ops_test.model
    await ops_test.model.deploy(
        GRAFANA_AGENT_CHARM_NAME,
        application_name=GRAFANA_AGENT_CHARM_NAME,
        channel=GRAFANA_AGENT_CHARM_CHANNEL,
    )


async def _deploy_self_signed_certificates(ops_test: OpsTest):
    assert ops_test.model
    await ops_test.model.deploy(
        TLS_CHARM_NAME,
        application_name=TLS_CHARM_NAME,
        channel=TLS_CHARM_CHANNEL,
    )
