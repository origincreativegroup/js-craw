"""
Comprehensive tests for Ollama integration and AI functionality.

Run with: pytest tests/test_ollama_integration.py -v
Or directly: python tests/test_ollama_integration.py
"""
import asyncio
import pytest
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.ai.ollama_verifier import OllamaVerifier, verify_ollama_setup
from app.ai.analyzer import JobAnalyzer
from app.ai.document_generator import DocumentGenerator
from app.config import settings
from app.models import Job, UserProfile
from datetime import datetime


class TestOllamaVerification:
    """Test Ollama connection and verification"""

    @pytest.mark.asyncio
    async def test_ollama_accessible(self):
        """Test if Ollama server is accessible"""
        verifier = OllamaVerifier()
        result = await verifier._check_server_accessible()
        assert result['status'] == 'pass', f"Ollama server not accessible: {result}"

    @pytest.mark.asyncio
    async def test_api_responding(self):
        """Test if Ollama API is responding"""
        verifier = OllamaVerifier()
        result = await verifier._check_api_responding()
        assert result['status'] == 'pass', f"Ollama API not responding: {result}"

    @pytest.mark.asyncio
    async def test_model_available(self):
        """Test if configured model is available"""
        verifier = OllamaVerifier()
        result = await verifier._check_model_available()
        assert result['status'] == 'pass', f"Model not available: {result}"

    @pytest.mark.asyncio
    async def test_text_generation(self):
        """Test basic text generation"""
        verifier = OllamaVerifier()
        result = await verifier._check_generation()
        assert result['status'] == 'pass', f"Text generation failed: {result}"

    @pytest.mark.asyncio
    async def test_json_generation(self):
        """Test JSON response generation"""
        verifier = OllamaVerifier()
        result = await verifier._check_json_generation()
        assert result['status'] in ['pass', 'warn'], f"JSON generation failed: {result}"

    @pytest.mark.asyncio
    async def test_full_verification(self):
        """Test complete verification suite"""
        results = await verify_ollama_setup()
        assert results['overall_status'] == 'healthy', f"Ollama not healthy: {results}"
        assert results['ready_for_production'] is True

    @pytest.mark.asyncio
    async def test_quick_check(self):
        """Test quick health check"""
        verifier = OllamaVerifier()
        is_healthy = await verifier.quick_check()
        assert is_healthy is True, "Quick health check failed"


class TestJobAnalyzer:
    """Test JobAnalyzer functionality"""

    @pytest.fixture
    def sample_job(self):
        """Sample job data for testing"""
        return {
            'title': 'Senior Python Developer',
            'company': 'Tech Company Inc',
            'location': 'Remote',
            'description': '''
                We are seeking a Senior Python Developer with experience in:
                - Python 3.x development
                - FastAPI and async programming
                - PostgreSQL and SQLAlchemy
                - Docker and cloud deployment
                - AI/ML integration is a plus

                Responsibilities:
                - Design and implement backend services
                - Work with AI/ML models
                - Collaborate with team members
                - Write clean, maintainable code

                Requirements:
                - 5+ years Python experience
                - Strong understanding of async programming
                - Experience with REST APIs
                - Bachelor's degree or equivalent
            '''
        }

    @pytest.fixture
    def sample_criteria(self):
        """Sample search criteria"""
        class SearchCriteria:
            keywords = "python developer fastapi"
            location = "remote"
            remote_only = True
            job_type = "full-time"
            experience_level = "senior"

        return SearchCriteria()

    @pytest.mark.asyncio
    async def test_analyzer_initialization(self):
        """Test analyzer can be initialized"""
        analyzer = JobAnalyzer()
        assert analyzer.model == settings.OLLAMA_MODEL
        assert analyzer.ollama_url

    @pytest.mark.asyncio
    async def test_job_analysis(self, sample_job, sample_criteria):
        """Test job analysis produces valid results"""
        analyzer = JobAnalyzer()
        analysis = await analyzer.analyze_job(sample_job, sample_criteria)

        # Check required fields
        assert 'summary' in analysis
        assert 'match_score' in analysis
        assert 'pros' in analysis
        assert 'cons' in analysis
        assert 'keywords_matched' in analysis

        # Check match score is valid
        assert 0 <= analysis['match_score'] <= 100

        print("\n=== Job Analysis Results ===")
        print(f"Match Score: {analysis['match_score']}")
        print(f"Summary: {analysis['summary']}")
        print(f"Pros: {analysis['pros']}")
        print(f"Cons: {analysis['cons']}")

    @pytest.mark.asyncio
    async def test_company_profile_analysis(self, sample_job):
        """Test enhanced company profile analysis"""
        analyzer = JobAnalyzer()
        analysis = await analyzer.analyze_company_job_profile(sample_job)

        # Check all expected fields
        expected_fields = [
            'company_profile',
            'company_culture',
            'what_they_want',
            'simplified_requirements',
            'must_haves',
            'nice_to_haves',
            'role_summary',
            'why_this_role'
        ]

        for field in expected_fields:
            assert field in analysis, f"Missing field: {field}"

        print("\n=== Company Profile Analysis ===")
        print(f"Company Profile: {analysis['company_profile']}")
        print(f"What They Want: {analysis['what_they_want']}")
        print(f"Must-Haves: {analysis['must_haves']}")


