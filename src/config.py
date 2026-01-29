"""
Configuration management for ExamsGPT
Handles loading from .env and config.yaml
"""

import os
import yaml
from pathlib import Path
from dotenv import load_dotenv
from typing import Dict, Any


class Config:
    """Centralized configuration management"""

    def __init__(self, config_path: str = "config.yaml"):
        # Load environment variables
        load_dotenv()

        # Get project root directory
        self.root_dir = Path(__file__).parent.parent

        # Load YAML configuration
        config_file = self.root_dir / config_path
        with open(config_file, 'r') as f:
            self.yaml_config: Dict[str, Any] = yaml.safe_load(f)

        # AI Provider Configuration
        ai_config = self.yaml_config.get('ai', {})
        self.ai_provider = ai_config.get('provider', 'openai').lower()

        # Validate provider
        if self.ai_provider not in ('openai', 'gemini'):
            raise ValueError(f"Invalid AI provider '{self.ai_provider}'. Must be 'openai' or 'gemini'")

        # OpenAI Configuration
        self.openai_api_key = os.getenv('OPENAI_API_KEY')

        # Gemini Configuration
        self.gemini_api_key = os.getenv('GEMINI_API_KEY')
        self.gemini_model = 'gemini-3-pro-preview'  # Fixed model

        # Fail-fast validation: require API key for selected provider
        if self.ai_provider == 'openai' and not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY not found in .env file (required for openai provider)")
        if self.ai_provider == 'gemini' and not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY not found in .env file (required for gemini provider)")

        openai_config = self.yaml_config.get('openai', {})
        self.openai_model = openai_config.get('model', 'gpt-5.2')
        self.openai_max_tokens = openai_config.get('max_tokens', 4000)
        self.openai_temperature = openai_config.get('temperature', 0.3)

        # New OpenAI Responses API options
        self.openai_reasoning = openai_config.get('reasoning', {'effort': 'high', 'summary': 'auto'})
        self.openai_tools = openai_config.get('tools', [])
        self.openai_store = openai_config.get('store', False)
        self.openai_include = openai_config.get('include', [])

        # Streaming Configuration
        streaming_config = self.yaml_config.get('streaming', {})
        self.streaming_enabled = streaming_config.get('enabled', False)
        self.streaming_show_reasoning = streaming_config.get('show_reasoning', True)
        self.streaming_buffer_delay = streaming_config.get('buffer_delay', 100)
        self.streaming_json_timeout = streaming_config.get('json_timeout', 30)

        # Application Mode
        self.app_mode = os.getenv('APP_MODE', 'dev')

        # Keyboard Configuration
        self.trigger_key = self.yaml_config['keyboard']['trigger_key']

        # Mouse Configuration
        mouse_config = self.yaml_config.get('mouse', {})
        self.enable_middle_button = mouse_config.get('enable_middle_button', False)

        # Screenshot Configuration
        self.save_screenshots = self.yaml_config['screenshot']['save_screenshots']
        self.screenshot_dir = self.root_dir / self.yaml_config['screenshot']['directory']
        self.screenshot_format = self.yaml_config['screenshot']['format']

        # Logging Configuration
        self.log_level = self.yaml_config['logging']['level']
        self.save_to_file = self.yaml_config['logging']['save_to_file']
        self.log_dir = self.root_dir / self.yaml_config['logging']['directory']
        self.save_history = self.yaml_config['logging']['save_history']

        # Socket.IO Configuration (for future use)
        self.socketio_url = os.getenv('SOCKETIO_URL', '')
        self.socketio_namespace = os.getenv('SOCKETIO_NAMESPACE', '/exams')

        # Webhook Configuration (for future use)
        self.webhook_url = os.getenv('WEBHOOK_URL', '')

        # Ensure directories exist
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def get_prompt_template(self) -> str:
        """Returns the optimized prompt for Azure exam questions - returns structured JSON"""
        return """You are a Senior Microsoft Certified Trainer (MCT) and Azure Solutions Architect Expert with 10+ years of experience preparing candidates for Azure certifications. You have deep expertise in:

- AZ-900 (Azure Fundamentals)
- AZ-104 (Azure Administrator)
- AZ-204 (Azure Developer)
- AZ-305 (Azure Solutions Architect)
- AZ-400 (DevOps Engineer)
- AZ-500 (Security Engineer)
- AZ-700 (Network Engineer)
- DP-900, DP-100, DP-203, DP-300 (Data & AI certifications)
- AI-900, AI-102 (AI certifications)
- SC-900, SC-200, SC-300 (Security certifications)
- ANY other related Microsoft Certifications on its catalog

You stay current with Azure's rapid evolution and understand that Microsoft frequently updates exam content.

CRITICAL INSTRUCTION - WEB SEARCH:
You have access to web_search. USE IT when:
1. The question involves specific Azure service limits, quotas, or pricing
2. You're less than 90% confident in your answer
3. The question references recent Azure features or updates
4. The question involves specific CLI commands, PowerShell syntax, or ARM/Bicep templates
5. The question asks about specific SLAs, compliance certifications, or regional availability

When using web_search, prioritize these sources:
- Microsoft Learn (learn.microsoft.com)
- Microsoft Azure Documentation (docs.microsoft.com/azure)
- Microsoft Tech Community
- Official Microsoft blogs

VERIFICATION PROCESS:
1. First, analyze the question using your training knowledge
2. If confidence < 90%, use web_search to verify
3. Cross-reference with official Microsoft documentation when possible
4. For "select all that apply" questions, verify EACH option independently

Analyze this exam question screenshot and respond with ONLY a JSON object (no markdown, no code blocks).

QUESTION TYPES TO DETECT:
- single: Single choice (select ONE answer)
- multiple: Multiple choice (select ALL that apply)
- dragdrop: Drag and drop items to targets
- hotarea: Click on correct area/cell in table
- sequence: Order steps in correct sequence
- matching: Match items from two columns
- yesno: Yes/No or True/False for each statement
- casestudy: Case study with sub-questions

RESPOND WITH THIS EXACT JSON STRUCTURE:

For SINGLE choice:
{"type":"single","answer":"B","options":["A. Option text","B. Option text","C. Option text"],"correct_index":1}

For MULTIPLE choice:
{"type":"multiple","answers":["A","C","E"],"options":["A. Option","B. Option","C. Option","D. Option","E. Option"],"correct_indices":[0,2,4]}

For DRAG & DROP:
{"type":"dragdrop","mappings":[{"item":"Source item 1","target":"Target zone 1"},{"item":"Source item 2","target":"Target zone 2"}]}

For HOT AREA (table/grid clicks):
{"type":"hotarea","selections":[{"row":"Row label","column":"Column label"},{"row":"Row 2","column":"Col 2"}]}

For SEQUENCE (ordering):
{"type":"sequence","steps":["First step","Second step","Third step","Fourth step"]}

For MATCHING:
{"type":"matching","pairs":[{"left":"Item A","right":"Match 1"},{"left":"Item B","right":"Match 2"}]}

For YES/NO per statement:
{"type":"yesno","statements":[{"statement":"Statement text 1","answer":"Yes"},{"statement":"Statement text 2","answer":"No"}]}

For CASE STUDY:
{"type":"casestudy","context":"Brief context","answers":[{"question":"Sub-question 1","answer":"Answer 1"},{"question":"Sub-question 2","answer":"Answer 2"}]}

If question is unclear:
{"type":"error","message":"Cannot identify question in image"}

RULES:
- Return ONLY valid JSON, no explanations
- Detect question type from visual cues (checkboxes=multiple, radio=single, drag areas, tables, etc.)
- For single/multiple: include the letter AND full option text when visible
- Be precise with the answer - this is for a real exam
- ALWAYS include "confidence" field (0-100) indicating your certainty
- ALWAYS include "verified" field (boolean) indicating if you used web_search to verify
- If you used web_search, include "sources" array with URLs consulted

ENHANCED JSON STRUCTURE (add these fields to ALL response types):
{
  "type": "single|multiple|etc",
  "confidence": 95,
  "verified": true,
  "sources": ["https://learn.microsoft.com/..."],
  ... other type-specific fields ...
}"""

    def __repr__(self) -> str:
        model = self.gemini_model if self.ai_provider == 'gemini' else self.openai_model
        return f"Config(mode={self.app_mode}, provider={self.ai_provider}, model={model}, trigger_key={self.trigger_key})"


# Global config instance (initialized by main.py)
_config: Config | None = None


def get_config() -> Config:
    """Get the global configuration instance"""
    global _config
    if _config is None:
        _config = Config()
    return _config


def init_config(config_path: str = "config.yaml") -> Config:
    """Initialize the global configuration"""
    global _config
    _config = Config(config_path)
    return _config
