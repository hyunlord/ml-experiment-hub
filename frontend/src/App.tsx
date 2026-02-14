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
        <Route path="/schemas" element={<SchemasPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Routes>
    </Layout>
  )
}

export default App
