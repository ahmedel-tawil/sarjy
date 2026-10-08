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
    }
  }

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

    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }

    containers {
      image = local.placeholder_image

      # A first guess for Kokoro on CPU; the Kokoro spike and M1.10 will size it.
      resources {
        limits = {
          cpu    = "2"
          memory = "2Gi"
        }
        startup_cpu_boost = true
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
