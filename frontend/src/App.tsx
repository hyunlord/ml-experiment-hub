import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import DashboardPage from './pages/DashboardPage'
import ExperimentListPage from './pages/ExperimentListPage'
import ExperimentCreatePage from './pages/ExperimentCreatePage'
import ExperimentDetailPage from './pages/ExperimentDetailPage'
import RunMonitorPage from './pages/RunMonitorPage'
import ExperimentComparePage from './pages/ExperimentComparePage'
import SchemasPage from './pages/SchemasPage'
import SettingsPage from './pages/SettingsPage'
import RunningPage from './pages/RunningPage'
import SearchDemoPage from './pages/SearchDemoPage'
import HyperparamListPage from './pages/HyperparamListPage'
import HyperparamSearchPage from './pages/HyperparamSearchPage'
import QueuePage from './pages/QueuePage'
import DatasetsPage from './pages/DatasetsPage'

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/experiments" element={<ExperimentListPage />} />
        <Route path="/experiments/new" element={<ExperimentCreatePage />} />
        <Route path="/experiments/:id/edit" element={<ExperimentCreatePage />} />
        <Route path="/experiments/:id" element={<ExperimentDetailPage />} />
        <Route path="/runs/:runId" element={<RunMonitorPage />} />
        <Route path="/compare" element={<ExperimentComparePage />} />
        <Route path="/experiments/compare" element={<ExperimentComparePage />} />
        <Route path="/running" element={<RunningPage />} />
        <Route path="/hyperparam" element={<HyperparamListPage />} />
        <Route path="/hyperparam/new" element={<HyperparamSearchPage />} />
        <Route path="/hyperparam/:studyId" element={<HyperparamSearchPage />} />
        <Route path="/queue" element={<QueuePage />} />
        <Route path="/datasets" element={<DatasetsPage />} />
        <Route path="/schemas" element={<SchemasPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/demo/search" element={<SearchDemoPage />} />
      </Routes>
    </Layout>
  )
}

export default App
