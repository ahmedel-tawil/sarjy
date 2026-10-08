variable "project_id" {
  type        = string
  description = "GCP project that holds every Sarjy resource."
  default     = "sarjy-ahmed-2026"
}

variable "region" {
  type        = string
  description = "Region for every regional resource (D-44)."
  default     = "me-central1"
}
