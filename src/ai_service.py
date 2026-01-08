"""
AI API integration for ExamsGPT
Handles image analysis using OpenAI (GPT-4o/GPT-5.2) or Gemini vision capabilities
"""

import logging
import base64
from datetime import datetime
from typing import Optional
from PIL import Image
from io import BytesIO

from openai import OpenAI

from .config import get_config


logger = logging.getLogger(__name__)

# Lazy import for Gemini to avoid dependency when using OpenAI
_gemini_client = None


def _get_gemini_client():
    """Lazy initialization of Gemini client"""
    global _gemini_client
    if _gemini_client is None:
        from google import genai
        config = get_config()
        _gemini_client = genai.Client(api_key=config.gemini_api_key)
    return _gemini_client


class AIService:
    """Handles communication with OpenAI or Gemini API for exam question analysis"""

    def __init__(self):
        self.config = get_config()
        self.prompt_template = self.config.get_prompt_template()

        # Initialize appropriate client based on provider
        if self._uses_gemini():
            self.client = None  # Gemini uses lazy initialization via _get_gemini_client()
            model_name = self.config.gemini_model
        else:
            self.client = OpenAI(api_key=self.config.openai_api_key)
            model_name = self.config.openai_model

        logger.info(f"AIService initialized with provider: {self.config.ai_provider}, model: {model_name}")

    def _uses_gemini(self) -> bool:
        """Check if using Gemini provider"""
        return self.config.ai_provider == 'gemini'

    def _uses_responses_api(self) -> bool:
        """
        Determine if the model uses the new Responses API (GPT-5.x)
        or the legacy Completions API (GPT-4o and earlier)
        """
        model = self.config.openai_model.lower()
        # GPT-5.x uses the new Responses API
        return model.startswith('gpt-5')

    def analyze_exam_screenshot(self, image: Image.Image) -> dict:
        """
        Analyze exam screenshot using configured AI provider (OpenAI or Gemini)

        Args:
            image: PIL Image object of the screenshot

        Returns:
            dict: Contains 'answer', 'model', 'timestamp', 'success', and optional 'error'
        """
        try:
            start_time = datetime.now()
            provider = self.config.ai_provider
            logger.info(f"Sending screenshot to {provider} for analysis...")

            # Route to appropriate provider/API
            if self._uses_gemini():
                result = self._analyze_with_gemini(image, start_time)
            elif self._uses_responses_api():
                result = self._analyze_with_responses_api(image, start_time)
            else:
                result = self._analyze_with_completions_api(image, start_time)

            return result

        except Exception as e:
            logger.error(f"Error analyzing screenshot: {e}")
            model = self.config.gemini_model if self._uses_gemini() else self.config.openai_model
            return {
                'success': False,
                'answer': None,
                'model': model,
                'timestamp': datetime.now().isoformat(),
                'error': str(e)
            }

    def _analyze_with_responses_api(self, image: Image.Image, start_time: datetime) -> dict:
        """
        Analyze using the new Responses API (GPT-5.x)
        Uses config for reasoning, tools, store, and include options
        """
        # Convert image to base64
        image_base64 = self._image_to_base64(image)

        # Build API parameters from config
        api_params = {
            "model": self.config.openai_model,
            "input": [
                {
                    "type": "message",
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": self.prompt_template
                        },
                        {
                            "type": "input_image",
                            "image_url": f"data:image/png;base64,{image_base64}"
                        }
                    ]
                }
            ],
            "text": {
                "format": {
                    "type": "text"
                },
                "verbosity": "low"  # Concise answers for exams
            },
            "reasoning": self.config.openai_reasoning,
            "store": self.config.openai_store
        }

        # Add tools if configured (e.g., web_search)
        if self.config.openai_tools:
            api_params["tools"] = self.config.openai_tools

        # Add include if configured (e.g., reasoning.encrypted_content)
        if self.config.openai_include:
            api_params["include"] = self.config.openai_include

        logger.debug(f"Responses API params: reasoning={self.config.openai_reasoning}, "
                     f"tools={len(self.config.openai_tools)}, store={self.config.openai_store}")

        # Call OpenAI Responses API
        response = self.client.responses.create(**api_params)

        # Debug: log response structure
        logger.debug(f"Response type: {type(response)}")
        logger.debug(f"Response attributes: {dir(response)}")

        # Extract answer from Responses API
        answer = None

        try:
            if hasattr(response, 'output') and response.output:
                # The output array contains multiple items:
                # - reasoning (type: "reasoning") with summary
                # - message (type: "message") with the actual answer

                # Find the message in output
                for output_item in response.output:
                    if hasattr(output_item, 'type') and output_item.type == 'message':
                        if hasattr(output_item, 'content') and output_item.content:
                            # Extract text from content[0]
                            content_item = output_item.content[0]
                            if hasattr(content_item, 'text'):
                                answer = content_item.text
                                if isinstance(answer, str):
                                    answer = answer.strip()
                                else:
                                    # If it's still an object, convert to string
                                    answer = str(answer).strip()
                                break

            if not answer:
                raise ValueError("Could not find message content in response output")

        except Exception as e:
            logger.error(f"Error extracting answer: {e}")

            # Debug: dump full response structure
            try:
                response_dict = response.model_dump() if hasattr(response, 'model_dump') else str(response)
                logger.error(f"Response structure: {response_dict}")
            except:
                logger.error(f"Response object: {response}")

            raise ValueError(f"Unable to extract answer from API response: {e}")

        elapsed_time = (datetime.now() - start_time).total_seconds()

        result = {
            'success': True,
            'answer': answer,
            'model': self.config.openai_model,
            'timestamp': datetime.now().isoformat(),
            'elapsed_seconds': elapsed_time,
            'tokens_used': response.usage.total_tokens if hasattr(response, 'usage') else None
        }

        logger.info(f"Analysis complete in {elapsed_time:.2f}s - Tokens used: {result['tokens_used']}")
        return result

    def _analyze_with_completions_api(self, image: Image.Image, start_time: datetime) -> dict:
        """
        Analyze using the legacy Completions API (GPT-4o and earlier)
        """
        # Convert image to base64
        image_base64 = self._image_to_base64(image)

        # Prepare Completions API parameters
        response = self.client.chat.completions.create(
            model=self.config.openai_model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": self.prompt_template
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_base64}",
                                "detail": "high"
                            }
                        }
                    ]
                }
            ],
            max_tokens=self.config.openai_max_tokens,
            temperature=self.config.openai_temperature
        )

        # Extract answer from Completions API
        answer = response.choices[0].message.content.strip()
        elapsed_time = (datetime.now() - start_time).total_seconds()

        result = {
            'success': True,
            'answer': answer,
            'model': self.config.openai_model,
            'timestamp': datetime.now().isoformat(),
            'elapsed_seconds': elapsed_time,
            'tokens_used': response.usage.total_tokens if hasattr(response, 'usage') else None
        }

        logger.info(f"Analysis complete in {elapsed_time:.2f}s - Tokens used: {result['tokens_used']}")
        return result

    def _clean_json_response(self, text: str) -> str:
        """
        Clean Gemini response to extract pure JSON.
        Removes markdown code blocks and extra whitespace.
        """
        import re

        cleaned = text.strip()

        # Remove markdown code blocks (```json ... ``` or ``` ... ```)
        code_block_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
        match = re.search(code_block_pattern, cleaned)
        if match:
            cleaned = match.group(1).strip()

        # If still not valid JSON, try to find JSON object in text
        if not cleaned.startswith('{'):
            json_pattern = r'(\{[\s\S]*\})'
            match = re.search(json_pattern, cleaned)
            if match:
                cleaned = match.group(1).strip()

        return cleaned

    def _analyze_with_gemini(self, image: Image.Image, start_time: datetime) -> dict:
        """
        Analyze using Gemini API with thinking and Google Search enabled
        """
        from google.genai import types

        client = _get_gemini_client()

        # Configure Gemini with HIGH thinking, Google Search, and JSON output
        config = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_level="HIGH"),
            tools=[types.Tool(google_search=types.GoogleSearch())],
            response_mime_type="application/json",
        )

        # Gemini can accept PIL Image directly - no base64 conversion needed
        response = client.models.generate_content(
            model=self.config.gemini_model,
            contents=[self.prompt_template, image],
            config=config
        )

        # Extract answer from Gemini response (JSON guaranteed by response_mime_type)
        answer = response.text.strip() if response.text else None

        if not answer:
            raise ValueError("Gemini returned empty response")

        # Fallback cleaning in case response_mime_type doesn't work as expected
        if not answer.startswith('{'):
            answer = self._clean_json_response(answer)
            logger.debug("Applied fallback JSON cleaning")

        elapsed_time = (datetime.now() - start_time).total_seconds()

        # Get token usage if available
        tokens_used = None
        if hasattr(response, 'usage_metadata'):
            tokens_used = response.usage_metadata.total_token_count

        result = {
            'success': True,
            'answer': answer,
            'model': self.config.gemini_model,
            'timestamp': datetime.now().isoformat(),
            'elapsed_seconds': elapsed_time,
            'tokens_used': tokens_used
        }

        logger.info(f"Analysis complete in {elapsed_time:.2f}s - Tokens used: {tokens_used}")
        return result

    def _image_to_base64(self, image: Image.Image) -> str:
        """
        Convert PIL Image to base64 string

        Args:
            image: PIL Image object

        Returns:
            str: Base64 encoded image
        """
        buffer = BytesIO()
        # Convert to RGB if necessary (handles RGBA, etc.)
        if image.mode != 'RGB':
            image = image.convert('RGB')

        image.save(buffer, format='PNG')
        image_bytes = buffer.getvalue()
        return base64.b64encode(image_bytes).decode('utf-8')

    def test_connection(self) -> bool:
        """
        Test API connection for configured provider

        Returns:
            bool: True if connection successful
        """
        try:
            if self._uses_gemini():
                # Test Gemini connection
                client = _get_gemini_client()
                response = client.models.generate_content(
                    model=self.config.gemini_model,
                    contents="Test"
                )
                logger.info("Gemini API connection test successful")
            elif self._uses_responses_api():
                # Test with Responses API (GPT-5.x) using config options
                api_params = {
                    "model": self.config.openai_model,
                    "input": [
                        {
                            "type": "message",
                            "role": "user",
                            "content": [{"type": "input_text", "text": "Test"}]
                        }
                    ],
                    "text": {
                        "format": {"type": "text"},
                        "verbosity": "low"
                    },
                    "reasoning": self.config.openai_reasoning,
                    "store": self.config.openai_store
                }
                if self.config.openai_tools:
                    api_params["tools"] = self.config.openai_tools
                if self.config.openai_include:
                    api_params["include"] = self.config.openai_include

                response = self.client.responses.create(**api_params)
                logger.info(f"OpenAI API connection test successful (reasoning: {self.config.openai_reasoning.get('effort', 'default')})")
            else:
                # Test with Completions API (GPT-4o and earlier)
                response = self.client.chat.completions.create(
                    model=self.config.openai_model,
                    messages=[{"role": "user", "content": "Test"}],
                    max_tokens=5
                )
                logger.info("OpenAI API connection test successful")

            return True

        except Exception as e:
            provider = self.config.ai_provider
            logger.error(f"{provider} API connection test failed: {e}")
            return False
