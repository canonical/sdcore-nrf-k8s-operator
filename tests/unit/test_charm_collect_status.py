# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.


import tempfile

from ops import testing
from ops.model import ActiveStatus, BlockedStatus, WaitingStatus
from ops.pebble import Layer, ServiceStatus

from tests.unit.certificates_helpers import example_cert_and_key
from tests.unit.fixtures import NRFUnitTestFixtures


class TestCharmCollectStatus(NRFUnitTestFixtures):
    def test_given_container_not_ready_when_collect_unit_status_then_status_is_waiting(self):
        container = testing.Container(
            name="nrf",
        )
        state_in = testing.State(
            containers=[container],
            leader=True,
        )

        state_out = self.ctx.run(self.ctx.on.collect_unit_status(), state_in)

        assert state_out.unit_status == WaitingStatus("Waiting for container to be ready")

    def test_given_relations_not_created_when_collect_unit_status_then_status_is_blocked(self):
        container = testing.Container(
            name="nrf",
            can_connect=True,
        )
        state_in = testing.State(
            containers=[container],
            leader=True,
        )

        state_out = self.ctx.run(self.ctx.on.collect_unit_status(), state_in)

        assert state_out.unit_status == BlockedStatus(
            "Waiting for database, sdcore_config, certificates relation(s)"
        )

    def test_given_certificates_and_nms_relations_not_created_when_collect_unit_status_then_status_is_blocked(  # noqa: E501
        self,
    ):
        database_relation = testing.Relation(
            endpoint="database",
            interface="mongodb_client",
        )
        container = testing.Container(
            name="nrf",
            can_connect=True,
        )
        state_in = testing.State(
            containers=[container],
            relations=[database_relation],
            leader=True,
        )

        state_out = self.ctx.run(self.ctx.on.collect_unit_status(), state_in)

        assert state_out.unit_status == BlockedStatus(
            "Waiting for sdcore_config, certificates relation(s)"
        )

    def test_given_nms_relation_not_created_when_collect_unit_status_then_status_is_blocked(
        self,
    ):
        database_relation = testing.Relation(
            endpoint="database",
            interface="mongodb_client",
        )
        certificates_relation = testing.Relation(
            endpoint="certificates",
            interface="tls-certificates",
        )
        container = testing.Container(
            name="nrf",
            can_connect=True,
        )
        state_in = testing.State(
            containers=[container],
            relations=[database_relation, certificates_relation],
            leader=True,
        )

        state_out = self.ctx.run(self.ctx.on.collect_unit_status(), state_in)

        assert state_out.unit_status == BlockedStatus("Waiting for sdcore_config relation(s)")

    def test_given_database_not_available_when_collect_unit_status_then_status_is_waiting(
        self,
    ):
        database_relation = testing.Relation(
            endpoint="database",
            interface="mongodb_client",
        )
        certificates_relation = testing.Relation(
            endpoint="certificates",
            interface="tls-certificates",
        )
        nms_relation = testing.Relation(
            endpoint="sdcore_config",
            interface="sdcore_config",
        )
        container = testing.Container(
            name="nrf",
            can_connect=True,
        )
        state_in = testing.State(
            containers=[container],
            relations=[database_relation, certificates_relation, nms_relation],
            leader=True,
        )
        self.mock_database_resource_created.return_value = False

        state_out = self.ctx.run(self.ctx.on.collect_unit_status(), state_in)

        assert state_out.unit_status == WaitingStatus("Waiting for the database to be available")

    def test_given_database_information_not_available_when_collect_unit_status_then_status_is_waiting(  # noqa: E501
        self,
    ):
        certificates_relation = testing.Relation(
            endpoint="certificates",
            interface="tls-certificates",
        )
        database_relation = testing.Relation(
            endpoint="database",
            interface="mongodb_client",
        )
        nms_relation = testing.Relation(
            endpoint="sdcore_config",
            interface="sdcore_config",
        )
        container = testing.Container(
            name="nrf",
            can_connect=True,
        )
        state_in = testing.State(
            containers=[container],
            relations=[certificates_relation, database_relation, nms_relation],
            leader=True,
        )
        self.mock_database_resource_created.return_value = True
        self.mock_database_relation_data.return_value = {}

        state_out = self.ctx.run(self.ctx.on.collect_unit_status(), state_in)

        assert state_out.unit_status == WaitingStatus("Waiting for database URI")

    def test_given_webui_data_not_available_when_collect_unit_status_then_status_is_waiting(
        self,
    ):
        certificates_relation = testing.Relation(
            endpoint="certificates",
            interface="tls-certificates",
        )
        database_relation = testing.Relation(
            endpoint="database",
            interface="mongodb_client",
        )
        nms_relation = testing.Relation(
            endpoint="sdcore_config",
            interface="sdcore_config",
        )
        container = testing.Container(
            name="nrf",
            can_connect=True,
        )
        state_in = testing.State(
            containers=[container],
            relations=[certificates_relation, database_relation, nms_relation],
            leader=True,
        )
        self.mock_database_resource_created.return_value = True
        self.mock_database_relation_data.return_value = {
            database_relation.id: {"uris": "mongodb://localhost:27017"},
        }
        self.mock_sdcore_config_webui_url.return_value = None

        state_out = self.ctx.run(self.ctx.on.collect_unit_status(), state_in)

        assert state_out.unit_status == WaitingStatus("Waiting for Webui data to be available")

    def test_given_storage_not_attached_when_collect_unit_status_then_status_is_waiting(
        self,
    ):
        certificates_relation = testing.Relation(
            endpoint="certificates",
            interface="tls-certificates",
        )
        database_relation = testing.Relation(
            endpoint="database",
            interface="mongodb_client",
        )
        nms_relation = testing.Relation(
            endpoint="sdcore_config",
            interface="sdcore_config",
        )
        container = testing.Container(
            name="nrf",
            can_connect=True,
        )
        state_in = testing.State(
            containers=[container],
            relations=[certificates_relation, database_relation, nms_relation],
            leader=True,
        )
        self.mock_database_resource_created.return_value = True
        self.mock_database_relation_data.return_value = {
            database_relation.id: {"uris": "mongodb://localhost:27017"},
        }
        self.mock_sdcore_config_webui_url.return_value = "https://webui.url"

        state_out = self.ctx.run(self.ctx.on.collect_unit_status(), state_in)

        assert state_out.unit_status == WaitingStatus("Waiting for storage to be attached")

    def test_given_certificates_not_stored_when_collect_unit_status_then_status_is_waiting(
        self,
    ):
        with tempfile.TemporaryDirectory() as tempdir:
            certificates_relation = testing.Relation(
                endpoint="certificates",
                interface="tls-certificates",
            )
            database_relation = testing.Relation(
                endpoint="database",
                interface="mongodb_client",
            )
            nms_relation = testing.Relation(
                endpoint="sdcore_config",
                interface="sdcore_config",
            )
            config_mount = testing.Mount(
                location="/etc/nrf/",
                source=tempdir,
            )
            certs_mount = testing.Mount(
                location="/support/TLS/",
                source=tempdir,
            )
            container = testing.Container(
                name="nrf",
                can_connect=True,
                mounts={
                    "config": config_mount,
                    "certs": certs_mount,
                },
            )
            state_in = testing.State(
                containers=[container],
                relations=[certificates_relation, database_relation, nms_relation],
                leader=True,
            )
            self.mock_database_resource_created.return_value = True
            self.mock_database_relation_data.return_value = {
                database_relation.id: {"uris": "mongodb://localhost:27017"},
            }
            self.mock_sdcore_config_webui_url.return_value = "https://webui.url"
            self.mock_get_assigned_certificate.return_value = (None, None)

            state_out = self.ctx.run(self.ctx.on.collect_unit_status(), state_in)

            assert state_out.unit_status == WaitingStatus(
                "Waiting for certificates to be available"
            )

    def test_given_nrf_service_not_started_when_collect_unit_status_then_status_is_waiting(
        self,
    ):
        with tempfile.TemporaryDirectory() as tempdir:
            certificates_relation = testing.Relation(
                endpoint="certificates",
                interface="tls-certificates",
            )
            database_relation = testing.Relation(
                endpoint="database",
                interface="mongodb_client",
            )
            nms_relation = testing.Relation(
                endpoint="sdcore_config",
                interface="sdcore_config",
            )
            config_mount = testing.Mount(
                location="/etc/nrf/",
                source=tempdir,
            )
            certs_mount = testing.Mount(
                location="/support/TLS/",
                source=tempdir,
            )
            container = testing.Container(
                name="nrf",
                can_connect=True,
                mounts={
                    "config": config_mount,
                    "certs": certs_mount,
                },
            )
            state_in = testing.State(
                containers=[container],
                relations=[certificates_relation, database_relation, nms_relation],
                leader=True,
            )
            self.mock_database_resource_created.return_value = True
            self.mock_database_relation_data.return_value = {
                database_relation.id: {"uris": "mongodb://localhost:27017"},
            }
            self.mock_sdcore_config_webui_url.return_value = "https://webui.url"
            provider_certificate, private_key = example_cert_and_key(
                tls_relation_id=certificates_relation.id
            )
            self.mock_get_assigned_certificate.return_value = (provider_certificate, private_key)

            state_out = self.ctx.run(self.ctx.on.collect_unit_status(), state_in)

            assert state_out.unit_status == WaitingStatus("Waiting for NRF service to start")

    def test_given_database_relation_is_created_and_config_file_is_written_when_collect_unit_status_then_status_is_active(  # noqa: E501
        self,
    ):
        with tempfile.TemporaryDirectory() as tempdir:
            certificates_relation = testing.Relation(
                endpoint="certificates",
                interface="tls-certificates",
            )
            database_relation = testing.Relation(
                endpoint="database",
                interface="mongodb_client",
            )
            nms_relation = testing.Relation(
                endpoint="sdcore_config",
                interface="sdcore_config",
            )
            config_mount = testing.Mount(
                location="/etc/nrf/",
                source=tempdir,
            )
            certs_mount = testing.Mount(
                location="/support/TLS/",
                source=tempdir,
            )
            container = testing.Container(
                name="nrf",
                can_connect=True,
                layers={"nrf": Layer({"services": {"nrf": {}}})},
                service_statuses={
                    "nrf": ServiceStatus.ACTIVE,
                },
                mounts={
                    "config": config_mount,
                    "certs": certs_mount,
                },
            )
            state_in = testing.State(
                containers=[container],
                relations=[certificates_relation, database_relation, nms_relation],
                leader=True,
            )
            self.mock_database_resource_created.return_value = True
            self.mock_database_relation_data.return_value = {
                database_relation.id: {"uris": "mongodb://localhost:27017"},
            }
            self.mock_sdcore_config_webui_url.return_value = "https://webui.url"

            provider_certificate, private_key = example_cert_and_key(
                tls_relation_id=certificates_relation.id
            )
            self.mock_get_assigned_certificate.return_value = provider_certificate, private_key
            with open(f"{tempdir}/nrf.pem", "w") as f:
                f.write("whatever cert")

            state_out = self.ctx.run(self.ctx.on.collect_unit_status(), state_in)

            assert state_out.unit_status == ActiveStatus()

    def test_given_no_workload_version_file_when_collect_unit_status_then_workload_version_not_set(  # noqa: E501
        self,
    ):
        container = testing.Container(
            name="nrf",
            can_connect=True,
        )
        state_in = testing.State(
            containers=[container],
            leader=True,
        )

        state_out = self.ctx.run(self.ctx.on.collect_unit_status(), state_in)

        assert state_out.workload_version == ""

    def test_given_workload_version_file_when_container_can_connect_then_workload_version_set(
        self,
    ):
        with tempfile.TemporaryDirectory() as temp_dir:
            workload_version_mount = testing.Mount(
                location="/etc",
                source=temp_dir,
            )
            container = testing.Container(
                name="nrf",
                can_connect=True,
                mounts={"workload-version": workload_version_mount},
            )
            state_in = testing.State(
                containers=[container],
                leader=True,
            )
            with open(f"{temp_dir}/workload-version", "w") as f:
                f.write("1.2.3")

            state_out = self.ctx.run(self.ctx.on.collect_unit_status(), state_in)

            assert state_out.workload_version == "1.2.3"
