#!/usr/bin/env python3
"""
GitHub repository listener for pi-forge.
Monitors GitHub repository for changes and automatically pulls new code.
Optionally runs tests/debug checks and handles failures.
"""

import sys
import os
import subprocess
import json
import logging
import time
import requests
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict
import signal

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class GitHubListener:
    """Listens for GitHub repository changes and auto-pulls code"""
    
    def __init__(
        self,
        repo_path: str,
        repo_url: Optional[str] = None,
        branch: str = 'main',
        check_interval: int = 60,
        run_tests: bool = True,
        handle_failures: bool = True
    ):
        self.repo_path = Path(repo_path)
        self.repo_url = repo_url
        self.branch = branch
        self.check_interval = check_interval
        self.run_tests = run_tests
        self.handle_failures = handle_failures
        self.running = True
        self.last_commit_sha = None
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
    
    def start(self):
        """Start listening for changes"""
        logger.info(f"Starting GitHub listener for {self.repo_path}")
        logger.info(f"Branch: {self.branch}, Check interval: {self.check_interval}s")
        
        # Initialize repository
        self._init_repo()
        
        # Get initial commit SHA
        self.last_commit_sha = self._get_current_commit_sha()
        logger.info(f"Initial commit: {self.last_commit_sha}")
        
        # Main loop
        while self.running:
            try:
                self._check_for_updates()
                time.sleep(self.check_interval)
            except KeyboardInterrupt:
                logger.info("Interrupted by user")
                break
            except Exception as e:
                logger.error(f"Error in listener loop: {e}")
                time.sleep(self.check_interval)
        
        logger.info("GitHub listener stopped")
    
    def _init_repo(self):
        """Initialize or update git repository"""
        if not self.repo_path.exists():
            logger.info(f"Repository path does not exist: {self.repo_path}")
            if self.repo_url:
                logger.info(f"Cloning repository from {self.repo_url}")
                self.repo_path.parent.mkdir(parents=True, exist_ok=True)
                subprocess.run(
                    ['git', 'clone', self.repo_url, str(self.repo_path)],
                    check=False
                )
            else:
                raise ValueError(f"Repository path does not exist and no repo_url provided")
        
        # Ensure we're on the correct branch
        try:
            subprocess.run(
                ['git', 'checkout', self.branch],
                cwd=self.repo_path,
                check=False,
                capture_output=True
            )
        except Exception as e:
            logger.warning(f"Failed to checkout branch: {e}")
    
    def _get_current_commit_sha(self) -> Optional[str]:
        """Get current commit SHA"""
        try:
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception as e:
            logger.warning(f"Failed to get commit SHA: {e}")
        return None
    
    def _check_for_updates(self):
        """Check for updates and pull if available"""
        try:
            # Fetch latest changes
            subprocess.run(
                ['git', 'fetch', 'origin', self.branch],
                cwd=self.repo_path,
                check=False,
                capture_output=True,
                timeout=30
            )
            
            # Check if there are new commits
            result = subprocess.run(
                ['git', 'rev-list', '--count', f'HEAD..origin/{self.branch}'],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                commits_behind = int(result.stdout.strip())
                
                if commits_behind > 0:
                    logger.info(f"Found {commits_behind} new commit(s), pulling...")
                    
                    # Get commit info before pulling
                    old_commit = self._get_current_commit_sha()
                    
                    # Pull changes
                    pull_result = subprocess.run(
                        ['git', 'pull', 'origin', self.branch],
                        cwd=self.repo_path,
                        capture_output=True,
                        text=True,
                        timeout=60
                    )
                    
                    if pull_result.returncode == 0:
                        new_commit = self._get_current_commit_sha()
                        logger.info(f"Successfully pulled code. Commit: {old_commit} -> {new_commit}")
                        
                        # Run tests and handle failures if configured
                        if self.run_tests or self.handle_failures:
                            self._process_update(old_commit, new_commit)
                    else:
                        logger.error(f"Failed to pull changes: {pull_result.stderr}")
                        if self.handle_failures:
                            self._handle_pull_failure(pull_result.stderr)
                else:
                    logger.debug("No new commits")
                    
        except subprocess.TimeoutExpired:
            logger.error("Git fetch/pull timed out")
        except Exception as e:
            logger.error(f"Error checking for updates: {e}")
    
    def _process_update(self, old_commit: str, new_commit: str):
        """Process code update: run tests and handle failures"""
        logger.info(f"Processing update: {old_commit} -> {new_commit}")
        
        if self.run_tests:
            # Run test suite
            test_runner_path = self.repo_path / 'scripts' / 'deployment' / 'debug_test_runner.py'
            if test_runner_path.exists():
                logger.info("Running deployment tests...")
                
                try:
                    result = subprocess.run(
                        [sys.executable, str(test_runner_path), '--json'],
                        cwd=self.repo_path,
                        capture_output=True,
                        text=True,
                        timeout=300
                    )
                    
                    # Parse test results
                    test_results = None
                    if result.stdout:
                        try:
                            test_results = json.loads(result.stdout)
                        except json.JSONDecodeError:
                            pass
                    
                    tests_passed = (
                        result.returncode == 0 and
                        test_results and
                        test_results.get('passed', False)
                    )
                    
                    if not tests_passed and self.handle_failures:
                        logger.error("Tests failed, handling failure...")
                        self._handle_test_failure(test_results, old_commit, new_commit)
                    else:
                        logger.info("Tests passed!")
                        
                except subprocess.TimeoutExpired:
                    logger.error("Test runner timed out")
                    if self.handle_failures:
                        self._handle_test_failure(
                            None, old_commit, new_commit,
                            error="Test runner timed out"
                        )
                except Exception as e:
                    logger.error(f"Error running tests: {e}")
                    if self.handle_failures:
                        self._handle_test_failure(
                            None, old_commit, new_commit,
                            error=str(e)
                        )
    
    def _handle_test_failure(
        self,
        test_results: Optional[Dict],
        old_commit: str,
        new_commit: str,
        error: Optional[str] = None
    ):
        """Handle test failure"""
        failure_handler_path = self.repo_path / 'scripts' / 'deployment' / 'failure_handler.py'
        
        if not failure_handler_path.exists():
            logger.warning("Failure handler not found, skipping failure handling")
            return
        
        try:
            # Save test results to temp file if available
            test_results_file = None
            if test_results:
                import tempfile
                with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                    json.dump(test_results, f)
                    test_results_file = f.name
            
            # Prepare error message
            error_message = error or "Post-pull tests failed"
            if test_results and 'errors' in test_results:
                error_message += f"\nErrors: {len(test_results['errors'])}"
            
            # Run failure handler
            cmd = [
                sys.executable,
                str(failure_handler_path),
                'test_failure',
                error_message,
                '--project-root', str(self.repo_path)
            ]
            
            if test_results_file:
                cmd.extend(['--test-results', test_results_file])
            
            cmd.append('--context')
            cmd.append(json.dumps({
                'old_commit': old_commit,
                'new_commit': new_commit,
                'source': 'github_listener'
            }))
            
            subprocess.run(cmd, cwd=self.repo_path, timeout=60)
            
            # Cleanup temp file
            if test_results_file and os.path.exists(test_results_file):
                os.unlink(test_results_file)
                
        except Exception as e:
            logger.error(f"Error handling test failure: {e}")
    
    def _handle_pull_failure(self, error_output: str):
        """Handle pull failure"""
        failure_handler_path = self.repo_path / 'scripts' / 'deployment' / 'failure_handler.py'
        
        if not failure_handler_path.exists():
            return
        
        try:
            subprocess.run(
                [
                    sys.executable,
                    str(failure_handler_path),
                    'pull_failure',
                    f"Git pull failed: {error_output[:200]}",
                    '--project-root', str(self.repo_path),
                    '--context', json.dumps({'source': 'github_listener'})
                ],
                cwd=self.repo_path,
                timeout=60
            )
        except Exception as e:
            logger.error(f"Error handling pull failure: {e}")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='GitHub repository listener')
    parser.add_argument('--repo-path', required=True, help='Local repository path')
    parser.add_argument('--repo-url', help='GitHub repository URL (for cloning)')
    parser.add_argument('--branch', default='main', help='Branch to monitor')
    parser.add_argument('--interval', type=int, default=60, help='Check interval in seconds')
    parser.add_argument('--no-tests', action='store_true', help='Skip running tests')
    parser.add_argument('--no-handle-failures', action='store_true', help='Skip failure handling')
    
    args = parser.parse_args()
    
    listener = GitHubListener(
        repo_path=args.repo_path,
        repo_url=args.repo_url,
        branch=args.branch,
        check_interval=args.interval,
        run_tests=not args.no_tests,
        handle_failures=not args.no_handle_failures
    )
    
    listener.start()


if __name__ == '__main__':
    main()

