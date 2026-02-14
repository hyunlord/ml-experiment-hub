import { useState, useRef, useCallback, useEffect } from 'react'
import {
  Search,
  Upload,
  Image as ImageIcon,
  Type,
  Loader2,
  Clock,
  Hash,
  AlertCircle,
  Play,
  X,
  RefreshCw,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import {
  searchByText,
  searchByImage,
  createIndexBuildJob,
  getJob,
  listJobs,
  type SearchResponse,
  type SearchResult,
  type JobResponse,
} from '@/api/jobs'

// --- Constants ---

const BIT_OPTIONS = [8, 16, 32, 64, 128] as const
const METHODS = ['hamming', 'cosine'] as const

const SAMPLE_QUERIES = [
  { label: '고양이가 소파에 앉아있다', lang: 'KR' },
  { label: '바다 위의 일몰', lang: 'KR' },
  { label: '산 위에서 본 풍경', lang: 'KR' },
  { label: 'A cat sitting on a sofa', lang: 'EN' },
  { label: 'Sunset over the ocean', lang: 'EN' },
  { label: 'A dog playing in the park', lang: 'EN' },
]

// --- Main Page ---

export default function SearchDemoPage() {
  const [mode, setMode] = useState<'text' | 'image'>('text')
  const [textQuery, setTextQuery] = useState('')
  const [imageFile, setImageFile] = useState<File | null>(null)
  const [imagePreview, setImagePreview] = useState<string | null>(null)
  const [bitLength, setBitLength] = useState(64)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Two-column results: hamming + cosine
  const [hammingResults, setHammingResults] = useState<SearchResponse | null>(null)
  const [cosineResults, setCosineResults] = useState<SearchResponse | null>(null)

  // Index build
  const [indexPath, setIndexPath] = useState('tests/fixtures/dummy_index.pt')
  const [checkpointPath, setCheckpointPath] = useState('tests/fixtures/dummy_checkpoint.pt')
  const [buildingIndex, setBuildingIndex] = useState(false)
  const [buildJob, setBuildJob] = useState<JobResponse | null>(null)
  const [indexJobs, setIndexJobs] = useState<JobResponse[]>([])

  const fileInputRef = useRef<HTMLInputElement>(null)

  // Load existing index build jobs
  const loadIndexJobs = useCallback(async () => {
    try {
      const allJobs = await listJobs({ job_type: 'index_build' })
      setIndexJobs(allJobs)
    } catch {
      // ignore
    }
  }, [])

  useEffect(() => {
    loadIndexJobs()
  }, [loadIndexJobs])

  // Poll build job progress
  useEffect(() => {
    if (!buildJob || (buildJob.status !== 'running' && buildJob.status !== 'pending')) return
    const interval = setInterval(async () => {
      try {
        const job = await getJob(buildJob.id)
        setBuildJob(job)
        if (job.status === 'completed' || job.status === 'failed' || job.status === 'cancelled') {
          setBuildingIndex(false)
          loadIndexJobs()
        }
      } catch {
        setBuildingIndex(false)
      }
    }, 2000)
    return () => clearInterval(interval)
  }, [buildJob, loadIndexJobs])

  const handleImageSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      setImageFile(file)
      const reader = new FileReader()
      reader.onload = (ev) => setImagePreview(ev.target?.result as string)
      reader.readAsDataURL(file)
    }
  }

  const handleSearch = async () => {
    setLoading(true)
    setError(null)
    setHammingResults(null)
    setCosineResults(null)

    try {
      if (mode === 'text' && textQuery.trim()) {
        // Run both methods in parallel
        const [hamming, cosine] = await Promise.all([
          searchByText({
            query: textQuery,
            index_path: indexPath,
            checkpoint_path: checkpointPath,
            bit_length: bitLength,
            method: 'hamming',
          }),
          searchByText({
            query: textQuery,
            index_path: indexPath,
            checkpoint_path: checkpointPath,
            bit_length: bitLength,
            method: 'cosine',
          }),
        ])
        setHammingResults(hamming)
        setCosineResults(cosine)
      } else if (mode === 'image' && imageFile) {
        const [hamming, cosine] = await Promise.all([
          searchByImage({
            image: imageFile,
            index_path: indexPath,
            checkpoint_path: checkpointPath,
            bit_length: bitLength,
            method: 'hamming',
          }),
          searchByImage({
            image: imageFile,
            index_path: indexPath,
            checkpoint_path: checkpointPath,
            bit_length: bitLength,
            method: 'cosine',
          }),
        ])
        setHammingResults(hamming)
        setCosineResults(cosine)
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Search failed'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  const handleBuildIndex = async () => {
    setBuildingIndex(true)
    setError(null)
    try {
      const job = await createIndexBuildJob({
        run_id: 1,
        checkpoint: 'best',
      })
      setBuildJob(job)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Failed to build index'
      setError(msg)
      setBuildingIndex(false)
    }
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold text-foreground">Cross-Modal Search Demo</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Search images by text or find similar texts by image using learned hash codes.
        </p>
      </div>

      {/* Index Management */}
      <div className="rounded-lg border border-border bg-card p-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-card-foreground">Search Index</h3>
          <button
            type="button"
            onClick={loadIndexJobs}
            className="text-xs text-muted-foreground hover:text-foreground"
          >
            <RefreshCw className="h-3 w-3" />
          </button>
        </div>

        <div className="mt-3 grid gap-3 sm:grid-cols-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              Index Path
            </label>
            <input
              type="text"
              value={indexPath}
              onChange={(e) => setIndexPath(e.target.value)}
              className="w-full rounded-md border border-border bg-background px-3 py-1.5 text-xs"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              Checkpoint Path
            </label>
            <input
              type="text"
              value={checkpointPath}
              onChange={(e) => setCheckpointPath(e.target.value)}
              className="w-full rounded-md border border-border bg-background px-3 py-1.5 text-xs"
            />
          </div>
          <div className="flex items-end">
            <button
              type="button"
              onClick={handleBuildIndex}
              disabled={buildingIndex}
              className="flex items-center gap-2 rounded-md border border-border px-4 py-1.5 text-xs font-medium text-card-foreground transition-colors hover:bg-accent disabled:opacity-50"
            >
              {buildingIndex ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Play className="h-3.5 w-3.5" />
              )}
              Build Search Index
            </button>
          </div>
        </div>

        {/* Build progress */}
        {buildJob && (buildJob.status === 'running' || buildJob.status === 'pending') && (
          <div className="mt-3">
            <div className="mb-1 flex items-center justify-between text-xs text-muted-foreground">
              <span>Building index...</span>
              <span className="tabular-nums">{buildJob.progress}%</span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-primary transition-all duration-500"
                style={{ width: `${buildJob.progress}%` }}
              />
            </div>
          </div>
        )}

        {/* Recent index builds */}
        {indexJobs.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {indexJobs.slice(0, 3).map((job) => (
              <span
                key={job.id}
                className={cn(
                  'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium',
                  job.status === 'completed'
                    ? 'bg-green-500/10 text-green-600'
                    : job.status === 'failed'
                      ? 'bg-red-500/10 text-red-600'
                      : 'bg-yellow-500/10 text-yellow-600',
                )}
              >
                Index #{job.id}: {job.status}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Search Controls */}
      <div className="rounded-lg border border-border bg-card p-4">
        {/* Mode Toggle */}
        <div className="mb-4 flex gap-1 rounded-lg bg-muted p-1">
          <button
            type="button"
            onClick={() => setMode('text')}
            className={cn(
              'flex flex-1 items-center justify-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-colors',
              mode === 'text'
                ? 'bg-background text-foreground shadow-sm'
                : 'text-muted-foreground hover:text-foreground',
            )}
          >
            <Type className="h-4 w-4" />
            Text to Image
          </button>
          <button
            type="button"
            onClick={() => setMode('image')}
            className={cn(
              'flex flex-1 items-center justify-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-colors',
              mode === 'image'
                ? 'bg-background text-foreground shadow-sm'
                : 'text-muted-foreground hover:text-foreground',
            )}
          >
            <ImageIcon className="h-4 w-4" />
            Image to Text
          </button>
        </div>

        {/* Text Input */}
        {mode === 'text' && (
          <div className="space-y-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <input
                type="text"
                placeholder="Enter a text query..."
                value={textQuery}
                onChange={(e) => setTextQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                className="w-full rounded-lg border border-border bg-background py-2.5 pl-10 pr-4 text-sm"
              />
            </div>

            {/* Sample Queries */}
            <div className="flex flex-wrap gap-1.5">
              {SAMPLE_QUERIES.map((sq) => (
                <button
                  key={sq.label}
                  type="button"
                  onClick={() => {
                    setTextQuery(sq.label)
                  }}
                  className="inline-flex items-center gap-1 rounded-full border border-border px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                >
                  <span className="text-[10px] font-bold text-primary/60">{sq.lang}</span>
                  {sq.label}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Image Upload */}
        {mode === 'image' && (
          <div className="space-y-3">
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              onChange={handleImageSelect}
              className="hidden"
            />
            {imagePreview ? (
              <div className="relative inline-block">
                <img
                  src={imagePreview}
                  alt="Query"
                  className="h-32 w-32 rounded-lg border border-border object-cover"
                />
                <button
                  type="button"
                  onClick={() => {
                    setImageFile(null)
                    setImagePreview(null)
                  }}
                  className="absolute -right-2 -top-2 rounded-full bg-destructive p-1 text-destructive-foreground"
                >
                  <X className="h-3 w-3" />
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="flex h-32 w-full items-center justify-center rounded-lg border-2 border-dashed border-border transition-colors hover:border-primary hover:bg-primary/5"
              >
                <div className="text-center">
                  <Upload className="mx-auto h-6 w-6 text-muted-foreground" />
                  <p className="mt-1 text-xs text-muted-foreground">Upload an image</p>
                </div>
              </button>
            )}
          </div>
        )}

        {/* Bit Length Selector + Search Button */}
        <div className="mt-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Hash className="h-4 w-4 text-muted-foreground" />
            <span className="text-xs text-muted-foreground">Bit length:</span>
            <div className="flex gap-1">
              {BIT_OPTIONS.map((bit) => (
                <button
                  key={bit}
                  type="button"
                  onClick={() => setBitLength(bit)}
                  className={cn(
                    'rounded-md px-2.5 py-1 text-xs font-medium transition-colors',
                    bitLength === bit
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-muted text-muted-foreground hover:text-foreground',
                  )}
                >
                  {bit}
                </button>
              ))}
            </div>
          </div>

          <button
            type="button"
            onClick={handleSearch}
            disabled={loading || (mode === 'text' ? !textQuery.trim() : !imageFile)}
            className="flex items-center gap-2 rounded-md bg-primary px-5 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
            Search
          </button>
        </div>

        {error && (
          <div className="mt-3 flex items-center gap-2 text-xs text-red-500">
            <AlertCircle className="h-3.5 w-3.5" />
            {error}
          </div>
        )}
      </div>

      {/* Results: Side-by-side Hamming vs Cosine */}
      {(hammingResults || cosineResults) && (
        <div className="grid gap-4 lg:grid-cols-2">
          {METHODS.map((method) => {
            const results = method === 'hamming' ? hammingResults : cosineResults
            if (!results) return null
            return (
              <ResultsPanel key={method} method={method} response={results} mode={mode} />
            )
          })}
        </div>
      )}
    </div>
  )
}

// --- Results Panel ---

function ResultsPanel({
  method,
  response,
  mode,
}: {
  method: string
  response: SearchResponse
  mode: 'text' | 'image'
}) {
  const isHamming = method === 'hamming'

  return (
    <div className="rounded-lg border border-border bg-card">
      <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
        <div className="flex items-center gap-2">
          <span
            className={cn(
              'inline-flex rounded-full px-2 py-0.5 text-[10px] font-bold uppercase',
              isHamming
                ? 'bg-blue-500/10 text-blue-600'
                : 'bg-purple-500/10 text-purple-600',
            )}
          >
            {method}
          </span>
          <span className="text-xs font-medium text-card-foreground">
            {response.bit_length}-bit
          </span>
        </div>
        <div className="flex items-center gap-1 text-xs text-muted-foreground">
          <Clock className="h-3 w-3" />
          {response.search_time_ms.toFixed(1)}ms
        </div>
      </div>

      <div className="divide-y divide-border">
        {response.results.length === 0 ? (
          <div className="flex h-32 items-center justify-center text-xs text-muted-foreground">
            No results found
          </div>
        ) : mode === 'text' ? (
          // Text→Image: show thumbnails grid
          <div className="grid grid-cols-4 gap-2 p-3">
            {response.results.map((r) => (
              <ImageResult key={r.rank} result={r} isHamming={isHamming} />
            ))}
          </div>
        ) : (
          // Image→Text: show text list
          <div className="p-3">
            {response.results.map((r) => (
              <TextResult key={r.rank} result={r} isHamming={isHamming} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function ImageResult({ result, isHamming }: { result: SearchResult; isHamming: boolean }) {
  return (
    <div className="group relative overflow-hidden rounded-md border border-border bg-muted">
      {result.thumbnail_b64 ? (
        <img
          src={`data:image/jpeg;base64,${result.thumbnail_b64}`}
          alt={result.caption || `Result #${result.rank}`}
          className="aspect-square w-full object-cover"
        />
      ) : (
        <div className="flex aspect-square items-center justify-center bg-muted">
          <ImageIcon className="h-6 w-6 text-muted-foreground" />
        </div>
      )}
      <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/70 to-transparent p-1.5">
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-bold text-white">#{result.rank}</span>
          <span className={cn(
            'text-[10px] tabular-nums',
            isHamming ? 'text-blue-300' : 'text-purple-300',
          )}>
            {isHamming ? `d=${result.score.toFixed(0)}` : result.score.toFixed(3)}
          </span>
        </div>
      </div>
      {result.caption && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/70 p-2 opacity-0 transition-opacity group-hover:opacity-100">
          <p className="text-center text-[10px] leading-tight text-white">{result.caption}</p>
        </div>
      )}
    </div>
  )
}

function TextResult({ result, isHamming }: { result: SearchResult; isHamming: boolean }) {
  return (
    <div className="flex items-center gap-3 rounded-md px-2 py-1.5 transition-colors hover:bg-muted/50">
      <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-muted text-[10px] font-bold text-muted-foreground">
        {result.rank}
      </span>
      <p className="flex-1 text-xs text-card-foreground">
        {result.caption || `Item #${result.index}`}
      </p>
      <span
        className={cn(
          'text-[10px] tabular-nums',
          isHamming ? 'text-blue-600' : 'text-purple-600',
        )}
      >
        {isHamming ? `d=${result.score.toFixed(0)}` : result.score.toFixed(3)}
      </span>
    </div>
  )
}
