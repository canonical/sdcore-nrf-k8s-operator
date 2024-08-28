#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charmed operator for the Aether SD-Core NRF service for K8s."""

import logging
from typing import List, Optional

from charms.data_platform_libs.v0.data_interfaces import DatabaseRequires
from charms.loki_k8s.v1.loki_push_api import LogForwarder
from charms.prometheus_k8s.v0.prometheus_scrape import (
    MetricsEndpointProvider,
)
from charms.sdcore_nms_k8s.v0.sdcore_config import (
    SdcoreConfigRequires,
)
from charms.sdcore_nrf_k8s.v0.fiveg_nrf import NRFProvides
from charms.tls_certificates_interface.v4.tls_certificates import (
    Certificate,
    CertificateRequest,
    PrivateKey,
    TLSCertificatesRequiresV4,
)
from jinja2 import Environment, FileSystemLoader
from ops import (
    ActiveStatus,
    BlockedStatus,
    CollectStatusEvent,
    ModelError,
    RelationBrokenEvent,
    WaitingStatus,
)
from ops.charm import CharmBase, RelationJoinedEvent
from ops.framework import EventBase
from ops.main import main
from ops.pebble import Layer

logger = logging.getLogger(__name__)

PROMETHEUS_PORT = 8080
BASE_CONFIG_PATH = "/etc/nrf"
CONFIG_FILE_NAME = "nrfcfg.yaml"
DATABASE_NAME = "free5gc"
NRF_SBI_PORT = 29510
CERTS_DIR_PATH = "/support/TLS"  # Certificate paths are hardcoded in NRF code
PRIVATE_KEY_NAME = "nrf.key"
CERTIFICATE_NAME = "nrf.pem"
CERTIFICATE_COMMON_NAME = "nrf.sdcore"
DATABASE_RELATION_NAME = "database"
NRF_RELATION_NAME = "fiveg_nrf"
SDCORE_CONFIG_RELATION_NAME = "sdcore_config"
TLS_RELATION_NAME = "certificates"
LOGGING_RELATION_NAME = "logging"
WORKLOAD_VERSION_FILE_NAME = "/etc/workload-version"


def _render_config(
    database_name: str,
    database_url: str,
    webui_url: str,
    nrf_host: str,
    nrf_sbi_port: int,
    scheme: str,
) -> str:
    """Render the nrfcfg config file.

    Args:
        database_name: Name of the database
        database_url: URL of the database
        webui_url (str): URL of the Webui.
        nrf_host: Hostname or IP of the NRF service
        nrf_sbi_port: Port of the NRF service
        scheme: SBI interface scheme ("http" or "https")

    Returns:
        str: Rendered config file content
    """
    jinja2_environment = Environment(loader=FileSystemLoader("src/templates/"))
    template = jinja2_environment.get_template("nrfcfg.yaml.j2")
    content = template.render(
        database_name=database_name,
        database_url=database_url,
        webui_url=webui_url,
        nrf_sbi_port=nrf_sbi_port,
        nrf_ip=nrf_host,
        scheme=scheme,
    )
    return content


