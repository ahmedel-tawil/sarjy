locals {
  # Google's sample container; CI replaces it with our images (M1.5, M1.10).
  placeholder_image = "us-docker.pkg.dev/cloudrun/container/hello"
}

resource "google_cloud_run_v2_service" "gateway" {
  name     = "gateway"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.gateway.email
    # A WebSocket session is one long request, so allow the 60-minute maximum.
    timeout = "3600s"

    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }

    containers {
      image = local.placeholder_image

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
        startup_cpu_boost = true
      }

      env {
        name  = "SARJY_TTS_URL"
        value = google_cloud_run_v2_service.tts.uri
      }

      # TTS is private, so each call carries a token for the gateway's identity (D-45).
      env {
        name  = "SARJY_TTS_AUTH"
        value = "id_token"
      }

      # Cloud Run reads the value from Secret Manager when an instance starts, so it never
      # passes through Terraform. "latest" picks up a rotated key on the next revision.
      env {
        name = "SARJY_GROQ_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.groq_api_key.secret_id
            version = "latest"
          }
        }
      }

      # The OpenAI-compatible chat provider, Groq; the same secret as speech to text.
      env {
        name = "SARJY_LLM_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.groq_api_key.secret_id
            version = "latest"
          }
        }
      }

      # Claude, the second chat provider. var.llm_primary says which of the two answers
      # first; the other steps in when it fails before answering (D-63).
      env {
        name = "SARJY_ANTHROPIC_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.anthropic_api_key.secret_id
            version = "latest"
          }
        }
      }
      env {
        name  = "SARJY_LLM_PRIMARY"
        value = var.llm_primary
      }
    }
  }

  # The gateway's identity must be able to read the secrets before a revision uses them.
  depends_on = [
    google_secret_manager_secret_iam_member.gateway_reads_groq_api_key,
    google_secret_manager_secret_iam_member.gateway_reads_anthropic_api_key,
  ]

  lifecycle {
    # CI deploys new images; Terraform owns everything else about the service.
    ignore_changes = [template[0].containers[0].image, client, client_version]
  }
}

resource "google_cloud_run_v2_service_iam_member" "gateway_is_public" {
  name     = google_cloud_run_v2_service.gateway.name
  location = google_cloud_run_v2_service.gateway.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_v2_service" "tts" {
  name     = "tts"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.tts.email
    # Synthesis is CPU-bound: past a few at once, requests only slow each other down,
    # so Cloud Run starts another instance instead.
    max_instance_request_concurrency = 4

    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }

    containers {
      image = local.placeholder_image

      # The 325 MB model and onnxruntime's working memory fit in 2 GiB; M1.10 measures
      # synthesis time on 2 vCPU.
      resources {
        limits = {
          cpu    = "2"
          memory = "2Gi"
        }
        startup_cpu_boost = true
      }

      # Match onnxruntime's threads to the vCPUs we pay for, not the host's cores.
      env {
        name  = "SARJY_THREADS"
        value = "2"
      }
    }
  }

  lifecycle {
    ignore_changes = [template[0].containers[0].image, client, client_version]
  }
}

# No allUsers binding: only the gateway's identity may call TTS (O-09).
resource "google_cloud_run_v2_service_iam_member" "gateway_calls_tts" {
  name     = google_cloud_run_v2_service.tts.name
  location = google_cloud_run_v2_service.tts.location
  role     = "roles/run.invoker"
  member   = google_service_account.gateway.member
}
