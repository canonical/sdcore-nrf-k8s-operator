# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

from unittest.mock import Mock, patch

import pytest
from charm import NRFOperatorCharm
from charms.tls_certificates_interface.v3.tls_certificates import ProviderCertificate
from ops import testing
from ops.model import ActiveStatus, BlockedStatus, WaitingStatus

DB_APPLICATION_NAME = "mongodb-k8s"
DB_RELATION_NAME = "database"
BASE_CONFIG_PATH = "/etc/nrf"
CONFIG_FILE_NAME = "nrfcfg.yaml"
TLS_APPLICATION_NAME = "self-signed-certificates"
TLS_RELATION_NAME = "certificates"
NAMESPACE = "whatever"
PRIVATE_KEY = b"whatever key content"
CSR = b"whatever csr content"
CERTIFICATE = "Whatever certificate content"
EXPECTED_CONFIG_FILE = "tests/unit/expected_config/config.conf"


class TestCharm:
    patcher_generate_crs = patch("charm.generate_csr")
    patcher_generate_private_key = patch("charm.generate_private_key")
    patcher_get_assigned_certificates = patch(
        "charms.tls_certificates_interface.v3.tls_certificates.TLSCertificatesRequiresV3.get_assigned_certificates",
    )
    patcher_request_certificate_creation = patch(
        "charms.tls_certificates_interface.v3.tls_certificates.TLSCertificatesRequiresV3.request_certificate_creation",
    )
    patcher_resource_created = patch("charms.data_platform_libs.v0.data_interfaces.DatabaseRequires.is_resource_created")  # noqa: E501

    @pytest.fixture()
    def setUp(self):
        self.mock_generate_csr = TestCharm.patcher_generate_crs.start()
        self.mock_generate_private_key = TestCharm.patcher_generate_private_key.start()
        self.mock_get_assigned_certificates = TestCharm.patcher_get_assigned_certificates.start()
        self.mock_request_certificate_creation = TestCharm.patcher_request_certificate_creation.start()  # noqa: E501
        self.mock_resource_created = TestCharm.patcher_resource_created.start()

    def tearDown(self) -> None:
        patch.stopall()

    @pytest.fixture(autouse=True)
    def harness(self, setUp, request):
        self.harness = testing.Harness(NRFOperatorCharm)
        self.harness.set_model_name(name=NAMESPACE)
        self.harness.set_leader(is_leader=True)
        self.harness.begin()
        yield self.harness
        self.harness.cleanup()
        request.addfinalizer(self.tearDown)

    def _create_database_relation(self) -> int:
        """Create a database relation.

        Returns:
            relation_id: ID of the created relation
        """
        relation_id = self.harness.add_relation(
            relation_name=DB_RELATION_NAME,
            remote_app=DB_APPLICATION_NAME,
        )
        self.harness.add_relation_unit(
            relation_id=relation_id,
            remote_unit_name=f"{DB_APPLICATION_NAME}/0",
        )
        return relation_id

    def _create_database_relation_and_populate_data(self) -> int:
        """Create a database relation and set the database information.

        Returns:
            relation_id: ID of the created relation
        """
        database_relation_id = self._create_database_relation()
        self.harness.update_relation_data(
            relation_id=database_relation_id,
            app_or_unit=DB_APPLICATION_NAME,
            key_values={
                "username": "dummy",
                "password": "dummy",
                "uris": "http://dummy",
            },
        )
        return database_relation_id

    @staticmethod
    def _read_file(path: str) -> str:
        """Read a file and returns as a string.

        Args:
            path (str): path to the file.

        Returns:
            str: content of the file.
        """
        with open(path, "r") as f:
            content = f.read()
        return content

    def test_given_database_relation_not_created_when_pebble_ready_then_status_is_blocked(self):
        self.harness.container_pebble_ready(container_name="nrf")
        self.harness.evaluate_status()

        assert self.harness.model.unit.status == BlockedStatus("Waiting for database relation to be created")  # noqa: E501

    def test_given_certificates_relation_not_created_when_pebble_ready_then_status_is_blocked(
        self,
    ):
        self.harness.container_pebble_ready(container_name="nrf")
        self._create_database_relation()
        self.harness.evaluate_status()

        assert self.harness.model.unit.status == BlockedStatus(f"Waiting for {TLS_RELATION_NAME} relation to be created")  # noqa: E501

    def test_given_nrf_charm_in_active_state_when_database_relation_breaks_then_status_is_blocked(
        self,
    ):
        self.harness.add_storage("config", attach=True)
        self.harness.add_storage("certs", attach=True)
        self.mock_generate_private_key.return_value = PRIVATE_KEY
        self.mock_generate_csr.return_value = CSR
        root = self.harness.get_filesystem_root("nrf")
        (root / "support/TLS/nrf.pem").write_text(CERTIFICATE)
        database_relation_id = self._create_database_relation_and_populate_data()
        self.harness.add_relation(relation_name=TLS_RELATION_NAME, remote_app=TLS_APPLICATION_NAME)
        self.harness.container_pebble_ready(container_name="nrf")

        self.harness.remove_relation(database_relation_id)
        self.harness.evaluate_status()

        assert self.harness.model.unit.status == BlockedStatus("Waiting for database relation to be created")  # noqa: E501

    def test_given_database_not_available_when_pebble_ready_then_status_is_waiting(
        self,
    ):
        self._create_database_relation()
        self.mock_resource_created.return_value = False
        self.harness.add_relation(relation_name=TLS_RELATION_NAME, remote_app=TLS_APPLICATION_NAME)
        self.harness.container_pebble_ready(container_name="nrf")
        self.harness.evaluate_status()
        assert self.harness.model.unit.status == WaitingStatus("Waiting for the database to be available")  # noqa: E501

    def test_given_database_information_not_available_when_pebble_ready_then_status_is_waiting(
        self,
    ):
        self.mock_resource_created.return_value = True
        self._create_database_relation()
        self.harness.add_relation(relation_name=TLS_RELATION_NAME, remote_app=TLS_APPLICATION_NAME)
        self.harness.container_pebble_ready(container_name="nrf")
        self.harness.evaluate_status()
        assert self.harness.model.unit.status == WaitingStatus("Waiting for database URI")

    def test_given_storage_not_attached_when_pebble_ready_then_status_is_waiting(
        self,
    ):
        self._create_database_relation_and_populate_data()
        self.harness.add_relation(relation_name=TLS_RELATION_NAME, remote_app=TLS_APPLICATION_NAME)
        self.harness.container_pebble_ready(container_name="nrf")
        self.harness.evaluate_status()
        assert self.harness.model.unit.status == WaitingStatus("Waiting for storage to be attached")  # noqa: E501

    def test_given_certificates_not_stored_when_pebble_ready_then_status_is_waiting(
        self
    ):
        self.harness.add_storage("config", attach=True)
        self.harness.add_storage("certs", attach=True)
        self.mock_generate_private_key.return_value = PRIVATE_KEY
        self.mock_generate_csr.return_value = CSR
        self.harness.set_can_connect(container="nrf", val=True)
        self._create_database_relation_and_populate_data()
        self.harness.add_relation(relation_name=TLS_RELATION_NAME, remote_app=TLS_APPLICATION_NAME)
        self.harness.container_pebble_ready("nrf")
        self.harness.evaluate_status()
        assert self.harness.model.unit.status == WaitingStatus("Waiting for certificates to be stored")  # noqa: E501

    def test_given_database_info_and_storage_attached_and_certs_stored_when_pebble_ready_then_config_file_is_rendered_and_pushed(  # noqa: E501
        self,
    ):
        self.harness.add_storage("config", attach=True)
        self.harness.add_storage("certs", attach=True)
        root = self.harness.get_filesystem_root("nrf")
        self.mock_generate_private_key.return_value = PRIVATE_KEY
        self.mock_generate_csr.return_value = CSR
        provider_certificate = Mock(ProviderCertificate)
        provider_certificate.certificate = CERTIFICATE
        provider_certificate.csr = CSR.decode()
        self.mock_get_assigned_certificates.return_value = [
            provider_certificate,
        ]
        (root / "support/TLS/nrf.csr").write_text(CSR.decode())
        (root / f"etc/nrf/{CONFIG_FILE_NAME}").write_text("Dummy Content")
        self.harness.set_can_connect(container="nrf", val=True)
        self._create_database_relation_and_populate_data()
        self.harness.add_relation(relation_name=TLS_RELATION_NAME, remote_app=TLS_APPLICATION_NAME)
        self.harness.container_pebble_ready(container_name="nrf")
        self.harness.evaluate_status()
        assert self.harness.model.unit.status == ActiveStatus("")
        with open(EXPECTED_CONFIG_FILE) as expected_config_file:
            expected_content = expected_config_file.read()
            assert (root / f"etc/nrf/{CONFIG_FILE_NAME}").read_text() == expected_content.strip()

    def test_given_content_of_config_file_not_changed_when_pebble_ready_then_config_file_is_not_pushed(  # noqa: E501
        self,
    ):
        self.harness.add_storage("config", attach=True)
        self.harness.add_storage("certs", attach=True)
        root = self.harness.get_filesystem_root("nrf")
        (root / "support/TLS/nrf.pem").write_text(CERTIFICATE)
        (root / f"etc/nrf/{CONFIG_FILE_NAME}").write_text(
            self._read_file(EXPECTED_CONFIG_FILE).strip()
        )
        config_modification_time = (root / f"etc/nrf/{CONFIG_FILE_NAME}").stat().st_mtime
        self.harness.set_can_connect(container="nrf", val=True)
        self._create_database_relation_and_populate_data()
        self.harness.container_pebble_ready(container_name="nrf")
        assert(root / f"etc/nrf/{CONFIG_FILE_NAME}").stat().st_mtime == config_modification_time

    def test_given_config_pushed_when_pebble_ready_then_pebble_plan_is_applied(
        self,
    ):
        self.harness.add_storage("config", attach=True)
        self.harness.add_storage("certs", attach=True)
        root = self.harness.get_filesystem_root("nrf")
        self.mock_generate_private_key.return_value = PRIVATE_KEY
        self.mock_generate_csr.return_value = CSR
        provider_certificate = Mock(ProviderCertificate)
        provider_certificate.certificate = CERTIFICATE
        provider_certificate.csr = CSR.decode()
        self.mock_get_assigned_certificates.return_value = [
            provider_certificate,
        ]
        (root / "support/TLS/nrf.csr").write_text(CSR.decode())
        (root / f"etc/nrf/{CONFIG_FILE_NAME}").write_text(
            self._read_file(EXPECTED_CONFIG_FILE).strip()
        )

        self.harness.set_can_connect(container="nrf", val=True)
        self._create_database_relation_and_populate_data()
        self.harness.add_relation(relation_name=TLS_RELATION_NAME, remote_app=TLS_APPLICATION_NAME)

        self.harness.container_pebble_ready(container_name="nrf")

        expected_plan = {
            "services": {
                "nrf": {
                    "override": "replace",
                    "command": "/bin/nrf --nrfcfg /etc/nrf/nrfcfg.yaml",
                    "startup": "enabled",
                    "environment": {
                        "GRPC_GO_LOG_VERBOSITY_LEVEL": "99",
                        "GRPC_GO_LOG_SEVERITY_LEVEL": "info",
                        "GRPC_TRACE": "all",
                        "GRPC_VERBOSITY": "debug",
                        "MANAGED_BY_CONFIG_POD": "true",
                    },
                }
            },
        }

        updated_plan = self.harness.get_container_pebble_plan("nrf").to_dict()

        assert expected_plan == updated_plan

    def test_given_database_relation_is_created_and_config_file_is_written_when_pebble_ready_then_status_is_active(  # noqa: E501
        self,
    ):
        self.harness.add_storage("config", attach=True)
        self.harness.add_storage("certs", attach=True)
        root = self.harness.get_filesystem_root("nrf")
        self.mock_generate_private_key.return_value = PRIVATE_KEY
        self.mock_generate_csr.return_value = CSR
        provider_certificate = Mock(ProviderCertificate)
        provider_certificate.certificate = CERTIFICATE
        provider_certificate.csr = CSR.decode()
        self.mock_get_assigned_certificates.return_value = [
            provider_certificate,
        ]
        (root / "support/TLS/nrf.csr").write_text(CSR.decode())
        (root / f"etc/nrf/{CONFIG_FILE_NAME}").write_text(
            self._read_file(EXPECTED_CONFIG_FILE).strip()
        )

        self.harness.set_can_connect(container="nrf", val=True)

        self._create_database_relation_and_populate_data()
        self.harness.add_relation(relation_name=TLS_RELATION_NAME, remote_app=TLS_APPLICATION_NAME)

        self.harness.container_pebble_ready("nrf")
        self.harness.evaluate_status()

        assert self.harness.model.unit.status == ActiveStatus()

    def test_given_https_nrf_url_and_service_is_running_when_fiveg_nrf_relation_joined_then_nrf_url_is_in_relation_databag(  # noqa: E501
        self,
    ):
        self.harness.add_storage(storage_name="certs", attach=True)
        self.harness.add_storage(storage_name="config", attach=True)
        root = self.harness.get_filesystem_root("nrf")
        self.mock_generate_private_key.return_value = PRIVATE_KEY
        self.mock_generate_csr.return_value = CSR
        provider_certificate = Mock(ProviderCertificate)
        provider_certificate.certificate = CERTIFICATE
        provider_certificate.csr = CSR.decode()
        self.mock_get_assigned_certificates.return_value = [
            provider_certificate,
        ]
        (root / "support/TLS/nrf.pem").write_text(CERTIFICATE)
        (root / f"etc/nrf/{CONFIG_FILE_NAME}").write_text(
            self._read_file(EXPECTED_CONFIG_FILE).strip()
        )
        self._create_database_relation_and_populate_data()
        self.harness.add_relation(relation_name=TLS_RELATION_NAME, remote_app=TLS_APPLICATION_NAME)
        self.harness.set_can_connect(container="nrf", val=True)
        self.harness.container_pebble_ready("nrf")
        relation_id = self.harness.add_relation(
            relation_name="fiveg_nrf",
            remote_app="nrf-requirer",
        )
        self.harness.add_relation_unit(relation_id=relation_id, remote_unit_name="nrf-requirer/0")
        relation_data = self.harness.get_relation_data(
            relation_id=relation_id, app_or_unit=self.harness.charm.app.name
        )
        assert relation_data["url"] == "https://sdcore-nrf-k8s:29510"

    def test_service_starts_running_after_nrf_relation_joined_when_fiveg_pebble_ready_then_nrf_url_is_in_relation_databag(  # noqa: E501
        self
    ):
        self.harness.add_storage("config", attach=True)
        self.harness.add_storage("certs", attach=True)
        root = self.harness.get_filesystem_root("nrf")
        self.mock_generate_private_key.return_value = PRIVATE_KEY
        self.mock_generate_csr.return_value = CSR
        provider_certificate = Mock(ProviderCertificate)
        provider_certificate.certificate = CERTIFICATE
        provider_certificate.csr = CSR.decode()
        self.mock_get_assigned_certificates.return_value = [
            provider_certificate,
        ]
        (root / "support/TLS/nrf.csr").write_text(CSR.decode())
        (root / f"etc/nrf/{CONFIG_FILE_NAME}").write_text(
            self._read_file(EXPECTED_CONFIG_FILE).strip()
        )

        self.harness.set_can_connect(container="nrf", val=False)

        relation_1_id = self.harness.add_relation(
            relation_name="fiveg_nrf",
            remote_app="nrf-requirer-1",
        )

        relation_2_id = self.harness.add_relation(
            relation_name="fiveg_nrf",
            remote_app="nrf-requirer-2",
        )
        self.harness.add_relation_unit(
            relation_id=relation_1_id, remote_unit_name="nrf-requirer-1/0"
        )
        self.harness.add_relation_unit(
            relation_id=relation_2_id, remote_unit_name="nrf-requirer-2/0"
        )

        self._create_database_relation_and_populate_data()
        self.harness.add_relation(relation_name=TLS_RELATION_NAME, remote_app=TLS_APPLICATION_NAME)

        self.harness.container_pebble_ready("nrf")

        relation_1_data = self.harness.get_relation_data(
            relation_id=relation_1_id, app_or_unit=self.harness.charm.app.name
        )
        relation_2_data = self.harness.get_relation_data(
            relation_id=relation_2_id, app_or_unit=self.harness.charm.app.name
        )
        assert relation_1_data["url"] == "https://sdcore-nrf-k8s:29510"
        assert relation_2_data["url"] == "https://sdcore-nrf-k8s:29510"

    def test_given_can_connect_when_on_certificates_relation_created_then_private_key_is_generated(
        self,
    ):
        self.harness.add_storage("config", attach=True)
        self.harness.add_storage("certs", attach=True)
        root = self.harness.get_filesystem_root("nrf")
        self.mock_generate_private_key.return_value = PRIVATE_KEY
        self.mock_generate_csr.return_value = CSR
        self._create_database_relation_and_populate_data()
        self.harness.add_relation(relation_name=TLS_RELATION_NAME, remote_app=TLS_APPLICATION_NAME)
        self.harness.set_can_connect(container="nrf", val=True)
        self.harness.container_pebble_ready("nrf")
        assert (root / "support/TLS/nrf.key").read_text() == PRIVATE_KEY.decode()

    def test_given_certificates_are_stored_when_on_certificates_relation_broken_then_certificates_are_removed(  # noqa: E501
        self,
    ):
        self.harness.add_storage("certs", attach=True)
        private_key = "whatever key content"
        csr = "Whatever CSR content"
        root = self.harness.get_filesystem_root("nrf")
        (root / "support/TLS/nrf.key").write_text(private_key)
        (root / "support/TLS/nrf.csr").write_text(csr)
        (root / "support/TLS/nrf.pem").write_text(CERTIFICATE)
        self.harness.set_can_connect(container="nrf", val=True)

        self.harness.charm._on_certificates_relation_broken(event=Mock)

        with pytest.raises(FileNotFoundError):
            (root / "support/TLS/nrf.key").read_text()
        with pytest.raises(FileNotFoundError):
            (root / "support/TLS/nrf.pem").read_text()
        with pytest.raises(FileNotFoundError):
            (root / "support/TLS/nrf.csr").read_text()

    def test_given_certificates_are_stored_when_on_certificates_relation_broken_then_status_is_blocked(  # noqa: E501
        self,
    ):
        self.harness.add_storage("certs", attach=True)
        self.harness.add_storage("config", attach=True)
        private_key = "whatever key content"
        csr = "Whatever CSR content"
        root = self.harness.get_filesystem_root("nrf")
        (root / "support/TLS/nrf.key").write_text(private_key)
        (root / "support/TLS/nrf.csr").write_text(csr)
        (root / "support/TLS/nrf.pem").write_text(CERTIFICATE)
        self.harness.set_can_connect(container="nrf", val=True)
        self._create_database_relation_and_populate_data()
        cert_rel_id = self.harness.add_relation(
            relation_name=TLS_RELATION_NAME, remote_app=TLS_APPLICATION_NAME
        )
        self.harness.remove_relation(cert_rel_id)
        self.harness.evaluate_status()
        assert self.harness.charm.unit.status == BlockedStatus(f"Waiting for {TLS_RELATION_NAME} relation to be created")  # noqa: E501

    def test_given_private_key_exists_when_pebble_ready_then_csr_is_generated(
        self
    ):
        self.harness.add_storage("config", attach=True)
        self.harness.add_storage("certs", attach=True)
        private_key = "whatever key content"
        self.mock_generate_private_key.return_value = private_key
        root = self.harness.get_filesystem_root("nrf")
        (root / "support/TLS/nrf.key").write_text(private_key)
        self.mock_generate_csr.return_value = CSR
        self._create_database_relation_and_populate_data()
        self.harness.add_relation(relation_name=TLS_RELATION_NAME, remote_app=TLS_APPLICATION_NAME)
        self.harness.set_can_connect(container="nrf", val=True)

        self.harness.container_pebble_ready(container_name="nrf")

        assert (root / "support/TLS/nrf.csr").read_text() == CSR.decode()

    def test_given_csr_matches_stored_one_when_certificate_available_then_certificate_is_pushed(
        self
    ):
        self.harness.add_storage("config", attach=True)
        self.harness.add_storage("certs", attach=True)
        root = self.harness.get_filesystem_root("nrf")
        self.mock_generate_private_key.return_value = PRIVATE_KEY
        self.mock_generate_csr.return_value = CSR
        provider_certificate = Mock(ProviderCertificate)
        provider_certificate.certificate = CERTIFICATE
        provider_certificate.csr = CSR.decode()
        self.mock_get_assigned_certificates.return_value = [
            provider_certificate,
        ]
        (root / "support/TLS/nrf.csr").write_text(CSR.decode())
        self._create_database_relation_and_populate_data()
        self.harness.add_relation(relation_name=TLS_RELATION_NAME, remote_app=TLS_APPLICATION_NAME)

        self.harness.set_can_connect(container="nrf", val=False)
        self.harness.container_pebble_ready("nrf")

        assert (root / "support/TLS/nrf.pem").read_text() == CERTIFICATE

    def test_given_csr_doesnt_match_stored_one_when_certificate_available_then_certificate_is_not_pushed(  # noqa: E501
        self,
    ):
        self.harness.add_storage("config", attach=True)
        self.harness.add_storage("certs", attach=True)
        root = self.harness.get_filesystem_root("nrf")
        self.mock_generate_private_key.return_value = PRIVATE_KEY
        self.mock_generate_csr.return_value = CSR
        provider_certificate = Mock(ProviderCertificate)
        provider_certificate.certificate = CERTIFICATE
        provider_certificate.csr = "This is a different CSR"
        self.mock_get_assigned_certificates.return_value = [
            provider_certificate,
        ]
        (root / "support/TLS/nrf.csr").write_text(CSR.decode())
        self._create_database_relation_and_populate_data()
        self.harness.add_relation(relation_name=TLS_RELATION_NAME, remote_app=TLS_APPLICATION_NAME)
        self.harness.set_can_connect(container="nrf", val=False)
        self.harness.container_pebble_ready("nrf")
        with pytest.raises(FileNotFoundError):
            (root / "support/TLS/nrf.pem").read_text()

    def test_given_certificate_does_not_match_stored_one_when_certificate_expiring_then_certificate_is_not_requested(  # noqa: E501
        self,
    ):
        self.harness.add_storage("config", attach=True)
        self.harness.add_storage("certs", attach=True)
        certificate = "Stored certificate content"
        root = self.harness.get_filesystem_root("nrf")
        (root / "support/TLS/nrf.pem").write_text(certificate)
        event = Mock()
        event.certificate = "Relation certificate content (different from stored)"
        self.mock_generate_csr.return_value = CSR
        self.harness.set_can_connect(container="nrf", val=True)

        self.harness.charm._on_certificate_expiring(event=event)

        self.mock_request_certificate_creation.assert_not_called()

    def test_given_certificate_matches_stored_one_when_certificate_expiring_then_certificate_is_requested(  # noqa: E501
        self,
    ):
        self.harness.add_storage("certs", attach=True)
        private_key = "whatever key content"
        root = self.harness.get_filesystem_root("nrf")
        (root / "support/TLS/nrf.key").write_text(private_key)
        (root / "support/TLS/nrf.pem").write_text(CERTIFICATE)
        event = Mock()
        event.certificate = CERTIFICATE
        self.mock_generate_csr.return_value = CSR
        self.harness.set_can_connect(container="nrf", val=True)
        self.harness.charm._on_certificate_expiring(event=event)

        self.mock_request_certificate_creation.assert_called_with(certificate_signing_request=CSR)
