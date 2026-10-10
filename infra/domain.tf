# The gateway on its own domain over HTTPS (M4.7, D-101). Cloud Run can't map a domain in
# me-central1 (D-44), so a global external Application Load Balancer sits in front of the
# same service, with a Google-managed certificate. The run.app URL keeps working.

resource "google_compute_global_address" "gateway" {
  name = "gateway"
}

# Points the load balancer at the Cloud Run service, whichever revision is serving.
resource "google_compute_region_network_endpoint_group" "gateway" {
  name                  = "gateway"
  region                = var.region
  network_endpoint_type = "SERVERLESS"

  cloud_run {
    service = google_cloud_run_v2_service.gateway.name
  }
}

# No timeout here: a serverless backend takes Cloud Run's own request timeout, 3600 s,
# which is how long one visit's WebSocket may stay open.
resource "google_compute_backend_service" "gateway" {
  name                  = "gateway"
  load_balancing_scheme = "EXTERNAL_MANAGED"

  backend {
    group = google_compute_region_network_endpoint_group.gateway.id
  }
}

resource "google_compute_url_map" "gateway" {
  name            = "gateway"
  default_service = google_compute_backend_service.gateway.id
}

# Issued once the domain's A record points at the address above; usually within an hour.
resource "google_compute_managed_ssl_certificate" "gateway" {
  name = "gateway"

  managed {
    domains = [var.custom_domain]
  }
}

resource "google_compute_target_https_proxy" "gateway" {
  name             = "gateway"
  url_map          = google_compute_url_map.gateway.id
  ssl_certificates = [google_compute_managed_ssl_certificate.gateway.id]
}

resource "google_compute_global_forwarding_rule" "gateway_https" {
  name                  = "gateway-https"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  ip_address            = google_compute_global_address.gateway.id
  port_range            = "443"
  target                = google_compute_target_https_proxy.gateway.id
}

# Plain http:// on the domain redirects to https://, where the microphone is allowed.
resource "google_compute_url_map" "gateway_redirect" {
  name = "gateway-redirect"

  default_url_redirect {
    https_redirect = true
    strip_query    = false
  }
}

resource "google_compute_target_http_proxy" "gateway_redirect" {
  name    = "gateway-redirect"
  url_map = google_compute_url_map.gateway_redirect.id
}

resource "google_compute_global_forwarding_rule" "gateway_http" {
  name                  = "gateway-http"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  ip_address            = google_compute_global_address.gateway.id
  port_range            = "80"
  target                = google_compute_target_http_proxy.gateway_redirect.id
}
