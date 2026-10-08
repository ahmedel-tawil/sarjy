# GitHub Actions deploys without any stored key: GitHub's short-lived OIDC token for a
# push to this repository's main branch is exchanged for the deployer's credentials.

resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "github"
  display_name              = "GitHub Actions"
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "sarjy-main"
  display_name                       = "sarjy main branch"

  attribute_mapping = {
    "google.subject"          = "assertion.sub"
    "attribute.repository_id" = "assertion.repository_id"
    "attribute.ref"           = "assertion.ref"
  }
  # The numeric ID, not the name, so a repository later created under the same name
  # cannot deploy.
  attribute_condition = "assertion.repository_id == '${var.github_repository_id}' && assertion.ref == 'refs/heads/main'"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account" "deployer" {
  account_id   = "sarjy-deployer"
  display_name = "Sarjy CI deployer (GitHub Actions)"
}

resource "google_service_account_iam_member" "github_acts_as_deployer" {
  service_account_id = google_service_account.deployer.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository_id/${var.github_repository_id}"
}

resource "google_artifact_registry_repository_iam_member" "deployer_pushes_images" {
  repository = google_artifact_registry_repository.images.name
  location   = google_artifact_registry_repository.images.location
  role       = "roles/artifactregistry.writer"
  member     = google_service_account.deployer.member
}

resource "google_cloud_run_v2_service_iam_member" "deployer_updates_gateway" {
  name     = google_cloud_run_v2_service.gateway.name
  location = google_cloud_run_v2_service.gateway.location
  role     = "roles/run.developer"
  member   = google_service_account.deployer.member
}

resource "google_cloud_run_v2_service_iam_member" "deployer_updates_tts" {
  name     = google_cloud_run_v2_service.tts.name
  location = google_cloud_run_v2_service.tts.location
  role     = "roles/run.developer"
  member   = google_service_account.deployer.member
}

# Deploying a revision that runs as a service account requires permission to act as it.
resource "google_service_account_iam_member" "deployer_acts_as_gateway" {
  service_account_id = google_service_account.gateway.name
  role               = "roles/iam.serviceAccountUser"
  member             = google_service_account.deployer.member
}

resource "google_service_account_iam_member" "deployer_acts_as_tts" {
  service_account_id = google_service_account.tts.name
  role               = "roles/iam.serviceAccountUser"
  member             = google_service_account.deployer.member
}
