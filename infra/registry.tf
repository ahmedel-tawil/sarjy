resource "google_artifact_registry_repository" "images" {
  repository_id = "sarjy"
  location      = var.region
  format        = "DOCKER"
  description   = "Container images for the Sarjy services, pushed by CI."

  # Keep the five newest versions of each image, enough to roll back a few deploys, and
  # delete the rest; a keep rule wins over a delete rule (D-73). Google applies the
  # policies about once a day.
  cleanup_policy_dry_run = false
  cleanup_policies {
    id     = "keep-five-newest"
    action = "KEEP"
    most_recent_versions {
      keep_count = 5
    }
  }
  cleanup_policies {
    id     = "delete-the-rest"
    action = "DELETE"
    condition {
      tag_state = "ANY"
    }
  }

  lifecycle {
    prevent_destroy = true
  }
}
