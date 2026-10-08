terraform {
  required_version = ">= 1.15"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 8.6"
    }
  }

  # Created by hand before the first `terraform init` (see docs/TASKS.md, M1.2).
  backend "gcs" {
    bucket = "sarjy-ahmed-2026-tfstate"
    prefix = "sarjy"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}