class TestDocumentGenerator:
    """Test DocumentGenerator functionality"""

    @pytest.fixture
    def sample_job_model(self):
        """Sample Job model for testing"""
        return Job(
            id=999,
            title="Senior Python Developer",
            company="Tech Company Inc",
            location="Remote",
            description="""
                Senior Python Developer position with focus on:
                - Backend API development with FastAPI
                - AI/ML integration
                - Cloud infrastructure
                - Database optimization
            """,
            url="https://example.com/job/123",
            external_id="test-123",
            ai_match_score=92.5
        )

    @pytest.fixture
    def sample_user_profile(self):
        """Sample UserProfile for testing"""
        return UserProfile(
            id=1,
            skills=[
                "Python",
                "FastAPI",
                "PostgreSQL",
                "Docker",
                "AWS",
                "Machine Learning",
                "RESTful APIs"
            ],
            experience=[
                {
                    "title": "Senior Software Engineer",
                    "company": "Previous Company",
                    "duration": "2020-2023",
                    "description": "Developed backend services using Python and FastAPI"
                },
                {
                    "title": "Software Engineer",
                    "company": "Another Company",
                    "duration": "2018-2020",
                    "description": "Full-stack development with focus on Python"
                }
            ],
            education=[
                {
                    "degree": "Bachelor of Science in Computer Science",
                    "institution": "University",
                    "year": "2018"
                }
            ],
            base_resume="""
                Experienced software engineer with 5+ years of Python development.
                Specialized in backend services, API development, and cloud infrastructure.
                Strong background in AI/ML integration and scalable system design.
            """
        )

    @pytest.mark.asyncio
    async def test_generator_initialization(self):
        """Test document generator can be initialized"""
        generator = DocumentGenerator()
        assert generator.model == settings.OLLAMA_MODEL
        assert generator.resume_path.exists()
        assert generator.cover_letter_path.exists()

    @pytest.mark.asyncio
    async def test_resume_prompt_building(self, sample_job_model, sample_user_profile):
        """Test resume prompt is built correctly"""
        generator = DocumentGenerator()
        prompt = generator._build_resume_prompt(sample_job_model, sample_user_profile)

        # Check prompt contains key information
        assert sample_job_model.title in prompt
        assert sample_job_model.company in prompt
        assert "Python" in prompt  # From skills
        assert "resume" in prompt.lower()

        print("\n=== Resume Prompt Preview ===")
        print(prompt[:500] + "...")

    @pytest.mark.asyncio
    async def test_cover_letter_prompt_building(self, sample_job_model, sample_user_profile):
        """Test cover letter prompt is built correctly"""
        generator = DocumentGenerator()
        prompt = generator._build_cover_letter_prompt(sample_job_model, sample_user_profile)

        # Check prompt contains key information
        assert sample_job_model.title in prompt
        assert sample_job_model.company in prompt
        assert "cover letter" in prompt.lower()

        print("\n=== Cover Letter Prompt Preview ===")
        print(prompt[:500] + "...")

    @pytest.mark.asyncio
    async def test_ollama_call(self):
        """Test direct Ollama API call"""
        generator = DocumentGenerator()
        test_prompt = "Write a one-sentence introduction for a Python developer."

        result = await generator._call_ollama(test_prompt, max_tokens=100)

        assert result, "Ollama call returned empty result"
        assert len(result) > 10, "Ollama result too short"
        assert "python" in result.lower() or "developer" in result.lower()

        print("\n=== Ollama Generation Test ===")
        print(f"Prompt: {test_prompt}")
        print(f"Result: {result}")


