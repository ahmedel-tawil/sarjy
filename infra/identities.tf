# One runtime identity per service, so each gets only the permissions it needs.

resource "google_service_account" "gateway" {
  account_id   = "sarjy-gateway"
  display_name = "Sarjy gateway (Cloud Run runtime)"
}

resource "google_service_account" "tts" {
  account_id   = "sarjy-tts"
  display_name = "Sarjy TTS (Cloud Run runtime)"
}
