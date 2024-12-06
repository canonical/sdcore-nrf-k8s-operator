# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.


import os
import tempfile

from ops import testing
from ops.pebble import Layer

from tests.unit.certificates_helpers import example_cert_and_key
from tests.unit.fixtures import NRFUnitTestFixtures


class TestCharmConfigure(NRFUnitTestFixtures):
    def test_given_database_info_and_storage_attached_and_certs_stored_when_configure_then_config_file_is_rendered_and_pushed(  # noqa: E501
        self,
    ):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_relation = testing.Relation(
                endpoint="database",
                interface="data-platform",
            )
            certificates_relation = testing.Relation(
                endpoint="certificates",
                interface="tls-certificates",
            )
            nms_relation = testing.Relation(
                endpoint="sdcore_config",
                interface="sdcore_config",
            )
            config_mount = testing.Mount(
                location="/etc/nrf",
                source=temp_dir,
            )
            certs_mount = testing.Mount(
                location="/support/TLS",
                source=temp_dir,
            )
            container = testing.Container(
                name="nrf",
                can_connect=True,
                mounts={"config": config_mount, "certs": certs_mount},
            )
            state_in = testing.State(
                containers=[container],
                relations=[database_relation, certificates_relation, nms_relation],
                leader=True,
            )
            self.mock_database_resource_created.return_value = True
            self.mock_database_relation_data.return_value = {
                database_relation.id: {"uris": "http://dummy"},
            }
            self.mock_sdcore_config_webui_url.return_value = "some-webui:7890"
            provider_certificate, private_key = example_cert_and_key(
                tls_relation_id=certificates_relation.id
            )
            self.mock_get_assigned_certificate.return_value = (provider_certificate, private_key)

            self.ctx.run(self.ctx.on.pebble_ready(container=container), state_in)

            with open(f"{temp_dir}/nrfcfg.yaml", "r") as config_file:
                config_content = config_file.read()

            with open("tests/unit/expected_config/config.conf", "r") as expected_config_file:
                expected_content = expected_config_file.read()

            assert config_content.strip() == expected_content.strip()

    def test_given_content_of_config_file_not_changed_when_configure_then_config_file_is_not_pushed(  # noqa: E501
        self,
    ):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_relation = testing.Relation(
                endpoint="database",
                interface="data-platform",
            )
            certificates_relation = testing.Relation(
                endpoint="certificates",
                interface="tls-certificates",
            )
            nms_relation = testing.Relation(
                endpoint="sdcore_config",
                interface="sdcore_config",
            )
            config_mount = testing.Mount(
                location="/etc/nrf",
                source=temp_dir,
            )
            certs_mount = testing.Mount(
                location="/support/TLS",
                source=temp_dir,
            )
            container = testing.Container(
                name="nrf",
                can_connect=True,
                mounts={"config": config_mount, "certs": certs_mount},
            )
            state_in = testing.State(
                containers=[container],
                relations=[database_relation, certificates_relation, nms_relation],
                leader=True,
            )
            self.mock_database_resource_created.return_value = True
            self.mock_database_relation_data.return_value = {
                database_relation.id: {"uris": "http://dummy"},
            }
            self.mock_sdcore_config_webui_url.return_value = "some-webui:7890"
            provider_certificate, private_key = example_cert_and_key(
                tls_relation_id=certificates_relation.id
            )
            self.mock_get_assigned_certificate.return_value = (provider_certificate, private_key)
            with open("tests/unit/expected_config/config.conf", "r") as expected_config_file:
                expected_content = expected_config_file.read()
            with open(f"{temp_dir}/nrfcfg.yaml", "w") as config_file:
                config_file.write(expected_content.strip())
            config_modification_time = os.stat(temp_dir + "/nrfcfg.yaml").st_mtime

            self.ctx.run(self.ctx.on.pebble_ready(container=container), state_in)

            with open(f"{temp_dir}/nrfcfg.yaml", "r") as config_file:
                config_content = config_file.read()

            with open("tests/unit/expected_config/config.conf", "r") as expected_config_file:
                expected_content = expected_config_file.read()

            assert config_content.strip() == expected_content.strip()
            assert os.stat(temp_dir + "/nrfcfg.yaml").st_mtime == config_modification_time

    def test_given_config_pushed_when_configure_then_pebble_plan_is_applied(
        self,
    ):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_relation = testing.Relation(
                endpoint="database",
                interface="data-platform",
            )
            certificates_relation = testing.Relation(
                endpoint="certificates",
                interface="tls-certificates",
            )
            nms_relation = testing.Relation(
                endpoint="sdcore_config",
                interface="sdcore_config",
            )
            config_mount = testing.Mount(
                location="/etc/nrf",
                source=temp_dir,
            )
            certs_mount = testing.Mount(
                location="/support/TLS",
                source=temp_dir,
            )
            container = testing.Container(
                name="nrf",
                can_connect=True,
                mounts={"config": config_mount, "certs": certs_mount},
            )
            state_in = testing.State(
                containers=[container],
                relations=[database_relation, certificates_relation, nms_relation],
                leader=True,
            )
            self.mock_database_resource_created.return_value = True
            self.mock_database_relation_data.return_value = {
                database_relation.id: {"uris": "http://dummy"},
            }
            self.mock_sdcore_config_webui_url.return_value = "some-webui:7890"
            provider_certificate, private_key = example_cert_and_key(
                tls_relation_id=certificates_relation.id
            )
            self.mock_get_assigned_certificate.return_value = (provider_certificate, private_key)

            state_out = self.ctx.run(self.ctx.on.pebble_ready(container=container), state_in)

            container = state_out.get_container("nrf")
            assert container.layers["nrf"] == Layer(
                {
                    "summary": "nrf layer",
                    "description": "pebble config layer for nrf",
                    "services": {
                        "nrf": {
                            "startup": "enabled",
                            "override": "replace",
                            "command": "/bin/nrf --cfg /etc/nrf/nrfcfg.yaml",
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
            )

    def test_service_starts_running_after_nrf_relation_joined_when_configure_then_nrf_url_is_in_relation_databag(  # noqa: E501
        self,
    ):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_relation = testing.Relation(
                endpoint="database",
                interface="data-platform",
            )
            certificates_relation = testing.Relation(
                endpoint="certificates",
                interface="tls-certificates",
            )
            nms_relation = testing.Relation(
                endpoint="sdcore_config",
                interface="sdcore_config",
            )
            fiveg_nrf_relation = testing.Relation(
                endpoint="fiveg_nrf",
                interface="fiveg_nrf",
            )
            config_mount = testing.Mount(
                location="/etc/nrf",
                source=temp_dir,
            )
            certs_mount = testing.Mount(
                location="/support/TLS",
                source=temp_dir,
            )
            container = testing.Container(
                name="nrf",
                can_connect=True,
                mounts={"config": config_mount, "certs": certs_mount},
            )
            state_in = testing.State(
                containers=[container],
                relations=[
                    database_relation,
                    certificates_relation,
                    nms_relation,
                    fiveg_nrf_relation,
                ],
                leader=True,
            )
            self.mock_database_resource_created.return_value = True
            self.mock_database_relation_data.return_value = {
                database_relation.id: {"uris": "http://dummy"},
            }
            self.mock_sdcore_config_webui_url.return_value = "some-webui:7890"
            provider_certificate, private_key = example_cert_and_key(
                tls_relation_id=certificates_relation.id
            )
            self.mock_get_assigned_certificate.return_value = (provider_certificate, private_key)

            self.ctx.run(self.ctx.on.pebble_ready(container=container), state_in)

            self.mock_set_nrf_information_in_all_relations.assert_called_once()

    def test_given_certificate_available_when_configure_then_certificate_is_pushed(
        self,
    ):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_relation = testing.Relation(
                endpoint="database",
                interface="data-platform",
            )
            certificates_relation = testing.Relation(
                endpoint="certificates",
                interface="tls-certificates",
            )
            nms_relation = testing.Relation(
                endpoint="sdcore_config",
                interface="sdcore_config",
            )
            config_mount = testing.Mount(
                location="/etc/nrf",
                source=temp_dir,
            )
            certs_mount = testing.Mount(
                location="/support/TLS",
                source=temp_dir,
            )
            container = testing.Container(
                name="nrf",
                can_connect=True,
                mounts={"config": config_mount, "certs": certs_mount},
            )
            state_in = testing.State(
                containers=[container],
                relations=[
                    database_relation,
                    certificates_relation,
                    nms_relation,
                ],
                leader=True,
            )
            provider_certificate, private_key = example_cert_and_key(
                tls_relation_id=certificates_relation.id
            )
            self.mock_get_assigned_certificate.return_value = (provider_certificate, private_key)

            self.ctx.run(self.ctx.on.pebble_ready(container=container), state_in)

            with open(f"{temp_dir}/nrf.pem", "r") as f:
                certificate = f.read()
            with open(f"{temp_dir}/nrf.key", "r") as f:
                private_key = f.read()

            assert certificate == str(provider_certificate.certificate)
            assert private_key == str(private_key)
