# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.
import logging
from unittest.mock import call, patch

import pytest
from ops import BoundEvent, testing

from tests.unit.charms.sdcore_nrf.v0.dummy_requirer_charm.src.dummy_requirer_charm import (  # noqa: E501
    DummyFiveGNRFRequirerCharm,
)

DUMMY_REQUIRER_CHARM = "tests.unit.charms.sdcore_nrf.v0.dummy_requirer_charm.src.dummy_requirer_charm.DummyFiveGNRFRequirerCharm"  # noqa: E501
FIVEG_NRF_LIB = "lib.charms.sdcore_nrf_k8s.v0.fiveg_nrf.NRFRequirerCharmEvents"
RELATION_NAME = "fiveg_nrf"
REMOTE_APP_NAME = "dummy-nrf-requirer"
NRF_URL = "https://nrf.example.com"


class TestFiveGNRFRequirer:
    patcher_fiveg_nrf_available = patch(f"{FIVEG_NRF_LIB}.nrf_available")
    patcher_fiveg_nrf_broken = patch(f"{FIVEG_NRF_LIB}.nrf_broken")

    @pytest.fixture()
    def setUp(self) -> None:
        self.mock_fiveg_nrf_available = TestFiveGNRFRequirer.patcher_fiveg_nrf_available.start()
        self.mock_fiveg_nrf_broken = TestFiveGNRFRequirer.patcher_fiveg_nrf_broken.start()
        self.mock_fiveg_nrf_available.__class__ = BoundEvent
        self.mock_fiveg_nrf_broken.__class__ = BoundEvent

    def tearDown(self) -> None:
        patch.stopall()

    @pytest.fixture(autouse=True)
    def setup_harness(self, setUp, request):
        self.harness = testing.Harness(DummyFiveGNRFRequirerCharm)
        self.harness.begin()
        yield self.harness
        self.harness.cleanup()
        request.addfinalizer(self.tearDown)

    def _create_relation(self, remote_app_name: str):
        relation_id = self.harness.add_relation(
            relation_name=RELATION_NAME, remote_app=remote_app_name
        )
        self.harness.add_relation_unit(
            relation_id=relation_id, remote_unit_name=f"{remote_app_name}/0"
        )

        return relation_id

    def test_given_nrf_information_in_relation_data_when_relation_changed_then_nrf_available_event_emitted(  # noqa: E501
        self,
    ):
        relation_id = self._create_relation(remote_app_name=REMOTE_APP_NAME)

        relation_data = {
            "url": NRF_URL,
        }
        self.harness.update_relation_data(
            relation_id=relation_id, app_or_unit=REMOTE_APP_NAME, key_values=relation_data
        )

    def test_given_nrf_information_not_in_relation_data_when_relation_changed_then_nrf_available_event_not_emitted(  # noqa: E501
        self,
    ):
        relation_id = self._create_relation(remote_app_name=REMOTE_APP_NAME)
        relation_data = {}

        self.harness.update_relation_data(
            relation_id=relation_id, app_or_unit=REMOTE_APP_NAME, key_values=relation_data
        )
        self.mock_fiveg_nrf_available.assert_not_called()

    def test_given_invalid_nrf_information_in_relation_data_when_relation_changed_then_nrf_available_event_not_emitted(  # noqa: E501
        self,
    ):
        relation_id = self._create_relation(remote_app_name=REMOTE_APP_NAME)
        relation_data = {"pizza": "steak"}

        self.harness.update_relation_data(
            relation_id=relation_id, app_or_unit=REMOTE_APP_NAME, key_values=relation_data
        )
        self.mock_fiveg_nrf_available.assert_not_called()

    def test_given_invalid_nrf_information_in_relation_data_when_relation_changed_then_error_is_logged(  # noqa: E501
        self, caplog
    ):
        relation_id = self._create_relation(remote_app_name=REMOTE_APP_NAME)
        relation_data = {"pizza": "steak"}
        caplog.set_level(logging.DEBUG)
        self.harness.update_relation_data(
            relation_id=relation_id, app_or_unit=REMOTE_APP_NAME, key_values=relation_data
        )
        assert "Invalid relation data: {'pizza': 'steak'}" in caplog.messages

    def test_given_nrf_information_in_relation_data_when_get_nrf_url_is_called_then_expected_url_is_returned(  # noqa: E501
        self,
    ):
        relation_id = self._create_relation(remote_app_name=REMOTE_APP_NAME)
        relation_data = {
            "url": NRF_URL,
        }
        self.harness.update_relation_data(
            relation_id=relation_id, app_or_unit=REMOTE_APP_NAME, key_values=relation_data
        )

        nrf_url = self.harness.charm.nrf_requirer.nrf_url
        assert nrf_url == NRF_URL

    def test_given_nrf_information_not_in_relation_data_when_get_nrf_url_then_returns_none(  # noqa: E501
        self, caplog
    ):
        relation_id = self._create_relation(remote_app_name=REMOTE_APP_NAME)
        relation_data = {}

        self.harness.update_relation_data(
            relation_id=relation_id, app_or_unit=REMOTE_APP_NAME, key_values=relation_data
        )
        caplog.set_level(logging.DEBUG)
        nrf_url = self.harness.charm.nrf_requirer.nrf_url
        assert nrf_url is None
        assert "Invalid relation data: {}" in caplog.messages

    def test_given_nrf_information_in_relation_data_is_not_valid_when_get_nrf_url_then_returns_none_and_error_is_logged(  # noqa: E501
        self, caplog
    ):
        relation_id = self._create_relation(remote_app_name=REMOTE_APP_NAME)
        relation_data = {"pizza": "steak"}
        self.harness.update_relation_data(
            relation_id=relation_id, app_or_unit=REMOTE_APP_NAME, key_values=relation_data
        )
        caplog.set_level(logging.DEBUG)
        nrf_url = self.harness.charm.nrf_requirer.nrf_url
        assert nrf_url is None
        assert "Invalid relation data: {'pizza': 'steak'}" in caplog.messages

    def test_given_nrf_relation_created_when_relation_broken_then_nrf_broken_event_emitted(self):
        relation_id = self._create_relation(remote_app_name=REMOTE_APP_NAME)
        self.harness.remove_relation(relation_id)
        calls = [call.emit()]
        self.mock_fiveg_nrf_broken.assert_has_calls(calls)
