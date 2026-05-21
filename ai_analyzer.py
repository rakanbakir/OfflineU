"""
OfflineU AI Analyzer
Analyzes lessons using pluggable AI providers and stores results as JSON.
"""

import json
import os
import re
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple


def _root_cause(exc: BaseException) -> str:
    """Walk the exception chain and return the deepest cause with its type."""
    seen: set = set()
    current: Optional[BaseException] = exc
    while current is not None:
        if id(current) in seen:
            break
        seen.add(id(current))
        nxt = current.__cause__ or current.__context__
        if nxt is None:
            break
        current = nxt
    return f"{type(current).__name__}: {current}"

# ---------------------------------------------------------------------------
# Optional provider SDK availability flags
# ---------------------------------------------------------------------------
try:
    import openai as _openai_sdk
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import anthropic as _anthropic_sdk
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    import google.generativeai as _genai_sdk
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False

# ---------------------------------------------------------------------------
# Provider catalogue
# ---------------------------------------------------------------------------
AI_PROVIDERS: Dict[str, Dict[str, Any]] = {
    "openai": {
        "name": "OpenAI",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
        "requires_api_key": True,
        "base_url": "https://api.openai.com/v1",
        "install_hint": "pip install openai",
    },
    "anthropic": {
        "name": "Anthropic",
        "models": [
            "claude-opus-4-5",
            "claude-sonnet-4-5",
            "claude-3-5-sonnet-20241022",
            "claude-3-haiku-20240307",
        ],
        "requires_api_key": True,
        "install_hint": "pip install anthropic",
    },
    "google": {
        "name": "Google Gemini",
        "models": ["gemini-1.5-pro", "gemini-1.5-flash", "gemini-2.0-flash", "gemini-pro"],
        "requires_api_key": True,
        "install_hint": "pip install google-generativeai",
    },
    "ollama": {
        "name": "Ollama (Local)",
        "models": ["llama3.2", "llama3.1", "llama3", "mistral", "mixtral", "phi3", "gemma2"],
        "requires_api_key": False,
        "base_url": "http://localhost:11434",
        "install_hint": "Install Ollama from https://ollama.ai",
    },
    "github_copilot": {
        "name": "GitHub Copilot",
        "models": [
            "gpt-4o",
            "gpt-4o-mini",
            "claude-3.5-sonnet",
            "claude-3.7-sonnet",
            "o1",
            "o3-mini",
            "gemini-2.0-flash-001",
        ],
        "requires_api_key": True,
        "base_url": "https://api.githubcopilot.com",
        "install_hint": "pip install openai  |  Token: GitHub PAT with 'copilot_chat' scope",
    },
    "openai_compatible": {
        "name": "OpenAI-Compatible API",
        "models": [],  # user-defined
        "requires_api_key": False,
        "base_url": "",  # user-defined
        "install_hint": "pip install openai",
    },
}

# ---------------------------------------------------------------------------
# Subtitle / transcript parsers
# ---------------------------------------------------------------------------

class SubtitleParser:
    @staticmethod
    def parse_srt(content: str) -> str:
        """Strip SRT timing/index lines and return plain transcript text."""
        # Remove sequence numbers on their own line
        text = re.sub(r'^\d+\s*$', '', content, flags=re.MULTILINE)
        # Remove timing lines  00:00:01,000 --> 00:00:04,000
        text = re.sub(
            r'\d{2}:\d{2}:\d{2}[,\.]\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}[,\.]\d{3}[^\n]*',
            '',
            text,
        )
        # Strip HTML/SDH tags
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\{[^}]+\}', '', text)
        # Collapse excess blank lines
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    @staticmethod
    def parse_vtt(content: str) -> str:
        """Strip VTT header/timing lines and return plain transcript text."""
        lines = content.splitlines()
        text_lines: List[str] = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith('WEBVTT') or line.startswith('NOTE') or line.startswith('STYLE'):
                continue
            if re.match(r'\d{2}:\d{2}[:\.]', line) and '-->' in line:
                continue
            if re.match(r'^\d+$', line):
                continue
            # Strip inline tags
            clean = re.sub(r'<[^>]+>', '', line)
            if clean.strip():
                text_lines.append(clean.strip())
        return '\n'.join(text_lines)

    @staticmethod
    def parse_auto(path: Path) -> str:
        """Detect format and parse accordingly."""
        try:
            content = path.read_text(encoding='utf-8', errors='ignore')
        except OSError:
            return ''
        ext = path.suffix.lower()
        if ext == '.srt':
            return SubtitleParser.parse_srt(content)
        elif ext in ('.vtt', '.sbv'):
            return SubtitleParser.parse_vtt(content)
        return content  # .ass / .sub — return as-is and let the LLM handle it


# ---------------------------------------------------------------------------
# Core analyser
# ---------------------------------------------------------------------------

