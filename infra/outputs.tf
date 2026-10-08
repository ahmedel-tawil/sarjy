output "gateway_url" {
  description = "Public HTTPS URL of the gateway."
  value       = google_cloud_run_v2_service.gateway.uri
}

output "tts_url" {
  description = "URL of the TTS service; callable only with the gateway's identity."
  value       = google_cloud_run_v2_service.tts.uri
}

output "image_repository" {
  description = "Artifact Registry path that CI pushes images to."
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.images.repository_id}"
}
