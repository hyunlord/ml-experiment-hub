export enum ProjectStatus {
  REGISTERED = 'registered',
  CLONING = 'cloning',
  SCANNING = 'scanning',
  READY = 'ready',
  ERROR = 'error',
}

export interface Project {
  id: number
  name: string
  source_type: string
  path: string
  git_url: string | null
  git_branch: string | null
  git_token_id: number | null
  template_type: string | null
  template_task: string | null
  template_model: string | null
  description: string
  project_type: string
  train_command_template: string
  eval_command_template: string | null
  config_dir: string
  config_format: string
  checkpoint_dir: string
  python_env: string
  env_path: string | null
  status: ProjectStatus
  detected_configs: ConfigFileInfo[]
  detected_scripts: ScriptFiles
  tags: string[]
  created_at: string
  updated_at: string
  experiment_count: number
}

export interface ProjectCreate {
  name: string
  source_type?: string
  path: string
  git_url?: string | null
  git_branch?: string | null
  git_token_id?: number | null
  template_type?: string | null
  template_task?: string | null
  template_model?: string | null
  description?: string
  project_type?: string
  train_command_template?: string
  eval_command_template?: string | null
  config_dir?: string
  config_format?: string
  checkpoint_dir?: string
  python_env?: string
  env_path?: string | null
  detected_configs?: ConfigFileInfo[]
  detected_scripts?: ScriptFiles
  tags?: string[]
}

export interface ProjectUpdate {
  name?: string
  description?: string
  project_type?: string
  train_command_template?: string
  eval_command_template?: string | null
  config_dir?: string
  config_format?: string
  checkpoint_dir?: string
  python_env?: string
  env_path?: string | null
  tags?: string[]
}

export interface ProjectListResponse {
  projects: Project[]
  total: number
}

export interface ConfigFileInfo {
  path: string
  format: string
  size: number
}

export interface ScriptFiles {
  train: string[]
  eval: string[]
  other: string[]
}

export interface PythonEnvInfo {
  type: string
  indicator: string
  venv_exists: boolean
  venv_path: string | null
}

export interface GitLastCommit {
  hash: string | null
  message: string | null
  date: string | null
}

export interface StructureInfo {
  has_src: boolean
  has_tests: boolean
  has_docker: boolean
  main_dirs: string[]
}

export interface ScanResponse {
  exists: boolean
  is_git: boolean
  git_url: string | null
  git_branch: string | null
  git_last_commit: GitLastCommit | null
  python_env: PythonEnvInfo | null
  configs: ConfigFileInfo[]
  scripts: ScriptFiles
  structure: StructureInfo | null
  requirements: string[]
  suggested_train_command: string | null
  suggested_eval_command: string | null
}

export interface GitInfo {
  branch: string | null
  remote_url: string | null
  last_commit_hash: string | null
  last_commit_message: string | null
  last_commit_date: string | null
  dirty: boolean
}

export interface ConfigContent {
  path: string
  content: string
  format: string
}

// Clone types
export interface CloneRequest {
  git_url: string
  branch?: string
  token_id?: number | null
  subdirectory?: string
}

export interface CloneStatusResponse {
  job_id: string
  status: string
  progress: string | null
  local_path: string | null
  scan_result: ScanResponse | null
  error: string | null
}

// Filesystem browse types
export interface FileBrowseEntry {
  name: string
  type: 'dir' | 'file'
  size: number
  modified: string | null
}

export interface FileBrowseResponse {
  path: string
  entries: FileBrowseEntry[]
}

// Upload types
export interface UploadResponse {
  local_path: string
  files_saved: string[]
  scan_result: ScanResponse | null
}

// Git credential types
export interface GitCredentialCreate {
  name: string
  provider?: string
  token: string
}

export interface GitCredentialResponse {
  id: number
  name: string
  provider: string
  token_masked: string
  created_at: string
}

export interface GitCredentialListResponse {
  credentials: GitCredentialResponse[]
}

// Template types
export interface TemplateTask {
  id: string
  name: string
  description: string
}

export interface TemplateInfo {
  id: string
  framework: string
  name: string
  description: string
  tasks: TemplateTask[]
}

export interface TemplateConfigSchema {
  template_id: string
  task_id: string | null
  fields: Record<string, unknown>
}

// Config parsing types
export interface ParsedConfigValue {
  value: unknown
  type: 'string' | 'integer' | 'float' | 'boolean' | 'array' | 'object'
}

export interface ParsedConfigResponse {
  raw_yaml: string
  parsed: Record<string, Record<string, ParsedConfigValue>>
  groups: string[]
}
