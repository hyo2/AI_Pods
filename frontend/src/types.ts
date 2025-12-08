export interface ExistingSource {
  id: number;
  title: string;
  link_url?: string;
}

export interface OutputContent {
  id: number;
  title: string;
  status: "processing" | "completed" | "failed";
  created_at?: string;

  // 아래 필드는 processing 때는 없음 -> optional로 변경
  audio_url?: string;
  audio_path?: string;
  script_url?: string;
  script_path?: string;
  summary?: string;

  error_message?: string;
}
