export type FrontendTaskStatus =
  | "queued"
  | "static_analyzing"
  | "dynamic_analyzing"
  | "report_generating"
  | "completed"
  | "static_failed"
  | "dynamic_failed";
export type FrontendStageRunStatus = "success" | "failed" | "running";

export type BackendTaskStatus =
  | "queued"
  | "static_analyzing"
  | "dynamic_analyzing"
  | "report_generating"
  | "completed"
  | "static_failed"
  | "dynamic_failed";

export type FrontendRiskLevel = "high" | "medium" | "low" | "safe" | "unknown";

export type BackendRiskLevel =
  | FrontendRiskLevel
  | "HIGH"
  | "MEDIUM"
  | "LOW"
  | "SAFE"
  | "UNKNOWN";

export interface Pagination {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  has_next: boolean;
  has_prev: boolean;
}

export interface FrontendTaskListItem {
  id: string;
  app_name: string | null;
  package_name: string | null;
  apk_file_name: string;
  apk_file_size: number | null;
  apk_md5: string | null;
  status: BackendTaskStatus | string;
  risk_level: BackendRiskLevel | string | null;
  submitter: string | null;
  icon_url: string | null;
  retryable: boolean;
  deletable: boolean;
  failure_reason: string | null;
  created_at: string;
  completed_at: string | null;
  report_ready: boolean;
  report_url: string | null;
}

export interface FrontendTaskDeleteResponse {
  id: string;
  deleted: boolean;
}

export interface FrontendTaskListResponse {
  items: FrontendTaskListItem[];
  pagination: Pagination;
}

export interface FrontendTaskListQuery {
  page?: number;
  page_size?: number;
  search?: string;
  status?: string;
  risk_level?: string;
  report_ready?: boolean;
}

export interface FrontendUploadRejectedFile {
  file_name: string;
  reason: string;
}

export interface FrontendTaskUploadResponse {
  accepted_files: string[];
  rejected_files: FrontendUploadRejectedFile[];
  created_tasks: FrontendTaskListItem[];
  extracted_apk_count: number;
  message: string;
}

export interface FrontendUploadProgress {
  loaded: number;
  total: number | null;
  percent: number | null;
  bytesPerSecond: number | null;
  etaSeconds: number | null;
  phase: "uploading" | "processing";
}

export interface FrontendRuntimeStatusSlot {
  slot_name: string;
  container_name: string;
  healthy: boolean;
  busy: boolean;
  holder_task_id: string | null;
  detail: string | null;
}

export interface FrontendRuntimeStatus {
  api_healthy: boolean;
  worker_ready: boolean;
  queue_backend: string;
  tasks: {
    queued_count: number;
    static_running_count: number;
    dynamic_running_count: number;
    report_running_count: number;
    running_count: number;
  };
  redroid: {
    configured_slots: number;
    healthy_slots: number;
    busy_slots: number;
    slots: FrontendRuntimeStatusSlot[];
  };
  checked_at: string;
}

export interface FrontendTaskDetailTask {
  id: string;
  app_name: string;
  package_name: string | null;
  apk_file_name: string;
  apk_file_size: number;
  apk_md5: string;
  status: BackendTaskStatus | string;
  risk_level: BackendRiskLevel | string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  retry_count: number;
}

export interface FrontendStageSummaryItem {
  stage: string;
  runs: number;
  success_runs: number;
  failed_runs: number;
  latest_status: string;
  total_duration_seconds: number;
}

export interface FrontendEvidenceSummary {
  runs_count: number;
  domains_count: number;
  ips_count: number;
  observation_hits: number;
  network_requests_count: number;
  screenshots_count: number;
  source_breakdown: Record<string, number>;
  capture_mode: string | null;
}

export interface FrontendRunPreviewItem {
  id: string;
  stage: string;
  attempt: number;
  status: string;
  worker_name: string | null;
  emulator: string | null;
  started_at: string | null;
  completed_at: string | null;
  duration_seconds: number;
  error_message: string | null;
}

export interface FrontendDomainPreviewItem {
  domain: string | null;
  ip: string | null;
  score: number;
  confidence: string | null;
  hit_count: number;
  request_count: number;
  post_count: number;
  unique_ip_count: number;
  source_types: string[];
  first_seen_at: string | null;
  last_seen_at: string | null;
}

export interface FrontendIpStatsPreviewItem {
  ip: string;
  hit_count: number;
  domain_count: number;
  primary_domain: string | null;
  source_types: string[];
  first_seen_at: string | null;
  last_seen_at: string | null;
}