class TestIntegration:
    """Integration tests combining multiple components"""

    @pytest.mark.asyncio
    async def test_end_to_end_verification(self):
        """Test complete end-to-end verification"""
        print("\n" + "="*70)
        print("RUNNING COMPREHENSIVE OLLAMA VERIFICATION")
        print("="*70)

        verifier = OllamaVerifier()
        results = await verifier.verify_connection()
        report = verifier.format_report(results)

        print(report)

        # Assert all checks pass
        for check_name, check_result in results['checks'].items():
            assert check_result['status'] in ['pass', 'warn'], \
                f"Check '{check_name}' failed: {check_result}"

        assert results['overall_status'] == 'healthy'
        assert results['ready_for_production'] is True


# Standalone execution
async def run_all_tests():
    """Run all tests manually"""
    print("\n" + "="*70)
    print("OLLAMA INTEGRATION TEST SUITE")
    print("="*70)

    # 1. Verification Tests
    print("\n[1/4] Running Ollama Verification Tests...")
    verifier = OllamaVerifier()
    verification_results = await verifier.verify_connection()
    print(verifier.format_report(verification_results))

    if not verification_results['ready_for_production']:
        print("\n❌ OLLAMA NOT READY - Stopping tests")
        return False

    # 2. Analyzer Tests
    print("\n[2/4] Testing Job Analyzer...")
    analyzer = JobAnalyzer()

    sample_job = {
        'title': 'Senior Python Developer',
        'company': 'Tech Company Inc',
        'location': 'Remote',
        'description': 'Looking for Python developer with FastAPI and ML experience'
    }

    class Criteria:
        keywords = "python developer"
        location = "remote"
        remote_only = True
        job_type = "full-time"
        experience_level = "senior"

    analysis = await analyzer.analyze_job(sample_job, Criteria())
    print(f"✓ Job analyzed - Match Score: {analysis['match_score']}")
    print(f"  Summary: {analysis['summary'][:100]}...")

    # 3. Company Profile Test
    print("\n[3/4] Testing Company Profile Analysis...")
    profile_analysis = await analyzer.analyze_company_job_profile(sample_job)
    print(f"✓ Company profile generated")
    print(f"  Profile: {profile_analysis.get('company_profile', 'N/A')[:100]}...")

    # 4. Document Generator Test
    print("\n[4/4] Testing Document Generation...")
    generator = DocumentGenerator()
    test_prompt = "Write a brief professional summary for a Python developer (2 sentences)."
    test_result = await generator._call_ollama(test_prompt, max_tokens=150)
    print(f"✓ Document generation working")
    print(f"  Sample: {test_result[:150]}...")

    print("\n" + "="*70)
    print("✓ ALL TESTS PASSED - Ollama integration is working correctly!")
    print("="*70)
    return True


if __name__ == "__main__":
    # Run tests directly
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
