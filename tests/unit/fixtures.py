# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

from unittest.mock import PropertyMock, patch

import pytest
import scenario

from charm import NRFOperatorCharm


class NRFUnitTestFixtures:
    patcher_database_resource_created = patch(
        "charms.data_platform_libs.v0.data_interfaces.DatabaseRequires.is_resource_created"
    )
    patcher_database_relation_data = patch(
        "charms.data_platform_libs.v0.data_interfaces.DatabaseRequires.fetch_relation_data"
    )
    patcher_sdcore_config_webui_url = patch(
        "charms.sdcore_nms_k8s.v0.sdcore_config.SdcoreConfigRequires.webui_url",
        new_callable=PropertyMock,
    )
    patcher_get_assigned_certificates = patch(
        "charms.tls_certificates_interface.v3.tls_certificates.TLSCertificatesRequiresV3.get_assigned_certificates"
    )
    patcher_set_nrf_information = patch(
        "charms.sdcore_nrf_k8s.v0.fiveg_nrf.NRFProvides.set_nrf_information"
    )
    patcher_set_nrf_information_in_all_relations = patch(
        "charms.sdcore_nrf_k8s.v0.fiveg_nrf.NRFProvides.set_nrf_information_in_all_relations"
    )

    @pytest.fixture(autouse=True)
    def setup(self, request):
        self.mock_database_resource_created = (
            NRFUnitTestFixtures.patcher_database_resource_created.start()
        )
        self.mock_database_relation_data = (
            NRFUnitTestFixtures.patcher_database_relation_data.start()
        )
        self.mock_sdcore_config_webui_url = (
            NRFUnitTestFixtures.patcher_sdcore_config_webui_url.start()
        )
        self.mock_get_assigned_certificates = (
            NRFUnitTestFixtures.patcher_get_assigned_certificates.start()
        )
        self.mock_set_nrf_information = NRFUnitTestFixtures.patcher_set_nrf_information.start()
        self.mock_set_nrf_information_in_all_relations = (
            NRFUnitTestFixtures.patcher_set_nrf_information_in_all_relations.start()
        )
        yield
        request.addfinalizer(self.teardown)

    @staticmethod
    def teardown() -> None:
        patch.stopall()

    @pytest.fixture(autouse=True)
    def context(self):
        self.ctx = scenario.Context(
            charm_type=NRFOperatorCharm,
        )
