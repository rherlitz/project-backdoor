from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging
import openai
from openai import AsyncOpenAI

from .config import settings

logger = logging.getLogger(__name__)

class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    @abstractmethod
    async def generate(self, prompt: str, model: str, temperature: float = 0.7, max_tokens: int = 150, **kwargs) -> Optional[str]:
        """Generate text using the LLM."""
        pass

class OpenAIProvider(LLMProvider):
    """Implementation for the OpenAI API."""
    def __init__(self, api_key: str = settings.OPENAI_API_KEY):
        if not api_key or api_key == "YOUR_API_KEY_HERE":
            logger.warning("OpenAI API key is not configured. OpenAIProvider will not function.")
            self.client = None
        else:
            self.client = AsyncOpenAI(api_key=api_key)
            logger.info("OpenAI client initialized.")

    async def generate(self, prompt: str, model: str = "gpt-4o-mini", temperature: float = 0.7, max_tokens: int = 250, **kwargs) -> Optional[str]:
        if not self.client:
            logger.error("OpenAI client is not initialized. Cannot generate text.")
            return None

        try:
            # Using ChatCompletion for newer models like gpt-3.5-turbo and gpt-4
            response = await self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant for a retro adventure game. Make your responses short and concise."},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            # TODO: Add more robust response parsing and error handling
            if response.choices and len(response.choices) > 0:
                return response.choices[0].message.content.strip()
            else:
                logger.warning(f"OpenAI API call returned no choices. Response: {response}")
                return None
        except openai.APIConnectionError as e:
            logger.error(f"OpenAI API request failed to connect: {e}")
        except openai.RateLimitError as e:
            logger.error(f"OpenAI API request hit rate limit: {e}")
        except openai.APIStatusError as e:
            logger.error(f"OpenAI API returned an error status: {e.status_code} - {e.response}")
        except Exception as e:
            logger.error(f"An unexpected error occurred during OpenAI API call: {e}", exc_info=True)

        return None

# Example factory function (can be expanded later)
def get_llm_provider(provider_name: str = "openai") -> Optional[LLMProvider]:
    if provider_name.lower() == "openai":
        return OpenAIProvider()
    # Add other providers here (e.g., Anthropic)
    # elif provider_name.lower() == "anthropic":
    #    return AnthropicProvider()
    else:
        logger.error(f"Unknown LLM provider requested: {provider_name}")
        return None 