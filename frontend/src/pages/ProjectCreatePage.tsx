import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FolderOpen,
  GitBranch,
  Terminal,
  FileCode,
  ChevronRight,
  ChevronLeft,
  Check,
  X,
  Loader2,
  AlertCircle,
  RefreshCw,
  Upload,
  FileText,
  Github,
  HardDrive,
  Layers,
  UploadCloud,
} from 'lucide-react';
import {
  scanDirectory,
  createProject,
  cloneRepository,
  getCloneStatus,
  uploadProjectFiles,
} from '@/api/projects';
import { browseDirectory } from '@/api/filesystem';
import { getTemplates } from '@/api/templates';
import { getGitCredentials } from '@/api/gitCredentials';
import type {
  ScanResponse,
  ProjectCreate,
  ConfigFileInfo,
  CloneStatusResponse,
  FileBrowseResponse,
  TemplateInfo,
  GitCredentialResponse,
} from '@/types/project';

type SourceType = 'github' | 'local' | 'template' | 'upload';

type FormData = {
  name: string;
  path: string;
  description: string;
  tags: string;
  train_command: string;
  eval_command: string;
  config_dir: string;
  config_format: string;
  checkpoint_dir: string;
  python_env: string;
  env_path: string;
  project_type: string;
  // GitHub specific
  git_url: string;
  git_branch: string;
  git_token_id: number | null;
  git_subdirectory: string;
  // Template specific
  template_id: string;
  template_task_id: string;
  template_model_name: string;
  template_batch_size: string;
  template_lr: string;
  template_epochs: string;
  template_optimizer: string;
};

