export enum ProjectStatus {
  REGISTERED = 'registered',
  SCANNING = 'scanning',
  READY = 'ready',
  ERROR = 'error',
}

export interface Project {
  id: number
  name: string
  path: string
  git_url: string | null
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
  path: string
  git_url?: string | null
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

export interface ScanResponse {
  exists: boolean
  is_git: boolean
  git_url: string | null
  git_branch: string | null
  python_env: PythonEnvInfo | null
  configs: ConfigFileInfo[]
  scripts: ScriptFiles
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
