variable "project_id" {
  type        = string
  description = "GCP project that holds every Sarjy resource."
  default     = "sarjy-ahmed-2026"
}

variable "github_repository_id" {
  type        = string
  description = "Numeric ID of ahmedel-tawil/sarjy, the only repository allowed to deploy."
  default     = "1409336200"
}

variable "region" {
  type        = string
  description = "Region for every regional resource (D-44)."
  default     = "me-central1"
}

variable "llm_primary" {
  type        = string
  description = "Which chat provider answers first, groq or claude; the other is the fallback (D-63)."
  default     = "groq"

  validation {
    condition     = contains(["groq", "claude"], var.llm_primary)
    error_message = "llm_primary must be groq or claude."
  }
}
