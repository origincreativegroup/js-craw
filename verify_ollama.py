#!/usr/bin/env python3
"""
Ollama Verification CLI Tool

Quick command-line tool to verify Ollama setup and functionality.

Usage:
    python verify_ollama.py              # Run full verification
    python verify_ollama.py --quick      # Quick health check only
    python verify_ollama.py --test       # Run full test suite
"""
import asyncio
import sys
import argparse
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.ai.ollama_verifier import OllamaVerifier, verify_ollama_setup


async def quick_check():
    """Quick health check"""
    print("Running quick Ollama health check...")
    verifier = OllamaVerifier()
    is_healthy = await verifier.quick_check()

    if is_healthy:
        print("✓ Ollama is running and accessible")
        return True
    else:
        print("✗ Ollama is not accessible")
        print(f"  Expected host: {verifier.ollama_host}")
        print("  Check that Ollama is running and the host URL is correct")
        return False


async def full_verification():
    """Full verification with detailed report"""
    print("Running comprehensive Ollama verification...\n")

    verifier = OllamaVerifier()
    results = await verifier.verify_connection()
    report = verifier.format_report(results)

    print(report)

    if results['ready_for_production']:
        print("\n✓ Ollama is ready for production use!")
        return True
    else:
        print("\n✗ Ollama has issues that need attention")
        print("\nRecommendations:")

        for check_name, check_result in results['checks'].items():
            if check_result.get('status') != 'pass':
                suggestion = check_result.get('suggestion', '')
                if suggestion:
                    print(f"  - {check_name}: {suggestion}")

        return False


async def run_tests():
    """Run the full test suite"""
    print("Running Ollama integration test suite...\n")

    try:
        from tests.test_ollama_integration import run_all_tests
        success = await run_all_tests()
        return success
    except ImportError:
        print("✗ Test suite not available")
        print("  Install pytest to run tests: pip install pytest pytest-asyncio")
        return False


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Verify Ollama setup and functionality",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python verify_ollama.py              # Full verification report
  python verify_ollama.py --quick      # Quick health check
  python verify_ollama.py --test       # Run test suite

Configuration:
  Set these environment variables to configure Ollama:
    OLLAMA_HOST=http://ollama:11434
    OLLAMA_MODEL=llama2
        """
    )

    parser.add_argument(
        '--quick',
        action='store_true',
        help='Quick health check only'
    )

    parser.add_argument(
        '--test',
        action='store_true',
        help='Run full test suite'
    )

    args = parser.parse_args()

    # Run appropriate check
    if args.quick:
        success = asyncio.run(quick_check())
    elif args.test:
        success = asyncio.run(run_tests())
    else:
        success = asyncio.run(full_verification())

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
