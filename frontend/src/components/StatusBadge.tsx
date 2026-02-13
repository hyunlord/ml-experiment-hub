import { ExperimentStatus } from '@/types/experiment'
import { cn } from '@/lib/utils'

interface StatusBadgeProps {
  status: ExperimentStatus | string
}

const statusStyles: Record<string, string> = {
  [ExperimentStatus.DRAFT]: 'bg-gray-500/20 text-gray-300 border-gray-500/30',
  [ExperimentStatus.QUEUED]: 'bg-yellow-500/20 text-yellow-300 border-yellow-500/30',
  [ExperimentStatus.RUNNING]: 'bg-blue-500/20 text-blue-300 border-blue-500/30',
  [ExperimentStatus.COMPLETED]: 'bg-green-500/20 text-green-300 border-green-500/30',
  [ExperimentStatus.FAILED]: 'bg-red-500/20 text-red-300 border-red-500/30',
  [ExperimentStatus.CANCELLED]: 'bg-orange-500/20 text-orange-300 border-orange-500/30',
}

export default function StatusBadge({ status }: StatusBadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold uppercase transition-colors',
        statusStyles[status] ?? 'bg-gray-500/20 text-gray-300 border-gray-500/30'
      )}
    >
      {status}
    </span>
  )
}
