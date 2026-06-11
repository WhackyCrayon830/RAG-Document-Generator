"""Recursive validation and rewrite flow for document sections."""

from typing import Optional
from dataclasses import dataclass
from enum import Enum


class ValidationLevel(str, Enum):
    """Validation severity levels."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationIssue:
    """A validation issue found in a section."""
    level: ValidationLevel
    message: str
    location: Optional[str] = None
    suggestion: Optional[str] = None


@dataclass
class ValidationResult:
    """Result of validating a section."""
    is_valid: bool
    issues: list[ValidationIssue]
    rewrite_suggested: bool
    confidence: float  # 0-1, how confident we are in the validation


class RecursiveValidator:
    """Validate sections with deep checking and suggest rewrites."""

    def __init__(self, validation_model: str = "mistral"):
        """Initialize validator with LLM model."""
        self.validation_model = validation_model
        self.max_iterations = 3
        self.iteration_count = 0

    def validate_section(self, section: dict) -> ValidationResult:
        """
        Validate a single section for quality and accuracy.

        Args:
            section: Dict with 'title' and 'content' keys

        Returns:
            ValidationResult with any issues found
        """
        self.iteration_count = 0
        return self._validate_recursive(section)

    def _validate_recursive(self, section: dict) -> ValidationResult:
        """Recursively validate and optionally rewrite section."""
        if self.iteration_count >= self.max_iterations:
            return ValidationResult(
                is_valid=True,
                issues=[],
                rewrite_suggested=False,
                confidence=0.7,
            )

        self.iteration_count += 1
        issues = []

        # Check 1: Content length
        content = section.get("content", "")
        if len(content) < 50:
            issues.append(
                ValidationIssue(
                    level=ValidationLevel.WARNING,
                    message="Section content is very short",
                    suggestion="Expand content to at least 100 characters",
                )
            )

        # Check 2: Coherence
        coherence_ok = self._check_coherence(content)
        if not coherence_ok:
            issues.append(
                ValidationIssue(
                    level=ValidationLevel.WARNING,
                    message="Section may lack coherent structure",
                    suggestion="Organize content with clear logical flow",
                )
            )

        # Check 3: Citations/References
        has_citations = self._check_citations(content)
        if not has_citations and len(content) > 200:
            issues.append(
                ValidationIssue(
                    level=ValidationLevel.INFO,
                    message="No citations found in longer section",
                    suggestion="Consider adding citations to support claims",
                )
            )

        # Check 4: Formatting
        format_issues = self._check_formatting(content)
        issues.extend(format_issues)

        # Check 5: Hallucinations
        hallucination_score = self._detect_hallucinations(section)
        if hallucination_score > 0.3:
            issues.append(
                ValidationIssue(
                    level=ValidationLevel.ERROR,
                    message=f"Potential hallucinations detected (score: {hallucination_score:.2f})",
                    suggestion="Review content for factual accuracy",
                )
            )

        # Determine if rewrite is needed
        error_count = sum(1 for i in issues if i.level == ValidationLevel.ERROR)
        warning_count = sum(1 for i in issues if i.level == ValidationLevel.WARNING)
        
        rewrite_suggested = error_count > 0 or (warning_count >= 2)
        is_valid = error_count == 0

        confidence = max(0.5, 1.0 - (len(issues) * 0.1))

        return ValidationResult(
            is_valid=is_valid,
            issues=issues,
            rewrite_suggested=rewrite_suggested,
            confidence=confidence,
        )

    def _check_coherence(self, content: str) -> bool:
        """Check if content has coherent structure."""
        lines = [l.strip() for l in content.split("\n") if l.strip()]
        
        # Check for minimum paragraph structure
        if len(lines) < 2:
            return False
        
        # Check for some length variation (not all one-liners)
        line_lengths = [len(l) for l in lines]
        avg_length = sum(line_lengths) / len(line_lengths)
        
        return avg_length > 20

    def _check_citations(self, content: str) -> bool:
        """Check if content includes citations."""
        citation_patterns = [
            "(",  # Year citations like (Smith, 2020)
            "[",  # Reference brackets like [1]
            "cited",
            "according to",
            "research shows",
            "study found",
        ]
        
        return any(pattern.lower() in content.lower() for pattern in citation_patterns)

    def _check_formatting(self, content: str) -> list[ValidationIssue]:
        """Check content formatting."""
        issues = []
        
        # Check for excessive whitespace
        if "\n\n\n" in content:
            issues.append(
                ValidationIssue(
                    level=ValidationLevel.INFO,
                    message="Excessive blank lines detected",
                    suggestion="Remove extra blank lines",
                )
            )
        
        # Check for incomplete sentences
        if content.rstrip().endswith(","):
            issues.append(
                ValidationIssue(
                    level=ValidationLevel.WARNING,
                    message="Content may end with incomplete thought",
                    suggestion="Complete the final sentence",
                )
            )
        
        return issues

    def _detect_hallucinations(self, section: dict) -> float:
        """
        Detect potential hallucinations in section.
        Returns a score 0-1 indicating likelihood of hallucination.
        """
        # Placeholder implementation
        # Real implementation would use more sophisticated NLP techniques
        content = section.get("content", "")
        title = section.get("title", "")
        
        hallucination_score = 0.0
        
        # Check for vague claims without support
        vague_patterns = ["definitely", "definitely", "100% sure", "obviously", "clearly"]
        if any(p.lower() in content.lower() for p in vague_patterns):
            hallucination_score += 0.1
        
        # Check for contradictions in title and content
        if len(title) > 5 and title.lower() not in content.lower()[:100]:
            # Title not mentioned early in content - possible mismatch
            hallucination_score += 0.05
        
        return min(1.0, hallucination_score)

    def suggest_rewrite(self, section: dict, issues: list[ValidationIssue]) -> str:
        """
        Generate a rewrite suggestion for a section.

        Args:
            section: The section to rewrite
            issues: Validation issues to address

        Returns:
            Suggested rewrite prompt for the LLM
        """
        issue_summaries = [f"- {issue.message}" for issue in issues if issue.suggestion]
        
        prompt = f"""
Rewrite the following section to address these issues:

Original section:
Title: {section.get('title')}
Content: {section.get('content')}

Issues to fix:
{chr(10).join(issue_summaries)}

Please provide an improved version that:
1. Maintains the original intent
2. Addresses all listed issues
3. Improves clarity and coherence
4. Ensures factual accuracy
"""
        return prompt.strip()
