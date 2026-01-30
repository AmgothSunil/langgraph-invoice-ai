import sys
from pathlib import Path
from typing import Optional

from src.config.exception import AppException
from src.config.logger import setup_logger

logger = setup_logger("PromptManager", "prompt_manager.log")


class PromptManager:
    def load_prompt(self, path: str) -> str:
        """
        Load contextual prompt from a given file path.

        Args:
            path (str): Path to the prompt file.

        Returns:
            str: The prompt text. Returns a default fallback prompt if file not found.
        """
        try:
            prompt_path = Path(path)
            if not prompt_path.exists():
                logger.warning(f"Prompt file not found: {path}. Using default prompt.")
                return "You are a helpful assistant. Answer questions based on the provided context."

            with open(prompt_path, "r", encoding="utf-8") as file:
                prompt_text = file.read().strip()
                logger.info(f"Prompt loaded successfully from: {path}")
                return prompt_text

        except Exception as e:
            logger.error(f"Error while loading prompt file {path}: {e}")
            raise AppException(e, sys)
