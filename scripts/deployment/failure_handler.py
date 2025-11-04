#!/usr/bin/env python3
"""
Failure handler for deployment pipeline.
Handles failures by:
1. Generating detailed logs
2. Committing failure report to GitHub
3. Sending push notification
"""

import sys
import os
import subprocess
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional
import traceback

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.notifications.telegram_bot import TelegramBotAgent
from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DeploymentFailureHandler:
    """Handles deployment failures with logging, GitHub commits, and notifications"""
    
    def __init__(self, project_root: str = None):
        self.project_root = Path(project_root) if project_root else Path(__file__).parent.parent.parent
        self.log_dir = self.project_root / 'logs' / 'deployment' / 'failures'
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        
    def handle_failure(
        self,
        error_type: str,
        error_message: str,
        test_results: Optional[Dict] = None,
        stack_trace: Optional[str] = None,
        context: Optional[Dict] = None
    ) -> bool:
        """
        Handle deployment failure
        
        Args:
            error_type: Type of error (e.g., 'test_failure', 'build_failure', 'deployment_failure')
            error_message: Error message
            test_results: Optional test results dictionary
            stack_trace: Optional stack trace
            context: Optional additional context
            
        Returns:
            True if handling was successful
        """
        logger.error(f"Handling deployment failure: {error_type} - {error_message}")
        
        try:
            # 1. Generate detailed failure log
            failure_log = self._generate_failure_log(
                error_type, error_message, test_results, stack_trace, context
            )
            
            # 2. Save failure log
            log_file = self._save_failure_log(failure_log)
            
            # 3. Create GitHub commit with failure report
            commit_success = self._commit_to_github(failure_log, log_file)
            
            # 4. Send push notification
            notification_success = self._send_notification(error_type, error_message, failure_log)
            
            return commit_success and notification_success
            
        except Exception as e:
            logger.error(f"Error handling failure: {e}")
            logger.error(traceback.format_exc())
            return False
    
    def _generate_failure_log(
        self,
        error_type: str,
        error_message: str,
        test_results: Optional[Dict],
        stack_trace: Optional[str],
        context: Optional[Dict]
    ) -> Dict:
        """Generate comprehensive failure log"""
        
        # Get git information
        git_info = self._get_git_info()
        
        # Get system information
        system_info = self._get_system_info()
        
        # Get Docker service status
        docker_status = self._get_docker_status()
        
        failure_log = {
            'timestamp': datetime.utcnow().isoformat(),
            'error_type': error_type,
            'error_message': error_message,
            'git_info': git_info,
            'system_info': system_info,
            'docker_status': docker_status,
            'test_results': test_results,
            'stack_trace': stack_trace,
            'context': context or {}
        }
        
        return failure_log
    
    def _get_git_info(self) -> Dict:
        """Get current git commit information"""
        git_info = {}
        
        try:
            # Get current commit
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                git_info['commit_sha'] = result.stdout.strip()
            
            # Get commit message
            result = subprocess.run(
                ['git', 'log', '-1', '--pretty=format:%s'],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                git_info['commit_message'] = result.stdout.strip()
            
            # Get branch
            result = subprocess.run(
                ['git', 'branch', '--show-current'],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                git_info['branch'] = result.stdout.strip()
            
            # Get author
            result = subprocess.run(
                ['git', 'log', '-1', '--pretty=format:%an <%ae>'],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                git_info['author'] = result.stdout.strip()
                
        except Exception as e:
            logger.warning(f"Error getting git info: {e}")
            git_info['error'] = str(e)
        
        return git_info
    
    def _get_system_info(self) -> Dict:
        """Get system information"""
        import platform
        
        return {
            'platform': platform.platform(),
            'python_version': sys.version,
            'hostname': platform.node(),
            'cwd': str(self.project_root)
        }
    
    def _get_docker_status(self) -> Dict:
        """Get Docker service status"""
        docker_status = {}
        
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
                            services.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
                
                docker_status['services'] = services
                docker_status['running'] = [s.get('Name') for s in services if s.get('State') == 'running']
                docker_status['stopped'] = [s.get('Name') for s in services if s.get('State') != 'running']
            else:
                docker_status['error'] = result.stderr
                
        except Exception as e:
            logger.warning(f"Error getting Docker status: {e}")
            docker_status['error'] = str(e)
        
        return docker_status
    
    def _save_failure_log(self, failure_log: Dict) -> Path:
        """Save failure log to file"""
        log_file = self.log_dir / f"failure_{self.timestamp}.json"
        
        with open(log_file, 'w') as f:
            json.dump(failure_log, f, indent=2)
        
        # Also create a human-readable summary
        summary_file = self.log_dir / f"failure_{self.timestamp}.txt"
        with open(summary_file, 'w') as f:
            f.write("=" * 80 + "\n")
            f.write("DEPLOYMENT FAILURE REPORT\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"Timestamp: {failure_log['timestamp']}\n")
            f.write(f"Error Type: {failure_log['error_type']}\n")
            f.write(f"Error Message: {failure_log['error_message']}\n\n")
            
            if failure_log.get('git_info'):
                f.write("Git Information:\n")
                for key, value in failure_log['git_info'].items():
                    f.write(f"  {key}: {value}\n")
                f.write("\n")
            
            if failure_log.get('test_results'):
                f.write("Test Results Summary:\n")
                test_results = failure_log['test_results']
                if isinstance(test_results, dict):
                    if 'errors' in test_results:
                        f.write(f"  Errors: {len(test_results['errors'])}\n")
                        for error in test_results['errors'][:5]:
                            f.write(f"    - {error}\n")
                    if 'warnings' in test_results:
                        f.write(f"  Warnings: {len(test_results['warnings'])}\n")
                f.write("\n")
            
            if failure_log.get('docker_status'):
                f.write("Docker Services:\n")
                docker_status = failure_log['docker_status']
                if 'running' in docker_status:
                    f.write(f"  Running: {len(docker_status['running'])}\n")
                if 'stopped' in docker_status:
                    f.write(f"  Stopped: {len(docker_status['stopped'])}\n")
                f.write("\n")
            
            if failure_log.get('stack_trace'):
                f.write("Stack Trace:\n")
                f.write(failure_log['stack_trace'])
                f.write("\n")
        
        logger.info(f"Failure log saved to {log_file}")
        return log_file
    
    def _commit_to_github(self, failure_log: Dict, log_file: Path) -> bool:
        """Commit failure report to GitHub"""
        logger.info("Committing failure report to GitHub...")
        
        try:
            # Ensure we're in the git repository
            result = subprocess.run(
                ['git', 'rev-parse', '--git-dir'],
                cwd=self.project_root,
                capture_output=True,
                timeout=5
            )
            
            if result.returncode != 0:
                logger.warning("Not in a git repository, skipping GitHub commit")
                return False
            
            # Configure git user if not set (required for commits)
            subprocess.run(
                ['git', 'config', 'user.email', 'deployment-bot@pi-forge.local'],
                cwd=self.project_root,
                check=False
            )
            subprocess.run(
                ['git', 'config', 'user.name', 'Deployment Bot'],
                cwd=self.project_root,
                check=False
            )
            
            # Create failure report directory in repo
            report_dir = self.project_root / 'deployment-failures'
            report_dir.mkdir(exist_ok=True)
            
            # Copy failure log to repo
            report_file = report_dir / f"failure_{self.timestamp}.json"
            import shutil
            shutil.copy(log_file, report_file)
            
            # Create summary file
            summary_file = report_dir / f"failure_{self.timestamp}.md"
            with open(summary_file, 'w') as f:
                f.write(f"# Deployment Failure Report\n\n")
                f.write(f"**Timestamp:** {failure_log['timestamp']}\n\n")
                f.write(f"**Error Type:** {failure_log['error_type']}\n\n")
                f.write(f"**Error Message:**\n```\n{failure_log['error_message']}\n```\n\n")
                
                if failure_log.get('git_info'):
                    f.write("## Git Information\n\n")
                    for key, value in failure_log['git_info'].items():
                        f.write(f"- **{key}:** {value}\n")
                    f.write("\n")
                
                if failure_log.get('test_results'):
                    f.write("## Test Results\n\n")
                    test_results = failure_log['test_results']
                    if isinstance(test_results, dict):
                        if 'errors' in test_results:
                            f.write(f"**Errors:** {len(test_results['errors'])}\n\n")
                            for error in test_results['errors'][:10]:
                                if isinstance(error, dict):
                                    f.write(f"- {error.get('check', 'unknown')}: {error.get('error', 'unknown')}\n")
                                else:
                                    f.write(f"- {error}\n")
                            f.write("\n")
                
                f.write(f"\n[Full Log](./failure_{self.timestamp}.json)\n")
            
            # Stage files
            subprocess.run(
                ['git', 'add', str(report_file.relative_to(self.project_root))],
                cwd=self.project_root,
                check=False
            )
            subprocess.run(
                ['git', 'add', str(summary_file.relative_to(self.project_root))],
                cwd=self.project_root,
                check=False
            )
            
            # Create commit
            commit_message = (
                f"🚨 Deployment Failure: {failure_log['error_type']}\n\n"
                f"Error: {failure_log['error_message'][:200]}\n\n"
                f"Timestamp: {failure_log['timestamp']}\n"
                f"Commit: {failure_log.get('git_info', {}).get('commit_sha', 'unknown')[:8]}"
            )
            
            result = subprocess.run(
                ['git', 'commit', '-m', commit_message],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                logger.info("Failure report committed to git")
                
                # Try to push (may fail if remote is not configured or no access)
                push_result = subprocess.run(
                    ['git', 'push', 'origin', 'main'],
                    cwd=self.project_root,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if push_result.returncode == 0:
                    logger.info("Failure report pushed to GitHub")
                    return True
                else:
                    logger.warning(f"Failed to push to GitHub: {push_result.stderr}")
                    logger.info("Failure report committed locally but not pushed")
                    return False
            else:
                logger.warning(f"Failed to commit failure report: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error committing to GitHub: {e}")
            logger.error(traceback.format_exc())
            return False
    
    def _send_notification(self, error_type: str, error_message: str, failure_log: Dict) -> bool:
        """Send push notification about failure"""
        logger.info("Sending push notification...")
        
        try:
            # Prepare notification message
            git_info = failure_log.get('git_info', {})
            commit_sha = git_info.get('commit_sha', 'unknown')[:8]
            commit_message = git_info.get('commit_message', 'unknown')[:100]
            
            title = f"🚨 Deployment Failed: {error_type}"
            message = (
                f"Error: {error_message[:200]}\n\n"
                f"Commit: {commit_sha}\n"
                f"Message: {commit_message}\n\n"
                f"Timestamp: {failure_log['timestamp']}"
            )
            
            # Try Telegram first
            if settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID:
                try:
                    bot = TelegramBotAgent()
                    if bot.application and bot.chat_id:
                        import asyncio
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            loop.run_until_complete(
                                bot.send_rich_notification(title, message)
                            )
                            logger.info("Telegram notification sent")
                            return True
                        finally:
                            loop.close()
                except Exception as e:
                    logger.warning(f"Failed to send Telegram notification: {e}")
            
            # Fallback to other notification methods
            # (Could add ntfy, pushover, etc. here)
            
            logger.warning("No notification method available or all failed")
            return False
            
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
            logger.error(traceback.format_exc())
            return False


def main():
    """Main entry point for failure handler"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Handle deployment failure')
    parser.add_argument('error_type', help='Type of error')
    parser.add_argument('error_message', help='Error message')
    parser.add_argument('--test-results', help='Path to test results JSON file')
    parser.add_argument('--stack-trace', help='Stack trace')
    parser.add_argument('--context', help='Additional context as JSON')
    parser.add_argument('--project-root', help='Project root directory', default=None)
    
    args = parser.parse_args()
    
    # Load test results if provided
    test_results = None
    if args.test_results:
        try:
            with open(args.test_results, 'r') as f:
                test_results = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load test results: {e}")
    
    # Parse context if provided
    context = None
    if args.context:
        try:
            context = json.loads(args.context)
        except Exception as e:
            logger.warning(f"Failed to parse context: {e}")
    
    handler = DeploymentFailureHandler(project_root=args.project_root)
    success = handler.handle_failure(
        error_type=args.error_type,
        error_message=args.error_message,
        test_results=test_results,
        stack_trace=args.stack_trace,
        context=context
    )
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()

