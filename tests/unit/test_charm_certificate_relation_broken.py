# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.


import os
import tempfile

from ops import testing

from tests.unit.fixtures import NRFUnitTestFixtures


class TestCharmCertificateRelationBroken(NRFUnitTestFixtures):
    def test_given_container_when_certificates_relation_broken_then_certificate_deleted(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            certificates_relation = testing.Relation(
                endpoint="certificates",
                interface="tls-certificates",
            )
            certs_mount = testing.Mount(
                location="/support/TLS",
                source=temp_dir,
            )
            container = testing.Container(
                name="nrf",
                can_connect=True,
                mounts={"certs": certs_mount},
            )
            state_in = testing.State(
                containers=[container],
                relations=[certificates_relation],
                leader=True,
            )
            with open(f"{temp_dir}/nrf.pem", "w") as cert_file:
                cert_file.write("cert")
            with open(f"{temp_dir}/nrf.key", "w") as key_file:
                key_file.write("key")

            self.ctx.run(self.ctx.on.relation_broken(certificates_relation), state_in)

            assert not os.path.exists(f"{temp_dir}/nrf.pem")
            assert not os.path.exists(f"{temp_dir}/nrf.key")
