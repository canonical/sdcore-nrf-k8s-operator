# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

output "app_name" {
  description = "Name of the deployed application."
  value       = juju_application.sdcore-nrf-k8s.name
}


output "requires" {
  value = {
    database      = "database"
    certificates  = "certificates"
    sdcore_config = "sdcore_config"
    logging       = "logging"
  }
}

output "provides" {
  value = {
    fiveg_nrf = "fiveg_nrf"
    metrics   = "metrics-endpoint"
  }
}
