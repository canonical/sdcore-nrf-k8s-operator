# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

from unittest.mock import patch

import pytest
import scenario
from ops.charm import ActionEvent, CharmBase

from lib.charms.sdcore_nrf_k8s.v0.fiveg_nrf import NRFAvailableEvent, NRFBrokenEvent, NRFRequires


class DummyFiveGNRFRequirerCharm(CharmBase):
    """Charm the service."""

    def __init__(self, *args):
        """Init."""
        super().__init__(*args)
        self.nrf_requirer = NRFRequires(self, "fiveg_nrf")
        self.framework.observe(self.on.get_nrf_url_action, self._on_get_nrf_url_action)

    def _on_get_nrf_url_action(self, event: ActionEvent) -> None:
        event.set_results({"nrf-url": self.nrf_requirer.nrf_url})


class TestFiveGNRFRequirer:
    @pytest.fixture(autouse=True)
    def setUp(self, request):
        yield
        request.addfinalizer(self.tearDown)

    def tearDown(self) -> None:
        patch.stopall()

    @pytest.fixture(autouse=True)
    def context(self):
        self.ctx = scenario.Context(
            charm_type=DummyFiveGNRFRequirerCharm,
            meta={
                "name": "nrf-requirer-charm",
                "requires": {"fiveg_nrf": {"interface": "fiveg_nrf"}},
            },
            actions={
                "get-nrf-url": {"params": {}},
            },
        )

    def test_given_nrf_information_in_relation_data_when_relation_changed_then_nrf_available_event_emitted(  # noqa: E501
        self,
    ):
        nrf_relation = scenario.Relation(
            endpoint="fiveg_nrf",
            interface="fiveg_nrf",
            remote_app_data={
                "url": "http://nrf.com",
            },
        )
        state_in = scenario.State(
            relations=[nrf_relation],
        )

        self.ctx.run(self.ctx.on.relation_changed(nrf_relation), state_in)

        assert len(self.ctx.emitted_events) == 2
        assert isinstance(self.ctx.emitted_events[1], NRFAvailableEvent)
        assert self.ctx.emitted_events[1].url == "http://nrf.com"

    def test_given_nrf_information_not_in_relation_data_when_relation_changed_then_nrf_available_event_not_emitted(  # noqa: E501
        self,
    ):
        nrf_relation = scenario.Relation(
            endpoint="fiveg_nrf",
            interface="fiveg_nrf",
        )
        state_in = scenario.State(
            relations=[nrf_relation],
        )

        self.ctx.run(self.ctx.on.relation_changed(nrf_relation), state_in)

        assert len(self.ctx.emitted_events) == 1

    def test_given_invalid_nrf_information_in_relation_data_when_relation_changed_then_nrf_available_event_not_emitted(  # noqa: E501
        self,
    ):
        nrf_relation = scenario.Relation(
            endpoint="fiveg_nrf",
            interface="fiveg_nrf",
            remote_app_data={
                "pizza": "steak",
            },
        )
        state_in = scenario.State(
            relations=[nrf_relation],
        )

        self.ctx.run(self.ctx.on.relation_changed(nrf_relation), state_in)

        assert len(self.ctx.emitted_events) == 1

    def test_given_invalid_nrf_information_in_relation_data_when_relation_changed_then_error_is_logged(  # noqa: E501
        self, caplog
    ):
        nrf_relation = scenario.Relation(
            endpoint="fiveg_nrf",
            interface="fiveg_nrf",
            remote_app_data={
                "pizza": "steak",
            },
        )
        state_in = scenario.State(
            relations=[nrf_relation],
        )

        self.ctx.run(self.ctx.on.relation_changed(nrf_relation), state_in)

        assert "Invalid relation data: {'pizza': 'steak'}" in caplog.messages

    def test_given_nrf_information_in_relation_data_when_get_nrf_url_is_called_then_expected_url_is_returned(  # noqa: E501
        self,
    ):
        nrf_relation = scenario.Relation(
            endpoint="fiveg_nrf",
            interface="fiveg_nrf",
            remote_app_data={
                "url": "http://nrf.com",
            },
        )
        state_in = scenario.State(
            relations=[nrf_relation],
        )

        self.ctx.run(self.ctx.on.action("get-nrf-url"), state_in)

        assert self.ctx.action_results
        assert self.ctx.action_results == {
            "nrf-url": "http://nrf.com",
        }

    def test_given_nrf_information_not_in_relation_data_when_get_nrf_url_then_returns_none(  # noqa: E501
        self, caplog
    ):
        nrf_relation = scenario.Relation(
            endpoint="fiveg_nrf",
            interface="fiveg_nrf",
        )
        state_in = scenario.State(
            relations=[nrf_relation],
        )

        self.ctx.run(self.ctx.on.action("get-nrf-url"), state_in)

        assert self.ctx.action_results
        assert self.ctx.action_results == {
            "nrf-url": None,
        }
        assert "Invalid relation data: {}" in caplog.messages

    def test_given_nrf_information_in_relation_data_is_not_valid_when_get_nrf_url_then_returns_none_and_error_is_logged(  # noqa: E501
        self, caplog
    ):
        nrf_relation = scenario.Relation(
            endpoint="fiveg_nrf",
            interface="fiveg_nrf",
            remote_app_data={
                "pizza": "steak",
            },
        )
        state_in = scenario.State(
            relations=[nrf_relation],
        )

        self.ctx.run(self.ctx.on.action("get-nrf-url"), state_in)

        assert self.ctx.action_results
        assert self.ctx.action_results == {
            "nrf-url": None,
        }
        assert "Invalid relation data: {'pizza': 'steak'}" in caplog.messages

    def test_given_nrf_relation_created_when_relation_broken_then_nrf_broken_event_emitted(self):
        nrf_relation = scenario.Relation(
            endpoint="fiveg_nrf",
            interface="fiveg_nrf",
        )
        state_in = scenario.State(
            relations=[nrf_relation],
        )

        self.ctx.run(self.ctx.on.relation_broken(nrf_relation), state_in)

        assert len(self.ctx.emitted_events) == 2
        assert isinstance(self.ctx.emitted_events[1], NRFBrokenEvent)
