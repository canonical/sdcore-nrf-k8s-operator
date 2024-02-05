# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

resource "juju_application" "sdcore-nrf-k8s" {
  name  = var.app_name
  model = var.model_name

  charm {
    name    = "sdcore-nrf-k8s"
    channel = var.channel
  }
  units = 1
  trust = true
}