class AIAnalyzer:
    """Wraps multiple AI providers behind a single `analyze_lesson` interface."""

    _MAX_CONTEXT_CHARS = 14_000  # ~3 500 tokens safety cap

    def __init__(self, config: Dict[str, Any]):
        self.provider: str = config.get('provider', '')
        self.model: str = config.get('model', '')
        self.api_key: str = config.get('api_key', '')
        self.base_url: str = config.get('base_url', '').rstrip('/')

    # ------------------------------------------------------------------
    # Context extraction
    # ------------------------------------------------------------------

    def _get_lesson_context(self, lesson, course_path: str) -> Tuple[str, str]:
        """Return (text_context, source_label) for the lesson."""
        course_root = Path(course_path)

        # 1. Subtitles
        if lesson.subtitle_file:
            sub_path = course_root / lesson.subtitle_file
            if sub_path.exists():
                text = SubtitleParser.parse_auto(sub_path)
                if text:
                    return self._truncate(text), 'subtitles'

        # 2. Text/markdown files attached to the lesson
        if lesson.text_files:
            parts: List[str] = []
            for tf in lesson.text_files[:3]:
                fp = course_root / tf
                if fp.exists() and fp.suffix.lower() in {'.txt', '.md'}:
                    try:
                        parts.append(fp.read_text(encoding='utf-8', errors='ignore')[:5000])
                    except OSError:
                        pass
            if parts:
                return self._truncate('\n\n'.join(parts)), 'text_files'

        return '', 'filename_only'

    def _truncate(self, text: str) -> str:
        if len(text) > self._MAX_CONTEXT_CHARS:
            return text[: self._MAX_CONTEXT_CHARS] + '\n...[truncated]'
        return text

    # ------------------------------------------------------------------
    # Prompt builder
    # ------------------------------------------------------------------

    def _build_prompt(self, lesson, context: str, context_source: str) -> str:
        lesson_info_lines = [
            f"Lesson Title: {lesson.title}",
            f"Lesson Type: {lesson.lesson_type}",
        ]
        if lesson.video_file:
            lesson_info_lines.append(f"Video File: {Path(lesson.video_file).name}")
        lesson_info = '\n'.join(lesson_info_lines)

        json_schema = '''{
  "summary": "A clear 2-3 paragraph summary of what this lesson covers",
  "key_points": ["key point 1", "key point 2", "..."],
  "notes": ["important note 1", "important note 2", "..."],
  "topics": ["topic1", "topic2", "..."],
  "difficulty_level": "beginner | intermediate | advanced",
  "prerequisites": ["prerequisite 1", "..."],
  "takeaways": ["main takeaway 1", "main takeaway 2", "..."]
}'''

        if context:
            return (
                "You are an expert educational content analyzer.\n"
                f"{lesson_info}\n\n"
                f"Content source: {context_source}\n\n"
                f"{context}\n\n"
                "Analyze the above lesson content and return ONLY a valid JSON object "
                "with this exact structure (no markdown fences, no extra text):\n"
                f"{json_schema}"
            )
        else:
            return (
                "You are an expert educational content analyzer.\n"
                f"{lesson_info}\n\n"
                "No transcript or subtitles are available. Based only on the metadata "
                "above, predict what this lesson likely covers and return ONLY a valid "
                "JSON object (no markdown fences, no extra text):\n"
                f"{json_schema}"
            )

    # ------------------------------------------------------------------
    # Provider call implementations
    # ------------------------------------------------------------------

    def _call_openai(self, prompt: str) -> str:
        if not OPENAI_AVAILABLE:
            raise ImportError(
                "openai package is not installed. Run: pip install openai"
            )
        base = self.base_url or 'https://api.openai.com/v1'
        import httpx as _httpx
        client = _openai_sdk.OpenAI(
            api_key=self.api_key,
            base_url=base,
            http_client=_httpx.Client(trust_env=False),
        )
        try:
            resp = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=2048,
            )
            return resp.choices[0].message.content or ''
        except _openai_sdk.AuthenticationError as exc:
            raise PermissionError(
                f"OpenAI authentication failed — check your API key. Detail: {exc.message}"
            ) from exc
        except _openai_sdk.APIConnectionError as exc:
            raise ConnectionError(
                f"Cannot reach the OpenAI API ({base}). "
                f"Root cause: {_root_cause(exc)}"
            ) from exc
        except _openai_sdk.RateLimitError as exc:
            raise RuntimeError(
                f"OpenAI rate limit exceeded — try again later. Detail: {exc.message}"
            ) from exc
        except _openai_sdk.APIStatusError as exc:
            raise RuntimeError(
                f"OpenAI API error {exc.status_code}: {exc.message}"
            ) from exc

    def _call_anthropic(self, prompt: str) -> str:
        if not ANTHROPIC_AVAILABLE:
            raise ImportError(
                "anthropic package is not installed. Run: pip install anthropic"
            )
        import httpx as _httpx
        client = _anthropic_sdk.Anthropic(
            api_key=self.api_key,
            base_url=self.base_url or 'https://api.anthropic.com',
            http_client=_httpx.Client(trust_env=False),
        )
        try:
            msg = client.messages.create(
                model=self.model,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            return msg.content[0].text
        except _anthropic_sdk.AuthenticationError as exc:
            raise PermissionError(
                f"Anthropic authentication failed — check your API key. Detail: {exc.message}"
            ) from exc
        except _anthropic_sdk.APIConnectionError as exc:
            raise ConnectionError(
                f"Cannot reach the Anthropic API. Root cause: {_root_cause(exc)}"
            ) from exc
        except _anthropic_sdk.RateLimitError as exc:
            raise RuntimeError(
                f"Anthropic rate limit exceeded — try again later. Detail: {exc.message}"
            ) from exc
        except _anthropic_sdk.APIStatusError as exc:
            raise RuntimeError(
                f"Anthropic API error {exc.status_code}: {exc.message}"
            ) from exc

    def _call_google(self, prompt: str) -> str:
        if not GOOGLE_AVAILABLE:
            raise ImportError(
                "google-generativeai package is not installed. "
                "Run: pip install google-generativeai"
            )
        try:
            _genai_sdk.configure(api_key=self.api_key)
            model = _genai_sdk.GenerativeModel(self.model)
            resp = model.generate_content(prompt)
            return resp.text
        except Exception as exc:
            msg = str(exc)
            if '401' in msg or 'API_KEY' in msg or 'Invalid' in msg:
                raise PermissionError(
                    f"Google Gemini authentication failed. Check your API key. ({msg})"
                ) from exc
            if 'connect' in msg.lower() or 'network' in msg.lower():
                raise ConnectionError(
                    "Cannot reach the Google Gemini API. Check your internet connection."
                ) from exc
            raise RuntimeError(f"Google Gemini error: {msg}") from exc

    def _call_ollama(self, prompt: str) -> str:
        base = self.base_url or 'http://localhost:11434'
        url = f"{base}/api/chat"
        payload = json.dumps({
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": 0.3},
        }).encode('utf-8')
        req = urllib.request.Request(
            url,
            data=payload,
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                return result.get('message', {}).get('content', '')
        except urllib.error.URLError as exc:
            raise ConnectionError(
                f"Cannot reach Ollama at {base}. "
                "Make sure Ollama is running (`ollama serve`)."
            ) from exc

    @staticmethod
    def _exchange_copilot_token(github_token: str) -> str:
        """
        Exchange a GitHub PAT / OAuth token for a short-lived Copilot API token.
        The Copilot API does not accept GitHub tokens directly.
        """
        url = "https://api.github.com/copilot_internal/v2/token"
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"token {github_token}",
                "Accept": "application/json",
                "Editor-Version": "vscode/1.99.0",
                "Editor-Plugin-Version": "copilot-chat/0.26.0",
                "User-Agent": "OfflineU/1.0",
            },
            method='GET',
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode('utf-8'))
        except urllib.error.HTTPError as exc:
            body = ''
            try:
                body = exc.read().decode('utf-8', errors='ignore')
            except Exception:
                pass
            if exc.code == 401:
                raise PermissionError(
                    "GitHub token rejected during Copilot token exchange. "
                    "Ensure your PAT has the 'copilot_chat' scope and you have "
                    "an active GitHub Copilot subscription."
                ) from exc
            raise ConnectionError(
                f"Copilot token exchange failed (HTTP {exc.code}): {body[:200]}"
            ) from exc
        except urllib.error.URLError as exc:
            raise ConnectionError(
                f"Cannot reach GitHub API for token exchange: {exc.reason}"
            ) from exc

        token = data.get('token')
        if not token:
            raise RuntimeError(
                f"Unexpected Copilot token exchange response: {str(data)[:200]}"
            )
        return token

    def _call_github_copilot(self, prompt: str) -> str:
        """Call the GitHub Copilot Chat API (OpenAI-compatible, with token exchange)."""
        if not OPENAI_AVAILABLE:
            raise ImportError(
                "openai package is not installed. Run: pip install openai"
            )
        if not self.api_key:
            raise ValueError(
                "A GitHub Personal Access Token with the 'copilot_chat' scope "
                "is required for GitHub Copilot."
            )
        # Exchange the GitHub PAT for a short-lived Copilot API token
        copilot_token = self._exchange_copilot_token(self.api_key)
        base = self.base_url or "https://api.githubcopilot.com"
        client = _openai_sdk.OpenAI(
            api_key=copilot_token,
            base_url=base,
            default_headers={
                "Copilot-Integration-Id": "vscode-chat",
                "Editor-Version": "vscode/1.99.0",
            },
        )
        try:
            resp = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=2048,
            )
            return resp.choices[0].message.content or ''
        except _openai_sdk.AuthenticationError as exc:
            raise PermissionError(
                "GitHub Copilot authentication failed. The exchanged token may "
                f"have expired or been rejected. ({exc.message})"
            ) from exc
        except _openai_sdk.APIConnectionError as exc:
            raise ConnectionError(
                f"Cannot reach GitHub Copilot API at {base}. "
                "Check your internet connection."
            ) from exc
        except _openai_sdk.APIStatusError as exc:
            raise RuntimeError(
                f"GitHub Copilot API error {exc.status_code}: {exc.message}"
            ) from exc

    def _call_openai_compatible(self, prompt: str) -> str:
        if not OPENAI_AVAILABLE:
            raise ImportError(
                "openai package is not installed. Run: pip install openai"
            )
        if not self.base_url:
            raise ValueError(
                "base_url must be set for openai_compatible provider."
            )
        client = _openai_sdk.OpenAI(
            api_key=self.api_key or 'no-key',
            base_url=self.base_url,
        )
        resp = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=2048,
        )
        return resp.choices[0].message.content or ''

    # ------------------------------------------------------------------
    # Dispatch + JSON parsing
    # ------------------------------------------------------------------

    def _dispatch(self, prompt: str) -> str:
        dispatch = {
            'openai': self._call_openai,
            'anthropic': self._call_anthropic,
            'google': self._call_google,
            'ollama': self._call_ollama,
            'github_copilot': self._call_github_copilot,
            'openai_compatible': self._call_openai_compatible,
        }
        if self.provider not in dispatch:
            raise ValueError(f"Unknown provider: '{self.provider}'")
        return dispatch[self.provider](prompt)

    @staticmethod
    def _parse_json_response(raw: str) -> Dict[str, Any]:
        """Extract a JSON object from the model response."""
        # Strip optional markdown code fences
        clean = re.sub(r'^```(?:json)?\s*', '', raw.strip(), flags=re.MULTILINE)
        clean = re.sub(r'```\s*$', '', clean, flags=re.MULTILINE)
        clean = clean.strip()
        try:
            return json.loads(clean)
        except json.JSONDecodeError:
            pass
        # Try to extract the first {...} block
        m = re.search(r'\{.*\}', clean, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
        # Fallback: wrap raw text
        return {
            "summary": raw,
            "key_points": [],
            "notes": [],
            "topics": [],
            "difficulty_level": "unknown",
            "prerequisites": [],
            "takeaways": [],
        }

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def analyze_lesson(self, lesson, course_path: str) -> Dict[str, Any]:
        """Run analysis and return structured dict (not yet persisted)."""
        if not self.provider or not self.model:
            raise ValueError("AI provider and model must be configured.")

        context, context_source = self._get_lesson_context(lesson, course_path)
        prompt = self._build_prompt(lesson, context, context_source)
        raw = self._dispatch(prompt)
        analysis = self._parse_json_response(raw)

        # Ensure all expected keys exist with sane defaults
        for key in ('summary', 'key_points', 'notes', 'topics',
                    'difficulty_level', 'prerequisites', 'takeaways'):
            analysis.setdefault(key, [] if key != 'summary' and key != 'difficulty_level' else '')

        analysis['_metadata'] = {
            'lesson_title': lesson.title,
            'lesson_path': lesson.path,
            'video_file': lesson.video_file,
            'provider': self.provider,
            'model': self.model,
            'analyzed_at': datetime.now().isoformat(),
            'context_source': context_source,
            'transcript_used': context_source not in ('filename_only',),
        }
        return analysis

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _analysis_path(course_path: str, lesson_rel_path: str) -> Path:
        ai_dir = Path(course_path) / '.offlineu_ai'
        ai_dir.mkdir(exist_ok=True)
        safe = re.sub(r'[/\\]', '_', lesson_rel_path.strip('/'))
        return ai_dir / f"{safe}.json"

    @staticmethod
    def load_analysis(course_path: str, lesson_rel_path: str) -> Optional[Dict]:
        p = AIAnalyzer._analysis_path(course_path, lesson_rel_path)
        if p.exists():
            try:
                return json.loads(p.read_text(encoding='utf-8'))
            except (OSError, json.JSONDecodeError):
                pass
        return None

    @staticmethod
    def save_analysis(course_path: str, lesson_rel_path: str, analysis: Dict) -> str:
        p = AIAnalyzer._analysis_path(course_path, lesson_rel_path)
        p.write_text(json.dumps(analysis, indent=2, ensure_ascii=False), encoding='utf-8')
        return str(p)
