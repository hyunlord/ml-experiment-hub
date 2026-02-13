import { create } from 'zustand'
import type { Experiment, ExperimentRun, MetricLog } from '@/types/experiment'
import { RunStatus } from '@/types/experiment'
import * as api from '@/api/experiments'

interface ExperimentStore {
  experiments: Experiment[]
  selectedExperiment: Experiment | null
  runs: ExperimentRun[]
  metrics: MetricLog[]
  loading: boolean
  error: string | null

  fetchExperiments: (params?: { skip?: number; limit?: number; status?: string }) => Promise<void>
  fetchExperiment: (id: number | string) => Promise<void>
  createExperiment: (data: { name: string; description?: string; config?: Record<string, unknown>; schema_id?: number | null; tags?: string[] }) => Promise<Experiment>
  updateExperiment: (id: number | string, data: { name?: string; description?: string; config?: Record<string, unknown>; tags?: string[] }) => Promise<void>
  deleteExperiment: (id: number | string) => Promise<void>
  cloneExperiment: (id: number | string) => Promise<Experiment>
  startRun: (experimentId: number | string) => Promise<ExperimentRun>
  stopRun: (runId: number | string) => Promise<void>
  fetchRuns: (experimentId: number | string) => Promise<void>
  fetchRunMetrics: (runId: number | string) => Promise<void>
  addMetricLog: (metric: MetricLog) => void
  clearMetrics: () => void
}

export const useExperimentStore = create<ExperimentStore>((set) => ({
  experiments: [],
  selectedExperiment: null,
  runs: [],
  metrics: [],
  loading: false,
  error: null,

  fetchExperiments: async (params) => {
    set({ loading: true, error: null })
    try {
      const response = await api.getExperiments(params)
      set({ experiments: response.experiments, loading: false })
    } catch (error) {
      set({ error: String(error), loading: false })
    }
  },

  fetchExperiment: async (id) => {
    set({ loading: true, error: null })
    try {
      const experiment = await api.getExperiment(id)
      set({ selectedExperiment: experiment, loading: false })
    } catch (error) {
      set({ error: String(error), loading: false })
    }
  },

  createExperiment: async (data) => {
    set({ loading: true, error: null })
    try {
      const experiment = await api.createExperiment(data)
      set((state) => ({
        experiments: [...state.experiments, experiment],
        loading: false,
      }))
      return experiment
    } catch (error) {
      set({ error: String(error), loading: false })
      throw error
    }
  },

  updateExperiment: async (id, data) => {
    const numId = Number(id)
    set({ loading: true, error: null })
    try {
      const experiment = await api.updateExperiment(id, data)
      set((state) => ({
        experiments: state.experiments.map((exp) =>
          exp.id === numId ? experiment : exp
        ),
        selectedExperiment:
          state.selectedExperiment?.id === numId ? experiment : state.selectedExperiment,
        loading: false,
      }))
    } catch (error) {
      set({ error: String(error), loading: false })
    }
  },

  deleteExperiment: async (id) => {
    const numId = Number(id)
    set({ loading: true, error: null })
    try {
      await api.deleteExperiment(id)
      set((state) => ({
        experiments: state.experiments.filter((exp) => exp.id !== numId),
        loading: false,
      }))
    } catch (error) {
      set({ error: String(error), loading: false })
    }
  },

  cloneExperiment: async (id) => {
    set({ loading: true, error: null })
    try {
      const clone = await api.cloneExperiment(id)
      set((state) => ({
        experiments: [...state.experiments, clone],
        loading: false,
      }))
      return clone
    } catch (error) {
      set({ error: String(error), loading: false })
      throw error
    }
  },

  startRun: async (experimentId) => {
    set({ loading: true, error: null })
    try {
      const run = await api.startRun(experimentId)
      set((state) => ({
        runs: [...state.runs, run],
        loading: false,
      }))
      // Refresh experiment to get updated status
      const numId = Number(experimentId)
      try {
        const updated = await api.getExperiment(experimentId)
        set((state) => ({
          experiments: state.experiments.map((exp) =>
            exp.id === numId ? updated : exp
          ),
          selectedExperiment:
            state.selectedExperiment?.id === numId ? updated : state.selectedExperiment,
        }))
      } catch { /* ignore refresh failure */ }
      return run
    } catch (error) {
      set({ error: String(error), loading: false })
      throw error
    }
  },

  stopRun: async (runId) => {
    set({ loading: true, error: null })
    try {
      await api.stopRun(runId)
      const numId = Number(runId)
      set((state) => ({
        runs: state.runs.map((r) =>
          r.id === numId ? { ...r, status: 'cancelled' as RunStatus } : r
        ),
        loading: false,
      }))
    } catch (error) {
      set({ error: String(error), loading: false })
    }
  },

  fetchRuns: async (experimentId) => {
    set({ loading: true, error: null })
    try {
      const runs = await api.getExperimentRuns(experimentId)
      set({ runs, loading: false })
    } catch (error) {
      set({ error: String(error), loading: false })
    }
  },

  fetchRunMetrics: async (runId) => {
    set({ loading: true, error: null })
    try {
      const metrics = await api.getRunMetrics(runId)
      set({ metrics, loading: false })
    } catch (error) {
      set({ error: String(error), loading: false })
    }
  },

  addMetricLog: (metric) => {
    set((state) => ({
      metrics: [...state.metrics, metric],
    }))
  },

  clearMetrics: () => {
    set({ metrics: [] })
  },
}))
