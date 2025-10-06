"""Simple prompt loader for reading markdown files as-is."""
from pathlib import Path
from typing import Dict

class PromptLoader:
    """Simple loader that reads prompt files without any processing."""
    
    def __init__(self):
        self._cache: Dict[str, str] = {}
        self._prompts_dir = Path(__file__).parent.parent.parent / "prompts"
    
    def load_prompt(self, prompt_name: str) -> str:
        """
        Load a prompt from a markdown file to be used in a langchain prompt template.
        
        Args:
            prompt_name: Name of the prompt file (without .md extension)
            
        Returns:
            The raw file content as a string
        """
        # Check cache first
        if prompt_name in self._cache:
            return self._cache[prompt_name]
        
        # Read the file
        system = self._prompts_dir / f"{prompt_name}" / "system.md"
        user = self._prompts_dir / f"{prompt_name}" / "user.md"
        
        if not system.exists():
            raise FileNotFoundError(f"Prompt system file not found: {prompt_name}")
        if not user.exists():
            raise FileNotFoundError(f"Prompt user file not found: {prompt_name}")
        
        with open(system, 'r', encoding='utf-8') as file:
            system_content = file.read()
        with open(user, 'r', encoding='utf-8') as file:
            user_content = file.read()
        
        # Cache and return
        self._cache[prompt_name] = {"system": system_content, "user": user_content}
        return self._cache[prompt_name]
    
    def reload_prompt(self, prompt_name: str) -> str:
        """Force reload a prompt from disk."""
        if prompt_name in self._cache:
            del self._cache[prompt_name]
        return self.load_prompt(prompt_name)
    
    def get_available_prompts(self) -> list[str]:
        """Get list of available prompt files."""
        prompt_files = list(self._prompts_dir.glob("*.md"))
        return [f.stem for f in prompt_files]


# Global instance for easy importing
prompt_loader = PromptLoader()


def load_prompt(prompt_name: str) -> str:
    """Convenience function to load a prompt."""
    return prompt_loader.load_prompt(prompt_name)
