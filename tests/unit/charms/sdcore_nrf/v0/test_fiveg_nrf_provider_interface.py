# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

from unittest.mock import patch

import pytest
from ops import testing
from ops.charm import ActionEvent, CharmBase

from lib.charms.sdcore_nrf_k8s.v0.fiveg_nrf import NRFProvides


class DummyFiveGNRFProviderCharm(CharmBase):
    """Charm the service."""

    def __init__(self, *args):
        """Init."""
        super().__init__(*args)
        self.nrf_provider = NRFProvides(self, "fiveg_nrf")
        self.framework.observe(
            self.on.set_nrf_information_action, self._on_set_nrf_information_action
        )
        self.framework.observe(
            self.on.set_nrf_information_in_all_relations_action,
            self._on_set_nrf_information_in_all_relations_action,
        )

    def _on_set_nrf_information_action(self, event: ActionEvent):
        url = event.params.get("url")
        relation_id = event.params.get("relation-id")
        assert url
        assert relation_id
        self.nrf_provider.set_nrf_information(
            url=url,
            relation_id=int(relation_id),
        )

    def _on_set_nrf_information_in_all_relations_action(self, event: ActionEvent):
        url = event.params.get("url")
        assert url
        self.nrf_provider.set_nrf_information_in_all_relations(
            url=url,
        )


class TestFiveGNRFProvider:
    @pytest.fixture(autouse=True)
    def setUp(self, request):
        yield
        request.addfinalizer(self.tearDown)

    def tearDown(self) -> None:
        patch.stopall()

    @pytest.fixture(autouse=True)
    def context(self):
        self.ctx = testing.Context(
            charm_type=DummyFiveGNRFProviderCharm,
            meta={
                "name": "nrf-provider-charm",
                "provides": {"fiveg_nrf": {"interface": "fiveg_nrf"}},
            },
            actions={
                "set-nrf-information": {
                    "params": {"url": {"type": "string"}, "relation-id": {"type": "string"}}
                },
                "set-nrf-information-in-all-relations": {"params": {"url": {"type": "string"}}},
            },
        )

    def test_given_unit_is_leader_when_set_nrf_information_then_data_is_in_application_databag(  # noqa: E501
        self,
    ):
        nrf_relation = testing.Relation(
            endpoint="fiveg_nrf",
            interface="fiveg_nrf",
        )
        state_in = testing.State(
            leader=True,
            relations=[nrf_relation],
        )
        params = {
            "url": "http://whatever.url.com",
            "relation-id": str(nrf_relation.id),
        }

        state_out = self.ctx.run(
            self.ctx.on.action("set-nrf-information", params=params), state_in
        )

        relation = state_out.get_relation(nrf_relation.id)
        assert relation.local_app_data["url"] == "http://whatever.url.com"

    def test_given_unit_is_not_leader_when_set_nrf_information_then_data_is_not_in_application_databag(  # noqa: E501
        self,
    ):
        nrf_relation = testing.Relation(
            endpoint="fiveg_nrf",
            interface="fiveg_nrf",
        )
        state_in = testing.State(
            leader=False,
            relations=[nrf_relation],
        )
        params = {
            "url": "http://whatever.url.com",
            "relation-id": str(nrf_relation.id),
        }

        with pytest.raises(Exception) as e:
            self.ctx.run(self.ctx.on.action("set-nrf-information", params=params), state_in)

        assert "Unit must be leader to set application relation data" in str(e.value)

    def test_given_provided_nrf_url_is_not_valid_when_set_nrf_information_then_error_is_raised(  # noqa: E501
        self,
    ):
        nrf_relation = testing.Relation(
            endpoint="fiveg_nrf",
            interface="fiveg_nrf",
        )
        state_in = testing.State(
            leader=True,
            relations=[nrf_relation],
        )
        params = {
            "url": "invalid url",
            "relation-id": str(nrf_relation.id),
        }

        with pytest.raises(Exception) as e:
            self.ctx.run(self.ctx.on.action("set-nrf-information", params=params), state_in)

        assert "invalid url" in str(e.value)

    def test_given_unit_is_leader_and_fiveg_nrf_relation_is_not_created_when_set_nrf_information_then_runtime_error_is_raised(  # noqa: E501
        self,
    ):
        state_in = testing.State(
            leader=True,
            relations=[],
        )
        params = {
            "url": "http://whatever.url.com",
            "relation-id": "0",
        }

        with pytest.raises(Exception) as e:
            self.ctx.run(self.ctx.on.action("set-nrf-information", params=params), state_in)

        assert "Relation fiveg_nrf not created yet." in str(e.value)

    def test_given_unit_is_leader_when_set_nrf_information_in_all_relations_then_data_in_application_databag(  # noqa: E501
        self,
    ):
        nrf_relation_1 = testing.Relation(
            endpoint="fiveg_nrf",
            interface="fiveg_nrf",
        )
        nrf_relation_2 = testing.Relation(
            endpoint="fiveg_nrf",
            interface="fiveg_nrf",
        )
        state_in = testing.State(
            leader=True,
            relations=[nrf_relation_1, nrf_relation_2],
        )
        params = {
            "url": "http://whatever.url.com",
        }

        state_out = self.ctx.run(
            self.ctx.on.action("set-nrf-information-in-all-relations", params=params), state_in
        )

        relation_1 = state_out.get_relation(nrf_relation_1.id)
        relation_2 = state_out.get_relation(nrf_relation_2.id)
        assert relation_1.local_app_data["url"] == "http://whatever.url.com"
        assert relation_2.local_app_data["url"] == "http://whatever.url.com"
