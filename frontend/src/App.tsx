import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import Discovery from './pages/Discovery';
import Jobs from './pages/Jobs';
import Tasks from './pages/Tasks';
import FollowUps from './pages/FollowUps';
import Companies from './pages/Companies';
import CompanyDiscovery from './pages/CompanyDiscovery';
import Automation from './pages/Automation';
import Settings from './pages/Settings';
import Apply from './pages/Apply';
import FilterProfile from './pages/FilterProfile';
import CareerCopilot from './pages/CareerCopilot';
import './App.css';

function App() {
  return (
    <Router>
      <Layout>
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/discovery" element={<Discovery />} />
          <Route path="/jobs" element={<Jobs />} />
          <Route path="/apply" element={<Apply />} />
          <Route path="/copilot" element={<CareerCopilot />} />
          <Route path="/tasks" element={<Tasks />} />
          <Route path="/follow-ups" element={<FollowUps />} />
          <Route path="/companies" element={<Companies />} />
          <Route path="/company-discovery" element={<CompanyDiscovery />} />
          <Route path="/automation" element={<Automation />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/filter-profile" element={<FilterProfile />} />
        </Routes>
      </Layout>
    </Router>
  );
}

export default App;

