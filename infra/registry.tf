resource "google_artifact_registry_repository" "images" {
  repository_id = "sarjy"
  location      = var.region
  format        = "DOCKER"
  description   = "Container images for the Sarjy services, pushed by CI."

  lifecycle {
    prevent_destroy = true
  }
}
