# Postgres for travellers' facts, sessions, turns and latency marks (M2.2, D-64).

resource "google_sql_database_instance" "main" {
  name                = "sarjy"
  region              = var.region
  database_version    = "POSTGRES_18"
  deletion_protection = true

  settings {
    # The smallest tier, shared-core, which only the Enterprise edition offers: Postgres
    # 16 and later default to Enterprise Plus.
    tier                        = "db-f1-micro"
    edition                     = "ENTERPRISE"
    availability_type           = "ZONAL"
    disk_size                   = 10
    deletion_protection_enabled = true

    ip_configuration {
      # Cloud Run's built-in Cloud SQL connection reaches the instance over its public
      # address through the Cloud SQL Auth Proxy, authorised by IAM. No networks are
      # authorised, so nothing else can connect.
      ipv4_enabled = true
      ssl_mode     = "ENCRYPTED_ONLY"
    }

    # A demo database of a few facts and timings: no backups, to keep the cost down.
    backup_configuration {
      enabled = false
    }
  }
}

resource "google_sql_database" "sarjy" {
  name     = "sarjy"
  instance = google_sql_database_instance.main.name

  # The instance has deletion protection; this keeps the database itself from a plan
  # that would drop it.
  lifecycle {
    prevent_destroy = true
  }
}

# The full connection URL, password included, added by hand after the database user is
# created, so the password never passes through Terraform.
resource "google_secret_manager_secret" "database_url" {
  secret_id           = "database-url"
  deletion_protection = true

  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }
}

resource "google_secret_manager_secret_iam_member" "gateway_reads_database_url" {
  secret_id = google_secret_manager_secret.database_url.id
  role      = "roles/secretmanager.secretAccessor"
  member    = google_service_account.gateway.member
}

# Lets the gateway's identity open connections through the Cloud SQL Auth Proxy.
resource "google_project_iam_member" "gateway_connects_to_sql" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = google_service_account.gateway.member
}
