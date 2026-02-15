import { useState, useRef } from 'react'
import {
  Upload,
  Loader2,
  AlertCircle,
  Shapes,
  BarChart3,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import axios from 'axios'

// --- Types ---

interface Prediction {
  class: string
  probability: number
}

interface PredictResponse {
  predictions: Prediction[]
  top_class: string
  confidence: number
}

// --- Main Page ---

export default function ClassifierDemoPage() {
  const [imageFile, setImageFile] = useState<File | null>(null)
  const [imagePreview, setImagePreview] = useState<string | null>(null)
  const [checkpointPath, setCheckpointPath] = useState('')
  const [adapterName] = useState('dummy_classifier')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<PredictResponse | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleImageSelect = (file: File) => {
    setImageFile(file)
    setResult(null)
    const reader = new FileReader()
    reader.onloadend = () => setImagePreview(reader.result as string)
    reader.readAsDataURL(file)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    const file = e.dataTransfer.files[0]
    if (file?.type.startsWith('image/')) {
      handleImageSelect(file)
    }
  }

  const handlePredict = async () => {
    if (!imageFile || !checkpointPath) return
    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const formData = new FormData()
      formData.append('file', imageFile)
      formData.append('adapter_name', adapterName)
      formData.append('checkpoint_path', checkpointPath)

      const res = await axios.post<PredictResponse>('/api/predict/image', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setResult(res.data)
    } catch (err) {
      if (axios.isAxiosError(err)) {
        setError(err.response?.data?.detail || err.message)
      } else {
        setError('Prediction failed')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
          Image Classification Demo
        </h2>
        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
          Upload an image and classify it using a trained model checkpoint.
        </p>
      </div>

      {/* Config */}
      <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-700 dark:bg-zinc-800">
        <h3 className="mb-3 text-sm font-medium text-zinc-700 dark:text-zinc-300">
          Model Configuration
        </h3>
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label className="block text-xs text-zinc-500 dark:text-zinc-400 mb-1">
              Checkpoint Path
            </label>
            <input
              type="text"
              value={checkpointPath}
              onChange={(e) => setCheckpointPath(e.target.value)}
              placeholder="e.g. checkpoints/best.pt"
              className="w-full rounded border border-zinc-300 bg-white px-3 py-1.5 text-sm dark:border-zinc-600 dark:bg-zinc-700 dark:text-zinc-100"
            />
          </div>
          <div>
            <label className="block text-xs text-zinc-500 dark:text-zinc-400 mb-1">
              Adapter
            </label>
            <input
              type="text"
              value={adapterName}
              disabled
              className="w-full rounded border border-zinc-300 bg-zinc-50 px-3 py-1.5 text-sm dark:border-zinc-600 dark:bg-zinc-700/50 dark:text-zinc-400"
            />
          </div>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Upload Area */}
        <div className="space-y-4">
          <div
            className={cn(
              'relative flex min-h-[280px] cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-6 transition-colors',
              imagePreview
                ? 'border-blue-300 dark:border-blue-600'
                : 'border-zinc-300 hover:border-zinc-400 dark:border-zinc-600 dark:hover:border-zinc-500'
            )}
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0]
                if (file) handleImageSelect(file)
              }}
            />
            {imagePreview ? (
              <img
                src={imagePreview}
                alt="Preview"
                className="max-h-[250px] rounded object-contain"
              />
            ) : (
              <>
                <Upload className="mb-2 h-8 w-8 text-zinc-400" />
                <p className="text-sm text-zinc-500 dark:text-zinc-400">
                  Drop an image here or click to select
                </p>
              </>
            )}
          </div>

          <button
            onClick={handlePredict}
            disabled={!imageFile || !checkpointPath || loading}
            className={cn(
              'flex w-full items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium text-white transition-colors',
              !imageFile || !checkpointPath || loading
                ? 'cursor-not-allowed bg-zinc-400'
                : 'bg-blue-600 hover:bg-blue-700'
            )}
          >
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Shapes className="h-4 w-4" />
            )}
            {loading ? 'Classifying...' : 'Classify Image'}
          </button>

          {error && (
            <div className="flex items-start gap-2 rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-400">
              <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
              {error}
            </div>
          )}
        </div>

        {/* Results */}
        <div className="space-y-4">
          {result ? (
            <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-700 dark:bg-zinc-800">
              <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-zinc-700 dark:text-zinc-300">
                <BarChart3 className="h-4 w-4" />
                Classification Results
              </h3>

              {/* Top prediction */}
              <div className="mb-4 rounded-lg bg-blue-50 p-3 dark:bg-blue-900/20">
                <div className="text-xs text-blue-600 dark:text-blue-400">Top Prediction</div>
                <div className="text-lg font-bold text-blue-700 dark:text-blue-300">
                  {result.top_class}
                </div>
                <div className="text-sm text-blue-600 dark:text-blue-400">
                  {(result.confidence * 100).toFixed(1)}% confidence
                </div>
              </div>

              {/* All predictions bar chart */}
              <div className="space-y-2">
                {result.predictions.map((pred, i) => (
                  <div key={i} className="space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-medium text-zinc-700 dark:text-zinc-300">
                        {pred.class}
                      </span>
                      <span className="text-zinc-500 dark:text-zinc-400">
                        {(pred.probability * 100).toFixed(1)}%
                      </span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-700">
                      <div
                        className={cn(
                          'h-full rounded-full transition-all',
                          i === 0 ? 'bg-blue-500' : 'bg-zinc-400 dark:bg-zinc-500'
                        )}
                        style={{ width: `${pred.probability * 100}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="flex min-h-[280px] items-center justify-center rounded-lg border border-dashed border-zinc-300 dark:border-zinc-600">
              <div className="text-center text-sm text-zinc-400 dark:text-zinc-500">
                <Shapes className="mx-auto mb-2 h-8 w-8" />
                Upload an image and click Classify to see results
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
