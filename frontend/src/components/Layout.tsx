import { ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { 
  LayoutDashboard, 
  Briefcase, 
  Building2, 
  Sparkles,
  Zap
} from 'lucide-react';
import './Layout.css';

interface LayoutProps {
  children: ReactNode;
}

const Layout = ({ children }: LayoutProps) => {
  const location = useLocation();

  const navItems = [
    { path: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
    { path: '/pipeline', icon: Briefcase, label: 'Pipeline' },
    { path: '/career-hub', icon: Briefcase, label: 'Career Hub' },
    { path: '/companies', icon: Building2, label: 'Companies' },
    { path: '/automation-control', icon: Zap, label: 'Automation Control' },
  ];

  // Check if current path matches career hub or old routes
  const isCareerHubActive = location.pathname === '/career-hub' || 
    location.pathname === '/apply' || 
    location.pathname === '/copilot' || 
    location.pathname === '/filter-profile';

  // Check if current path matches automation control or old routes
  const isAutomationControlActive = location.pathname === '/automation-control' || 
    location.pathname === '/automation' || 
    location.pathname === '/company-discovery' || 
    location.pathname === '/settings';

  // Check if current path matches pipeline or old workflow routes
  const isPipelineActive = location.pathname === '/pipeline' ||
    location.pathname === '/jobs' ||
    location.pathname === '/tasks' ||
    location.pathname === '/follow-ups' ||
    location.pathname === '/discovery';

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="logo">
            <Sparkles className="logo-icon" />
            <span className="logo-text">Job Crawler</span>
          </div>
          <div className="logo-subtitle">AI-Powered</div>
        </div>
        <nav className="sidebar-nav">
          {navItems.map((item) => {
            const Icon = item.icon;
            let isActive = false;
            if (item.path === '/career-hub') {
              isActive = isCareerHubActive;
            } else if (item.path === '/automation-control') {
              isActive = isAutomationControlActive;
            } else if (item.path === '/pipeline') {
              isActive = isPipelineActive;
            } else {
              isActive = location.pathname === item.path;
            }
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`nav-item ${isActive ? 'active' : ''}`}
              >
                <Icon className="nav-icon" />
                <span className="nav-label">{item.label}</span>
              </Link>
            );
          })}
        </nav>
      </aside>
      <main className="main-content">
        <div className="content-wrapper">
          {children}
        </div>
      </main>
    </div>
  );
};

export default Layout;

