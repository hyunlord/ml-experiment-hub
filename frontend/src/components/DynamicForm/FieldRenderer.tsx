import type { FieldProps } from '@/types/schema'
import {
  TextField,
  NumberField,
  SelectField,
  MultiSelectField,
  SliderField,
  BooleanField,
  JsonField,
  ArrayField,
} from './fields'

const FIELD_MAP: Record<string, React.ComponentType<FieldProps>> = {
  text: TextField,
  number: NumberField,
  select: SelectField,
  multi_select: MultiSelectField,
  slider: SliderField,
  boolean: BooleanField,
  json: JsonField,
  array: ArrayField,
}

export default function FieldRenderer(props: FieldProps) {
  const Component = FIELD_MAP[props.field.type] ?? TextField
  return <Component {...props} />
}
