import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Union

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RulesConfigManager:
    """Manages static analysis rule configurations for different languages and tools."""
    
    def __init__(self, config_dir: Optional[str] = None):
        # Set default config directory if not provided
        if config_dir is None:
            self.config_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config")
        else:
            self.config_dir = config_dir
        
        # Create config directory if it doesn't exist
        os.makedirs(self.config_dir, exist_ok=True)
        
        # Initialize default rule sets
        self._initialize_default_rules()
    
    def _initialize_default_rules(self) -> None:
        """Initialize default rule sets for all supported languages."""
        # Define default rule sets for each language/tool
        self.default_rules = {
            "javascript": {
                "eslint": self._get_default_eslint_rules()
            },
            "typescript": {
                "eslint": self._get_default_eslint_rules(typescript=True)
            },
            "python": {
                "pylint": self._get_default_pylint_rules(),
                "bandit": self._get_default_bandit_rules()
            }
        }
        
        # Define rule presets
        self.rule_presets = {
            "javascript": {
                "strict": self._get_eslint_strict_preset(),
                "recommended": self._get_eslint_recommended_preset(),
                "security": self._get_eslint_security_preset()
            },
            "typescript": {
                "strict": self._get_eslint_strict_preset(typescript=True),
                "recommended": self._get_eslint_recommended_preset(typescript=True),
                "security": self._get_eslint_security_preset(typescript=True)
            },
            "python": {
                "strict": {
                    "pylint": self._get_pylint_strict_preset(),
                    "bandit": self._get_bandit_strict_preset()
                },
                "recommended": {
                    "pylint": self._get_pylint_recommended_preset(),
                    "bandit": self._get_bandit_recommended_preset()
                },
                "security": {
                    "pylint": self._get_pylint_security_preset(),
                    "bandit": self._get_bandit_security_preset()
                }
            }
        }
        
        # Save default rules to disk
        self._save_default_rules()
    
    def _save_default_rules(self) -> None:
        """Save default rules to disk for persistence."""
        try:
            # Create language-specific directories
            for language in self.default_rules.keys():
                language_dir = os.path.join(self.config_dir, language)
                os.makedirs(language_dir, exist_ok=True)
                
                # Save default rules for each tool
                for tool, rules in self.default_rules[language].items():
                    rule_file = os.path.join(language_dir, f"{tool}_default.json")
                    with open(rule_file, 'w') as f:
                        json.dump(rules, f, indent=2)
                
                # Save presets
                presets_dir = os.path.join(language_dir, "presets")
                os.makedirs(presets_dir, exist_ok=True)
                
                for preset_name, preset_config in self.rule_presets[language].items():
                    preset_file = os.path.join(presets_dir, f"{preset_name}.json")
                    with open(preset_file, 'w') as f:
                        json.dump(preset_config, f, indent=2)
                        
            logger.info(f"Default rules and presets saved to {self.config_dir}")
        except Exception as e:
            logger.error(f"Error saving default rules: {str(e)}")
    
    def get_default_rules(self, language: str) -> Dict[str, Any]:
        """Get default rules for a specific language.
        
        Args:
            language: The programming language to get rules for
            
        Returns:
            Dictionary of default rules for the specified language
        """
        language = language.lower()
        if language not in self.default_rules:
            logger.warning(f"No default rules found for language: {language}")
            return {}
        
        return self.default_rules[language]
    
    def get_rule_templates(self) -> Dict[str, Dict]:
        """Get rule templates for all supported languages.
        
        Returns:
            Dictionary of rule templates by language
        """
        templates = {}
        
        # Create templates for each language
        for language, tools in self.default_rules.items():
            templates[language] = {}
            
            # Add templates for each tool
            for tool, rules in tools.items():
                # Create a simplified template with key rule categories
                if tool == "eslint":
                    templates[language][tool] = {
                        "extends": ["eslint:recommended"],
                        "rules": {
                            "no-unused-vars": "error",
                            "no-console": "warn",
                            # Add more common rules as examples
                        }
                    }
                elif tool == "pylint":
                    templates[language][tool] = {
                        "disabled": ["missing-docstring", "invalid-name"],
                        "enabled": ["unused-import", "unused-variable"],
                        "options": {
                            "format": {
                                "max-line-length": 100
                            }
                        }
                    }
                elif tool == "bandit":
                    templates[language][tool] = {
                        "severity": "medium",
                        "confidence": "medium",
                        "tests": ["B201", "B301"],
                        "skips": []
                    }
        
        return templates
    
    def get_rule_presets(self, language: str) -> Dict[str, Any]:
        """Get available rule presets for a specific language.
        
        Args:
            language: The programming language to get presets for
            
        Returns:
            Dictionary of available presets for the specified language
        """
        language = language.lower()
        if language not in self.rule_presets:
            logger.warning(f"No rule presets found for language: {language}")
            return {}
        
        return self.rule_presets[language]
    
    def validate_custom_rules(self, language: str, tool: str, rules: Dict) -> bool:
        """Validate custom rules against the expected schema for a tool.
        
        Args:
            language: The programming language
            tool: The analysis tool (eslint, pylint, bandit)
            rules: The custom rules to validate
            
        Returns:
            True if rules are valid, False otherwise
        """
        try:
            language = language.lower()
            tool = tool.lower()
            
            # Get validation schema based on tool
            if tool == "eslint":
                return self._validate_eslint_rules(rules)
            elif tool == "pylint":
                return self._validate_pylint_rules(rules)
            elif tool == "bandit":
                return self._validate_bandit_rules(rules)
            else:
                logger.warning(f"Unknown tool: {tool}")
                return False
        except Exception as e:
            logger.error(f"Error validating rules: {str(e)}")
            return False
    
    def merge_rule_sets(self, base: Dict, custom: Dict) -> Dict:
        """Merge base rules with custom rules, with custom rules taking precedence.
        
        Args:
            base: Base rule set
            custom: Custom rule set to merge
            
        Returns:
            Merged rule set
        """
        # Create a deep copy of the base rules
        merged = json.loads(json.dumps(base))
        
        # Recursively merge dictionaries
        self._deep_merge(merged, custom)
        
        return merged
    
    def _deep_merge(self, base: Dict, custom: Dict) -> None:
        """Recursively merge custom dict into base dict."""
        for key, value in custom.items():
            # If both values are dicts, merge them recursively
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            # If both values are lists, combine them
            elif key in base and isinstance(base[key], list) and isinstance(value, list):
                base[key] = list(set(base[key] + value))  # Remove duplicates
            # Otherwise, custom value overrides base
            else:
                base[key] = value
    
    def save_custom_rules(self, language: str, tool: str, rules: Dict, name: str) -> bool:
        """Save custom rules to disk.
        
        Args:
            language: The programming language
            tool: The analysis tool
            rules: The custom rules to save
            name: Name for the custom rule set
            
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            language = language.lower()
            tool = tool.lower()
            
            # Validate rules first
            if not self.validate_custom_rules(language, tool, rules):
                logger.error(f"Invalid rules for {language}/{tool}")
                return False
            
            # Create directory if it doesn't exist
            language_dir = os.path.join(self.config_dir, language)
            os.makedirs(language_dir, exist_ok=True)
            
            # Save rules to file
            rule_file = os.path.join(language_dir, f"{tool}_{name}.json")
            with open(rule_file, 'w') as f:
                json.dump(rules, f, indent=2)
            
            logger.info(f"Custom rules saved to {rule_file}")
            return True
        except Exception as e:
            logger.error(f"Error saving custom rules: {str(e)}")
            return False
    
    def load_custom_rules(self, language: str, tool: str, name: str) -> Optional[Dict]:
        """Load custom rules from disk.
        
        Args:
            language: The programming language
            tool: The analysis tool
            name: Name of the custom rule set
            
        Returns:
            Custom rules if found, None otherwise
        """
        try:
            language = language.lower()
            tool = tool.lower()
            
            # Check if file exists
            rule_file = os.path.join(self.config_dir, language, f"{tool}_{name}.json")
            if not os.path.exists(rule_file):
                logger.warning(f"Custom rules not found: {rule_file}")
                return None
            
            # Load rules from file
            with open(rule_file, 'r') as f:
                rules = json.load(f)
            
            return rules
        except Exception as e:
            logger.error(f"Error loading custom rules: {str(e)}")
            return None
    
    def get_available_rule_sets(self, language: str, tool: str) -> List[str]:
        """Get list of available rule sets for a language and tool.
        
        Args:
            language: The programming language
            tool: The analysis tool
            
        Returns:
            List of rule set names
        """
        try:
            language = language.lower()
            tool = tool.lower()
            
            # Check if directory exists
            language_dir = os.path.join(self.config_dir, language)
            if not os.path.exists(language_dir):
                return []
            
            # Get all rule files for the tool
            rule_files = [f for f in os.listdir(language_dir) 
                         if f.startswith(f"{tool}_") and f.endswith(".json")]
            
            # Extract rule set names
            rule_sets = [f.replace(f"{tool}_", "").replace(".json", "") for f in rule_files]
            
            return rule_sets
        except Exception as e:
            logger.error(f"Error getting available rule sets: {str(e)}")
            return []
    
    # Default rule definitions
    def _get_default_eslint_rules(self, typescript: bool = False) -> Dict:
        """Get default ESLint rules."""
        rules = {
            "extends": ["eslint:recommended"],
            "rules": {
                "no-unused-vars": "error",
                "no-console": "warn",
                "no-debugger": "warn",
                "no-alert": "warn",
                "no-duplicate-imports": "error",
                "no-var": "warn",
                "prefer-const": "warn",
                "eqeqeq": "warn",
                "curly": "warn",
                "no-eval": "error"
            }
        }
        
        # Add TypeScript-specific rules
        if typescript:
            rules["extends"].append("plugin:@typescript-eslint/recommended")
            rules["parser"] = "@typescript-eslint/parser"
            rules["plugins"] = ["@typescript-eslint"]
            rules["rules"]["@typescript-eslint/explicit-function-return-type"] = "warn"
            rules["rules"]["@typescript-eslint/no-explicit-any"] = "warn"
        
        return rules
    
    def _get_default_pylint_rules(self) -> Dict:
        """Get default Pylint rules."""
        return {
            "disabled": [
                "missing-docstring",
                "invalid-name",
                "too-few-public-methods"
            ],
            "enabled": [
                "unused-import",
                "unused-variable",
                "undefined-variable"
            ],
            "options": {
                "format": {
                    "max-line-length": 100
                },
                "basic": {
                    "good-names": "i,j,k,ex,Run,_"
                }
            }
        }
    
    def _get_default_bandit_rules(self) -> Dict:
        """Get default Bandit rules."""
        return {
            "severity": "medium",
            "confidence": "medium",
            "tests": [],  # Empty list means all tests
            "skips": []
        }
    
    # Rule presets
    def _get_eslint_strict_preset(self, typescript: bool = False) -> Dict:
        """Get strict ESLint preset."""
        rules = {
            "extends": ["eslint:recommended", "eslint:all"],
            "rules": {
                "no-unused-vars": "error",
                "no-console": "error",
                "no-debugger": "error",
                "no-alert": "error",
                "no-duplicate-imports": "error",
                "no-var": "error",
                "prefer-const": "error",
                "eqeqeq": "error",
                "curly": "error",
                "no-eval": "error",
                "max-len": ["error", { "code": 80 }],
                "complexity": ["error", 5],
                "max-depth": ["error", 3],
                "max-params": ["error", 4]
            }
        }
        
        # Add TypeScript-specific rules
        if typescript:
            rules["extends"].append("plugin:@typescript-eslint/recommended")
            rules["extends"].append("plugin:@typescript-eslint/recommended-requiring-type-checking")
            rules["parser"] = "@typescript-eslint/parser"
            rules["plugins"] = ["@typescript-eslint"]
            rules["rules"]["@typescript-eslint/explicit-function-return-type"] = "error"
            rules["rules"]["@typescript-eslint/no-explicit-any"] = "error"
            rules["rules"]["@typescript-eslint/strict-boolean-expressions"] = "error"
        
        return rules
    
    def _get_eslint_recommended_preset(self, typescript: bool = False) -> Dict:
        """Get recommended ESLint preset."""
        # The recommended preset is the same as the default rules
        return self._get_default_eslint_rules(typescript)
    
    def _get_eslint_security_preset(self, typescript: bool = False) -> Dict:
        """Get security-focused ESLint preset."""
        rules = {
            "extends": ["eslint:recommended", "plugin:security/recommended"],
            "plugins": ["security"],
            "rules": {
                "no-eval": "error",
                "no-implied-eval": "error",
                "no-new-func": "error",
                "security/detect-buffer-noassert": "error",
                "security/detect-child-process": "error",
                "security/detect-disable-mustache-escape": "error",
                "security/detect-eval-with-expression": "error",
                "security/detect-no-csrf-before-method-override": "error",
                "security/detect-non-literal-fs-filename": "error",
                "security/detect-non-literal-regexp": "error",
                "security/detect-non-literal-require": "error",
                "security/detect-object-injection": "error",
                "security/detect-possible-timing-attacks": "error",
                "security/detect-pseudoRandomBytes": "error",
                "security/detect-unsafe-regex": "error"
            }
        }
        
        # Add TypeScript-specific rules
        if typescript:
            rules["extends"].append("plugin:@typescript-eslint/recommended")
            rules["parser"] = "@typescript-eslint/parser"
            rules["plugins"].append("@typescript-eslint")
        
        return rules
    
    def _get_pylint_strict_preset(self) -> Dict:
        """Get strict Pylint preset."""
        return {
            "disabled": [],  # Enable all checks
            "enabled": [
                "all"
            ],
            "options": {
                "format": {
                    "max-line-length": 80
                },
                "design": {
                    "max-args": 4,
                    "max-attributes": 7,
                    "max-bool-expr": 3,
                    "max-branches": 8,
                    "max-locals": 10,
                    "max-parents": 3,
                    "max-public-methods": 15,
                    "max-returns": 5,
                    "max-statements": 30,
                    "min-public-methods": 1
                }
            }
        }
    
    def _get_pylint_recommended_preset(self) -> Dict:
        """Get recommended Pylint preset."""
        # The recommended preset is the same as the default rules
        return self._get_default_pylint_rules()
    
    def _get_pylint_security_preset(self) -> Dict:
        """Get security-focused Pylint preset."""
        return {
            "disabled": [
                "missing-docstring",
                "invalid-name",
                "too-few-public-methods"
            ],
            "enabled": [
                "security",  # Enable security checks
                "unused-import",
                "unused-variable",
                "undefined-variable"
            ],
            "options": {
                "format": {
                    "max-line-length": 100
                }
            }
        }
    
    def _get_bandit_strict_preset(self) -> Dict:
        """Get strict Bandit preset."""
        return {
            "severity": "low",  # Detect all severity levels
            "confidence": "low",  # Include even low-confidence findings
            "tests": [],  # Run all tests
            "skips": []
        }
    
    def _get_bandit_recommended_preset(self) -> Dict:
        """Get recommended Bandit preset."""
        # The recommended preset is the same as the default rules
        return self._get_default_bandit_rules()
    
    def _get_bandit_security_preset(self) -> Dict:
        """Get security-focused Bandit preset."""
        # Bandit is already security-focused, but we can make it more strict
        return self._get_bandit_strict_preset()
    
    # Validation methods
    def _validate_eslint_rules(self, rules: Dict) -> bool:
        """Validate ESLint rules."""
        # Basic structure validation
        if not isinstance(rules, dict):
            return False
        
        # Check for required fields
        if "rules" in rules and not isinstance(rules["rules"], dict):
            return False
        
        if "extends" in rules and not isinstance(rules["extends"], list):
            return False
        
        return True
    
    def _validate_pylint_rules(self, rules: Dict) -> bool:
        """Validate Pylint rules."""
        # Basic structure validation
        if not isinstance(rules, dict):
            return False
        
        # Check for valid fields
        for field in ["disabled", "enabled"]:
            if field in rules and not isinstance(rules[field], list):
                return False
        
        if "options" in rules and not isinstance(rules["options"], dict):
            return False
        
        return True
    
    def _validate_bandit_rules(self, rules: Dict) -> bool:
        """Validate Bandit rules."""
        # Basic structure validation
        if not isinstance(rules, dict):
            return False
        
        # Check for valid fields
        for field in ["tests", "skips"]:
            if field in rules and not isinstance(rules[field], list):
                return False
        
        # Check severity and confidence values
        valid_levels = ["low", "medium", "high"]
        if "severity" in rules and rules["severity"].lower() not in valid_levels:
            return False
        
        if "confidence" in rules and rules["confidence"].lower() not in valid_levels:
            return False
        
        return True


# Singleton instance
rules_config_manager = RulesConfigManager()