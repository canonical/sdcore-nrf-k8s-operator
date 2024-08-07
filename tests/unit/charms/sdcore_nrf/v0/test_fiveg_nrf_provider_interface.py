# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

from unittest.mock import PropertyMock, patch

import pytest
from ops import testing

from tests.unit.charms.sdcore_nrf.v0.dummy_provider_charm.src.dummy_provider_charm import (  # noqa: E501
    DummyFiveGNRFProviderCharm,
)

DUMMY_PROVIDER_CHARM = "tests.unit.charms.sdcore_nrf.v0.dummy_provider_charm.src.dummy_provider_charm.DummyFiveGNRFProviderCharm"  # noqa: E501
RELATION_NAME = "fiveg_nrf"
REMOTE_APP_NAME = "dummy-nrf-requirer"
NRF_URL = "https://nrf.example.com"


class TestFiveGNRFProvider:
    patcher_nrf_url = patch(f"{DUMMY_PROVIDER_CHARM}.NRF_URL", new_callable=PropertyMock)

    @pytest.fixture()
    def setUp(self) -> None:
        self.mock_nrf_url = TestFiveGNRFProvider.patcher_nrf_url.start()

    def tearDown(self) -> None:
        patch.stopall()

    @pytest.fixture(autouse=True)
    def setup_harness(self, setUp, request):
        self.harness = testing.Harness(DummyFiveGNRFProviderCharm)
        self.harness.begin()
        self.harness.set_leader(is_leader=True)
        self.mock_nrf_url.return_value = NRF_URL
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

    def test_given_unit_is_leader_when_fiveg_nrf_relation_joined_then_data_is_in_application_databag(  # noqa: E501
        self,
    ):
        self.harness.set_leader(is_leader=True)
        expected_nrf_url = NRF_URL
        relation_id = self.harness.add_relation(
            relation_name=RELATION_NAME, remote_app=REMOTE_APP_NAME
        )
        self.harness.add_relation_unit(
            relation_id=relation_id, remote_unit_name=f"{REMOTE_APP_NAME}/0"
        )

        relation_data = self.harness.get_relation_data(
            relation_id=relation_id, app_or_unit=self.harness.charm.app.name
        )
        assert relation_data["url"] == expected_nrf_url

    def test_given_unit_is_not_leader_when_fiveg_nrf_relation_joined_then_data_is_not_in_application_databag(  # noqa: E501
        self,
    ):
        self.harness.set_leader(is_leader=False)

        with pytest.raises(RuntimeError):
            relation_id = self._create_relation(remote_app_name=REMOTE_APP_NAME)
            relation_data = self.harness.get_relation_data(
                relation_id=relation_id, app_or_unit=self.harness.charm.app.name
            )
            assert relation_data == {}

    def test_given_provided_nrf_url_is_not_valid_when_set_url_then_error_is_raised(  # noqa: E501
        self,
    ):
        self.harness.set_leader(is_leader=True)
        self.mock_nrf_url.return_value = "invalid url"

        with pytest.raises(ValueError):
            self._create_relation(remote_app_name=REMOTE_APP_NAME)

    def test_given_unit_is_leader_and_fiveg_nrf_relation_is_not_created_when_set_nrf_information_then_runtime_error_is_raised(  # noqa: E501
        self,
    ):
        self.harness.set_leader(is_leader=True)
        relation_id_for_unexsistant_relation = 0

        with pytest.raises(RuntimeError) as e:
            self.harness.charm.nrf_provider.set_nrf_information(
                url=NRF_URL, relation_id=relation_id_for_unexsistant_relation
            )
        assert str(e.value) == "Relation fiveg_nrf not created yet."

    def test_given_unit_is_leader_when_multiple_fiveg_nrf_relation_joined_then_data_in_application_databag(  # noqa: E501
        self,
    ):
        self.harness.set_leader(is_leader=True)
        remote_app_name_1 = REMOTE_APP_NAME
        remote_app_name_2 = f"second-{REMOTE_APP_NAME}"

        relation_id_1 = self._create_relation(remote_app_name=remote_app_name_1)
        self.harness.get_relation_data(
            relation_id=relation_id_1, app_or_unit=self.harness.charm.app.name
        )
        relation_id_2 = self._create_relation(remote_app_name=remote_app_name_2)
        relation_data_2 = self.harness.get_relation_data(
            relation_id=relation_id_2, app_or_unit=self.harness.charm.app.name
        )
        assert relation_data_2["url"] == NRF_URL

    def test_given_unit_is_leader_and_multiple_fiveg_nrf_relations_when_set_nrf_information_in_all_relations_then_all_relations_are_updated(  # noqa: E501
        self,
    ):
        self.harness.set_leader(is_leader=True)
        remote_app_name_1 = REMOTE_APP_NAME
        remote_app_name_2 = f"second-{REMOTE_APP_NAME}"
        expected_nrf_url = NRF_URL
        relation_id_1 = self._create_relation(remote_app_name=remote_app_name_1)
        relation_data_1 = self.harness.get_relation_data(
            relation_id=relation_id_1, app_or_unit=self.harness.charm.app.name
        )
        relation_id_2 = self._create_relation(remote_app_name=remote_app_name_2)
        relation_data_2 = self.harness.get_relation_data(
            relation_id=relation_id_2, app_or_unit=self.harness.charm.app.name
        )

        self.harness.charm.nrf_provider.set_nrf_information_in_all_relations(url=expected_nrf_url)

        assert relation_data_1["url"] == expected_nrf_url
        assert relation_data_2["url"] == expected_nrf_url