class NRFOperatorCharm(CharmBase):
    """Main class to describe juju event handling for the SD-Core NRF operator for K8s."""

    def __init__(self, *args):
        """Initialize charm."""
        super().__init__(*args)
        self.framework.observe(self.on.collect_unit_status, self._on_collect_unit_status)
        if not self.unit.is_leader():
            return
        self._container_name = self._service_name = "nrf"
        self._container = self.unit.get_container(self._container_name)
        self._database = DatabaseRequires(
            self, relation_name=DATABASE_RELATION_NAME, database_name=DATABASE_NAME
        )
        self.nrf_provider = NRFProvides(self, NRF_RELATION_NAME)
        self._webui = SdcoreConfigRequires(charm=self, relation_name=SDCORE_CONFIG_RELATION_NAME)
        self._certificates = TLSCertificatesRequiresV4(
            charm=self,
            relationship_name=TLS_RELATION_NAME,
            certificate_requests=[self._get_certificate_request()],
        )
        self._logging = LogForwarder(charm=self, relation_name=LOGGING_RELATION_NAME)
        self._nrf_metrics_endpoint = MetricsEndpointProvider(
            self,
            jobs=[
                {
                    "static_configs": [{"targets": [f"*:{PROMETHEUS_PORT}"]}],
                }
            ],
        )
        self.unit.set_ports(PROMETHEUS_PORT, NRF_SBI_PORT)
        self.framework.observe(self.on.database_relation_joined, self._configure_nrf)
        self.framework.observe(self.on.nrf_pebble_ready, self._configure_nrf)
        self.framework.observe(self._database.on.database_created, self._configure_nrf)
        self.framework.observe(
            self.on.fiveg_nrf_relation_joined, self._on_fiveg_nrf_relation_joined
        )
        self.framework.observe(self.on.sdcore_config_relation_joined, self._configure_nrf)
        self.framework.observe(self._webui.on.webui_url_available, self._configure_nrf)
        self.framework.observe(self.on.certificates_relation_joined, self._configure_nrf)
        self.framework.observe(self._certificates.on.certificate_available, self._configure_nrf)
        self.framework.observe(
            self.on.certificates_relation_broken, self._on_certificates_relation_broken
        )

    def _configure_nrf(self, _: EventBase) -> None:
        """Handle Juju events.

        This event handler is called for every event that affects the charm state
        (ex. configuration files, relation data). This method performs a couple of checks
        to make sure that the workload is ready to be started. Then, it generates a configuration
        for the NRF workload, runs the Pebble services and exposes service information
        the requirers.
        """
        if not self.ready_to_configure():
            logger.info("The preconditions for the configuration are not met yet.")
            return
        if not self._certificate_is_available():
            logger.info("The certificate is not available yet.")
            return
        certificate_update_required = self._check_and_update_certificate()
        desired_config_file = self._generate_nrf_config_file()
        if config_update_required := self._is_config_update_required(desired_config_file):
            self._push_config_file(content=desired_config_file)
        self._configure_workload(restart=(config_update_required or certificate_update_required))
        self._publish_nrf_info_for_all_requirers()

    def ready_to_configure(self) -> bool:
        """Return whether all preconditions are met to proceed with configuration."""
        if not self._container.can_connect():
            return False
        if self._missing_relations():
            return False
        if not self._database_is_available():
            return False
        if not self._get_database_uri():
            return False
        if not self._webui_data_is_available:
            return False
        if not self._container.exists(path=BASE_CONFIG_PATH) or not self._container.exists(
            path=CERTS_DIR_PATH
        ):
            return False
        return True

    def _check_and_update_certificate(self) -> bool:
        """Check if the certificate or private key needs an update and perform the update.

        This method retrieves the currently assigned certificate and private key associated with
        the charm's TLS relation. It checks whether the certificate or private key has changed
        or needs to be updated. If an update is necessary, the new certificate or private key is
        stored.

        Returns:
            bool: True if either the certificate or the private key was updated, False otherwise.
        """
        provider_certificate, private_key = self._certificates.get_assigned_certificate(
            certificate_request=self._get_certificate_request()
        )
        if not provider_certificate or not private_key:
            logger.debug("Certificate or private key is not available")
            return False
        if certificate_update_required := self._is_certificate_update_required(
            provider_certificate.certificate
        ):
            self._store_certificate(certificate=provider_certificate.certificate)
        if private_key_update_required := self._is_private_key_update_required(private_key):
            self._store_private_key(private_key=private_key)
        return certificate_update_required or private_key_update_required

    def _on_collect_unit_status(self, event: CollectStatusEvent):  # noqa C901
        """Check the unit status and set to Unit when CollectStatusEvent is fired.

        Sets the unit workload status if present in workload.

        Args:
            event: CollectStatusEvent
        """
        if not self.unit.is_leader():
            # NOTE: In cases where leader status is lost before the charm is
            # finished processing all teardown events, this prevents teardown
            # event code from running. Luckily, for this charm, none of the
            # teardown code is necessary to perform if we're removing the
            # charm.
            event.add_status(BlockedStatus("Scaling is not implemented for this charm"))
            logger.info("Scaling is not implemented for this charm")
            return
        if not self._container.can_connect():
            event.add_status(WaitingStatus("Waiting for container to be ready"))
            logger.info("Waiting for container to be ready")
            return
        self.unit.set_workload_version(self._get_workload_version())
        if missing_relations := self._missing_relations():
            event.add_status(
                BlockedStatus(f"Waiting for {', '.join(missing_relations)} relation(s)")
            )
            logger.info("Waiting for %s  relation", ", ".join(missing_relations))
            return
        if not self._database_is_available():
            event.add_status(WaitingStatus("Waiting for the database to be available"))
            logger.info("Waiting for the database to be available")
            return
        if not self._get_database_uri():
            event.add_status(WaitingStatus("Waiting for database URI"))
            logger.info("Waiting for database URI")
            return
        if not self._webui_data_is_available:
            event.add_status(WaitingStatus("Waiting for Webui data to be available"))
            logger.info("Waiting for Webui data to be available")
            return
        if not self._container.exists(path=BASE_CONFIG_PATH) or not self._container.exists(
            path=CERTS_DIR_PATH
        ):
            event.add_status(WaitingStatus("Waiting for storage to be attached"))
            logger.info("Waiting for storage to be attached")
            return
        if not self._certificate_is_available():
            event.add_status(WaitingStatus("Waiting for certificates to be available"))
            logger.info("Waiting for certificates to be available")
            return
        if not self._nrf_service_is_running():
            event.add_status(WaitingStatus("Waiting for NRF service to start"))
            logger.info("Waiting for NRF service to start")
            return
        event.add_status(ActiveStatus())

    def _on_certificates_relation_broken(self, event: RelationBrokenEvent) -> None:
        """Delete TLS related artifacts and reconfigures workload."""
        if not self._container.can_connect():
            event.defer()
            return
        self._delete_private_key()
        self._delete_certificate()

    def _certificate_is_available(self) -> bool:
        cert, key = self._certificates.get_assigned_certificate(
            certificate_request=self._get_certificate_request()
        )
        return bool(cert and key)

    def _is_certificate_update_required(self, certificate: Certificate) -> bool:
        return self._get_existing_certificate() != certificate

    def _is_private_key_update_required(self, private_key: PrivateKey) -> bool:
        return self._get_existing_private_key() != private_key

    def _get_existing_certificate(self) -> Optional[Certificate]:
        return self._get_stored_certificate() if self._certificate_is_stored() else None

    def _get_existing_private_key(self) -> Optional[PrivateKey]:
        return self._get_stored_private_key() if self._private_key_is_stored() else None

    def _delete_private_key(self):
        """Remove private key from workload."""
        if not self._private_key_is_stored():
            return
        self._container.remove_path(path=f"{CERTS_DIR_PATH}/{PRIVATE_KEY_NAME}")
        logger.info("Removed private key from workload")

    def _delete_certificate(self):
        """Delete certificate from workload."""
        if not self._certificate_is_stored():
            return
        self._container.remove_path(path=f"{CERTS_DIR_PATH}/{CERTIFICATE_NAME}")
        logger.info("Removed certificate from workload")

    def _private_key_is_stored(self) -> bool:
        """Return whether private key is stored in workload."""
        return self._container.exists(path=f"{CERTS_DIR_PATH}/{PRIVATE_KEY_NAME}")

    def _get_stored_certificate(self) -> Certificate:
        cert_string = str(self._container.pull(path=f"{CERTS_DIR_PATH}/{CERTIFICATE_NAME}").read())
        return Certificate.from_string(cert_string)

    def _get_stored_private_key(self) -> PrivateKey:
        key_string = str(self._container.pull(path=f"{CERTS_DIR_PATH}/{PRIVATE_KEY_NAME}").read())
        return PrivateKey.from_string(key_string)

    def _certificate_is_stored(self) -> bool:
        """Return whether certificate is stored in workload."""
        return self._container.exists(path=f"{CERTS_DIR_PATH}/{CERTIFICATE_NAME}")

    def _store_certificate(self, certificate: Certificate) -> None:
        """Store certificate in workload."""
        self._container.push(path=f"{CERTS_DIR_PATH}/{CERTIFICATE_NAME}", source=str(certificate))
        logger.info("Pushed certificate to workload")

    def _store_private_key(self, private_key: PrivateKey) -> None:
        """Store private key in workload."""
        self._container.push(
            path=f"{CERTS_DIR_PATH}/{PRIVATE_KEY_NAME}",
            source=str(private_key),
        )
        logger.info("Pushed private key to workload")

    def _get_workload_version(self) -> str:
        """Return the workload version.

        Checks for the presence of /etc/workload-version file
        and if present, returns the contents of that file. If
        the file is not present, an empty string is returned.

        Returns:
            string: A human readable string representing the
            version of the workload
        """
        if self._container.exists(path=f"{WORKLOAD_VERSION_FILE_NAME}"):
            version_file_content = self._container.pull(
                path=f"{WORKLOAD_VERSION_FILE_NAME}"
            ).read()
            return version_file_content
        return ""

    def _generate_nrf_config_file(self) -> str:
        """Handle creation of the NRF config file.

        Generate NRF config file based on a given template.

        Returns:
            content (str): desired config file content.
        """
        if not self._webui.webui_url:
            return ""
        return _render_config(
            database_url=self._database_info()["uris"].split(",")[0],
            nrf_host=self.model.app.name,
            database_name=DATABASE_NAME,
            webui_url=self._webui.webui_url,
            nrf_sbi_port=NRF_SBI_PORT,
            scheme="https",
        )

    def _is_config_update_required(self, content: str) -> bool:
        """Decide whether config update is required by checking existence and config content.

        Args:
            content (str): desired config file content

        Returns:
            True if config update is required else False
        """
        if not self._config_file_is_written() or not self._config_file_content_matches(
            content=content
        ):
            return True
        return False

    def _config_file_is_written(self) -> bool:
        """Return whether the config file was written to the workload container.

        Returns:
            bool: Whether the config file was written.
        """
        return bool(self._container.exists(f"{BASE_CONFIG_PATH}/{CONFIG_FILE_NAME}"))

    def _configure_workload(self, restart: bool = False) -> None:
        """Configure pebble layer for the nrf container."""
        plan = self._container.get_plan()
        if plan.services != self._pebble_layer.services:
            self._container.add_layer(self._container_name, self._pebble_layer, combine=True)
            self._container.replan()
            logger.info("New layer added: %s", self._pebble_layer)
        if restart:
            self._container.restart(self._service_name)
            logger.info("Restarted container %s", self._service_name)
            return

    def _config_file_content_matches(self, content: str) -> bool:
        """Return whether the nrfcfg config file content matches the provided content.

        Returns:
            bool: Whether the nrfcfg config file content matches
        """
        if not self._container.exists(path=f"{BASE_CONFIG_PATH}/{CONFIG_FILE_NAME}"):
            return False
        existing_content = self._container.pull(path=f"{BASE_CONFIG_PATH}/{CONFIG_FILE_NAME}")
        if existing_content.read() != content:
            return False
        return True

    def _on_fiveg_nrf_relation_joined(self, event: RelationJoinedEvent) -> None:
        """Handle fiveg_nrf relation joined event.

        Args:
            event: RelationJoinedEvent
        """
        if not self._nrf_service_is_running():
            return
        nrf_url = self._get_nrf_url()
        self.nrf_provider.set_nrf_information(
            url=nrf_url,
            relation_id=event.relation.id,
        )

    def _publish_nrf_info_for_all_requirers(self) -> None:
        """Publish nrf information in the databags of all relations requiring it."""
        if not self._relation_created(NRF_RELATION_NAME):
            return
        nrf_url = self._get_nrf_url()
        self.nrf_provider.set_nrf_information_in_all_relations(nrf_url)

    @staticmethod
    def _get_certificate_request() -> CertificateRequest:
        return CertificateRequest(
            common_name=CERTIFICATE_COMMON_NAME,
            sans_dns=frozenset([CERTIFICATE_COMMON_NAME]),
        )

    def _missing_relations(self) -> List[str]:
        missing_relations = []
        for relation in [DATABASE_RELATION_NAME, SDCORE_CONFIG_RELATION_NAME, TLS_RELATION_NAME]:
            if not self._relation_created(relation):
                missing_relations.append(relation)
        return missing_relations

    def _relation_created(self, relation_name: str) -> bool:
        """Return whether a given Juju relation was created.

        Args:
            relation_name (str): Relation name

        Returns:
            bool: Whether the relation was created.
        """
        return bool(self.model.relations[relation_name])

    def _push_config_file(self, content: str) -> None:
        """Push config file to workload.

        Args:
            content: config file content
        """
        if not self._container.can_connect():
            return
        self._container.push(path=f"{BASE_CONFIG_PATH}/{CONFIG_FILE_NAME}", source=content)
        logger.info("Pushed %s config file to workload", CONFIG_FILE_NAME)

    def _database_is_available(self) -> bool:
        """Return True if the database is available.

        Returns:
            bool: True if the database is available.
        """
        return self._database.is_resource_created()

    def _database_info(self) -> dict:
        """Return the database data.

        Returns:
            Dict: The database data.
        """
        if not self._database_is_available():
            raise RuntimeError(f"Database `{DATABASE_NAME}` is not available")
        return self._database.fetch_relation_data()[self._database.relations[0].id]

    def _get_database_uri(self) -> str:
        """Return the database URI.

        Returns:
            str: The database URI.
        """
        try:
            return self._database_info()["uris"].split(",")[0]
        except KeyError:
            return ""

    @property
    def _webui_data_is_available(self) -> bool:
        return bool(self._webui.webui_url)

    @property
    def _pebble_layer(self) -> Layer:
        """Return pebble layer for the charm.

        Returns:
            Layer: Pebble Layer
        """
        return Layer(
            {
                "summary": "nrf layer",
                "description": "pebble config layer for nrf",
                "services": {
                    "nrf": {
                        "override": "replace",
                        "startup": "enabled",
                        "command": f"/bin/nrf --nrfcfg {BASE_CONFIG_PATH}/{CONFIG_FILE_NAME}",
                        "environment": self._environment_variables,
                    },
                },
            }
        )

    @property
    def _environment_variables(self) -> dict:
        """Return workload service environment variables.

        Returns:
            dict: Environment variables
        """
        return {
            "GRPC_GO_LOG_VERBOSITY_LEVEL": "99",
            "GRPC_GO_LOG_SEVERITY_LEVEL": "info",
            "GRPC_TRACE": "all",
            "GRPC_VERBOSITY": "debug",
            "MANAGED_BY_CONFIG_POD": "true",
        }

    def _nrf_service_is_running(self) -> bool:
        """Return whether the NRF service is running.

        Returns:
            bool: Whether the NRF service is running.
        """
        if not self._container.can_connect():
            return False
        try:
            service = self._container.get_service(self._service_name)
        except ModelError:
            return False
        return service.is_running()

    def _get_nrf_url(self) -> str:
        """Return NRF URL."""
        return f"https://{self.model.app.name}:{NRF_SBI_PORT}"


if __name__ == "__main__":
    main(NRFOperatorCharm)
