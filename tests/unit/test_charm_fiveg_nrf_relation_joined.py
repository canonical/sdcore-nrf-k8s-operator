# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.


from ops import testing
from ops.pebble import Layer, ServiceStatus

from tests.unit.fixtures import NRFUnitTestFixtures


class TestCharmGiveGNRFRelatonJoined(NRFUnitTestFixtures):
    def test_given_https_nrf_url_and_service_is_running_when_fiveg_nrf_relation_joined_then_nrf_url_is_in_relation_databag(  # noqa: E501
        self,
    ):
        fiveg_nrf_relation = testing.Relation(
            endpoint="fiveg_nrf",
            interface="fiveg_nrf",
        )
        container = testing.Container(
            name="nrf",
            can_connect=True,
            layers={"nrf": Layer({"services": {"nrf": {}}})},
            service_statuses={
                "nrf": ServiceStatus.ACTIVE,
            },
        )
        state_in = testing.State(
            containers=[container],
            relations=[fiveg_nrf_relation],
            leader=True,
        )

        self.ctx.run(self.ctx.on.relation_joined(fiveg_nrf_relation), state_in)

        self.mock_set_nrf_information.assert_called_with(
            url="https://sdcore-nrf-k8s:29510",
            relation_id=fiveg_nrf_relation.id,
        )
