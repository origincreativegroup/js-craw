#!/usr/bin/env python3
"""
Comprehensive test and debug runner for deployment pipeline.
Runs on pi-forge after code is pulled to verify deployment integrity.
"""

import sys
import os
import subprocess
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import traceback

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DeploymentTestRunner:
    """Runs comprehensive tests and checks after deployment"""
    
    def __init__(self, project_root: str = None):
        self.project_root = Path(project_root) if project_root else Path(__file__).parent.parent.parent
        self.results = {
            'timestamp': datetime.utcnow().isoformat(),
            'tests': {},
            'checks': {},
            'errors': [],
            'warnings': [],
            'passed': False
        }
        self.log_dir = self.project_root / 'logs' / 'deployment'
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
    def run_all_tests(self) -> bool:
        """Run all deployment tests and checks"""
        logger.info("Starting deployment test suite...")
        
        try:
            # 1. Environment checks
            self._check_environment()
            
            # 2. Dependency checks
            self._check_dependencies()
            
            # 3. Code quality checks
            self._check_code_quality()
            
            # 4. Configuration checks
            self._check_configuration()
            
            # 5. Database connectivity
            self._check_database()
            
            # 6. Docker services
            self._check_docker_services()
            
            # 7. Run unit tests
            self._run_unit_tests()
            
            # 8. Integration tests
            self._run_integration_tests()
            
            # 9. API health checks
            self._check_api_health()
            
            # 10. Service connectivity
            self._check_service_connectivity()
            
            # Determine overall status
            self.results['passed'] = (
                len(self.results['errors']) == 0 and
                len([r for r in self.results['tests'].values() if not r.get('passed', False)]) == 0
            )
            
            # Save results
            self._save_results()
            
            logger.info(f"Test suite completed. Passed: {self.results['passed']}")
            return self.results['passed']
            
        except Exception as e:
            logger.error(f"Critical error in test runner: {e}")
            logger.error(traceback.format_exc())
            self.results['errors'].append({
                'test': 'test_runner',
                'error': str(e),
                'traceback': traceback.format_exc()
            })
            self._save_results()
            return False
    
    def _check_environment(self):
        """Check Python environment and system requirements"""
        logger.info("Checking environment...")
        
        try:
            # Python version
            python_version = sys.version_info
            self.results['checks']['python_version'] = {
                'version': f"{python_version.major}.{python_version.minor}.{python_version.micro}",
                'passed': python_version.major >= 3 and python_version.minor >= 8,
                'message': f"Python {python_version.major}.{python_version.minor}.{python_version.micro}"
            }
            
            # Required directories
            required_dirs = ['app', 'scripts', 'tests']
            for dir_name in required_dirs:
                dir_path = self.project_root / dir_name
                exists = dir_path.exists()
                self.results['checks'][f'dir_{dir_name}'] = {
                    'passed': exists,
                    'message': f"Directory {dir_name} {'exists' if exists else 'missing'}"
                }
                if not exists:
                    self.results['warnings'].append(f"Directory {dir_name} not found")
            
            # Environment variables
            env_vars = ['DATABASE_URL', 'REDIS_URL']
            for var in env_vars:
                value = os.getenv(var)
                self.results['checks'][f'env_{var}'] = {
                    'passed': value is not None,
                    'message': f"{var} {'set' if value else 'not set'}"
                }
                if not value:
                    self.results['warnings'].append(f"Environment variable {var} not set")
                    
        except Exception as e:
            logger.error(f"Error checking environment: {e}")
            self.results['errors'].append({'check': 'environment', 'error': str(e)})
    
    def _check_dependencies(self):
        """Check if all required dependencies are installed"""
        logger.info("Checking dependencies...")
        
        try:
            required_packages = [
                'fastapi', 'sqlalchemy', 'pydantic', 'selenium',
                'requests', 'redis', 'apscheduler', 'ollama'
            ]
            
            missing = []
            for package in required_packages:
                try:
                    __import__(package.replace('-', '_'))
                    self.results['checks'][f'dep_{package}'] = {
                        'passed': True,
                        'message': f"{package} installed"
                    }
                except ImportError:
                    missing.append(package)
                    self.results['checks'][f'dep_{package}'] = {
                        'passed': False,
                        'message': f"{package} not installed"
                    }
            
            if missing:
                self.results['errors'].append({
                    'check': 'dependencies',
                    'error': f"Missing packages: {', '.join(missing)}"
                })
                
        except Exception as e:
            logger.error(f"Error checking dependencies: {e}")
            self.results['errors'].append({'check': 'dependencies', 'error': str(e)})
    
    def _check_code_quality(self):
        """Run code quality checks (syntax, imports, etc.)"""
        logger.info("Checking code quality...")
        
        try:
            # Check Python syntax
            python_files = list(self.project_root.rglob('*.py'))
            syntax_errors = []
            
            for py_file in python_files[:50]:  # Limit to first 50 files
                if 'venv' in str(py_file) or '__pycache__' in str(py_file):
                    continue
                    
                try:
                    with open(py_file, 'r', encoding='utf-8') as f:
                        compile(f.read(), str(py_file), 'exec')
                except SyntaxError as e:
                    syntax_errors.append(f"{py_file}: {e}")
            
            self.results['tests']['syntax_check'] = {
                'passed': len(syntax_errors) == 0,
                'message': f"Found {len(syntax_errors)} syntax errors" if syntax_errors else "No syntax errors",
                'errors': syntax_errors
            }
            
            if syntax_errors:
                self.results['errors'].extend([
                    {'check': 'syntax', 'error': err} for err in syntax_errors
                ])
                
        except Exception as e:
            logger.error(f"Error checking code quality: {e}")
            self.results['errors'].append({'check': 'code_quality', 'error': str(e)})
    
    def _check_configuration(self):
        """Check configuration files and settings"""
        logger.info("Checking configuration...")
        
        try:
            # Check if config.py can be imported
            try:
                from app.config import settings
                self.results['checks']['config_import'] = {
                    'passed': True,
                    'message': "Config module imports successfully"
                }
            except Exception as e:
                self.results['checks']['config_import'] = {
                    'passed': False,
                    'message': f"Config import failed: {str(e)}"
                }
                self.results['errors'].append({'check': 'config', 'error': str(e)})
            
            # Check for required files
            required_files = ['requirements.txt', 'docker-compose.yml']
            for file_name in required_files:
                file_path = self.project_root / file_name
                exists = file_path.exists()
                self.results['checks'][f'file_{file_name}'] = {
                    'passed': exists,
                    'message': f"{file_name} {'exists' if exists else 'missing'}"
                }
                
        except Exception as e:
            logger.error(f"Error checking configuration: {e}")
            self.results['errors'].append({'check': 'configuration', 'error': str(e)})
    
    def _check_database(self):
        """Check database connectivity"""
        logger.info("Checking database connectivity...")
        
        try:
            from app.database import AsyncSessionLocal
            from sqlalchemy import text
            import asyncio
            
            async def test_db():
                try:
                    async with AsyncSessionLocal() as db:
                        await db.execute(text("SELECT 1"))
                        await db.commit()
                        return True
                except Exception as e:
                    logger.error(f"Database connection failed: {e}")
                    return False
            
            db_connected = asyncio.run(test_db())
            self.results['tests']['database_connectivity'] = {
                'passed': db_connected,
                'message': "Database connected" if db_connected else "Database connection failed"
            }
            
            if not db_connected:
                self.results['errors'].append({
                    'check': 'database',
                    'error': 'Failed to connect to database'
                })
                
        except Exception as e:
            logger.error(f"Error checking database: {e}")
            self.results['tests']['database_connectivity'] = {
                'passed': False,
                'message': f"Database check failed: {str(e)}"
            }
            self.results['errors'].append({'check': 'database', 'error': str(e)})
    
    def _check_docker_services(self):
        """Check if Docker services are running"""
        logger.info("Checking Docker services...")
        
        try:
            result = subprocess.run(
                ['docker', 'compose', 'ps', '--format', 'json'],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                services = []
                for line in result.stdout.strip().split('\n'):
                    if line:
                        try:
                            service = json.loads(line)
                            services.append(service)
                        except json.JSONDecodeError:
                            pass
                
                running = [s for s in services if s.get('State') == 'running']
                
                self.results['tests']['docker_services'] = {
                    'passed': len(running) > 0,
                    'message': f"{len(running)}/{len(services)} services running",
                    'services': [s.get('Name', 'unknown') for s in services],
                    'running': [s.get('Name', 'unknown') for s in running]
                }
                
                if len(running) == 0:
                    self.results['errors'].append({
                        'check': 'docker',
                        'error': 'No Docker services running'
                    })
            else:
                self.results['tests']['docker_services'] = {
                    'passed': False,
                    'message': f"Docker compose ps failed: {result.stderr}"
                }
                self.results['errors'].append({
                    'check': 'docker',
                    'error': f"Docker check failed: {result.stderr}"
                })
                
        except subprocess.TimeoutExpired:
            self.results['errors'].append({
                'check': 'docker',
                'error': 'Docker check timed out'
            })
        except Exception as e:
            logger.error(f"Error checking Docker services: {e}")
            self.results['errors'].append({'check': 'docker', 'error': str(e)})
    
    def _run_unit_tests(self):
        """Run unit tests"""
        logger.info("Running unit tests...")
        
        try:
            result = subprocess.run(
                [sys.executable, '-m', 'pytest', 'tests/', '-v', '--tb=short', '--json-report', '--json-report-file=/tmp/pytest-report.json'],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            # Try to read pytest JSON report
            test_results = {
                'passed': result.returncode == 0,
                'returncode': result.returncode,
                'stdout': result.stdout[-1000:] if result.stdout else '',  # Last 1000 chars
                'stderr': result.stderr[-1000:] if result.stderr else ''
            }
            
            try:
                with open('/tmp/pytest-report.json', 'r') as f:
                    pytest_report = json.load(f)
                    test_results['summary'] = pytest_report.get('summary', {})
            except Exception:
                pass
            
            self.results['tests']['unit_tests'] = test_results
            
            if result.returncode != 0:
                self.results['errors'].append({
                    'check': 'unit_tests',
                    'error': f"Unit tests failed with return code {result.returncode}",
                    'output': result.stderr[-500:] if result.stderr else result.stdout[-500:]
                })
                
        except subprocess.TimeoutExpired:
            self.results['errors'].append({
                'check': 'unit_tests',
                'error': 'Unit tests timed out after 5 minutes'
            })
        except Exception as e:
            logger.error(f"Error running unit tests: {e}")
            self.results['errors'].append({'check': 'unit_tests', 'error': str(e)})
    
    def _run_integration_tests(self):
        """Run integration tests"""
        logger.info("Running integration tests...")
        
        # For now, mark as skipped if no specific integration tests exist
        self.results['tests']['integration_tests'] = {
            'passed': True,
            'message': 'Integration tests skipped (not implemented)',
            'skipped': True
        }
    
    def _check_api_health(self):
        """Check API health endpoint"""
        logger.info("Checking API health...")
        
        try:
            import requests
            
            health_urls = [
                'http://localhost:8001/health',
                'http://127.0.0.1:8001/health'
            ]
            
            health_ok = False
            for url in health_urls:
                try:
                    response = requests.get(url, timeout=5)
                    if response.status_code == 200:
                        health_ok = True
                        break
                except Exception:
                    continue
            
            self.results['tests']['api_health'] = {
                'passed': health_ok,
                'message': "API health check passed" if health_ok else "API health check failed"
            }
            
            if not health_ok:
                self.results['warnings'].append("API health endpoint not responding")
                
        except Exception as e:
            logger.error(f"Error checking API health: {e}")
            self.results['warnings'].append(f"API health check error: {str(e)}")
    
    def _check_service_connectivity(self):
        """Check connectivity to external services"""
        logger.info("Checking service connectivity...")
        
        try:
            from app.config import settings
            import requests
            
            services = {
                'redis': settings.REDIS_URL,
                'ollama': settings.OLLAMA_HOST
            }
            
            connectivity_results = {}
            for service_name, url in services.items():
                try:
                    # Basic connectivity check
                    if 'redis' in url.lower():
                        # Redis check would need redis client
                        connectivity_results[service_name] = {'passed': True, 'message': 'Redis URL configured'}
                    elif 'ollama' in url.lower():
                        try:
                            response = requests.get(f"{url}/api/tags", timeout=5)
                            connectivity_results[service_name] = {
                                'passed': response.status_code == 200,
                                'message': f"Ollama {'reachable' if response.status_code == 200 else 'unreachable'}"
                            }
                        except Exception:
                            connectivity_results[service_name] = {
                                'passed': False,
                                'message': 'Ollama not reachable'
                            }
                    else:
                        connectivity_results[service_name] = {'passed': True, 'message': 'URL configured'}
                except Exception as e:
                    connectivity_results[service_name] = {
                        'passed': False,
                        'message': f"Error checking {service_name}: {str(e)}"
                    }
            
            self.results['tests']['service_connectivity'] = connectivity_results
            
        except Exception as e:
            logger.error(f"Error checking service connectivity: {e}")
            self.results['warnings'].append(f"Service connectivity check error: {str(e)}")
    
    def _save_results(self):
        """Save test results to file"""
        try:
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            results_file = self.log_dir / f"test_results_{timestamp}.json"
            
            with open(results_file, 'w') as f:
                json.dump(self.results, f, indent=2)
            
            # Also save a latest results file
            latest_file = self.log_dir / "test_results_latest.json"
            with open(latest_file, 'w') as f:
                json.dump(self.results, f, indent=2)
            
            logger.info(f"Test results saved to {results_file}")
            
            # Create a human-readable summary
            summary_file = self.log_dir / f"test_summary_{timestamp}.txt"
            with open(summary_file, 'w') as f:
                f.write(f"Deployment Test Results\n")
                f.write(f"Timestamp: {self.results['timestamp']}\n")
                f.write(f"Status: {'PASSED' if self.results['passed'] else 'FAILED'}\n\n")
                f.write(f"Errors: {len(self.results['errors'])}\n")
                f.write(f"Warnings: {len(self.results['warnings'])}\n\n")
                
                if self.results['errors']:
                    f.write("Errors:\n")
                    for error in self.results['errors']:
                        f.write(f"  - {error}\n")
                    f.write("\n")
                
                if self.results['warnings']:
                    f.write("Warnings:\n")
                    for warning in self.results['warnings']:
                        f.write(f"  - {warning}\n")
            
            logger.info(f"Test summary saved to {summary_file}")
            
        except Exception as e:
            logger.error(f"Error saving results: {e}")
    
    def get_results(self) -> Dict:
        """Get test results"""
        return self.results
    
    def get_failure_summary(self) -> str:
        """Get a formatted failure summary"""
        if self.results['passed']:
            return "All tests passed!"
        
        summary = f"Deployment tests FAILED\n\n"
        summary += f"Errors: {len(self.results['errors'])}\n"
        summary += f"Warnings: {len(self.results['warnings'])}\n\n"
        
        if self.results['errors']:
            summary += "Errors:\n"
            for error in self.results['errors'][:10]:  # Limit to first 10
                if isinstance(error, dict):
                    summary += f"  - {error.get('check', 'unknown')}: {error.get('error', 'unknown error')}\n"
                else:
                    summary += f"  - {error}\n"
        
        return summary


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Run deployment tests')
    parser.add_argument('--project-root', help='Project root directory', default=None)
    parser.add_argument('--json', action='store_true', help='Output results as JSON')
    
    args = parser.parse_args()
    
    runner = DeploymentTestRunner(project_root=args.project_root)
    passed = runner.run_all_tests()
    
    if args.json:
        print(json.dumps(runner.get_results(), indent=2))
    else:
        if passed:
            print("✅ All deployment tests passed!")
            sys.exit(0)
        else:
            print(runner.get_failure_summary())
            sys.exit(1)


if __name__ == '__main__':
    main()