export default function ProjectCreatePage() {
  const navigate = useNavigate();
  const [sourceType, setSourceType] = useState<SourceType>('local');
  const [step, setStep] = useState(1);
  const [formData, setFormData] = useState<FormData>({
    name: '',
    path: '',
    description: '',
    tags: '',
    train_command: '',
    eval_command: '',
    config_dir: '',
    config_format: 'yaml',
    checkpoint_dir: '',
    python_env: 'system',
    env_path: '',
    project_type: 'custom',
    git_url: '',
    git_branch: 'main',
    git_token_id: null,
    git_subdirectory: '',
    template_id: '',
    template_task_id: '',
    template_model_name: '',
    template_batch_size: '32',
    template_lr: '0.001',
    template_epochs: '10',
    template_optimizer: 'adam',
  });

  const [scanResults, setScanResults] = useState<ScanResponse | null>(null);
  const [scanning, setScanning] = useState(false);
  const [scanError, setScanError] = useState<string | null>(null);
  const [pathDebounceTimer, setPathDebounceTimer] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // GitHub specific state
  const [cloning, setCloning] = useState(false);
  const [cloneJobId, setCloneJobId] = useState<string | null>(null);
  const [cloneStatus, setCloneStatus] = useState<CloneStatusResponse | null>(null);
  const [gitCredentials, setGitCredentials] = useState<GitCredentialResponse[]>([]);
  const [privateRepo, setPrivateRepo] = useState(false);

  // Template specific state
  const [templates, setTemplates] = useState<TemplateInfo[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<TemplateInfo | null>(null);

  // Upload specific state
  const [uploadFiles, setUploadFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);

  // Directory browser state
  const [showBrowser, setShowBrowser] = useState(false);
  const [browserData, setBrowserData] = useState<FileBrowseResponse | null>(null);
  const [browsingDir, setBrowsingDir] = useState(false);

  // Load git credentials when GitHub tab is selected
  useEffect(() => {
    if (sourceType === 'github') {
      loadGitCredentials();
    }
  }, [sourceType]);

  // Load templates when template tab is selected
  useEffect(() => {
    if (sourceType === 'template') {
      loadTemplates();
    }
  }, [sourceType]);

  // Auto-scan for local path
  useEffect(() => {
    if (sourceType !== 'local') return;

    if (pathDebounceTimer) {
      clearTimeout(pathDebounceTimer);
    }

    if (formData.path.trim()) {
      const timer = setTimeout(() => {
        handleScanDirectory(formData.path.trim());
      }, 500);
      setPathDebounceTimer(timer);
    } else {
      setScanResults(null);
      setScanError(null);
    }

    return () => {
      if (pathDebounceTimer) {
        clearTimeout(pathDebounceTimer);
      }
    };
  }, [formData.path, sourceType]);

  // Poll clone status (with retry limit and timeout)
  useEffect(() => {
    if (!cloneJobId || !cloning) return;

    let errorCount = 0;
    const maxErrors = 3;
    const maxPollDuration = 5 * 60 * 1000; // 5 minutes
    const startTime = Date.now();

    const interval = setInterval(async () => {
      // Timeout guard
      if (Date.now() - startTime > maxPollDuration) {
        clearInterval(interval);
        setCloning(false);
        setScanError('Clone timed out after 5 minutes. Please try again.');
        return;
      }

      try {
        const status = await getCloneStatus(cloneJobId);
        errorCount = 0; // Reset on success
        setCloneStatus(status);

        if (status.status === 'completed') {
          setCloning(false);
          if (status.scan_result) {
            setScanResults(status.scan_result);
            // Pre-fill form from scan
            setFormData((prev) => ({
              ...prev,
              name: prev.name || extractRepoName(formData.git_url),
              path: status.local_path || prev.path,
              train_command: status.scan_result?.suggested_train_command || prev.train_command,
              eval_command: status.scan_result?.suggested_eval_command || prev.eval_command,
              python_env: status.scan_result?.python_env?.type || prev.python_env,
              env_path: status.scan_result?.python_env?.venv_path || prev.env_path,
            }));
          }
        } else if (status.status === 'failed') {
          setCloning(false);
          setScanError(status.error || 'Clone failed');
        }
      } catch (error) {
        errorCount++;
        console.error(`Clone poll error (${errorCount}/${maxErrors}):`, error);
        if (errorCount >= maxErrors) {
          clearInterval(interval);
          setCloning(false);
          setScanError('Clone job not found. The server may have restarted. Please try again.');
        }
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [cloneJobId, cloning]);

  const loadGitCredentials = async () => {
    try {
      const response = await getGitCredentials();
      setGitCredentials(response.credentials);
    } catch (error) {
      console.error('Failed to load git credentials:', error);
    }
  };

  const loadTemplates = async () => {
    try {
      const data = await getTemplates();
      setTemplates(data);
    } catch (error) {
      console.error('Failed to load templates:', error);
    }
  };

  const handleScanDirectory = async (path: string) => {
    setScanning(true);
    setScanError(null);
    try {
      const results = await scanDirectory(path);
      setScanResults(results);

      setFormData((prev) => ({
        ...prev,
        train_command: results.suggested_train_command || prev.train_command,
        eval_command: results.suggested_eval_command || prev.eval_command,
        python_env: results.python_env?.type || prev.python_env,
        env_path: results.python_env?.venv_path || prev.env_path,
      }));
    } catch (error) {
      setScanError(error instanceof Error ? error.message : 'Failed to scan directory');
      setScanResults(null);
    } finally {
      setScanning(false);
    }
  };

  const handleCloneRepo = async () => {
    if (!formData.git_url.trim()) return;

    setCloning(true);
    setScanError(null);
    setCloneStatus(null);

    try {
      const response = await cloneRepository({
        git_url: formData.git_url.trim(),
        branch: formData.git_branch.trim() || undefined,
        token_id: privateRepo ? formData.git_token_id : null,
        subdirectory: formData.git_subdirectory.trim() || undefined,
      });

      setCloneJobId(response.job_id);
      setCloneStatus(response);
    } catch (error) {
      setCloning(false);
      setScanError(error instanceof Error ? error.message : 'Failed to start clone');
    }
  };

  const handleClearCloneError = () => {
    setCloneStatus(null);
    setScanError(null);
    setCloneJobId(null);
  };

  const handleUploadFiles = async () => {
    if (uploadFiles.length === 0 || !formData.name.trim()) return;

    setUploading(true);
    setScanError(null);

    try {
      const response = await uploadProjectFiles(uploadFiles, formData.name.trim());
      setScanResults(response.scan_result);
      setFormData((prev) => ({
        ...prev,
        path: response.local_path,
        train_command: response.scan_result?.suggested_train_command || prev.train_command,
        eval_command: response.scan_result?.suggested_eval_command || prev.eval_command,
        python_env: response.scan_result?.python_env?.type || prev.python_env,
        env_path: response.scan_result?.python_env?.venv_path || prev.env_path,
      }));
    } catch (error) {
      setScanError(error instanceof Error ? error.message : 'Failed to upload files');
    } finally {
      setUploading(false);
    }
  };

  const handleBrowseDirectory = async (path?: string) => {
    setBrowsingDir(true);
    try {
      const data = await browseDirectory(path);
      setBrowserData(data);
    } catch (error) {
      console.error('Failed to browse directory:', error);
    } finally {
      setBrowsingDir(false);
    }
  };

  const handleSelectDirectory = (path: string) => {
    setFormData((prev) => ({ ...prev, path }));
    setShowBrowser(false);
  };

  const handleInputChange = (field: keyof FormData, value: string | number | null) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const handleSourceTypeChange = (newType: SourceType) => {
    setSourceType(newType);
    setStep(1);
    setScanResults(null);
    setScanError(null);
    setCloneStatus(null);
    setUploadFiles([]);
  };

  const extractRepoName = (url: string): string => {
    try {
      // Remove trailing slashes and .git
      const cleaned = url.replace(/\/+$/, '').replace(/\.git$/, '');
      const parts = cleaned.split('/');
      return parts[parts.length - 1] || '';
    } catch {
      return '';
    }
  };

  const canProceedStep1 = () => {
    if (sourceType === 'github') {
      return formData.git_url.trim() && cloneStatus?.status === 'completed' && formData.name.trim().length > 0;
    }
    if (sourceType === 'local') {
      return formData.name.trim() && scanResults?.exists;
    }
    if (sourceType === 'template') {
      return formData.template_id.trim();
    }
    if (sourceType === 'upload') {
      return uploadFiles.length > 0 && formData.name.trim();
    }
    return false;
  };

  const getMaxSteps = (): number => {
    if (sourceType === 'template') return 4;
    return 3;
  };

  const handleNextStep = () => {
    const maxSteps = getMaxSteps();
    if (step < maxSteps) {
      setStep(step + 1);
    }
  };

  const handlePrevStep = () => {
    if (step > 1) {
      setStep(step - 1);
    }
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    setSubmitError(null);

    try {
      const projectData: ProjectCreate = {
        name: formData.name.trim(),
        source_type: sourceType,
        path: formData.path.trim(),
        description: formData.description.trim() || undefined,
        tags: formData.tags
          .split(',')
          .map((t) => t.trim())
          .filter(Boolean),
        train_command_template: formData.train_command.trim() || undefined,
        eval_command_template: formData.eval_command.trim() || undefined,
        config_dir: formData.config_dir.trim() || undefined,
        config_format: formData.config_format || undefined,
        checkpoint_dir: formData.checkpoint_dir.trim() || undefined,
        python_env: formData.python_env || undefined,
        env_path: formData.env_path.trim() || undefined,
        project_type: formData.project_type || undefined,
      };

      // Add source-specific fields
      if (sourceType === 'github') {
        projectData.git_url = formData.git_url.trim() || undefined;
        projectData.git_branch = formData.git_branch.trim() || undefined;
        projectData.git_token_id = formData.git_token_id || undefined;
      }

      if (sourceType === 'template') {
        projectData.template_type = formData.template_id || undefined;
        projectData.template_task = formData.template_task_id || undefined;
        projectData.template_model = formData.template_model_name.trim() || undefined;
      }

      const created = await createProject(projectData);
      navigate(`/projects/${created.id}`);
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : 'Failed to create project');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="container mx-auto max-w-4xl py-8 px-4">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-foreground mb-2">Register New Project</h1>
        <p className="text-muted-foreground">Set up ML experiment tracking for your project</p>
      </div>

      {/* Source Type Tabs */}
      <div className="flex items-center gap-2 mb-8 border-b border-border">
        <TabButton
          icon={<Github className="w-4 h-4" />}
          label="GitHub"
          active={sourceType === 'github'}
          onClick={() => handleSourceTypeChange('github')}
        />
        <TabButton
          icon={<HardDrive className="w-4 h-4" />}
          label="Local Path"
          active={sourceType === 'local'}
          onClick={() => handleSourceTypeChange('local')}
        />
        <TabButton
          icon={<Layers className="w-4 h-4" />}
          label="Template"
          active={sourceType === 'template'}
          onClick={() => handleSourceTypeChange('template')}
        />
        <TabButton
          icon={<UploadCloud className="w-4 h-4" />}
          label="Upload"
          active={sourceType === 'upload'}
          onClick={() => handleSourceTypeChange('upload')}
        />
      </div>

      {/* Step Indicator */}
      <div className="flex items-center justify-center mb-8">
        <div className="flex items-center gap-2">
          {Array.from({ length: getMaxSteps() }).map((_, idx) => {
            const stepNum = idx + 1;
            const labels =
              sourceType === 'template'
                ? ['Framework', 'Task', 'Config', 'Review']
                : sourceType === 'github'
                ? ['Repository', 'Configuration', 'Confirm']
                : sourceType === 'upload'
                ? ['Upload', 'Configuration', 'Confirm']
                : ['Basic Info', 'Configuration', 'Confirm'];

            return (
              <div key={stepNum} className="flex items-center gap-2">
                <StepIndicator
                  number={stepNum}
                  active={step === stepNum}
                  completed={step > stepNum}
                  label={labels[idx]}
                />
                {stepNum < getMaxSteps() && (
                  <div className={`h-0.5 w-16 ${step > stepNum ? 'bg-primary' : 'bg-border'}`} />
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Step Content */}
      <div className="bg-card border border-border rounded-lg p-6">
        {/* GitHub Flow */}
        {sourceType === 'github' && step === 1 && (
          <GitHubStep1
            formData={formData}
            privateRepo={privateRepo}
            gitCredentials={gitCredentials}
            cloning={cloning}
            cloneStatus={cloneStatus}
            scanError={scanError}
            onInputChange={handleInputChange}
            onPrivateRepoChange={setPrivateRepo}
            onClone={handleCloneRepo}
            onClearError={handleClearCloneError}
          />
        )}
        {sourceType === 'github' && step === 2 && scanResults && (
          <Step2Configuration
            formData={formData}
            scanResults={scanResults}
            onInputChange={handleInputChange}
          />
        )}
        {sourceType === 'github' && step === 3 && scanResults && (
          <Step3Confirmation formData={formData} scanResults={scanResults} sourceType="github" />
        )}

        {/* Local Path Flow */}
        {sourceType === 'local' && step === 1 && (
          <LocalStep1
            formData={formData}
            scanResults={scanResults}
            scanning={scanning}
            scanError={scanError}
            onInputChange={handleInputChange}
            onBrowseClick={() => {
              setShowBrowser(true);
              handleBrowseDirectory();
            }}
          />
        )}
        {sourceType === 'local' && step === 2 && scanResults && (
          <Step2Configuration
            formData={formData}
            scanResults={scanResults}
            onInputChange={handleInputChange}
          />
        )}
        {sourceType === 'local' && step === 3 && scanResults && (
          <Step3Confirmation formData={formData} scanResults={scanResults} sourceType="local" />
        )}

        {/* Template Flow */}
        {sourceType === 'template' && step === 1 && (
          <TemplateStep1
            templates={templates}
            selectedTemplate={selectedTemplate}
            onSelectTemplate={(template) => {
              setSelectedTemplate(template);
              setFormData((prev) => ({ ...prev, template_id: template.id }));
            }}
          />
        )}
        {sourceType === 'template' && step === 2 && selectedTemplate && (
          <TemplateStep2
            template={selectedTemplate}
            selectedTaskId={formData.template_task_id}
            onSelectTask={(taskId) => {
              setFormData((prev) => ({ ...prev, template_task_id: taskId }));
            }}
          />
        )}
        {sourceType === 'template' && step === 3 && (
          <TemplateStep3 formData={formData} onInputChange={handleInputChange} />
        )}
        {sourceType === 'template' && step === 4 && (
          <TemplateStep4 formData={formData} selectedTemplate={selectedTemplate} />
        )}

        {/* Upload Flow */}
        {sourceType === 'upload' && step === 1 && (
          <UploadStep1
            formData={formData}
            uploadFiles={uploadFiles}
            uploading={uploading}
            scanError={scanError}
            onInputChange={handleInputChange}
            onFilesChange={setUploadFiles}
            onUpload={handleUploadFiles}
          />
        )}
        {sourceType === 'upload' && step === 2 && scanResults && (
          <Step2Configuration
            formData={formData}
            scanResults={scanResults}
            onInputChange={handleInputChange}
          />
        )}
        {sourceType === 'upload' && step === 3 && scanResults && (
          <Step3Confirmation formData={formData} scanResults={scanResults} sourceType="upload" />
        )}

        {submitError && (
          <div className="mt-4 p-3 bg-destructive/10 border border-destructive rounded-lg flex items-start gap-2">
            <AlertCircle className="w-5 h-5 text-destructive flex-shrink-0 mt-0.5" />
            <p className="text-sm text-destructive">{submitError}</p>
          </div>
        )}

        {/* Navigation Buttons */}
        <div className="flex justify-between mt-8 pt-6 border-t border-border">
          <button
            onClick={handlePrevStep}
            disabled={step === 1}
            className="flex items-center gap-2 px-4 py-2 rounded-lg border border-border bg-background hover:bg-accent disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <ChevronLeft className="w-4 h-4" />
            Back
          </button>

          {step < getMaxSteps() ? (
            <button
              onClick={handleNextStep}
              disabled={!canProceedStep1()}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              Next
              <ChevronRight className="w-4 h-4" />
            </button>
          ) : (
            <button
              onClick={handleSubmit}
              disabled={submitting}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {submitting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Registering...
                </>
              ) : (
                <>
                  <Check className="w-4 h-4" />
                  Register Project
                </>
              )}
            </button>
          )}
        </div>
      </div>

      {/* Directory Browser Modal */}
      {showBrowser && (
        <DirectoryBrowserModal
          browserData={browserData}
          browsingDir={browsingDir}
          onClose={() => setShowBrowser(false)}
          onSelect={handleSelectDirectory}
          onNavigate={handleBrowseDirectory}
        />
      )}
    </div>
  );
}

function TabButton({
  icon,
  label,
  active,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 px-4 py-3 border-b-2 transition-colors ${
        active
          ? 'border-primary text-primary font-medium'
          : 'border-transparent text-muted-foreground hover:text-foreground'
      }`}
    >
      {icon}
      <span>{label}</span>
    </button>
  );
}

function StepIndicator({
  number,
  active,
  completed,
  label,
}: {
  number: number;
  active: boolean;
  completed: boolean;
  label: string;
}) {
  return (
    <div className="flex flex-col items-center gap-2">
      <div
        className={`w-10 h-10 rounded-full flex items-center justify-center font-semibold transition-colors ${
          completed
            ? 'bg-primary text-primary-foreground'
            : active
            ? 'bg-primary text-primary-foreground'
            : 'bg-muted text-muted-foreground'
        }`}
      >
        {completed ? <Check className="w-5 h-5" /> : number}
      </div>
      <span className={`text-xs ${active ? 'text-foreground font-medium' : 'text-muted-foreground'}`}>
        {label}
      </span>
    </div>
  );
}

function GitHubStep1({
  formData,
  privateRepo,
  gitCredentials,
  cloning,
  cloneStatus,
  scanError,
  onInputChange,
  onPrivateRepoChange,
  onClone,
  onClearError,
}: {
  formData: FormData;
  privateRepo: boolean;
  gitCredentials: GitCredentialResponse[];
  cloning: boolean;
  cloneStatus: CloneStatusResponse | null;
  scanError: string | null;
  onInputChange: (field: keyof FormData, value: string | number | null) => void;
  onPrivateRepoChange: (value: boolean) => void;
  onClone: () => void;
  onClearError: () => void;
}) {
  return (
    <div className="space-y-6">
      <div>
        <label className="block text-sm font-medium text-foreground mb-2">
          Repository URL <span className="text-destructive">*</span>
        </label>
        <input
          type="text"
          value={formData.git_url}
          onChange={(e) => {
            onInputChange('git_url', e.target.value);
            if (scanError || cloneStatus?.status === 'failed') {
              onClearError();
            }
          }}
          placeholder="https://github.com/username/repo.git"
          disabled={cloning}
          className="w-full px-3 py-2 bg-background border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-foreground mb-2">Branch</label>
        <input
          type="text"
          value={formData.git_branch}
          onChange={(e) => onInputChange('git_branch', e.target.value)}
          placeholder="main"
          disabled={cloning}
          className="w-full px-3 py-2 bg-background border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50"
        />
      </div>

      <div className="flex items-center gap-2">
        <input
          type="checkbox"
          id="private-repo"
          checked={privateRepo}
          onChange={(e) => onPrivateRepoChange(e.target.checked)}
          disabled={cloning}
          className="w-4 h-4 rounded border-border text-primary focus:ring-2 focus:ring-primary disabled:opacity-50"
        />
        <label htmlFor="private-repo" className="text-sm text-foreground">
          Private repository (requires credentials)
        </label>
      </div>

      {privateRepo && (
        <div>
          <label className="block text-sm font-medium text-foreground mb-2">
            Git Credential <span className="text-destructive">*</span>
          </label>
          <select
            value={formData.git_token_id || ''}
            onChange={(e) => onInputChange('git_token_id', e.target.value ? Number(e.target.value) : null)}
            disabled={cloning}
            className="w-full px-3 py-2 bg-background border border-border rounded-lg text-foreground focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50"
          >
            <option value="">Select credential</option>
            {gitCredentials.map((cred) => (
              <option key={cred.id} value={cred.id}>
                {cred.name} ({cred.provider})
              </option>
            ))}
          </select>
        </div>
      )}

      {!cloning && (!cloneStatus || cloneStatus.status === 'failed') && (
        <button
          onClick={onClone}
          disabled={!formData.git_url.trim() || (privateRepo && !formData.git_token_id)}
          className="w-full flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <GitBranch className="w-4 h-4" />
          {cloneStatus?.status === 'failed' ? 'Retry Clone & Scan' : 'Clone & Scan'}
        </button>
      )}

      {cloning && cloneStatus && (
        <div className="p-4 bg-muted rounded-lg space-y-2">
          <div className="flex items-center gap-2">
            <Loader2 className="w-5 h-5 animate-spin text-primary" />
            <span className="text-sm font-medium text-foreground">
              {cloneStatus.status === 'cloning' && 'Cloning repository...'}
              {cloneStatus.status === 'scanning' && 'Scanning project structure...'}
              {cloneStatus.status === 'started' && 'Starting clone...'}
            </span>
          </div>
          {cloneStatus.progress && (
            <p className="text-sm text-muted-foreground pl-7">{cloneStatus.progress}</p>
          )}
        </div>
      )}

      {cloneStatus?.status === 'completed' && cloneStatus.scan_result && (
        <div className="p-4 bg-green-50 dark:bg-green-950/20 border border-green-200 dark:border-green-900 rounded-lg space-y-2">
          <div className="flex items-center gap-2 text-green-700 dark:text-green-400">
            <Check className="w-5 h-5" />
            <span className="font-medium">Clone completed successfully</span>
          </div>
          <div className="space-y-1 pl-7 text-sm">
            <ValidationItem
              icon={<FolderOpen className="w-4 h-4" />}
              text={`Local path: ${cloneStatus.local_path}`}
              variant="neutral"
            />
            <ValidationItem
              icon={<GitBranch className="w-4 h-4" />}
              text={`Git: ${cloneStatus.scan_result.git_url} (${cloneStatus.scan_result.git_branch})`}
              variant="success"
            />
            <ValidationItem
              icon={<Terminal className="w-4 h-4" />}
              text={
                cloneStatus.scan_result.python_env
                  ? `Python env: ${cloneStatus.scan_result.python_env.type}`
                  : 'No Python env detected'
              }
              variant={cloneStatus.scan_result.python_env ? 'success' : 'neutral'}
            />
          </div>
        </div>
      )}

      {cloneStatus?.status === 'completed' && (
        <div>
          <label className="block text-sm font-medium text-foreground mb-2">
            Project Name <span className="text-destructive">*</span>
          </label>
          <input
            type="text"
            value={formData.name}
            onChange={(e) => onInputChange('name', e.target.value)}
            placeholder="my-project"
            className="w-full px-3 py-2 bg-background border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
          />
          <p className="mt-1 text-xs text-muted-foreground">
            Auto-detected from repository URL. You can change it.
          </p>
        </div>
      )}

      {scanError && (
        <div className="p-4 bg-destructive/10 border border-destructive rounded-lg">
          <div className="flex items-start gap-2">
            <AlertCircle className="w-5 h-5 text-destructive flex-shrink-0 mt-0.5" />
            <p className="text-sm font-medium text-destructive flex-1">{scanError}</p>
          </div>
          <div className="flex items-center justify-end gap-2 mt-3">
            <button
              onClick={onClearError}
              className="px-3 py-1.5 text-sm rounded-md border border-border bg-background hover:bg-accent transition-colors"
            >
              Clear
            </button>
            <button
              onClick={() => {
                onClearError();
                onClone();
              }}
              disabled={!formData.git_url.trim() || (privateRepo && !formData.git_token_id)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Retry
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function LocalStep1({
  formData,
  scanResults,
  scanning,
  scanError,
  onInputChange,
  onBrowseClick,
}: {
  formData: FormData;
  scanResults: ScanResponse | null;
  scanning: boolean;
  scanError: string | null;
  onInputChange: (field: keyof FormData, value: string | number | null) => void;
  onBrowseClick: () => void;
}) {
  return (
    <div className="space-y-6">
      <div>
        <label className="block text-sm font-medium text-foreground mb-2">
          Project Name <span className="text-destructive">*</span>
        </label>
        <input
          type="text"
          value={formData.name}
          onChange={(e) => onInputChange('name', e.target.value)}
          placeholder="my-ml-project"
          className="w-full px-3 py-2 bg-background border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-foreground mb-2">
          Project Path <span className="text-destructive">*</span>
        </label>
        <div className="flex gap-2">
          <div className="relative flex-1">
            <input
              type="text"
              value={formData.path}
              onChange={(e) => onInputChange('path', e.target.value)}
              placeholder="/absolute/path/to/project"
              className="w-full px-3 py-2 pr-10 bg-background border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
            />
            {scanning && (
              <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground animate-spin" />
            )}
          </div>
          <button
            onClick={onBrowseClick}
            className="px-4 py-2 rounded-lg border border-border bg-background hover:bg-accent transition-colors"
          >
            Browse
          </button>
        </div>

        {formData.path.trim() && !scanning && (
          <div className="mt-3 space-y-2">
            {scanError ? (
              <ValidationItem
                icon={<AlertCircle className="w-4 h-4" />}
                text={scanError}
                variant="error"
              />
            ) : scanResults ? (
              <>
                <ValidationItem
                  icon={scanResults.exists ? <Check className="w-4 h-4" /> : <X className="w-4 h-4" />}
                  text={scanResults.exists ? 'Path exists' : 'Path not found'}
                  variant={scanResults.exists ? 'success' : 'error'}
                />
                <ValidationItem
                  icon={<GitBranch className="w-4 h-4" />}
                  text={
                    scanResults.git_url
                      ? `Git repo detected (origin: ${scanResults.git_url})`
                      : 'No git repo'
                  }
                  variant={scanResults.git_url ? 'success' : 'neutral'}
                />
                <ValidationItem
                  icon={<Terminal className="w-4 h-4" />}
                  text={
                    scanResults.python_env
                      ? `Python env: ${scanResults.python_env.type} (${scanResults.python_env.indicator} found)`
                      : 'No Python env detected'
                  }
                  variant={scanResults.python_env ? 'success' : 'neutral'}
                />
              </>
            ) : null}
          </div>
        )}
      </div>

      <div>
        <label className="block text-sm font-medium text-foreground mb-2">Description</label>
        <textarea
          value={formData.description}
          onChange={(e) => onInputChange('description', e.target.value)}
          placeholder="Brief description of your ML project"
          rows={3}
          className="w-full px-3 py-2 bg-background border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary resize-none"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-foreground mb-2">
          Tags <span className="text-muted-foreground text-xs">(comma-separated)</span>
        </label>
        <input
          type="text"
          value={formData.tags}
          onChange={(e) => onInputChange('tags', e.target.value)}
          placeholder="vision, pytorch, resnet"
          className="w-full px-3 py-2 bg-background border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
        />
      </div>
    </div>
  );
}

function TemplateStep1({
  templates,
  selectedTemplate,
  onSelectTemplate,
}: {
  templates: TemplateInfo[];
  selectedTemplate: TemplateInfo | null;
  onSelectTemplate: (template: TemplateInfo) => void;
}) {
  return (
    <div className="space-y-6">
      <h3 className="text-lg font-semibold text-foreground">Select Framework</h3>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {templates.map((template) => (
          <button
            key={template.id}
            onClick={() => onSelectTemplate(template)}
            className={`p-4 rounded-lg border-2 text-left transition-all ${
              selectedTemplate?.id === template.id
                ? 'border-primary bg-primary/5'
                : 'border-border bg-card hover:border-primary/50'
            }`}
          >
            <div className="flex items-start justify-between mb-2">
              <h4 className="font-semibold text-foreground">{template.name}</h4>
              {selectedTemplate?.id === template.id && (
                <Check className="w-5 h-5 text-primary flex-shrink-0" />
              )}
            </div>
            <p className="text-sm text-muted-foreground mb-2">{template.description}</p>
            <p className="text-xs text-muted-foreground">{template.tasks.length} tasks available</p>
          </button>
        ))}
      </div>
    </div>
  );
}

function TemplateStep2({
  template,
  selectedTaskId,
  onSelectTask,
}: {
  template: TemplateInfo;
  selectedTaskId: string;
  onSelectTask: (taskId: string) => void;
}) {
  return (
    <div className="space-y-6">
      <h3 className="text-lg font-semibold text-foreground">Select Task</h3>
      <p className="text-sm text-muted-foreground">Choose a task for {template.name}</p>
      <div className="space-y-3">
        {template.tasks.map((task) => (
          <button
            key={task.id}
            onClick={() => onSelectTask(task.id)}
            className={`w-full p-4 rounded-lg border-2 text-left transition-all ${
              selectedTaskId === task.id
                ? 'border-primary bg-primary/5'
                : 'border-border bg-card hover:border-primary/50'
            }`}
          >
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <h4 className="font-semibold text-foreground mb-1">{task.name}</h4>
                <p className="text-sm text-muted-foreground">{task.description}</p>
              </div>
              {selectedTaskId === task.id && (
                <Check className="w-5 h-5 text-primary flex-shrink-0 ml-2" />
              )}
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

function TemplateStep3({
  formData,
  onInputChange,
}: {
  formData: FormData;
  onInputChange: (field: keyof FormData, value: string | number | null) => void;
}) {
  return (
    <div className="space-y-6">
      <h3 className="text-lg font-semibold text-foreground">Configuration</h3>

      <div>
        <label className="block text-sm font-medium text-foreground mb-2">
          Model Name <span className="text-muted-foreground text-xs">(optional)</span>
        </label>
        <input
          type="text"
          value={formData.template_model_name}
          onChange={(e) => onInputChange('template_model_name', e.target.value)}
          placeholder="resnet50, bert-base, etc."
          className="w-full px-3 py-2 bg-background border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-foreground mb-2">Batch Size</label>
          <input
            type="number"
            value={formData.template_batch_size}
            onChange={(e) => onInputChange('template_batch_size', e.target.value)}
            placeholder="32"
            className="w-full px-3 py-2 bg-background border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-foreground mb-2">Learning Rate</label>
          <input
            type="number"
            step="0.0001"
            value={formData.template_lr}
            onChange={(e) => onInputChange('template_lr', e.target.value)}
            placeholder="0.001"
            className="w-full px-3 py-2 bg-background border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-foreground mb-2">Epochs</label>
          <input
            type="number"
            value={formData.template_epochs}
            onChange={(e) => onInputChange('template_epochs', e.target.value)}
            placeholder="10"
            className="w-full px-3 py-2 bg-background border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-foreground mb-2">Optimizer</label>
          <select
            value={formData.template_optimizer}
            onChange={(e) => onInputChange('template_optimizer', e.target.value)}
            className="w-full px-3 py-2 bg-background border border-border rounded-lg text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
          >
            <option value="adam">Adam</option>
            <option value="sgd">SGD</option>
            <option value="adamw">AdamW</option>
            <option value="rmsprop">RMSprop</option>
          </select>
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-foreground mb-2">
          Project Name <span className="text-destructive">*</span>
        </label>
        <input
          type="text"
          value={formData.name}
          onChange={(e) => onInputChange('name', e.target.value)}
          placeholder="my-ml-project"
          className="w-full px-3 py-2 bg-background border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
        />
      </div>
    </div>
  );
}

function TemplateStep4({
  formData,
  selectedTemplate,
}: {
  formData: FormData;
  selectedTemplate: TemplateInfo | null;
}) {
  const selectedTask = selectedTemplate?.tasks.find((t) => t.id === formData.template_task_id);

  return (
    <div className="space-y-6">
      <h3 className="text-lg font-semibold text-foreground mb-4">Review Template Configuration</h3>
      <div className="space-y-4">
        <SummaryRow label="Framework" value={selectedTemplate?.name || ''} />
        <SummaryRow label="Task" value={selectedTask?.name || ''} />
        {formData.template_model_name && (
          <SummaryRow label="Model" value={formData.template_model_name} />
        )}
        <SummaryRow label="Batch Size" value={formData.template_batch_size} />
        <SummaryRow label="Learning Rate" value={formData.template_lr} />
        <SummaryRow label="Epochs" value={formData.template_epochs} />
        <SummaryRow label="Optimizer" value={formData.template_optimizer} />
        <SummaryRow label="Project Name" value={formData.name} />
      </div>
    </div>
  );
}

function UploadStep1({
  formData,
  uploadFiles,
  uploading,
  scanError,
  onInputChange,
  onFilesChange,
  onUpload,
}: {
  formData: FormData;
  uploadFiles: File[];
  uploading: boolean;
  scanError: string | null;
  onInputChange: (field: keyof FormData, value: string | number | null) => void;
  onFilesChange: (files: File[]) => void;
  onUpload: () => void;
}) {
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const files = Array.from(e.dataTransfer.files);
    onFilesChange([...uploadFiles, ...files]);
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const files = Array.from(e.target.files);
      onFilesChange([...uploadFiles, ...files]);
    }
  };

  const removeFile = (index: number) => {
    onFilesChange(uploadFiles.filter((_, i) => i !== index));
  };

  const totalSize = uploadFiles.reduce((sum, f) => sum + f.size, 0);

  return (
    <div className="space-y-6">
      <div>
        <label className="block text-sm font-medium text-foreground mb-2">
          Project Name <span className="text-destructive">*</span>
        </label>
        <input
          type="text"
          value={formData.name}
          onChange={(e) => onInputChange('name', e.target.value)}
          placeholder="my-ml-project"
          disabled={uploading}
          className="w-full px-3 py-2 bg-background border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50"
        />
      </div>

      <div
        onDrop={handleDrop}
        onDragOver={(e) => e.preventDefault()}
        className="border-2 border-dashed border-border rounded-lg p-8 text-center hover:border-primary/50 transition-colors cursor-pointer"
        onClick={() => document.getElementById('file-input')?.click()}
      >
        <UploadCloud className="w-12 h-12 mx-auto mb-4 text-muted-foreground" />
        <p className="text-sm font-medium text-foreground mb-2">
          Drop files here or click to browse
        </p>
        <p className="text-xs text-muted-foreground">Upload your project files</p>
        <input
          id="file-input"
          type="file"
          multiple
          onChange={handleFileSelect}
          className="hidden"
          disabled={uploading}
        />
      </div>

      {uploadFiles.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center justify-between mb-2">
            <h4 className="text-sm font-medium text-foreground">
              Files ({uploadFiles.length}) — {(totalSize / 1024 / 1024).toFixed(2)} MB
            </h4>
          </div>
          <div className="max-h-64 overflow-y-auto space-y-2">
            {uploadFiles.map((file, idx) => (
              <div
                key={idx}
                className="flex items-center justify-between p-3 bg-muted rounded-lg"
              >
                <div className="flex items-center gap-2 flex-1 min-w-0">
                  <FileText className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-foreground truncate">{file.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {(file.size / 1024).toFixed(1)} KB
                    </p>
                  </div>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    removeFile(idx);
                  }}
                  disabled={uploading}
                  className="p-1 hover:bg-destructive/10 rounded transition-colors disabled:opacity-50"
                >
                  <X className="w-4 h-4 text-destructive" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {!uploading && uploadFiles.length > 0 && (
        <button
          onClick={onUpload}
          disabled={!formData.name.trim()}
          className="w-full flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <Upload className="w-4 h-4" />
          Upload & Scan
        </button>
      )}

      {uploading && (
        <div className="p-4 bg-muted rounded-lg flex items-center gap-2">
          <Loader2 className="w-5 h-5 animate-spin text-primary" />
          <span className="text-sm font-medium text-foreground">Uploading files...</span>
        </div>
      )}

      {scanError && (
        <div className="p-3 bg-destructive/10 border border-destructive rounded-lg flex items-start gap-2">
          <AlertCircle className="w-5 h-5 text-destructive flex-shrink-0 mt-0.5" />
          <p className="text-sm text-destructive">{scanError}</p>
        </div>
      )}
    </div>
  );
}

function ValidationItem({
  icon,
  text,
  variant,
}: {
  icon: React.ReactNode;
  text: string;
  variant: 'success' | 'error' | 'warning' | 'neutral';
}) {
  const colorClasses = {
    success: 'text-green-600 dark:text-green-400',
    error: 'text-destructive',
    warning: 'text-yellow-600 dark:text-yellow-400',
    neutral: 'text-muted-foreground',
  };

  return (
    <div className={`flex items-center gap-2 text-sm ${colorClasses[variant]}`}>
      {icon}
      <span>{text}</span>
    </div>
  );
}

function Step2Configuration({
  formData,
  scanResults,
  onInputChange,
}: {
  formData: FormData;
  scanResults: ScanResponse;
  onInputChange: (field: keyof FormData, value: string | number | null) => void;
}) {
  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold text-foreground mb-3 flex items-center gap-2">
          <FileCode className="w-5 h-5" />
          Detected Config Files
        </h3>
        {scanResults.configs && scanResults.configs.length > 0 ? (
          <div className="space-y-2">
            {scanResults.configs.map((file: ConfigFileInfo, idx: number) => (
              <div key={idx} className="p-3 bg-muted rounded-lg flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-foreground">{file.path}</p>
                  <p className="text-xs text-muted-foreground">
                    {file.format} • {(file.size / 1024).toFixed(1)} KB
                  </p>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">No config files detected</p>
        )}
      </div>

      <div>
        <h3 className="text-lg font-semibold text-foreground mb-3 flex items-center gap-2">
          <Terminal className="w-5 h-5" />
          Detected Scripts
        </h3>
        {scanResults.scripts ? (
          <div className="space-y-4">
            {scanResults.scripts.train && scanResults.scripts.train.length > 0 && (
              <div>
                <p className="text-sm font-medium text-foreground mb-2">Train Scripts</p>
                <div className="space-y-1">
                  {scanResults.scripts.train.map((script: string, idx: number) => (
                    <div key={idx} className="text-sm text-muted-foreground pl-4">
                      • {script}
                    </div>
                  ))}
                </div>
              </div>
            )}
            {scanResults.scripts.eval && scanResults.scripts.eval.length > 0 && (
              <div>
                <p className="text-sm font-medium text-foreground mb-2">Eval Scripts</p>
                <div className="space-y-1">
                  {scanResults.scripts.eval.map((script: string, idx: number) => (
                    <div key={idx} className="text-sm text-muted-foreground pl-4">
                      • {script}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">No scripts detected</p>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4 border-t border-border">
        <div>
          <label className="block text-sm font-medium text-foreground mb-2">Train Command</label>
          <input
            type="text"
            value={formData.train_command}
            onChange={(e) => onInputChange('train_command', e.target.value)}
            placeholder="python train.py --config {config}"
            className="w-full px-3 py-2 bg-background border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-foreground mb-2">
            Eval Command <span className="text-muted-foreground text-xs">(optional)</span>
          </label>
          <input
            type="text"
            value={formData.eval_command}
            onChange={(e) => onInputChange('eval_command', e.target.value)}
            placeholder="python eval.py --config {config}"
            className="w-full px-3 py-2 bg-background border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-foreground mb-2">Config Directory</label>
          <input
            type="text"
            value={formData.config_dir}
            onChange={(e) => onInputChange('config_dir', e.target.value)}
            placeholder="configs/"
            className="w-full px-3 py-2 bg-background border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-foreground mb-2">Config Format</label>
          <select
            value={formData.config_format}
            onChange={(e) => onInputChange('config_format', e.target.value)}
            className="w-full px-3 py-2 bg-background border border-border rounded-lg text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
          >
            <option value="yaml">YAML</option>
            <option value="json">JSON</option>
            <option value="toml">TOML</option>
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-foreground mb-2">
            Checkpoint Directory
          </label>
          <input
            type="text"
            value={formData.checkpoint_dir}
            onChange={(e) => onInputChange('checkpoint_dir', e.target.value)}
            placeholder="checkpoints/"
            className="w-full px-3 py-2 bg-background border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-foreground mb-2">
            Python Environment
          </label>
          <select
            value={formData.python_env}
            onChange={(e) => onInputChange('python_env', e.target.value)}
            className="w-full px-3 py-2 bg-background border border-border rounded-lg text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
          >
            <option value="uv">uv</option>
            <option value="venv">venv</option>
            <option value="conda">conda</option>
            <option value="pip">pip</option>
            <option value="system">system</option>
          </select>
        </div>
      </div>
    </div>
  );
}

function Step3Confirmation({
  formData,
  scanResults,
  sourceType,
}: {
  formData: FormData;
  scanResults: ScanResponse;
  sourceType: SourceType;
}) {
  const configCount = scanResults.configs?.length || 0;
  const scriptCount =
    (scanResults.scripts?.train?.length || 0) +
    (scanResults.scripts?.eval?.length || 0) +
    (scanResults.scripts?.other?.length || 0);

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold text-foreground mb-4">Review Project Settings</h3>
        <div className="space-y-4">
          <SummaryRow label="Source Type" value={sourceType} />
          <SummaryRow label="Name" value={formData.name} />
          <SummaryRow label="Path" value={formData.path} />
          {sourceType === 'github' && scanResults.git_url && (
            <>
              <SummaryRow label="Git URL" value={scanResults.git_url} />
              <SummaryRow label="Branch" value={formData.git_branch} />
            </>
          )}
          <SummaryRow label="Project Type" value={formData.project_type} />
          <SummaryRow label="Python Environment" value={formData.python_env} />
          {formData.train_command && (
            <SummaryRow label="Train Command" value={formData.train_command} />
          )}
          {formData.eval_command && <SummaryRow label="Eval Command" value={formData.eval_command} />}
          {formData.config_dir && <SummaryRow label="Config Directory" value={formData.config_dir} />}
          {formData.checkpoint_dir && (
            <SummaryRow label="Checkpoint Directory" value={formData.checkpoint_dir} />
          )}
          {formData.tags && (
            <SummaryRow
              label="Tags"
              value={formData.tags
                .split(',')
                .map((t) => t.trim())
                .filter(Boolean)
                .join(', ')}
            />
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 pt-4 border-t border-border">
        <div className="p-4 bg-muted rounded-lg">
          <p className="text-sm text-muted-foreground mb-1">Config Files Detected</p>
          <p className="text-2xl font-bold text-foreground">{configCount}</p>
        </div>
        <div className="p-4 bg-muted rounded-lg">
          <p className="text-sm text-muted-foreground mb-1">Scripts Detected</p>
          <p className="text-2xl font-bold text-foreground">{scriptCount}</p>
        </div>
      </div>

      {formData.description && (
        <div className="pt-4 border-t border-border">
          <p className="text-sm font-medium text-foreground mb-2">Description</p>
          <p className="text-sm text-muted-foreground">{formData.description}</p>
        </div>
      )}
    </div>
  );
}

function SummaryRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start gap-4">
      <span className="text-sm font-medium text-muted-foreground w-40 flex-shrink-0">{label}:</span>
      <span className="text-sm text-foreground break-all">{value}</span>
    </div>
  );
}

function DirectoryBrowserModal({
  browserData,
  browsingDir,
  onClose,
  onSelect,
  onNavigate,
}: {
  browserData: FileBrowseResponse | null;
  browsingDir: boolean;
  onClose: () => void;
  onSelect: (path: string) => void;
  onNavigate: (path?: string) => void;
}) {
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-card border border-border rounded-lg w-full max-w-2xl max-h-[80vh] flex flex-col">
        <div className="p-4 border-b border-border flex items-center justify-between">
          <h3 className="text-lg font-semibold text-foreground">Browse Directory</h3>
          <button
            onClick={onClose}
            className="p-1 hover:bg-accent rounded transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-4 border-b border-border">
          <div className="flex items-center gap-2">
            <FolderOpen className="w-5 h-5 text-muted-foreground" />
            <span className="text-sm font-medium text-foreground">
              {browserData?.path || '/'}
            </span>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          {browsingDir ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
            </div>
          ) : browserData ? (
            <div className="space-y-1">
              {browserData.path !== '/' && (
                <button
                  onClick={() => {
                    const parentPath = browserData.path.split('/').slice(0, -1).join('/') || '/';
                    onNavigate(parentPath);
                  }}
                  className="w-full p-3 rounded-lg hover:bg-accent transition-colors flex items-center gap-2 text-left"
                >
                  <ChevronLeft className="w-4 h-4 text-muted-foreground" />
                  <span className="text-sm text-foreground">..</span>
                </button>
              )}
              {browserData.entries
                .filter((e) => e.type === 'dir')
                .map((entry) => (
                  <button
                    key={entry.name}
                    onClick={() => {
                      const newPath = browserData.path === '/'
                        ? `/${entry.name}`
                        : `${browserData.path}/${entry.name}`;
                      onNavigate(newPath);
                    }}
                    className="w-full p-3 rounded-lg hover:bg-accent transition-colors flex items-center gap-2 text-left"
                  >
                    <FolderOpen className="w-4 h-4 text-blue-500" />
                    <span className="text-sm text-foreground">{entry.name}</span>
                  </button>
                ))}
            </div>
          ) : null}
        </div>

        <div className="p-4 border-t border-border flex justify-between">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg border border-border bg-background hover:bg-accent transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={() => browserData && onSelect(browserData.path)}
            disabled={!browserData}
            className="px-4 py-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Select Current Directory
          </button>
        </div>
      </div>
    </div>
  );
}
