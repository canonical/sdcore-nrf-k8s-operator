#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charmed operator for the SD-Core NRF service for K8s."""

import logging
from ipaddress import IPv4Address
from subprocess import check_output
from typing import Optional

from charms.data_platform_libs.v0.data_interfaces import DatabaseRequires  # type: ignore[import]
from charms.loki_k8s.v1.loki_push_api import LogForwarder
from charms.sdcore_nrf_k8s.v0.fiveg_nrf import NRFProvides  # type: ignore[import]
from charms.tls_certificates_interface.v3.tls_certificates import (  # type: ignore[import]
    CertificateExpiringEvent,
    TLSCertificatesRequiresV3,
    generate_csr,
    generate_private_key,
)
from jinja2 import Environment, FileSystemLoader  # type: ignore[import]
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

BASE_CONFIG_PATH = "/etc/nrf"
CONFIG_FILE_NAME = "nrfcfg.yaml"
DATABASE_NAME = "free5gc"
NRF_SBI_PORT = 29510
DATABASE_RELATION_NAME = "database"
NRF_RELATION_NAME = "fiveg_nrf"
CERTS_DIR_PATH = "/support/TLS"  # Certificate paths are hardcoded in NRF code
PRIVATE_KEY_NAME = "nrf.key"
CSR_NAME = "nrf.csr"
CERTIFICATE_NAME = "nrf.pem"
CERTIFICATE_COMMON_NAME = "nrf.sdcore"
LOGGING_RELATION_NAME = "logging"


def _get_pod_ip() -> Optional[str]:
    """Return the pod IP using juju client.

    Returns:
        str: The pod IP.
    """
    ip_address = check_output(["unit-get", "private-address"])
    return str(IPv4Address(ip_address.decode().strip())) if ip_address else None


