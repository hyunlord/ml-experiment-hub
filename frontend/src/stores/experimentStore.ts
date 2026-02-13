import { create } from 'zustand'
import type { Experiment, MetricPoint } from '@/types/experiment'
import * as api from '@/api/experiments'

interface ExperimentStore {
  experiments: Experiment[]
  selectedExperiment: Experiment | null
  metrics: MetricPoint[]
  loading: boolean
  error: string | null

  fetchExperiments: (params?: { skip?: number; limit?: number; status?: string }) => Promise<void>
  fetchExperiment: (id: string) => Promise<void>
  createExperiment: (data: { name: string; description?: string; framework: string; script_path: string; hyperparameters: Record<string, unknown> }) => Promise<Experiment>
  updateExperiment: (id: string, data: Partial<{ name: string; description?: string; framework: string; hyperparameters: Record<string, unknown> }>) => Promise<void>
  deleteExperiment: (id: string) => Promise<void>
  startExperiment: (id: string) => Promise<void>
  stopExperiment: (id: string) => Promise<void>
  fetchMetrics: (id: string) => Promise<void>
  addMetricPoint: (metric: MetricPoint) => void
  clearMetrics: () => void
}

export const useExperimentStore = create<ExperimentStore>((set) => ({
  experiments: [],
  selectedExperiment: null,
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

  startExperiment: async (id) => {
    const numId = Number(id)
    set({ loading: true, error: null })
    try {
      const experiment = await api.startExperiment(id)
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

  stopExperiment: async (id) => {
    const numId = Number(id)
    set({ loading: true, error: null })
    try {
      const experiment = await api.stopExperiment(id)
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

  fetchMetrics: async (id) => {
    set({ loading: true, error: null })
    try {
      const metrics = await api.getExperimentMetrics(id)
      set({ metrics, loading: false })
    } catch (error) {
      set({ error: String(error), loading: false })
    }
  },

  addMetricPoint: (metric) => {
    set((state) => ({
      metrics: [...state.metrics, metric],
    }))
  },

  clearMetrics: () => {
    set({ metrics: [] })
  },
}))
