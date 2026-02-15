import { useEffect, useState } from 'react'
import { Plus, Trash2, Wrench } from 'lucide-react'
import axios from 'axios'
import { formatAbsoluteTime } from '@/utils/time'

interface ConfigSchemaItem {
  id: number
  name: string
  description: string
  fields_schema: { fields?: unknown[]; groups_order?: string[] }
  created_at: string
  updated_at: string
}

const API = '/api/schemas'

export default function SchemasPage() {
  const [schemas, setSchemas] = useState<ConfigSchemaItem[]>([])
  const [loading, setLoading] = useState(true)

  const load = async () => {
    setLoading(true)
    try {
      const res = await axios.get(API)
      setSchemas(res.data.schemas ?? [])
    } catch {
      // API may not be running yet
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const handleDelete = async (id: number) => {
    if (!confirm('Delete this schema?')) return
    try {
      await axios.delete(`${API}/${id}`)
      setSchemas((prev) => prev.filter((s) => s.id !== id))
    } catch {
      // ignore
    }
  }

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <p className="text-muted-foreground">Loading schemas...</p>
      </div>
    )
  }

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          Manage config schema templates for experiment form generation
        </p>
        <button className="flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90">
          <Plus className="h-4 w-4" />
          New Schema
        </button>
      </div>

      {schemas.length === 0 ? (
        <div className="flex h-64 flex-col items-center justify-center rounded-lg border border-dashed border-border">
          <Wrench className="mb-3 h-12 w-12 text-muted-foreground/40" />
          <p className="text-lg font-medium text-muted-foreground">
            No schemas yet
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            Run the seed script to create the first schema
          </p>
          <code className="mt-3 rounded bg-secondary px-3 py-1 text-xs text-secondary-foreground">
            python -m backend.seeds.vlm_quantization
          </code>
        </div>
      ) : (
        <div className="space-y-3">
          {schemas.map((schema) => {
            const fieldCount = Array.isArray(schema.fields_schema?.fields)
              ? schema.fields_schema.fields.length
              : 0
            const groups = schema.fields_schema?.groups_order ?? []

            return (
              <div
                key={schema.id}
                className="rounded-lg border border-border bg-card p-4"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="font-semibold text-card-foreground">
                      {schema.name}
                    </h3>
                    {schema.description && (
                      <p className="mt-1 text-sm text-muted-foreground">
                        {schema.description}
                      </p>
                    )}
                    <div className="mt-2 flex items-center gap-4 text-xs text-muted-foreground">
                      <span>{fieldCount} fields</span>
                      {groups.length > 0 && (
                        <span>{groups.join(' / ')}</span>
                      )}
                      <span>
                        Updated {formatAbsoluteTime(schema.updated_at)}
                      </span>
                    </div>
                  </div>
                  <button
                    onClick={() => handleDelete(schema.id)}
                    className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
                    aria-label="Delete schema"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
