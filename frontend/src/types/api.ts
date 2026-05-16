export interface ApiErrorEnvelope {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
  request_id: string;
}

export interface BootstrapRequest {
  timezone?: string;
}

export interface VisitMetadataUpdateRequest {
  gpsConsent?: boolean;
  gpsLat?: number;
  gpsLng?: number;
}

export interface BootstrapResponse {
  clsid: string;
  callback_url: string;
  viewer_url: string;
  expires_at: string;
  new_session: boolean;
}

export interface InboxEventSummary {
  request_id: string;
  received_at: string;
  method: string;
  content_type: string | null;
  payload_yaml: string;
  source_ip_masked: string;
}

export interface InboxEventDetail {
  request_id: string;
  received_at: string;
  method: string;
  content_type: string | null;
  headers: Record<string, string>;
  payload_yaml: string;
  source_ip_masked: string;
  payload_size_bytes: number;
}

export interface InboxMetadata {
  inbox_issued_at: string;
  expires_at: string;
  capture_count: number;
}

export interface InboxResponse {
  hook_url: string;
  events: InboxEventSummary[];
  next_token: string | null;
  metadata: InboxMetadata;
}