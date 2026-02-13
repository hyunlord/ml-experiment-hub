import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import ExperimentsPage from './pages/ExperimentsPage'
import ExperimentCreatePage from './pages/ExperimentCreatePage'
import ExperimentDetailPage from './pages/ExperimentDetailPage'

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<ExperimentsPage />} />
        <Route path="/experiments/new" element={<ExperimentCreatePage />} />
        <Route path="/experiments/:id" element={<ExperimentDetailPage />} />
      </Routes>
    </Layout>
  )
}

export default App
