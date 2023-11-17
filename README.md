# SD-Core NRF Operator (k8s)
[![CharmHub Badge](https://charmhub.io/sdcore-nrf/badge.svg)](https://charmhub.io/sdcore-nrf)

Charmed Operator for the SD-Core Network Repository Function (NRF).

# Usage

```bash
juju deploy sdcore-nrf --trust --channel=edge
juju deploy mongodb-k8s --trust --channel=5/edge
juju deploy self-signed-certificates --channel=beta

juju integrate sdcore-nrf:database mongodb-k8s
juju integrate self-signed-certificates:certificates sdcore-nrf:certificates
```

# Image

- **nrf**: `ghcr.io/canonical/sdcore-nrf:1.3`
