"""Document template service for consistent document generation"""
import logging
from pathlib import Path
from typing import Dict, Optional
from jinja2 import Template, Environment, FileSystemLoader

logger = logging.getLogger(__name__)


class DocumentTemplateService:
    """Service for managing document templates"""
    
    def __init__(self):
        self.template_dir = Path(__file__).parent.parent / "templates"
        self.template_dir.mkdir(exist_ok=True)
        
        # Initialize Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            trim_blocks=True,
            lstrip_blocks=True
        )
    
    def get_template(self, template_name: str) -> Optional[Template]:
        """Get a template by name"""
        try:
            return self.env.get_template(template_name)
        except Exception as e:
            logger.error(f"Error loading template {template_name}: {e}")
            return None
    
    def render_resume_template(
        self,
        user_data: Dict,
        job_data: Dict,
        custom_variables: Optional[Dict] = None
    ) -> str:
        """Render resume template with data"""
        template = self.get_template("resume_template.md")
        if not template:
            # Fallback to basic template
            return self._render_basic_resume(user_data, job_data)
        
        context = {
            "name": user_data.get("name", ""),
            "email": user_data.get("email", ""),
            "phone": user_data.get("phone", ""),
            "location": user_data.get("location", ""),
            "summary": user_data.get("summary", ""),
            "skills_list": self._format_skills(user_data.get("skills", [])),
            "experience_sections": self._format_experience(user_data.get("experience", [])),
            "education_sections": self._format_education(user_data.get("education", [])),
            "custom_sections": custom_variables.get("custom_sections", "") if custom_variables else ""
        }
        
        return template.render(**context)
    
    def render_cover_letter_template(
        self,
        user_data: Dict,
        job_data: Dict,
        custom_variables: Optional[Dict] = None
    ) -> str:
        """Render cover letter template with data"""
        template = self.get_template("cover_letter_template.md")
        if not template:
            # Fallback to basic template
            return self._render_basic_cover_letter(user_data, job_data)
        
        from datetime import datetime
        
        context = {
            "date": datetime.now().strftime("%B %d, %Y"),
            "company_name": job_data.get("company", ""),
            "company_address": job_data.get("location", ""),
            "hiring_manager_name": job_data.get("hiring_manager", "Hiring Manager"),
            "opening_paragraph": custom_variables.get("opening_paragraph", "") if custom_variables else "",
            "body_paragraphs": custom_variables.get("body_paragraphs", "") if custom_variables else "",
            "closing_paragraph": custom_variables.get("closing_paragraph", "") if custom_variables else "",
            "your_name": user_data.get("name", "")
        }
        
        return template.render(**context)
    
    def _format_skills(self, skills: list) -> str:
        """Format skills list"""
        if isinstance(skills, list):
            return ", ".join(skills)
        return str(skills) if skills else ""
    
    def _format_experience(self, experience: list) -> str:
        """Format experience sections"""
        if not isinstance(experience, list):
            return ""
        
        sections = []
        for exp in experience:
            section = f"### {exp.get('title', '')}\n"
            section += f"{exp.get('company', '')} - {exp.get('location', '')}\n"
            section += f"{exp.get('start_date', '')} - {exp.get('end_date', 'Present')}\n\n"
            section += f"{exp.get('description', '')}\n"
            sections.append(section)
        
        return "\n\n".join(sections)
    
    def _format_education(self, education: list) -> str:
        """Format education sections"""
        if not isinstance(education, list):
            return ""
        
        sections = []
        for edu in education:
            section = f"### {edu.get('degree', '')}\n"
            section += f"{edu.get('institution', '')}\n"
            section += f"{edu.get('year', '')}\n"
            sections.append(section)
        
        return "\n\n".join(sections)
    
    def _render_basic_resume(self, user_data: Dict, job_data: Dict) -> str:
        """Fallback basic resume rendering"""
        return f"Resume for {job_data.get('title', 'position')} at {job_data.get('company', 'company')}"
    
    def _render_basic_cover_letter(self, user_data: Dict, job_data: Dict) -> str:
        """Fallback basic cover letter rendering"""
        return f"Cover letter for {job_data.get('title', 'position')} at {job_data.get('company', 'company')}"

