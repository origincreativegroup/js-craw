"""AI analysis modules"""

from app.ai.analyzer import JobAnalyzer
from app.ai.job_filter import JobFilter
from app.ai.document_generator import DocumentGenerator
from app.ai.job_fit_advisor import JobFitAdvisor
from app.ai.application_builder import TailoredApplicationBuilder
from app.ai.ollama_verifier import OllamaVerifier, verify_ollama_setup

__all__ = [
    'JobAnalyzer',
    'JobFilter',
    'DocumentGenerator',
    'JobFitAdvisor',
    'TailoredApplicationBuilder',
    'OllamaVerifier',
    'verify_ollama_setup'
]



