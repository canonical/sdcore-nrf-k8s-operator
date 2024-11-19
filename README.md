# Aether SD-Core NRF Operator (k8s)
[![CharmHub Badge](https://charmhub.io/sdcore-nrf-k8s/badge.svg)](https://charmhub.io/sdcore-nrf-k8s)

Charmed Operator for the Aether SD-Core Network Repository Function (NRF) for K8s.

# Usage

```bash
juju deploy sdcore-nrf-k8s --channel=1.5/edge
juju deploy mongodb-k8s --trust --channel=6/beta
juju deploy sdcore-nms-k8s --channel=1.5/edge
juju deploy self-signed-certificates

juju integrate sdcore-nms-k8s:common_database mongodb-k8s:database
juju integrate sdcore-nms-k8s:auth_database mongodb-k8s:database
juju integrate sdcore-nms-k8s:certificates self-signed-certificates:certificates
juju integrate sdcore-nrf-k8s:database mongodb-k8s
juju integrate sdcore-nrf-k8s:sdcore_config sdcore-nms-k8s:sdcore_config
juju integrate sdcore-nrf-k8s:certificates self-signed-certificates:certificates
```

# Image

- **nrf**: `ghcr.io/canonical/sdcore-nrf:1.5.2`

