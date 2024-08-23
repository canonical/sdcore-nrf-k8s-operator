# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.


import datetime
import os
import tempfile

import scenario
from charms.tls_certificates_interface.v3.tls_certificates import (
    ProviderCertificate,
)
from ops.pebble import Layer

from tests.unit.fixtures import NRFUnitTestFixtures


class TestCharmConfigure(NRFUnitTestFixtures):
    def test_given_database_info_and_storage_attached_and_certs_stored_when_pebble_ready_then_config_file_is_rendered_and_pushed(  # noqa: E501
        self,
    ):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_relation = scenario.Relation(
                endpoint="database",
                interface="data-platform",
            )
            certificates_relation = scenario.Relation(
                endpoint="certificates",
                interface="tls-certificates",
            )
            nms_relation = scenario.Relation(
                endpoint="sdcore_config",
                interface="sdcore_config",
            )
            config_mount = scenario.Mount(
                location="/etc/nrf",
                src=temp_dir,
            )
            certs_mount = scenario.Mount(
                location="/support/TLS",
                src=temp_dir,
            )
            container = scenario.Container(
                name="nrf",
                can_connect=True,
                mounts={"config": config_mount, "certs": certs_mount},
            )
            state_in = scenario.State(
                containers=[container],
                relations=[database_relation, certificates_relation, nms_relation],
                leader=True,
            )
            self.mock_database_resource_created.return_value = True
            self.mock_database_relation_data.return_value = {
                database_relation.relation_id: {"uris": "http://dummy"},
            }
            self.mock_sdcore_config_webui_url.return_value = "some-webui:7890"
            self.mock_get_assigned_certificates.return_value = [
                ProviderCertificate(
                    relation_id=certificates_relation.relation_id,
                    application_name="nrf",
                    csr="whatever csr",
                    certificate="whatever cert",
                    ca="whatever ca",
                    chain=["whatever ca", "whatever cert"],
                    revoked=False,
                    expiry_time=datetime.datetime.now(),
                )
            ]
            with open(f"{temp_dir}/nrf.csr", "w") as f:
                f.write("whatever csr")

            self.ctx.run(container.pebble_ready_event, state_in)

            with open(f"{temp_dir}/nrfcfg.yaml", "r") as config_file:
                config_content = config_file.read()

            with open("tests/unit/expected_config/config.conf", "r") as expected_config_file:
                expected_content = expected_config_file.read()

            assert config_content.strip() == expected_content.strip()

    def test_given_content_of_config_file_not_changed_when_pebble_ready_then_config_file_is_not_pushed(  # noqa: E501
        self,
    ):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_relation = scenario.Relation(
                endpoint="database",
                interface="data-platform",
            )
            certificates_relation = scenario.Relation(
                endpoint="certificates",
                interface="tls-certificates",
            )
            nms_relation = scenario.Relation(
                endpoint="sdcore_config",
                interface="sdcore_config",
            )
            config_mount = scenario.Mount(
                location="/etc/nrf",
                src=temp_dir,
            )
            certs_mount = scenario.Mount(
                location="/support/TLS",
                src=temp_dir,
            )
            container = scenario.Container(
                name="nrf",
                can_connect=True,
                mounts={"config": config_mount, "certs": certs_mount},
            )
            state_in = scenario.State(
                containers=[container],
                relations=[database_relation, certificates_relation, nms_relation],
                leader=True,
            )
            self.mock_database_resource_created.return_value = True
            self.mock_database_relation_data.return_value = {
                database_relation.relation_id: {"uris": "http://dummy"},
            }
            self.mock_sdcore_config_webui_url.return_value = "some-webui:7890"
            self.mock_get_assigned_certificates.return_value = [
                ProviderCertificate(
                    relation_id=certificates_relation.relation_id,
                    application_name="nrf",
                    csr="whatever csr",
                    certificate="whatever cert",
                    ca="whatever ca",
                    chain=["whatever ca", "whatever cert"],
                    revoked=False,
                    expiry_time=datetime.datetime.now(),
                )
            ]
            with open(f"{temp_dir}/nrf.csr", "w") as f:
                f.write("whatever csr")
            with open("tests/unit/expected_config/config.conf", "r") as expected_config_file:
                expected_content = expected_config_file.read()
            with open(f"{temp_dir}/nrfcfg.yaml", "w") as config_file:
                config_file.write(expected_content.strip())
            config_modification_time = os.stat(temp_dir + "/nrfcfg.yaml").st_mtime

            self.ctx.run(container.pebble_ready_event, state_in)

            with open(f"{temp_dir}/nrfcfg.yaml", "r") as config_file:
                config_content = config_file.read()

            with open("tests/unit/expected_config/config.conf", "r") as expected_config_file:
                expected_content = expected_config_file.read()

            assert config_content.strip() == expected_content.strip()
            assert os.stat(temp_dir + "/nrfcfg.yaml").st_mtime == config_modification_time

    def test_given_config_pushed_when_pebble_ready_then_pebble_plan_is_applied(
        self,
    ):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_relation = scenario.Relation(
                endpoint="database",
                interface="data-platform",
            )
            certificates_relation = scenario.Relation(
                endpoint="certificates",
                interface="tls-certificates",
            )
            nms_relation = scenario.Relation(
                endpoint="sdcore_config",
                interface="sdcore_config",
            )
            config_mount = scenario.Mount(
                location="/etc/nrf",
                src=temp_dir,
            )
            certs_mount = scenario.Mount(
                location="/support/TLS",
                src=temp_dir,
            )
            container = scenario.Container(
                name="nrf",
                can_connect=True,
                mounts={"config": config_mount, "certs": certs_mount},
            )
            state_in = scenario.State(
                containers=[container],
                relations=[database_relation, certificates_relation, nms_relation],
                leader=True,
            )
            self.mock_database_resource_created.return_value = True
            self.mock_database_relation_data.return_value = {
                database_relation.relation_id: {"uris": "http://dummy"},
            }
            self.mock_sdcore_config_webui_url.return_value = "some-webui:7890"
            self.mock_get_assigned_certificates.return_value = [
                ProviderCertificate(
                    relation_id=certificates_relation.relation_id,
                    application_name="nrf",
                    csr="whatever csr",
                    certificate="whatever cert",
                    ca="whatever ca",
                    chain=["whatever ca", "whatever cert"],
                    revoked=False,
                    expiry_time=datetime.datetime.now(),
                )
            ]
            with open(f"{temp_dir}/nrf.csr", "w") as f:
                f.write("whatever csr")

            state_out = self.ctx.run(container.pebble_ready_event, state_in)

            assert state_out.containers[0].layers["nrf"] == Layer(
                {
                    "summary": "nrf layer",
                    "description": "pebble config layer for nrf",
                    "services": {
                        "nrf": {
                            "startup": "enabled",
                            "override": "replace",
                            "command": "/bin/nrf --nrfcfg /etc/nrf/nrfcfg.yaml",
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

    def test_service_starts_running_after_nrf_relation_joined_when_fiveg_pebble_ready_then_nrf_url_is_in_relation_databag(  # noqa: E501
        self,
    ):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_relation = scenario.Relation(
                endpoint="database",
                interface="data-platform",
            )
            certificates_relation = scenario.Relation(
                endpoint="certificates",
                interface="tls-certificates",
            )
            nms_relation = scenario.Relation(
                endpoint="sdcore_config",
                interface="sdcore_config",
            )
            fiveg_nrf_relation = scenario.Relation(
                endpoint="fiveg_nrf",
                interface="fiveg_nrf",
            )
            config_mount = scenario.Mount(
                location="/etc/nrf",
                src=temp_dir,
            )
            certs_mount = scenario.Mount(
                location="/support/TLS",
                src=temp_dir,
            )
            container = scenario.Container(
                name="nrf",
                can_connect=True,
                mounts={"config": config_mount, "certs": certs_mount},
            )
            state_in = scenario.State(
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
                database_relation.relation_id: {"uris": "http://dummy"},
            }
            self.mock_sdcore_config_webui_url.return_value = "some-webui:7890"
            self.mock_get_assigned_certificates.return_value = [
                ProviderCertificate(
                    relation_id=certificates_relation.relation_id,
                    application_name="nrf",
                    csr="whatever csr",
                    certificate="whatever cert",
                    ca="whatever ca",
                    chain=["whatever ca", "whatever cert"],
                    revoked=False,
                    expiry_time=datetime.datetime.now(),
                )
            ]
            with open(f"{temp_dir}/nrf.csr", "w") as f:
                f.write("whatever csr")

            self.ctx.run(container.pebble_ready_event, state_in)

            self.mock_set_nrf_information_in_all_relations.assert_called_once()

    def test_given_can_connect_when_on_certificates_relation_created_then_private_key_and_csr_are_generated(  # noqa: E501
        self,
    ):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_relation = scenario.Relation(
                endpoint="database",
                interface="data-platform",
            )
            certificates_relation = scenario.Relation(
                endpoint="certificates",
                interface="tls-certificates",
            )
            nms_relation = scenario.Relation(
                endpoint="sdcore_config",
                interface="sdcore_config",
            )
            config_mount = scenario.Mount(
                location="/etc/nrf",
                src=temp_dir,
            )
            certs_mount = scenario.Mount(
                location="/support/TLS",
                src=temp_dir,
            )
            container = scenario.Container(
                name="nrf",
                can_connect=True,
                mounts={"config": config_mount, "certs": certs_mount},
            )
            state_in = scenario.State(
                containers=[container],
                relations=[
                    database_relation,
                    certificates_relation,
                    nms_relation,
                ],
                leader=True,
            )
            self.mock_database_resource_created.return_value = True
            self.mock_database_relation_data.return_value = {
                database_relation.relation_id: {"uris": "http://dummy"},
            }
            self.mock_sdcore_config_webui_url.return_value = "some-webui:7890"

            self.ctx.run(container.pebble_ready_event, state_in)

            with open(f"{temp_dir}/nrf.key", "r") as f:
                private_key = f.read()
            with open(f"{temp_dir}/nrf.csr", "r") as f:
                csr = f.read()

            assert private_key.startswith("-----BEGIN RSA PRIVATE KEY-----")
            assert csr.startswith("-----BEGIN CERTIFICATE REQUEST-----")

    def test_given_csr_matches_stored_one_when_certificate_available_then_certificate_is_pushed(
        self,
    ):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_relation = scenario.Relation(
                endpoint="database",
                interface="data-platform",
            )
            certificates_relation = scenario.Relation(
                endpoint="certificates",
                interface="tls-certificates",
            )
            nms_relation = scenario.Relation(
                endpoint="sdcore_config",
                interface="sdcore_config",
            )
            config_mount = scenario.Mount(
                location="/etc/nrf",
                src=temp_dir,
            )
            certs_mount = scenario.Mount(
                location="/support/TLS",
                src=temp_dir,
            )
            container = scenario.Container(
                name="nrf",
                can_connect=True,
                mounts={"config": config_mount, "certs": certs_mount},
            )
            state_in = scenario.State(
                containers=[container],
                relations=[
                    database_relation,
                    certificates_relation,
                    nms_relation,
                ],
                leader=True,
            )
            with open(f"{temp_dir}/nrf.csr", "w") as f:
                f.write("whatever csr")
            self.mock_get_assigned_certificates.return_value = [
                ProviderCertificate(
                    relation_id=certificates_relation.relation_id,
                    application_name="nrf",
                    csr="whatever csr",
                    certificate="whatever cert",
                    ca="whatever ca",
                    chain=["whatever ca", "whatever cert"],
                    revoked=False,
                    expiry_time=datetime.datetime.now(),
                )
            ]

            self.ctx.run(container.pebble_ready_event, state_in)

            with open(f"{temp_dir}/nrf.pem", "r") as f:
                certificate = f.read()

            assert certificate == "whatever cert"

    def test_given_csr_doesnt_match_stored_one_when_certificate_available_then_certificate_is_not_pushed(  # noqa: E501
        self,
    ):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_relation = scenario.Relation(
                endpoint="database",
                interface="data-platform",
            )
            certificates_relation = scenario.Relation(
                endpoint="certificates",
                interface="tls-certificates",
            )
            nms_relation = scenario.Relation(
                endpoint="sdcore_config",
                interface="sdcore_config",
            )
            config_mount = scenario.Mount(
                location="/etc/nrf",
                src=temp_dir,
            )
            certs_mount = scenario.Mount(
                location="/support/TLS",
                src=temp_dir,
            )
            container = scenario.Container(
                name="nrf",
                can_connect=True,
                mounts={"config": config_mount, "certs": certs_mount},
            )
            state_in = scenario.State(
                containers=[container],
                relations=[
                    database_relation,
                    certificates_relation,
                    nms_relation,
                ],
                leader=True,
            )
            with open(f"{temp_dir}/nrf.csr", "w") as f:
                f.write("whatever csr")
            self.mock_get_assigned_certificates.return_value = [
                ProviderCertificate(
                    relation_id=certificates_relation.relation_id,
                    application_name="nrf",
                    csr="different csr",
                    certificate="whatever cert",
                    ca="whatever ca",
                    chain=["whatever ca", "whatever cert"],
                    revoked=False,
                    expiry_time=datetime.datetime.now(),
                )
            ]

            self.ctx.run(container.pebble_ready_event, state_in)

            assert not os.path.exists(f"{temp_dir}/nrf.pem")


#
