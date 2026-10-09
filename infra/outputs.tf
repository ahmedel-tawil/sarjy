output "gateway_url" {
  description = "Public HTTPS URL of the gateway."
  value       = google_cloud_run_v2_service.gateway.uri
}

output "tts_url" {
  description = "URL of the TTS service; callable only with the gateway's identity."
  value       = google_cloud_run_v2_service.tts.uri
}

output "workload_identity_provider" {
  description = "Full provider name for google-github-actions/auth (a GitHub repo variable)."
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "deployer_service_account" {
  description = "Service account CI deploys as (a GitHub repo variable)."
  value       = google_service_account.deployer.email
}

output "image_repository" {
  description = "Artifact Registry path that CI pushes images to."
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.images.repository_id}"
}

output "database_connection_name" {
  description = "The Cloud SQL instance, as the gateway's socket path and gcloud name it."
  value       = google_sql_database_instance.main.connection_name
}
