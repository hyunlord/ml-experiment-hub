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
} from 'lucide-react';
import { scanDirectory, createProject } from '@/api/projects';
import type { ScanResponse, ProjectCreate, ConfigFileInfo } from '@/types/project';

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
};

export default function ProjectCreatePage() {
  const navigate = useNavigate();
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
  });

  const [scanResults, setScanResults] = useState<ScanResponse | null>(null);
  const [scanning, setScanning] = useState(false);
  const [scanError, setScanError] = useState<string | null>(null);
  const [pathDebounceTimer, setPathDebounceTimer] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  useEffect(() => {
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
  }, [formData.path]);

  const handleScanDirectory = async (path: string) => {
    setScanning(true);
    setScanError(null);
    try {
      const results = await scanDirectory(path);
      setScanResults(results);

      // Pre-fill form data from scan results
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

  const handleInputChange = (field: keyof FormData, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const canProceedFromStep1 = formData.name.trim() && scanResults?.exists;

  const handleNextStep = () => {
    if (step < 3) {
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
        path: formData.path.trim(),
        description: formData.description.trim() || undefined,
        tags: formData.tags
          .split(',')
          .map((t) => t.trim())
          .filter(Boolean),
        git_url: scanResults?.git_url || undefined,
        train_command_template: formData.train_command.trim() || undefined,
        eval_command_template: formData.eval_command.trim() || undefined,
        config_dir: formData.config_dir.trim() || undefined,
        config_format: formData.config_format || undefined,
        checkpoint_dir: formData.checkpoint_dir.trim() || undefined,
        python_env: formData.python_env || undefined,
        env_path: formData.env_path.trim() || undefined,
        project_type: formData.project_type || undefined,
      };

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

      {/* Step Indicator */}
      <div className="flex items-center justify-center mb-8">
        <div className="flex items-center gap-2">
          <StepIndicator number={1} active={step === 1} completed={step > 1} label="Basic Info" />
          <div className={`h-0.5 w-16 ${step > 1 ? 'bg-primary' : 'bg-border'}`} />
          <StepIndicator number={2} active={step === 2} completed={step > 2} label="Configuration" />
          <div className={`h-0.5 w-16 ${step > 2 ? 'bg-primary' : 'bg-border'}`} />
          <StepIndicator number={3} active={step === 3} completed={false} label="Confirm" />
        </div>
      </div>

      {/* Step Content */}
      <div className="bg-card border border-border rounded-lg p-6">
        {step === 1 && (
          <Step1BasicInfo
            formData={formData}
            scanResults={scanResults}
            scanning={scanning}
            scanError={scanError}
            onInputChange={handleInputChange}
          />
        )}

        {step === 2 && scanResults && (
          <Step2Configuration
            formData={formData}
            scanResults={scanResults}
            onInputChange={handleInputChange}
          />
        )}

        {step === 3 && scanResults && (
          <Step3Confirmation formData={formData} scanResults={scanResults} />
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

          {step < 3 ? (
            <button
              onClick={handleNextStep}
              disabled={step === 1 && !canProceedFromStep1}
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
    </div>
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

function Step1BasicInfo({
  formData,
  scanResults,
  scanning,
  scanError,
  onInputChange,
}: {
  formData: FormData;
  scanResults: ScanResponse | null;
  scanning: boolean;
  scanError: string | null;
  onInputChange: (field: keyof FormData, value: string) => void;
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
        <div className="relative">
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

        {/* Validation Results */}
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
                <ValidationItem
                  icon={<FolderOpen className="w-4 h-4" />}
                  text={
                    scanResults.python_env?.venv_path
                      ? `Virtual env found at ${scanResults.python_env.venv_path}`
                      : 'No .venv found'
                  }
                  variant={scanResults.python_env?.venv_path ? 'success' : 'warning'}
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
    success: 'text-green-600',
    error: 'text-destructive',
    warning: 'text-yellow-600',
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
  onInputChange: (field: keyof FormData, value: string) => void;
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
            {scanResults.scripts.other && scanResults.scripts.other.length > 0 && (
              <div>
                <p className="text-sm font-medium text-foreground mb-2">Other Scripts</p>
                <div className="space-y-1">
                  {scanResults.scripts.other.map((script: string, idx: number) => (
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
          <label className="block text-sm font-medium text-foreground mb-2">Checkpoint Directory</label>
          <input
            type="text"
            value={formData.checkpoint_dir}
            onChange={(e) => onInputChange('checkpoint_dir', e.target.value)}
            placeholder="checkpoints/"
            className="w-full px-3 py-2 bg-background border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-foreground mb-2">Python Environment</label>
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

        <div>
          <label className="block text-sm font-medium text-foreground mb-2">
            Env Path <span className="text-muted-foreground text-xs">(optional)</span>
          </label>
          <input
            type="text"
            value={formData.env_path}
            onChange={(e) => onInputChange('env_path', e.target.value)}
            placeholder=".venv/"
            className="w-full px-3 py-2 bg-background border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-foreground mb-2">Project Type</label>
          <select
            value={formData.project_type}
            onChange={(e) => onInputChange('project_type', e.target.value)}
            className="w-full px-3 py-2 bg-background border border-border rounded-lg text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
          >
            <option value="pytorch-lightning">PyTorch Lightning</option>
            <option value="huggingface">Hugging Face</option>
            <option value="custom">Custom</option>
          </select>
        </div>
      </div>
    </div>
  );
}

function Step3Confirmation({
  formData,
  scanResults,
}: {
  formData: FormData;
  scanResults: ScanResponse;
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
          <SummaryRow label="Name" value={formData.name} />
          <SummaryRow label="Path" value={formData.path} />
          {scanResults.git_url && <SummaryRow label="Git URL" value={scanResults.git_url} />}
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
