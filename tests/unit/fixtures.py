# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

from typing import Generator
from unittest.mock import patch

import pytest
from charm import NRFOperatorCharm
from ops import testing

NAMESPACE = "whatever"
TEST_DB_APPLICATION_NAME = "whatever-db"
DB_RELATION_NAME = "database"
TEST_TLS_APPLICATION_NAME = "whatever-tls"
TLS_RELATION_NAME = "certificates"
TEST_NMS_APPLICATION_NAME = "whatever-nms"
NMS_RELATION_NAME = "sdcore_config"
TEST_WEBUI_URL = "some-webui:7890"


class NRFUnitTestFixtures:
    patcher_generate_crs = patch("charm.generate_csr")
    patcher_generate_private_key = patch("charm.generate_private_key")
    patcher_get_assigned_certificates = patch(
        "charms.tls_certificates_interface.v3.tls_certificates.TLSCertificatesRequiresV3.get_assigned_certificates",  # noqa: E501
    )
    patcher_request_certificate_creation = patch(
        "charms.tls_certificates_interface.v3.tls_certificates.TLSCertificatesRequiresV3.request_certificate_creation",  # noqa: E501
    )
    patcher_resource_created = patch("charms.data_platform_libs.v0.data_interfaces.DatabaseRequires.is_resource_created")  # noqa: E501

    @pytest.fixture()
    def setup(self):
        self.mock_generate_csr = NRFUnitTestFixtures.patcher_generate_crs.start()
        self.mock_generate_private_key = NRFUnitTestFixtures.patcher_generate_private_key.start()
        self.mock_get_assigned_certificates = NRFUnitTestFixtures.patcher_get_assigned_certificates.start()  # noqa: E501
        self.mock_request_certificate_creation = NRFUnitTestFixtures.patcher_request_certificate_creation.start()  # noqa: E501
        self.mock_resource_created = NRFUnitTestFixtures.patcher_resource_created.start()

    @staticmethod
    def teardown() -> None:
        patch.stopall()

    @pytest.fixture(autouse=True)
    def create_harness(self, setup, request):
        self.harness = testing.Harness(NRFOperatorCharm)
        self.harness.set_model_name(name=NAMESPACE)
        self.harness.set_leader(is_leader=True)
        self.harness.begin()
        yield self.harness
        self.harness.cleanup()
        request.addfinalizer(self.teardown)

    @pytest.fixture()
    def add_storage(self):
        self.harness.add_storage(storage_name="certs", attach=True)
        self.harness.add_storage(storage_name="config", attach=True)

    @pytest.fixture()
    def create_database_relation_and_populate_data(self, database_relation_id):
        self.harness.add_relation_unit(
            relation_id=database_relation_id, remote_unit_name=f"{TEST_DB_APPLICATION_NAME}/0"
        )
        self.harness.update_relation_data(
            relation_id=database_relation_id,
            app_or_unit=TEST_DB_APPLICATION_NAME,
            key_values={
                "username": "dummy",
                "password": "dummy",
                "uris": "http://dummy",
            },
        )

    @pytest.fixture()
    def database_relation_id(self) -> Generator[int, None, None]:
        yield self.harness.add_relation(
            relation_name=DB_RELATION_NAME,
            remote_app=TEST_DB_APPLICATION_NAME,
        )

    @pytest.fixture()
    def create_nms_relation_and_set_webui_url(self, nms_relation_id):
        self.harness.add_relation_unit(
            relation_id=nms_relation_id, remote_unit_name=f"{TEST_NMS_APPLICATION_NAME}/0"
        )
        self.harness.update_relation_data(
            relation_id=nms_relation_id,
            app_or_unit=TEST_NMS_APPLICATION_NAME,
            key_values={"webui_url": TEST_WEBUI_URL},
        )

    @pytest.fixture()
    def nms_relation_id(self) -> Generator[int, None, None]:
        yield self.harness.add_relation(
            relation_name=NMS_RELATION_NAME,
            remote_app=TEST_NMS_APPLICATION_NAME,
        )

    @pytest.fixture()
    def certificates_relation_id(self) -> Generator[int, None, None]:
        yield self.harness.add_relation(
            relation_name=TLS_RELATION_NAME,
            remote_app=TEST_TLS_APPLICATION_NAME,
        )
