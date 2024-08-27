import tempfile

import pytest
import scenario
from interface_tester import InterfaceTester
from ops.pebble import Layer, ServiceStatus

from charm import NRFOperatorCharm


@pytest.fixture
def interface_tester(interface_tester: InterfaceTester):
    with tempfile.TemporaryDirectory() as tempdir:
        certificates_relation = scenario.Relation(
            endpoint="certificates",
            interface="tls-certificates",
        )
        database_relation = scenario.Relation(
            endpoint="database",
            interface="mongodb_client",
        )
        config_mount = scenario.Mount(
            location="/etc/nrf/",
            src=tempdir,
        )
        certs_mount = scenario.Mount(
            location="/support/TLS/",
            src=tempdir,
        )
        container = scenario.Container(
            name="nrf",
            can_connect=True,
            layers={"nrf": Layer({"services": {"nrf": {}}})},
            service_status={
                "nrf": ServiceStatus.ACTIVE,
            },
            mounts={
                "config": config_mount,
                "certs": certs_mount,
            },
        )
        interface_tester.configure(
            charm_type=NRFOperatorCharm,
            state_template=scenario.State(
                leader=True,
                relations=[certificates_relation, database_relation],
                containers=[container],
            ),
        )
        yield interface_tester