def _render_config(
    database_name: str,
    database_url: str,
    nrf_ip: str,
    nrf_sbi_port: int,
    scheme: str,
) -> str:
    """Render the nrfcfg config file.

    Args:
        database_name: Name of the database
        database_url: URL of the database
        nrf_ip: IP of the NRF service
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
        nrf_sbi_port=nrf_sbi_port,
        nrf_ip=nrf_ip,
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
        self._certificates = TLSCertificatesRequiresV3(self, "certificates")
        self._logging = LogForwarder(charm=self, relation_name=LOGGING_RELATION_NAME)
        self.unit.set_ports(NRF_SBI_PORT)
        self.framework.observe(self.on.database_relation_joined, self._configure_nrf)
        self.framework.observe(self.on.nrf_pebble_ready, self._configure_nrf)
        self.framework.observe(self._database.on.database_created, self._configure_nrf)
        self.framework.observe(
            self.on.fiveg_nrf_relation_joined, self._on_fiveg_nrf_relation_joined
        )
        self.framework.observe(self.on.certificates_relation_joined, self._configure_nrf)
        self.framework.observe(self._certificates.on.certificate_available, self._configure_nrf)
        self.framework.observe(
            self.on.certificates_relation_broken, self._on_certificates_relation_broken
        )
        self.framework.observe(
            self._certificates.on.certificate_expiring, self._on_certificate_expiring
        )

    def ready_to_configure(self) -> bool:
        """Return whether all preconditions are met to proceed with configuration."""
        if not self._container.can_connect():
            return False
        for relation in [DATABASE_RELATION_NAME, "certificates"]:
            if not self._relation_created(relation):
                return False
        if not self._database_is_available():
            return False
        if not self._get_database_uri():
            return False
        if not self._container.exists(path=BASE_CONFIG_PATH) or not self._container.exists(
            path=CERTS_DIR_PATH
        ):
            return False
        if not _get_pod_ip():
            return False
        return True

    def _on_collect_unit_status(self, event: CollectStatusEvent):  # noqa C901
        """Check the unit status and set to Unit when CollectStatusEvent is fired.

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
        for relation in [DATABASE_RELATION_NAME, "certificates"]:
            if not self._relation_created(relation):
                event.add_status(BlockedStatus(f"Waiting for {relation} relation to be created"))
                logger.info("Waiting for %s relation to be created", relation)
                return
        if not self._database_is_available():
            event.add_status(WaitingStatus("Waiting for the database to be available"))
            logger.info("Waiting for the database to be available")
            return
        if not self._get_database_uri():
            event.add_status(WaitingStatus("Waiting for database URI"))
            logger.info("Waiting for database URI")
            return
        if not self._container.exists(path=BASE_CONFIG_PATH) or not self._container.exists(
            path=CERTS_DIR_PATH
        ):
            event.add_status(WaitingStatus("Waiting for storage to be attached"))
            logger.info("Waiting for storage to be attached")
            return
        if not _get_pod_ip():
            event.add_status(WaitingStatus("Waiting for pod IP address to be available"))
            logger.info("Waiting for pod IP address to be available")
            return
        if self._csr_is_stored() and not self._get_current_provider_certificate():
            event.add_status(WaitingStatus("Waiting for certificates to be stored"))
            logger.info("Waiting for certificates to be stored")
            return
        if not self._nrf_service_is_running():
            event.add_status(WaitingStatus("Waiting for NRF service to start"))
            logger.info("Waiting for NRF service to start")
            return
        event.add_status(ActiveStatus())

    def _configure_nrf(self, event: EventBase) -> None:
        """Add pebble layer and manages Juju unit status.

        Args:
            event: Juju event
        """
        if not self.ready_to_configure():
            logger.info("The preconditions for the configuration are not met yet.")
            return
        if not self._private_key_is_stored():
            self._generate_private_key()
        if not self._csr_is_stored():
            self._request_new_certificate()
        provider_certificate = self._get_current_provider_certificate()
        if not provider_certificate:
            return
        if certificate_update_required := self._is_certificate_update_required(
            provider_certificate
        ):
            self._store_certificate(certificate=provider_certificate)
        desired_config_file = self._generate_nrf_config_file()
        if config_update_required := self._is_config_update_required(desired_config_file):
            self._push_config_file(content=desired_config_file)
        self._configure_workload(restart=(config_update_required or certificate_update_required))
        self._publish_nrf_info_for_all_requirers()

    def _on_certificates_relation_broken(self, event: RelationBrokenEvent) -> None:
        """Delete TLS related artifacts and reconfigures workload."""
        if not self._container.can_connect():
            event.defer()
            return
        self._delete_private_key()
        self._delete_csr()
        self._delete_certificate()

    def _on_certificate_expiring(self, event: CertificateExpiringEvent) -> None:
        """Request new certificate."""
        if not self._container.can_connect():
            event.defer()
            return
        if event.certificate != self._get_stored_certificate():
            logger.debug("Expiring certificate is not the one stored")
            return
        self._request_new_certificate()

    def _get_current_provider_certificate(self) -> str | None:
        """Compare the current certificate request to what is in the interface.

        Returns The current valid provider certificate if present
        """
        csr = self._get_stored_csr()
        for provider_certificate in self._certificates.get_assigned_certificates():
            if provider_certificate.csr == csr:
                return provider_certificate.certificate
        return None

    def _is_certificate_update_required(self, provider_certificate) -> bool:
        """Check the provided certificate and existing certificate.

        Returns True if update is required.

        Args:
            provider_certificate: str
        Returns:
            True if update is required else False
        """
        return self._get_existing_certificate() != provider_certificate

    def _get_existing_certificate(self) -> str:
        """Return the existing certificate if present else empty string."""
        return self._get_stored_certificate() if self._certificate_is_stored() else ""

    def _generate_private_key(self) -> None:
        """Generate and stores private key."""
        private_key = generate_private_key()
        self._store_private_key(private_key)

    def _request_new_certificate(self) -> None:
        """Generate and store CSR, and use it to request new certificate."""
        private_key = self._get_stored_private_key()
        csr = generate_csr(
            private_key=private_key,
            subject=CERTIFICATE_COMMON_NAME,
            sans_dns=[CERTIFICATE_COMMON_NAME],
        )
        self._store_csr(csr)
        self._certificates.request_certificate_creation(certificate_signing_request=csr)

    def _delete_private_key(self):
        """Remove private key from workload."""
        if not self._private_key_is_stored():
            return
        self._container.remove_path(path=f"{CERTS_DIR_PATH}/{PRIVATE_KEY_NAME}")
        logger.info("Removed private key from workload")

    def _delete_csr(self):
        """Delete CSR from workload."""
        if not self._csr_is_stored():
            return
        self._container.remove_path(path=f"{CERTS_DIR_PATH}/{CSR_NAME}")
        logger.info("Removed CSR from workload")

    def _delete_certificate(self):
        """Delete certificate from workload."""
        if not self._certificate_is_stored():
            return
        self._container.remove_path(path=f"{CERTS_DIR_PATH}/{CERTIFICATE_NAME}")
        logger.info("Removed certificate from workload")

    def _private_key_is_stored(self) -> bool:
        """Return whether private key is stored in workload."""
        return self._container.exists(path=f"{CERTS_DIR_PATH}/{PRIVATE_KEY_NAME}")

    def _csr_is_stored(self) -> bool:
        """Return whether CSR is stored in workload."""
        return self._container.exists(path=f"{CERTS_DIR_PATH}/{CSR_NAME}")

    def _get_stored_certificate(self) -> str:
        """Return stored certificate."""
        return str(self._container.pull(path=f"{CERTS_DIR_PATH}/{CERTIFICATE_NAME}").read())

    def _get_stored_csr(self) -> str:
        """Return stored CSR."""
        return str(self._container.pull(path=f"{CERTS_DIR_PATH}/{CSR_NAME}").read())

    def _get_stored_private_key(self) -> bytes:
        """Return stored private key."""
        return str(
            self._container.pull(path=f"{CERTS_DIR_PATH}/{PRIVATE_KEY_NAME}").read()
        ).encode()

    def _certificate_is_stored(self) -> bool:
        """Return whether certificate is stored in workload."""
        return self._container.exists(path=f"{CERTS_DIR_PATH}/{CERTIFICATE_NAME}")

    def _store_certificate(self, certificate: str) -> None:
        """Store certificate in workload."""
        self._container.push(path=f"{CERTS_DIR_PATH}/{CERTIFICATE_NAME}", source=certificate)
        logger.info("Pushed certificate to workload")

    def _store_private_key(self, private_key: bytes) -> None:
        """Store private key in workload."""
        self._container.push(
            path=f"{CERTS_DIR_PATH}/{PRIVATE_KEY_NAME}",
            source=private_key.decode(),
        )
        logger.info("Pushed private key to workload")

    def _store_csr(self, csr: bytes) -> None:
        """Store CSR in workload."""
        self._container.push(path=f"{CERTS_DIR_PATH}/{CSR_NAME}", source=csr.decode().strip())
        logger.info("Pushed CSR to workload")

    def _generate_nrf_config_file(self) -> str:
        """Handle creation of the NRF config file.

        Generate NRF config file based on a given template.

        Returns:
            content (str): desired config file content.
        """
        return _render_config(
            database_url=self._database_info()["uris"].split(",")[0],
            nrf_ip=_get_pod_ip(),  # type: ignore[arg-type]
            database_name=DATABASE_NAME,
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
        layer = self._pebble_layer
        if plan.services != layer.services or restart:
            self._container.add_layer("nrf", layer, combine=True)
            self._container.restart(self._service_name)

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
                        "command": f"/bin/nrf --nrfcfg {BASE_CONFIG_PATH}/{CONFIG_FILE_NAME}",  # noqa: E501
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

    @staticmethod
    def _get_nrf_url() -> str:
        """Return NRF URL."""
        return f"https://nrf:{NRF_SBI_PORT}"


if __name__ == "__main__":
    main(NRFOperatorCharm)