export interface FrontendObservationPreviewItem {
  id: string;
  domain: string | null;
  host: string | null;
  ip: string | null;
  port?: number | null;
  source_type: string;
  transport: string;
  protocol: string;
  hit_count: number;
  first_seen_at: string | null;
  last_seen_at: string | null;
  capture_mode?: string | null;
  attribution_tier?: string | null;
}

export interface FrontendScreenshotPreviewItem {
  id: string;
  image_url: string | null;
  storage_path: string | null;
  file_size: number;
  stage: string | null;
  description: string | null;
  captured_at: string | null;
}

export interface FrontendTaskDetailError {
  source: string;
  stage: string | null;
  message: string;
}

export interface FrontendStaticInfo {
  app_name: string | null;
  package_name: string | null;
  version_name: string | null;
  version_code: number | null;
  min_sdk: number | null;
  target_sdk: number | null;
  apk_file_size: number | null;
  apk_md5: string | null;
  declared_permissions: string[];
  icon_url: string | null;
}

export interface FrontendPermissionSummary {
  requested_permissions: string[];
  granted_permissions: string[];
  failed_permissions: string[];
}

export interface FrontendPermissionDetail {
  code: string;
  description_en: string | null;
  description_zh: string | null;
  source_url?: string | null;
}

export interface FrontendTaskDetailResponse {
  task: FrontendTaskDetailTask;
  static_info: FrontendStaticInfo;
  permission_summary: FrontendPermissionSummary;
  permission_details?: Record<string, FrontendPermissionDetail>;
  stage_summary: FrontendStageSummaryItem[];
  evidence_summary: FrontendEvidenceSummary;
  runs_preview: FrontendRunPreviewItem[];
  domains_preview: FrontendDomainPreviewItem[];
  ip_stats_preview: FrontendIpStatsPreviewItem[];
  observations_preview: FrontendObservationPreviewItem[];
  screenshots_preview: FrontendScreenshotPreviewItem[];
  errors: FrontendTaskDetailError[];
  retryable: boolean;
  report_ready: boolean;
  report_url: string | null;
}

export interface FrontendReportTask {
  id: string;
  app_name: string;
  package_name: string | null;
  apk_file_name: string;
  apk_file_size: number;
  apk_md5: string;
  status: BackendTaskStatus | string;
  risk_level: BackendRiskLevel | string | null;
  created_at: string | null;
  completed_at: string | null;
}

export interface FrontendReportSummary {
  risk_level: BackendRiskLevel | string | null;
  risk_label: string;
  conclusion: string;
  highlights: string[];
}

export interface FrontendReportEvidenceSummary {
  domains_count: number;
  ips_count: number;
  observation_hits: number;
  source_breakdown: Record<string, number>;
  capture_mode: string | null;
  screenshots_count: number;
}

export interface FrontendReportDomainItem {
  id: string;
  domain: string | null;
  ip: string | null;
  score: number;
  confidence: string | null;
  hit_count: number;
  request_count: number;
  post_count: number;
  unique_ip_count: number;
  source_types: string[];
  first_seen_at: string | null;
  last_seen_at: string | null;
}

export interface FrontendReportIpItem {
  ip: string;
  hit_count: number;
  domain_count: number;
  primary_domain: string | null;
  source_types: string[];
  first_seen_at: string | null;
  last_seen_at: string | null;
}

export interface FrontendReportTimelineItem {
  id: string;
  domain: string | null;
  host: string | null;
  ip: string | null;
  port?: number | null;
  source_type: string;
  transport: string;
  protocol: string;
  hit_count: number;
  first_seen_at: string | null;
  last_seen_at: string | null;
  capture_mode?: string | null;
  attribution_tier?: string | null;
}

export interface FrontendReportScreenshotItem {
  id: string;
  image_url: string | null;
  file_size: number;
  stage: string | null;
  description: string | null;
  captured_at: string | null;
}

export interface FrontendReportResponse {
  task: FrontendReportTask;
  static_info: FrontendStaticInfo;
  permission_summary: FrontendPermissionSummary;
  permission_details?: Record<string, FrontendPermissionDetail>;
  summary: FrontendReportSummary;
  evidence_summary: FrontendReportEvidenceSummary;
  top_domains: FrontendReportDomainItem[];
  top_ips: FrontendReportIpItem[];
  timeline: FrontendReportTimelineItem[];
  screenshots: FrontendReportScreenshotItem[];
  download_url: string | null;
}
