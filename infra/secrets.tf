# Terraform creates the secret, never its value: values are added by hand with
# `gcloud secrets versions add`, so they never appear in Terraform state.

resource "google_secret_manager_secret" "groq_api_key" {
  secret_id           = "groq-api-key"
  deletion_protection = true

  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }
}

resource "google_secret_manager_secret_iam_member" "gateway_reads_groq_api_key" {
  secret_id = google_secret_manager_secret.groq_api_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = google_service_account.gateway.member
}

# Created by hand on 9 Oct so the key could be stored straight away; this block brings it
# under Terraform. It can go once the first apply has imported it.
import {
  to = google_secret_manager_secret.anthropic_api_key
  id = "projects/${var.project_id}/secrets/anthropic-api-key"
}

resource "google_secret_manager_secret" "anthropic_api_key" {
  secret_id           = "anthropic-api-key"
  deletion_protection = true

  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }
}

resource "google_secret_manager_secret_iam_member" "gateway_reads_anthropic_api_key" {
  secret_id = google_secret_manager_secret.anthropic_api_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = google_service_account.gateway.member
}
