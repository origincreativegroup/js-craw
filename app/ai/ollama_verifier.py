"""Ollama connection verification and health check utility"""
import logging
import httpx
import asyncio
from typing import Dict, List, Optional
from datetime import datetime

from app.config import settings

logger = logging.getLogger(__name__)


class OllamaVerifier:
    """Verify Ollama connection and functionality"""

    def __init__(self):
        self.ollama_host = settings.OLLAMA_HOST
        self.model = settings.OLLAMA_MODEL
        self.base_url = self.ollama_host

    async def verify_connection(self) -> Dict:
        """
        Comprehensive verification of Ollama setup.
        Returns a detailed status report.
        """
        results = {
            'timestamp': datetime.utcnow().isoformat(),
            'ollama_host': self.ollama_host,
            'model': self.model,
            'checks': {}
        }

        # Check 1: Ollama server is accessible
        results['checks']['server_accessible'] = await self._check_server_accessible()

        # Check 2: API endpoint responds
        results['checks']['api_responding'] = await self._check_api_responding()

        # Check 3: Model is available
        results['checks']['model_available'] = await self._check_model_available()

        # Check 4: Can generate text
        results['checks']['generation_works'] = await self._check_generation()

        # Check 5: Can parse JSON responses
        results['checks']['json_parsing_works'] = await self._check_json_generation()

        # Overall status
        all_checks_passed = all(
            check.get('status') == 'pass'
            for check in results['checks'].values()
        )

        results['overall_status'] = 'healthy' if all_checks_passed else 'unhealthy'
        results['ready_for_production'] = all_checks_passed

        return results

    async def _check_server_accessible(self) -> Dict:
        """Check if Ollama server is accessible"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")

                if response.status_code == 200:
                    return {
                        'status': 'pass',
                        'message': 'Ollama server is accessible',
                        'response_time_ms': response.elapsed.total_seconds() * 1000
                    }
                else:
                    return {
                        'status': 'fail',
                        'message': f'Server returned status code {response.status_code}',
                        'error': response.text
                    }

        except httpx.ConnectError as e:
            return {
                'status': 'fail',
                'message': 'Cannot connect to Ollama server',
                'error': str(e),
                'suggestion': 'Check if Ollama is running and the host URL is correct'
            }
        except Exception as e:
            return {
                'status': 'fail',
                'message': 'Unexpected error connecting to Ollama',
                'error': str(e)
            }

    async def _check_api_responding(self) -> Dict:
        """Check if API endpoints are responding"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")

                if response.status_code == 200:
                    data = response.json()
                    models = data.get('models', [])

                    return {
                        'status': 'pass',
                        'message': 'API is responding correctly',
                        'available_models_count': len(models),
                        'models': [m.get('name') for m in models]
                    }
                else:
                    return {
                        'status': 'fail',
                        'message': 'API not responding as expected',
                        'status_code': response.status_code
                    }

        except Exception as e:
            return {
                'status': 'fail',
                'message': 'API check failed',
                'error': str(e)
            }

    async def _check_model_available(self) -> Dict:
        """Check if the configured model is available"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")

                if response.status_code == 200:
                    data = response.json()
                    models = data.get('models', [])
                    model_names = [m.get('name', '').split(':')[0] for m in models]

                    # Check if our model is in the list
                    model_base = self.model.split(':')[0]
                    is_available = model_base in model_names

                    if is_available:
                        return {
                            'status': 'pass',
                            'message': f'Model "{self.model}" is available',
                            'model': self.model
                        }
                    else:
                        return {
                            'status': 'fail',
                            'message': f'Model "{self.model}" is not available',
                            'available_models': model_names,
                            'suggestion': f'Run: ollama pull {self.model}'
                        }
                else:
                    return {
                        'status': 'fail',
                        'message': 'Could not retrieve model list',
                        'status_code': response.status_code
                    }

        except Exception as e:
            return {
                'status': 'fail',
                'message': 'Model availability check failed',
                'error': str(e)
            }

    async def _check_generation(self) -> Dict:
        """Check if text generation works"""
        test_prompt = "Say 'Hello World' and nothing else."

        try:
            start_time = datetime.utcnow()

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": test_prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.1,
                            "num_predict": 50
                        }
                    }
                )

                elapsed = (datetime.utcnow() - start_time).total_seconds()

                if response.status_code == 200:
                    data = response.json()
                    generated_text = data.get('response', '').strip()

                    return {
                        'status': 'pass',
                        'message': 'Text generation works',
                        'sample_output': generated_text[:100],
                        'generation_time_seconds': round(elapsed, 2),
                        'total_duration_ms': data.get('total_duration', 0) / 1000000
                    }
                else:
                    return {
                        'status': 'fail',
                        'message': f'Generation failed with status {response.status_code}',
                        'error': response.text
                    }

        except Exception as e:
            return {
                'status': 'fail',
                'message': 'Text generation test failed',
                'error': str(e)
            }

    async def _check_json_generation(self) -> Dict:
        """Check if JSON response generation and parsing works"""
        test_prompt = """Generate a JSON object with the following format:
{
    "test": "success",
    "number": 42,
    "items": ["a", "b", "c"]
}
Only output the JSON, nothing else."""

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": test_prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.1,
                            "num_predict": 200
                        }
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    generated_text = data.get('response', '').strip()

                    # Try to parse JSON from response
                    import json
                    start = generated_text.find('{')
                    end = generated_text.rfind('}') + 1

                    if start >= 0 and end > start:
                        json_str = generated_text[start:end]
                        parsed = json.loads(json_str)

                        return {
                            'status': 'pass',
                            'message': 'JSON generation and parsing works',
                            'sample_json': parsed
                        }
                    else:
                        return {
                            'status': 'warn',
                            'message': 'JSON generated but format needs improvement',
                            'raw_output': generated_text
                        }
                else:
                    return {
                        'status': 'fail',
                        'message': f'JSON generation failed with status {response.status_code}',
                        'error': response.text
                    }

        except json.JSONDecodeError:
            return {
                'status': 'warn',
                'message': 'Model generated text but not valid JSON',
                'suggestion': 'This may affect job analysis quality'
            }
        except Exception as e:
            return {
                'status': 'fail',
                'message': 'JSON generation test failed',
                'error': str(e)
            }

    async def quick_check(self) -> bool:
        """
        Quick health check - returns True if Ollama is ready to use.
        Use this for fast checks without detailed reporting.
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except:
            return False

    def format_report(self, results: Dict) -> str:
        """Format verification results as a readable report"""
        lines = [
            "=" * 70,
            "OLLAMA VERIFICATION REPORT",
            "=" * 70,
            f"Timestamp: {results['timestamp']}",
            f"Host: {results['ollama_host']}",
            f"Model: {results['model']}",
            f"Overall Status: {results['overall_status'].upper()}",
            f"Production Ready: {'YES' if results['ready_for_production'] else 'NO'}",
            "",
            "DETAILED CHECKS:",
            "-" * 70
        ]

        for check_name, check_result in results['checks'].items():
            status = check_result.get('status', 'unknown').upper()
            status_symbol = '✓' if status == 'PASS' else '✗' if status == 'FAIL' else '⚠'

            lines.append(f"\n{status_symbol} {check_name.replace('_', ' ').title()}")
            lines.append(f"  Status: {status}")
            lines.append(f"  Message: {check_result.get('message', 'N/A')}")

            # Add additional details
            for key, value in check_result.items():
                if key not in ['status', 'message']:
                    lines.append(f"  {key}: {value}")

        lines.append("\n" + "=" * 70)

        return "\n".join(lines)


async def verify_ollama_setup() -> Dict:
    """
    Convenience function to verify Ollama setup.
    Returns detailed verification results.
    """
    verifier = OllamaVerifier()
    return await verifier.verify_connection()


async def print_verification_report():
    """Run verification and print formatted report"""
    verifier = OllamaVerifier()
    results = await verifier.verify_connection()
    report = verifier.format_report(results)
    print(report)
    return results


# CLI support
if __name__ == "__main__":
    asyncio.run(print_verification_report())
