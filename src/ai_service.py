"""
AI API integration for ExamsGPT
Handles image analysis using OpenAI (GPT-4o/GPT-5.2) or Gemini vision capabilities
"""

import logging
import base64
import time
from datetime import datetime
from typing import Optional, Callable
from PIL import Image
from io import BytesIO

from openai import OpenAI

from .config import get_config


# Streaming callback type: (content, content_type) -> None
# content_type: 'reasoning' | 'answer' | 'error'
StreamingCallback = Callable[[str, str], None]


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

    def __init__(self, streaming_callback: Optional[StreamingCallback] = None):
        self.config = get_config()
        self.prompt_template = self.config.get_prompt_template()
        self.streaming_callback = streaming_callback

        # Initialize appropriate client based on provider
        if self._uses_gemini():
            self.client = None  # Gemini uses lazy initialization via _get_gemini_client()
            model_name = self.config.gemini_model
        else:
            self.client = OpenAI(api_key=self.config.openai_api_key)
            model_name = self.config.openai_model

        streaming_status = "enabled" if self.streaming_callback and self.config.streaming_enabled else "disabled"
        logger.info(f"AIService initialized with provider: {self.config.ai_provider}, model: {model_name}, streaming: {streaming_status}")

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

            # Check if streaming is enabled (OpenAI or Gemini, requires callback)
            use_streaming = (
                self.config.streaming_enabled and
                self.streaming_callback is not None
            )

            # Route to appropriate provider/API
            if self._uses_gemini():
                if use_streaming:
                    result = self._analyze_with_gemini_streaming(image, start_time)
                else:
                    result = self._analyze_with_gemini(image, start_time)
            elif use_streaming and self._uses_responses_api():
                result = self._analyze_with_responses_api_streaming(image, start_time)
            elif use_streaming and not self._uses_responses_api():
                result = self._analyze_with_completions_api_streaming(image, start_time)
            elif self._uses_responses_api():
                result = self._analyze_with_responses_api(image, start_time)
            else:
                result = self._analyze_with_completions_api(image, start_time)

            return result

        except Exception as e:
            logger.error(f"Error analyzing screenshot: {e}")
            # Send error via streaming callback if available
            if self.streaming_callback:
                self.streaming_callback(str(e), 'error')
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
        # Check if debug latency is enabled (zero overhead when disabled)
        debug_enabled = (
            self.config.debug_latency and
            logger.isEnabledFor(logging.DEBUG)
        )

        if debug_enabled:
            overall_start_ns = time.perf_counter_ns()

        # ===== PHASE 1: Request Setup =====
        if debug_enabled:
            setup_start_ns = time.perf_counter_ns()

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

        if debug_enabled:
            setup_ns = time.perf_counter_ns() - setup_start_ns
            network_start_ns = time.perf_counter_ns()

        # ===== PHASE 2: Network Call =====
        try:
            response = self.client.responses.create(**api_params)
        except Exception as e:
            if debug_enabled:
                network_ns = time.perf_counter_ns() - network_start_ns
                logger.debug(
                    f"[LATENCY] openai_responses_api | status=ERROR | "
                    f"setup={setup_ns / 1_000_000:.2f}ms | "
                    f"network={network_ns / 1_000_000:.2f}ms (FAILED: {type(e).__name__})"
                )
            raise

        if debug_enabled:
            network_ns = time.perf_counter_ns() - network_start_ns
            parsing_start_ns = time.perf_counter_ns()

        # ===== PHASE 3: Response Parsing =====

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

        if debug_enabled:
            parsing_ns = time.perf_counter_ns() - parsing_start_ns
            total_ns = time.perf_counter_ns() - overall_start_ns

            logger.debug(
                f"[LATENCY] openai_responses_api | "
                f"setup={setup_ns / 1_000_000:.2f}ms | "
                f"network={network_ns / 1_000_000:.2f}ms | "
                f"parsing={parsing_ns / 1_000_000:.2f}ms | "
                f"total={total_ns / 1_000_000:.2f}ms | "
                f"tokens={response.usage.total_tokens if hasattr(response, 'usage') else 'N/A'}"
            )

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

    def _analyze_with_responses_api_streaming(self, image: Image.Image, start_time: datetime) -> dict:
        """
        Analyze using the new Responses API (GPT-5.x) with streaming
        Streams both reasoning and answer content via callback
        """
        # Check if debug latency is enabled (zero overhead when disabled)
        debug_enabled = (
            self.config.debug_latency and
            logger.isEnabledFor(logging.DEBUG)
        )

        if debug_enabled:
            overall_start_ns = time.perf_counter_ns()
            ttft_ns = None  # Time to first token

        # ===== PHASE 1: Request Setup =====
        if debug_enabled:
            setup_start_ns = time.perf_counter_ns()

        # Convert image to base64
        image_base64 = self._image_to_base64(image)

        # Build API parameters (same as non-streaming)
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

        if debug_enabled:
            setup_ns = time.perf_counter_ns() - setup_start_ns
            network_start_ns = time.perf_counter_ns()

        # Accumulate content for final result
        answer_content = []
        total_tokens = 0

        try:
            # ===== PHASE 2: Network + Streaming =====
            # Create streaming response
            stream = self.client.responses.create(**api_params, stream=True)

            event_count = 0
            reasoning_content = []
            for event in stream:
                event_count += 1

                # Track TTFT on first content-bearing event
                if debug_enabled and ttft_ns is None:
                    if event.type in [
                        'response.reasoning_summary_text.delta',
                        'response.output_text.delta'
                    ]:
                        ttft_ns = time.perf_counter_ns() - network_start_ns

                # Log every event type for debugging (at DEBUG level)
                if event_count == 1 or event_count % 100 == 0:
                    logger.debug(f"[Stream Event #{event_count}] type: {event.type}")

                # Handle different event types from Responses API

                # Reasoning summary text (GPT-5.x extended reasoning)
                if event.type == "response.reasoning_summary_text.delta" and hasattr(event, 'delta'):
                    chunk = event.delta
                    if chunk and self.config.streaming_show_reasoning:
                        reasoning_content.append(chunk)
                        logger.debug(f"[Reasoning Chunk] Received {len(chunk)} chars")

                        # Stream reasoning to frontend if callback provided
                        if self.streaming_callback:
                            self.streaming_callback(chunk, 'reasoning')

                elif event.type == "response.reasoning_summary_text.done":
                    logger.debug(f"Reasoning completed. Total reasoning chars: {sum(len(c) for c in reasoning_content)}")

                # Web search events
                elif event.type == "response.web_search_call.searching":
                    logger.debug("Web search in progress...")
                    if self.streaming_callback:
                        self.streaming_callback('searching', 'searching')

                elif event.type == "response.web_search_call.done":
                    logger.debug("Web search completed")
                    if self.streaming_callback:
                        self.streaming_callback('done', 'searching')

                # Output text (final answer)
                elif event.type == "response.output_text.delta" and hasattr(event, 'delta'):
                    chunk = event.delta
                    if chunk:
                        answer_content.append(chunk)
                        logger.debug(f"[Answer Chunk] Received {len(chunk)} chars, total buffered: {sum(len(c) for c in answer_content)}")

                        # Stream to frontend if callback provided
                        if self.streaming_callback:
                            logger.debug(f"[Streaming] Calling callback with {len(chunk)} chars")
                            self.streaming_callback(chunk, 'answer')
                        else:
                            logger.warning("[Streaming] Callback is None - chunk not sent to frontend!")

                elif event.type == "response.output_text.done":
                    logger.debug("Output text streaming completed")

                elif event.type == "response.done":
                    if hasattr(event, 'response') and hasattr(event.response, 'usage'):
                        total_tokens = event.response.usage.total_tokens
                        logger.debug(f"Stream completed. Total events: {event_count}, Total tokens: {total_tokens}")

            logger.debug(f"Stream iteration finished. Total events processed: {event_count}")

            # ===== PHASE 3: Response Parsing =====
            if debug_enabled:
                parsing_start_ns = time.perf_counter_ns()

            # Join accumulated content
            final_answer = ''.join(answer_content).strip()

            if not final_answer:
                raise ValueError("Empty response received from streaming API")

            if debug_enabled:
                parsing_ns = time.perf_counter_ns() - parsing_start_ns
                total_ns = time.perf_counter_ns() - overall_start_ns
                network_ns = ttft_ns if ttft_ns else (time.perf_counter_ns() - network_start_ns)

                logger.debug(
                    f"[LATENCY] openai_responses_api_streaming | "
                    f"setup={setup_ns / 1_000_000:.2f}ms | "
                    f"ttft={network_ns / 1_000_000:.2f}ms | "
                    f"parsing={parsing_ns / 1_000_000:.2f}ms | "
                    f"total={total_ns / 1_000_000:.2f}ms | "
                    f"tokens={total_tokens}"
                )

            elapsed_time = (datetime.now() - start_time).total_seconds()

            result = {
                'success': True,
                'answer': final_answer,
                'model': self.config.openai_model,
                'timestamp': datetime.now().isoformat(),
                'elapsed_seconds': elapsed_time,
                'tokens_used': total_tokens
            }

            logger.info(f"Streaming analysis complete in {elapsed_time:.2f}s - Tokens used: {total_tokens}")
            return result

        except Exception as e:
            logger.error(f"Error in streaming analysis: {e}")
            # Send error via callback
            if self.streaming_callback:
                self.streaming_callback(str(e), 'error')
            raise

    def _analyze_with_completions_api(self, image: Image.Image, start_time: datetime) -> dict:
        """
        Analyze using the legacy Completions API (GPT-4o and earlier)
        """
        # Check if debug latency is enabled (zero overhead when disabled)
        debug_enabled = (
            self.config.debug_latency and
            logger.isEnabledFor(logging.DEBUG)
        )

        if debug_enabled:
            overall_start_ns = time.perf_counter_ns()

        # ===== PHASE 1: Request Setup =====
        if debug_enabled:
            setup_start_ns = time.perf_counter_ns()

        # Convert image to base64
        image_base64 = self._image_to_base64(image)

        # Prepare Completions API parameters
        if debug_enabled:
            setup_ns = time.perf_counter_ns() - setup_start_ns
            network_start_ns = time.perf_counter_ns()

        # ===== PHASE 2: Network Call =====
        try:
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
        except Exception as e:
            if debug_enabled:
                network_ns = time.perf_counter_ns() - network_start_ns
                logger.debug(
                    f"[LATENCY] openai_completions_api | status=ERROR | "
                    f"setup={setup_ns / 1_000_000:.2f}ms | "
                    f"network={network_ns / 1_000_000:.2f}ms (FAILED: {type(e).__name__})"
                )
            raise

        if debug_enabled:
            network_ns = time.perf_counter_ns() - network_start_ns
            parsing_start_ns = time.perf_counter_ns()

        # ===== PHASE 3: Response Parsing =====
        # Extract answer from Completions API
        answer = response.choices[0].message.content.strip()

        if debug_enabled:
            parsing_ns = time.perf_counter_ns() - parsing_start_ns
            total_ns = time.perf_counter_ns() - overall_start_ns

            logger.debug(
                f"[LATENCY] openai_completions_api | "
                f"setup={setup_ns / 1_000_000:.2f}ms | "
                f"network={network_ns / 1_000_000:.2f}ms | "
                f"parsing={parsing_ns / 1_000_000:.2f}ms | "
                f"total={total_ns / 1_000_000:.2f}ms | "
                f"tokens={response.usage.total_tokens if hasattr(response, 'usage') else 'N/A'}"
            )

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

    def _analyze_with_completions_api_streaming(self, image: Image.Image, start_time: datetime) -> dict:
        """
        Analyze using the legacy Completions API (GPT-4o and earlier) with streaming
        Streams answer content via callback
        """
        # Check if debug latency is enabled (zero overhead when disabled)
        debug_enabled = (
            self.config.debug_latency and
            logger.isEnabledFor(logging.DEBUG)
        )

        if debug_enabled:
            overall_start_ns = time.perf_counter_ns()
            ttft_ns = None  # Time to first token

        # ===== PHASE 1: Request Setup =====
        if debug_enabled:
            setup_start_ns = time.perf_counter_ns()

        # Convert image to base64
        image_base64 = self._image_to_base64(image)

        if debug_enabled:
            setup_ns = time.perf_counter_ns() - setup_start_ns
            network_start_ns = time.perf_counter_ns()

        # Accumulate content
        answer_chunks = []
        total_tokens = 0

        try:
            # ===== PHASE 2: Network + Streaming =====
            # Create streaming response
            stream = self.client.chat.completions.create(
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
                temperature=self.config.openai_temperature,
                stream=True
            )

            for chunk in stream:
                if chunk.choices:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        # Track TTFT on first content chunk
                        if debug_enabled and ttft_ns is None:
                            ttft_ns = time.perf_counter_ns() - network_start_ns

                        content = delta.content
                        answer_chunks.append(content)

                        # Stream to frontend if callback provided
                        if self.streaming_callback:
                            self.streaming_callback(content, 'answer')

                # Track usage from final chunk
                if hasattr(chunk, 'usage') and chunk.usage:
                    total_tokens = chunk.usage.total_tokens

            # ===== PHASE 3: Response Parsing =====
            if debug_enabled:
                parsing_start_ns = time.perf_counter_ns()

            # Join accumulated content
            final_answer = ''.join(answer_chunks).strip()

            if not final_answer:
                raise ValueError("Empty response received from streaming API")

            if debug_enabled:
                parsing_ns = time.perf_counter_ns() - parsing_start_ns
                total_ns = time.perf_counter_ns() - overall_start_ns
                network_ns = ttft_ns if ttft_ns else (time.perf_counter_ns() - network_start_ns)

                logger.debug(
                    f"[LATENCY] openai_completions_api_streaming | "
                    f"setup={setup_ns / 1_000_000:.2f}ms | "
                    f"ttft={network_ns / 1_000_000:.2f}ms | "
                    f"parsing={parsing_ns / 1_000_000:.2f}ms | "
                    f"total={total_ns / 1_000_000:.2f}ms | "
                    f"tokens={total_tokens}"
                )

            elapsed_time = (datetime.now() - start_time).total_seconds()

            result = {
                'success': True,
                'answer': final_answer,
                'model': self.config.openai_model,
                'timestamp': datetime.now().isoformat(),
                'elapsed_seconds': elapsed_time,
                'tokens_used': total_tokens
            }

            logger.info(f"Streaming analysis complete in {elapsed_time:.2f}s - Tokens used: {total_tokens}")
            return result

        except Exception as e:
            logger.error(f"Error in streaming analysis: {e}")
            # Send error via callback
            if self.streaming_callback:
                self.streaming_callback(str(e), 'error')
            raise

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
        # Check if debug latency is enabled (zero overhead when disabled)
        debug_enabled = (
            self.config.debug_latency and
            logger.isEnabledFor(logging.DEBUG)
        )

        if debug_enabled:
            overall_start_ns = time.perf_counter_ns()

        # ===== PHASE 1: Request Setup =====
        if debug_enabled:
            setup_start_ns = time.perf_counter_ns()

        from google.genai import types

        client = _get_gemini_client()

        # Configure Gemini with HIGH thinking, Google Search, and JSON output
        config = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_level="HIGH"),
            tools=[types.Tool(google_search=types.GoogleSearch())],
            response_mime_type="application/json",
        )

        if debug_enabled:
            setup_ns = time.perf_counter_ns() - setup_start_ns
            network_start_ns = time.perf_counter_ns()

        # ===== PHASE 2: Network Call =====
        try:
            # Gemini can accept PIL Image directly - no base64 conversion needed
            response = client.models.generate_content(
                model=self.config.gemini_model,
                contents=[self.prompt_template, image],
                config=config
            )
        except Exception as e:
            if debug_enabled:
                network_ns = time.perf_counter_ns() - network_start_ns
                logger.debug(
                    f"[LATENCY] gemini_api | status=ERROR | "
                    f"setup={setup_ns / 1_000_000:.2f}ms | "
                    f"network={network_ns / 1_000_000:.2f}ms (FAILED: {type(e).__name__})"
                )
            raise

        if debug_enabled:
            network_ns = time.perf_counter_ns() - network_start_ns
            parsing_start_ns = time.perf_counter_ns()

        # ===== PHASE 3: Response Parsing =====
        # Extract answer from Gemini response (JSON guaranteed by response_mime_type)
        answer = response.text.strip() if response.text else None

        if not answer:
            raise ValueError("Gemini returned empty response")

        # Fallback cleaning in case response_mime_type doesn't work as expected
        if not answer.startswith('{'):
            answer = self._clean_json_response(answer)
            logger.debug("Applied fallback JSON cleaning")

        if debug_enabled:
            parsing_ns = time.perf_counter_ns() - parsing_start_ns
            total_ns = time.perf_counter_ns() - overall_start_ns

            logger.debug(
                f"[LATENCY] gemini_api | "
                f"setup={setup_ns / 1_000_000:.2f}ms | "
                f"network={network_ns / 1_000_000:.2f}ms | "
                f"parsing={parsing_ns / 1_000_000:.2f}ms | "
                f"total={total_ns / 1_000_000:.2f}ms | "
                f"tokens={response.usage_metadata.total_token_count if hasattr(response, 'usage_metadata') else 'N/A'}"
            )

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

    def _analyze_with_gemini_streaming(self, image: Image.Image, start_time: datetime) -> dict:
        """
        Analyze using Gemini API with streaming, thinking, and Google Search enabled.
        Streams both reasoning content (thoughts) and answer content via callback.
        """
        # Check if debug latency is enabled
        debug_enabled = (
            self.config.debug_latency and
            logger.isEnabledFor(logging.DEBUG)
        )

        if debug_enabled:
            overall_start_ns = time.perf_counter_ns()
            ttft_ns = None  # Time to first token

        # ===== PHASE 1: Request Setup =====
        if debug_enabled:
            setup_start_ns = time.perf_counter_ns()

        from google.genai import types

        client = _get_gemini_client()

        # Configure Gemini with HIGH thinking (include thoughts for streaming),
        # Google Search, and JSON output
        config = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(
                thinking_level="HIGH",
                include_thoughts=True  # Required to receive thought parts in stream
            ),
            tools=[types.Tool(google_search=types.GoogleSearch())],
            response_mime_type="application/json",
        )

        if debug_enabled:
            setup_ns = time.perf_counter_ns() - setup_start_ns
            network_start_ns = time.perf_counter_ns()

        # Accumulate content for final result
        answer_chunks = []
        total_tokens = 0

        try:
            # ===== PHASE 2: Network + Streaming =====
            # Gemini can accept PIL Image directly - no base64 conversion needed
            stream = client.models.generate_content_stream(
                model=self.config.gemini_model,
                contents=[self.prompt_template, image],
                config=config
            )

            chunk_count = 0
            for chunk in stream:
                chunk_count += 1

                # Track TTFT on first chunk with actual content
                if debug_enabled and ttft_ns is None:
                    if hasattr(chunk, 'candidates') and chunk.candidates:
                        ttft_ns = time.perf_counter_ns() - network_start_ns

                # Log periodically
                if chunk_count == 1 or chunk_count % 50 == 0:
                    logger.debug(f"[Gemini Stream Chunk #{chunk_count}]")

                # Gemini streaming structure: chunk.candidates[0].content.parts
                if not hasattr(chunk, 'candidates') or not chunk.candidates:
                    continue

                candidate = chunk.candidates[0]
                if not hasattr(candidate, 'content') or not candidate.content:
                    continue

                # Process each part in the content
                for part in candidate.content.parts:
                    # Check if this is a thought (reasoning) or actual content
                    # Gemini uses the 'thought' attribute to distinguish
                    is_thought = getattr(part, 'thought', False)

                    if hasattr(part, 'text') and part.text:
                        content = part.text
                        answer_chunks.append(content)

                        # Stream to frontend via callback
                        if self.streaming_callback:
                            content_type = 'reasoning' if is_thought else 'answer'
                            self.streaming_callback(content, content_type)
                            logger.debug(f"[Gemini Streaming] {content_type}: {len(content)} chars")

                    # Check for grounding metadata (Google Search results)
                    if hasattr(part, 'grounding_metadata') and part.grounding_metadata:
                        if self.streaming_callback:
                            # Could emit search events here if desired
                            pass

                # Track token usage from final chunk
                if hasattr(chunk, 'usage_metadata') and chunk.usage_metadata:
                    total_tokens = chunk.usage_metadata.total_token_count

            logger.debug(f"Gemini stream iteration finished. Total chunks: {chunk_count}")

            # ===== PHASE 3: Response Parsing =====
            if debug_enabled:
                parsing_start_ns = time.perf_counter_ns()

            # Join accumulated content
            final_answer = ''.join(answer_chunks).strip()

            if not final_answer:
                raise ValueError("Empty response received from Gemini streaming API")

            # Clean JSON if needed (same as non-streaming)
            if not final_answer.startswith('{'):
                final_answer = self._clean_json_response(final_answer)
                logger.debug("Applied fallback JSON cleaning to streamed content")

            if debug_enabled:
                parsing_ns = time.perf_counter_ns() - parsing_start_ns
                total_ns = time.perf_counter_ns() - overall_start_ns
                network_ns = ttft_ns if ttft_ns else (time.perf_counter_ns() - network_start_ns)

                logger.debug(
                    f"[LATENCY] gemini_api_streaming | "
                    f"setup={setup_ns / 1_000_000:.2f}ms | "
                    f"ttft={network_ns / 1_000_000:.2f}ms | "
                    f"parsing={parsing_ns / 1_000_000:.2f}ms | "
                    f"total={total_ns / 1_000_000:.2f}ms | "
                    f"tokens={total_tokens}"
                )

            elapsed_time = (datetime.now() - start_time).total_seconds()

            result = {
                'success': True,
                'answer': final_answer,
                'model': self.config.gemini_model,
                'timestamp': datetime.now().isoformat(),
                'elapsed_seconds': elapsed_time,
                'tokens_used': total_tokens
            }

            logger.info(f"Gemini streaming analysis complete in {elapsed_time:.2f}s - Tokens used: {total_tokens}")
            return result

        except Exception as e:
            logger.error(f"Error in Gemini streaming analysis: {e}")
            # Send error via callback
            if self.streaming_callback:
                self.streaming_callback(str(e), 'error')
            raise

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

        # Determine format based on configuration
        if self.config.screenshot_format == 'jpeg':
            save_format = 'JPEG'
            quality = self.config.screenshot_jpeg_quality
        elif self.config.screenshot_format == 'webp':
            save_format = 'WEBP'
            quality = self.config.screenshot_webp_quality
        else:
            save_format = 'PNG'
            quality = None

        if save_format == 'JPEG':
            image.save(buffer, format='JPEG', quality=quality)
        elif save_format == 'WEBP':
            image.save(buffer, format='WEBP', quality=quality, method=6)
        else:
            image.save(buffer, format='PNG')

        image_bytes = buffer.getvalue()
        return base64.b64encode(image_bytes).decode('utf-8')

    def analyze_multi_screenshots(self, screenshots: list[tuple[Image.Image, Optional[str]]]) -> dict:
        """
        Analyze multiple screenshots as one combined question
        Works with both OpenAI (Responses/Completions) and Gemini

        Args:
            screenshots: List of (Image, path) tuples

        Returns:
            dict: Contains 'answer', 'model', 'timestamp', 'success', and optional 'error'
        """
        try:
            if not screenshots:
                return {
                    'success': False,
                    'answer': None,
                    'error': 'No screenshots provided',
                    'timestamp': datetime.now().isoformat()
                }

            start_time = datetime.now()
            provider = self.config.ai_provider
            image_count = len(screenshots)

            logger.info(f"Sending {image_count} screenshots to {provider} for combined analysis...")

            images = [img for img, _ in screenshots]
            paths = [path for _, path in screenshots]

            # Check if streaming is enabled
            use_streaming = (
                self.config.streaming_enabled and
                self.streaming_callback is not None
            )

            # Route to appropriate provider
            if self._uses_gemini():
                if use_streaming:
                    result = self._analyze_multiple_with_gemini_streaming(images, paths, start_time)
                else:
                    result = self._analyze_multiple_with_gemini(images, paths, start_time)
            elif self._uses_responses_api():
                result = self._analyze_multiple_with_responses_api(images, paths, start_time)
            else:
                result = self._analyze_multiple_with_completions_api(images, paths, start_time)

            return result

        except Exception as e:
            logger.error(f"Error analyzing multiple screenshots: {e}")
            model = self.config.gemini_model if self._uses_gemini() else self.config.openai_model
            return {
                'success': False,
                'answer': None,
                'model': model,
                'timestamp': datetime.now().isoformat(),
                'error': str(e)
            }

    def _analyze_multiple_with_responses_api(self, images: list[Image.Image], paths: list[str], start_time: datetime) -> dict:
        """Analyze multiple images using Responses API (GPT-5.x)"""
        # Convert all images to base64
        image_items = [
            {
                "type": "input_image",
                "image_url": f"data:image/png;base64,{self._image_to_base64(img)}"
            }
            for img in images
        ]

        api_params = {
            "model": self.config.openai_model,
            "input": [{
                "type": "message",
                "role": "user",
                "content": [
                    {"type": "input_text", "text": self._get_multi_image_prompt(len(images))},
                    *image_items  # Multiple images
                ]
            }],
            "text": {"format": {"type": "text"}, "verbosity": "low"},
            "reasoning": self.config.openai_reasoning,
            "store": self.config.openai_store
        }

        if self.config.openai_tools:
            api_params["tools"] = self.config.openai_tools
        if self.config.openai_include:
            api_params["include"] = self.config.openai_include

        response = self.client.responses.create(**api_params)

        # Extract answer (same logic as single-image)
        answer = None
        for output_item in response.output:
            if hasattr(output_item, 'type') and output_item.type == 'message':
                if hasattr(output_item, 'content') and output_item.content:
                    content_item = output_item.content[0]
                    if hasattr(content_item, 'text'):
                        answer = content_item.text
                        if isinstance(answer, str):
                            answer = answer.strip()
                        else:
                            answer = str(answer).strip()
                        break

        if not answer:
            raise ValueError("Could not find message content in response output")

        elapsed_time = (datetime.now() - start_time).total_seconds()

        return {
            'success': True,
            'answer': answer,
            'model': self.config.openai_model,
            'timestamp': datetime.now().isoformat(),
            'elapsed_seconds': elapsed_time,
            'tokens_used': response.usage.total_tokens if hasattr(response, 'usage') else None
        }

    def _analyze_multiple_with_completions_api(self, images: list[Image.Image], paths: list[str], start_time: datetime) -> dict:
        """Analyze multiple images using Completions API (GPT-4o)"""
        # Convert all images to base64
        image_content = [
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{self._image_to_base64(img)}",
                    "detail": "high"
                }
            }
            for img in images
        ]

        response = self.client.chat.completions.create(
            model=self.config.openai_model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": self._get_multi_image_prompt(len(images))},
                    *image_content  # Multiple images
                ]
            }],
            max_tokens=self.config.openai_max_tokens,
            temperature=self.config.openai_temperature
        )

        answer = response.choices[0].message.content.strip()
        elapsed_time = (datetime.now() - start_time).total_seconds()

        return {
            'success': True,
            'answer': answer,
            'model': self.config.openai_model,
            'timestamp': datetime.now().isoformat(),
            'elapsed_seconds': elapsed_time,
            'tokens_used': response.usage.total_tokens if hasattr(response, 'usage') else None
        }

    def _analyze_multiple_with_gemini(self, images: list[Image.Image], paths: list[str], start_time: datetime) -> dict:
        """Analyze multiple images using Gemini API"""
        from google.genai import types

        client = _get_gemini_client()

        # Gemini accepts multiple images in contents array
        contents = [
            self._get_multi_image_prompt(len(images)),
            *images  # Multiple PIL images
        ]

        config = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_level="HIGH"),
            tools=[types.Tool(google_search=types.GoogleSearch())],
            response_mime_type="application/json",
        )

        response = client.models.generate_content(
            model=self.config.gemini_model,
            contents=contents,
            config=config
        )

        answer = response.text.strip() if response.text else None

        if not answer:
            raise ValueError("Gemini returned empty response")

        # Fallback cleaning in case response_mime_type doesn't work as expected
        if not answer.startswith('{'):
            answer = self._clean_json_response(answer)
            logger.debug("Applied fallback JSON cleaning")

        elapsed_time = (datetime.now() - start_time).total_seconds()

        tokens_used = None
        if hasattr(response, 'usage_metadata'):
            tokens_used = response.usage_metadata.total_token_count

        return {
            'success': True,
            'answer': answer,
            'model': self.config.gemini_model,
            'timestamp': datetime.now().isoformat(),
            'elapsed_seconds': elapsed_time,
            'tokens_used': tokens_used
        }

    def _analyze_multiple_with_gemini_streaming(self, images: list[Image.Image], paths: list[str], start_time: datetime) -> dict:
        """Analyze multiple images using Gemini API with streaming"""
        from google.genai import types

        client = _get_gemini_client()

        # Gemini accepts multiple images in contents array
        contents = [
            self._get_multi_image_prompt(len(images)),
            *images  # Multiple PIL images
        ]

        config = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(
                thinking_level="HIGH",
                include_thoughts=True  # Required for streaming thoughts
            ),
            tools=[types.Tool(google_search=types.GoogleSearch())],
            response_mime_type="application/json",
        )

        # Accumulate content for final result
        answer_chunks = []
        total_tokens = 0

        try:
            # Create streaming response
            stream = client.models.generate_content_stream(
                model=self.config.gemini_model,
                contents=contents,
                config=config
            )

            for chunk in stream:
                # Gemini streaming structure: chunk.candidates[0].content.parts
                if not hasattr(chunk, 'candidates') or not chunk.candidates:
                    continue

                candidate = chunk.candidates[0]
                if not hasattr(candidate, 'content') or not candidate.content:
                    continue

                # Process each part in the content
                for part in candidate.content.parts:
                    # Check if this is a thought (reasoning) or actual content
                    is_thought = getattr(part, 'thought', False)

                    if hasattr(part, 'text') and part.text:
                        content = part.text
                        answer_chunks.append(content)

                        # Stream to frontend via callback
                        if self.streaming_callback:
                            content_type = 'reasoning' if is_thought else 'answer'
                            self.streaming_callback(content, content_type)

                # Track token usage from final chunk
                if hasattr(chunk, 'usage_metadata') and chunk.usage_metadata:
                    total_tokens = chunk.usage_metadata.total_token_count

            # Join accumulated content
            final_answer = ''.join(answer_chunks).strip()

            if not final_answer:
                raise ValueError("Empty response received from Gemini streaming API")

            # Clean JSON if needed
            if not final_answer.startswith('{'):
                final_answer = self._clean_json_response(final_answer)
                logger.debug("Applied fallback JSON cleaning to streamed multi-image content")

            elapsed_time = (datetime.now() - start_time).total_seconds()

            return {
                'success': True,
                'answer': final_answer,
                'model': self.config.gemini_model,
                'timestamp': datetime.now().isoformat(),
                'elapsed_seconds': elapsed_time,
                'tokens_used': total_tokens
            }

        except Exception as e:
            logger.error(f"Error in multi-image Gemini streaming: {e}")
            # Send error via callback
            if self.streaming_callback:
                self.streaming_callback(str(e), 'error')
            raise

    def _get_multi_image_prompt(self, image_count: int) -> str:
        """Get prompt modified for multi-image analysis"""
        base_prompt = self.prompt_template

        multi_instruction = f"""

IMPORTANT: You are receiving {image_count} screenshots that form ONE complete exam question.
These screenshots show different sections of the same question (scroll captures).
Analyze ALL images together to understand the complete question before answering.
Consider the context from all images when determining the answer."""

        return base_prompt + multi_instruction

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
