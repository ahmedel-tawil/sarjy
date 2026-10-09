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
  description = "Which chat provider answers first, groq or claude; the other is the fallback (D-63, D-69)."
  default     = "claude"

  validation {
    condition     = contains(["groq", "claude"], var.llm_primary)
    error_message = "llm_primary must be groq or claude."
  }
}

variable "pipeline_mode" {
  type        = string
  description = "How the gateway speaks a reply: sentence (each sentence as soon as it is written) or baseline (the whole reply at once) (D-77)."
  default     = "sentence"

  validation {
    condition     = contains(["baseline", "sentence"], var.pipeline_mode)
    error_message = "pipeline_mode must be baseline or sentence."
  }
}

variable "gateway_min_instances" {
  type        = number
  description = "Gateway instances kept warm: 1 for the review week (about $0.45 a day idle), 0 otherwise (D-78)."
  default     = 0

  validation {
    condition     = contains([0, 1], var.gateway_min_instances)
    error_message = "gateway_min_instances must be 0 or 1."
  }
}

variable "tts_min_instances" {
  type        = number
  description = "TTS instances kept warm: 1 for the review week (about $3.60 a day idle), 0 otherwise (D-78)."
  default     = 0

  validation {
    condition     = contains([0, 1], var.tts_min_instances)
    error_message = "tts_min_instances must be 0 or 1."
  }
}
