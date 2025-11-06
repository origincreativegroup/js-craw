import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import Discovery from './pages/Discovery';
import Jobs from './pages/Jobs';
import Tasks from './pages/Tasks';
import FollowUps from './pages/FollowUps';
import Companies from './pages/Companies';
import CareerHub from './pages/CareerHub';
import AutomationControl from './pages/AutomationControl';
import './App.css';

function App() {
  return (
    <Router>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/discovery" element={<Discovery />} />
          <Route path="/jobs" element={<Jobs />} />
          <Route path="/career-hub" element={<CareerHub />} />
          {/* Redirect old routes to unified Career Hub for backward compatibility */}
          <Route path="/apply" element={<Navigate to="/career-hub" replace />} />
          <Route path="/copilot" element={<Navigate to="/career-hub" replace />} />
          <Route path="/filter-profile" element={<Navigate to="/career-hub" replace />} />
          <Route path="/tasks" element={<Tasks />} />
          <Route path="/follow-ups" element={<FollowUps />} />
          <Route path="/companies" element={<Companies />} />
          <Route path="/automation-control" element={<AutomationControl />} />
          {/* Redirect old routes to unified Automation Control for backward compatibility */}
          <Route path="/company-discovery" element={<Navigate to="/automation-control" replace />} />
          <Route path="/automation" element={<Navigate to="/automation-control" replace />} />
          <Route path="/settings" element={<Navigate to="/automation-control" replace />} />
        </Routes>
      </Layout>
    </Router>
  );
}

export default App;

