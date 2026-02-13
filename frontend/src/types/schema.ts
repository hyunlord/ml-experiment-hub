/** Field types supported by the DynamicForm renderer. */
export type FieldType =
  | 'text'
  | 'number'
  | 'select'
  | 'multi_select'
  | 'boolean'
  | 'slider'
  | 'json'
  | 'array'

/** Single field definition inside a ConfigSchema. */
export interface FieldDef {
  key: string // dot-notation key, e.g. "model.backbone"
  type: FieldType
  label?: string
  description?: string
  group?: string
  required?: boolean
  default_value?: unknown

  // type-specific constraints
  options?: string[] // select / multi_select
  min?: number // number / slider
  max?: number // number / slider
  step?: number // number / slider
  placeholder?: string // text
  items_type?: FieldType // array item type
}

/** Schema definition (the "fields_schema" from backend ConfigSchema). */
export interface SchemaDefinition {
  fields: FieldDef[]
  groups_order?: string[]
}

/** Full ConfigSchema as returned by the backend API. */
export interface ConfigSchema {
  id: number
  name: string
  description: string
  fields_schema: SchemaDefinition
  created_at: string
  updated_at: string
}

/** Props for the top-level DynamicForm component. */
export interface DynamicFormProps {
  schema: SchemaDefinition | null // null = free-form mode
  values: Record<string, unknown>
  onChange: (key: string, value: unknown) => void
  onAddField?: (field: FieldDef) => void // free-form mode
  disabled?: boolean
}

/** Common props shared by every field renderer. */
export interface FieldProps {
  field: FieldDef
  value: unknown
  onChange: (value: unknown) => void
  disabled?: boolean
}
