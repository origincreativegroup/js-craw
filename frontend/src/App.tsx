import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import JobPipeline from './pages/JobPipeline';
import Jobs from './pages/Jobs';
import Tasks from './pages/Tasks';
import Companies from './pages/Companies';
import CareerHub from './pages/CareerHub';
import AutomationControl from './pages/AutomationControl';
import { WorkflowProvider } from './contexts/WorkflowContext';
import './App.css';

function App() {
  return (
    <Router>
      <WorkflowProvider>
        <Layout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/pipeline" element={<JobPipeline />} />
            <Route path="/jobs" element={<Navigate to="/pipeline" replace />} />
            <Route path="/career-hub" element={<CareerHub />} />
            {/* Redirect old routes to unified Career Hub for backward compatibility */}
            <Route path="/apply" element={<Navigate to="/career-hub" replace />} />
            <Route path="/copilot" element={<Navigate to="/career-hub" replace />} />
            <Route path="/filter-profile" element={<Navigate to="/career-hub" replace />} />
            <Route path="/tasks" element={<Navigate to="/pipeline" replace />} />
            <Route path="/follow-ups" element={<Navigate to="/pipeline" replace />} />
            <Route path="/discovery" element={<Navigate to="/pipeline" replace />} />
            <Route path="/companies" element={<Companies />} />
            <Route path="/automation-control" element={<AutomationControl />} />
            {/* Redirect old routes to unified Automation Control for backward compatibility */}
            <Route path="/company-discovery" element={<Navigate to="/automation-control" replace />} />
            <Route path="/automation" element={<Navigate to="/automation-control" replace />} />
            <Route path="/settings" element={<Navigate to="/automation-control" replace />} />
          </Routes>
        </Layout>
      </WorkflowProvider>
    </Router>
  );
}

export default App;

