import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import ExperimentListPage from './pages/ExperimentListPage'
import ExperimentCreatePage from './pages/ExperimentCreatePage'
import ExperimentDetailPage from './pages/ExperimentDetailPage'

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<ExperimentListPage />} />
        <Route path="/experiments/new" element={<ExperimentCreatePage />} />
        <Route path="/experiments/:id" element={<ExperimentDetailPage />} />
      </Routes>
    </Layout>
  )
}

export default App
