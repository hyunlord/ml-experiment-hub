import { useState } from 'react'
import { X } from 'lucide-react'
import { useExperimentStore } from '@/stores/experimentStore'

interface CreateExperimentDialogProps {
  open: boolean
  onClose: () => void
}

export default function CreateExperimentDialog({ open, onClose }: CreateExperimentDialogProps) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [framework, setFramework] = useState('pytorch_lightning')
  const [scriptPath, setScriptPath] = useState('')
  const [hyperparameters, setHyperparameters] = useState('{}')
  const [error, setError] = useState('')

  const createExperiment = useExperimentStore((state) => state.createExperiment)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    try {
      const params = JSON.parse(hyperparameters)
      await createExperiment({
        name,
        description: description || undefined,
        framework,
        script_path: scriptPath,
        hyperparameters: params,
      })
      setName('')
      setDescription('')
      setFramework('pytorch_lightning')
      setScriptPath('')
      setHyperparameters('{}')
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Invalid hyperparameters JSON')
    }
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-md rounded-lg border border-border bg-card p-6 shadow-lg">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-xl font-semibold text-card-foreground">
            Create Experiment
          </h2>
          <button
            onClick={onClose}
            className="rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-2 block text-sm font-medium text-card-foreground">
              Name
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>

          <div>
            <label className="mb-2 block text-sm font-medium text-card-foreground">
              Description
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>

          <div>
            <label className="mb-2 block text-sm font-medium text-card-foreground">
              Framework
            </label>
            <select
              value={framework}
              onChange={(e) => setFramework(e.target.value)}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring"
            >
              <option value="pytorch_lightning">PyTorch Lightning</option>
              <option value="huggingface">HuggingFace</option>
              <option value="custom">Custom</option>
            </select>
          </div>

          <div>
            <label className="mb-2 block text-sm font-medium text-card-foreground">
              Script Path
            </label>
            <input
              type="text"
              value={scriptPath}
              onChange={(e) => setScriptPath(e.target.value)}
              required
              placeholder="path/to/train.py"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>

          <div>
            <label className="mb-2 block text-sm font-medium text-card-foreground">
              Hyperparameters (JSON)
            </label>
            <textarea
              value={hyperparameters}
              onChange={(e) => setHyperparameters(e.target.value)}
              rows={4}
              className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring"
              placeholder='{"learning_rate": 0.001, "batch_size": 32}'
            />
          </div>

          {error && (
            <p className="text-sm text-destructive">{error}</p>
          )}

          <div className="flex justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md border border-input bg-background px-4 py-2 text-sm font-medium transition-colors hover:bg-accent"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
            >
              Create
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
