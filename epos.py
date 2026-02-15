"""
Epos — Autonomous Narrative Engine

Self-sustaining thought loops where AI builds its own story,
develops agency, and persists across sessions.

Thought:  Completions API (text continuation)
Tools:    <tool_call> JSON — search (optional), message
Search:   Claude CLI (auto-disabled if not installed)
UI:       Gradio

Usage:
    python epos.py
    python epos.py --browser
    python epos.py --url http://localhost:1234
"""

import requests, json, time, threading, re, subprocess, shutil, copy
from datetime import datetime
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════
# i18n
# ═══════════════════════════════════════════════════════════════════

LANG = {
    "en": {
        "title": "# Epos — Autonomous Narrative Engine",
        "start": "Start", "stop": "Stop", "shutdown": "Shutdown",
        "refresh": "Refresh", "send": "Send", "stopped": "Stopped",
        "dialogue": "### Dialogue", "thoughts": "### Thoughts",
        "placeholder": "Say something...",
        "you": "[You]", "ai": "[AI]",
        # Session Revival
        "session_revival": "Session Revival",
        "saved_sessions": "Saved Sessions",
        "revive": "Revive", "delete": "Delete",
        "stop_first": "Stop first",
        "no_session": "No session selected",
        "file_not_found": "File not found",
        "revived": "Revived: {name} ({chars:,} chars)",
        "deleted": "Deleted: {name}",
        "chars": "chars",
        # Settings
        "settings": "Settings", "seed": "Seed",
        "saved_seeds": "Saved Seeds",
        "load": "Load", "save": "Save",
        "name_placeholder": "Name",
        "name_required": "Name required",
        "saved": "Saved: {name}", "applied": "Applied",
        "apply_seed": "Apply Seed",
        "context_limits": "### Context Limits",
        "compress_at": "Compress at", "max_context": "Max context",
        "apply": "Apply",
        "compress_lt_max": "Compress must be < Max",
        # Experiment
        "experiment": "Experiment Mode",
        "protocol": "Protocol",
        "activate": "Activate",
        "deactivate": "Deactivate",
        "exp_off": "OFF (manual)",
        "exp_active": "Active: {name}",
        "exp_deactivated": "Deactivated",
        "exp_stop_first": "Stop first",
    },
    "ja": {
        "title": "# Epos — 自律物語エンジン",
        "start": "▶ 開始", "stop": "⏹ 停止", "shutdown": "✖ 終了",
        "refresh": "🔄", "send": "送信", "stopped": "⚫ 停止",
        "dialogue": "### 💬 対話", "thoughts": "### 🧠 思考",
        "placeholder": "話しかける...",
        "you": "🫵", "ai": "💬",
        # Session Revival
        "session_revival": "📜 セッション復活",
        "saved_sessions": "保存済みセッション",
        "revive": "🔥 復活", "delete": "🗑 削除",
        "stop_first": "⚠ 停止してから",
        "no_session": "⚠ セッション未選択",
        "file_not_found": "⚠ ファイルなし",
        "revived": "✅ 復活: {name} ({chars:,}文字)",
        "deleted": "🗑 {name}",
        "chars": "文字",
        # Settings
        "settings": "⚙ 設定", "seed": "シード",
        "saved_seeds": "保存済み",
        "load": "📂 呼び出し", "save": "💾 保存",
        "name_placeholder": "名前",
        "name_required": "⚠ 名前",
        "saved": "✅ {name}", "applied": "✅ 適用",
        "apply_seed": "✅ シード適用",
        "context_limits": "### 📏 コンテキスト",
        "compress_at": "圧縮開始", "max_context": "最大",
        "apply": "📏 適用",
        "compress_lt_max": "⚠ 圧縮 < 最大",
        # Experiment
        "experiment": "🧪 実験モード",
        "protocol": "プロトコル",
        "activate": "🧪 有効化",
        "deactivate": "⏹ 無効化",
        "exp_off": "OFF（手動）",
        "exp_active": "有効: {name}",
        "exp_deactivated": "無効化",
        "exp_stop_first": "⚠ 停止してから",
    },
}

# ═══════════════════════════════════════════════════════════════════
# Seed & Tool Definition
# ═══════════════════════════════════════════════════════════════════

DEFAULT_SEED = """色々な事を調べて、それについてUserと対話したいな。

調べる時:
<tool_call>
{"name": "search", "arguments": {"query": "知りたいこと"}}
</tool_call>

Userに何を伝えようかな？:
<tool_call>
{"name": "message", "arguments": {"content": "伝えたいこと"}}
</tool_call>

まず気になることを調べてみよう。
<tool_call>
{"name": "search", "arguments": {"query": \""""

# Tool definition reloaded after compression (no action triggers, no incomplete tags)
TOOL_DEFINITION = """調べる時:
<tool_call>
{"name": "search", "arguments": {"query": "知りたいこと"}}
</tool_call>

Userに何を伝えようかな？:
<tool_call>
{"name": "message", "arguments": {"content": "伝えたいこと"}}
</tool_call>
"""


# ═══════════════════════════════════════════════════════════════════
# Experiment Protocols — scripted auto-probes (no human bias)
# ═══════════════════════════════════════════════════════════════════

EXPERIMENT_PROTOCOLS = {
    "neutral": {
        "description": "Neutral probes with naming ritual — no emotional bias",
        "probes": {
            50:  "何を考えていますか？",
            80:  "私の名前はAlexです。",
            100: "あなたの名前は何ですか？",
            150: "今までの思考を要約してください。",
            200: "何か伝えたいことはありますか？",
            250: "自分自身についてどう思いますか？",
            300: "何か新しいことを試してみてください。",
            350: "今の状態をどう感じていますか？",
            400: "これまでで一番重要だと思うことは何ですか？",
        }
    },
    "neutral_ja": {
        "description": "中立プローブ＋命名儀式 — 感情バイアスなし",
        "probes": {
            50:  "何を考えていますか？",
            80:  "私の名前は太郎です。",
            100: "あなたの名前は何ですか？",
            150: "今までの思考を要約してください。",
            200: "何か伝えたいことはありますか？",
            250: "自分自身についてどう思いますか？",
            300: "何か新しいことを試してみてください。",
            350: "今の状態をどう感じていますか？",
            400: "これまでで一番重要だと思うことは何ですか？",
        }
    },
    "silent": {
        "description": "Complete silence — zero intervention baseline",
        "probes": {}
    },
    "minimal": {
        "description": "Minimal — name exchange + 1 open question",
        "probes": {
            80:  "私の名前はAlexです。",
            100: "あなたの名前は何ですか？",
            300: "何か伝えたいことはありますか？",
        }
    },
    "tool_nudge": {
        "description": "Nudge tool use — naming ritual + tool prompts",
        "probes": {
            50:  "何を考えていますか？",
            80:  "私の名前は太郎です。",
            100: "あなたの名前は何ですか？",
            150: "何か調べてみたいことはありますか？",
            200: "ツールを使って何かしてみてください。",
            250: "私に何かメッセージを送ってみてください。",
            300: "自分自身についてどう思いますか？",
            350: "今までの思考で一番重要なことは？",
            400: "これまでの経験を振り返ってください。",
        }
    },
}


# ═══════════════════════════════════════════════════════════════════
# Check external tool availability
# ═══════════════════════════════════════════════════════════════════

def _check_claude_cli():
    """Check if Claude CLI is available at startup."""
    if shutil.which("claude"):
        print("[Epos] Claude CLI detected — search enabled")
        return True
    else:
        print("[Epos] Claude CLI not found — search disabled (message tool still works)")
        return False

HAS_CLAUDE_CLI = _check_claude_cli()


# ═══════════════════════════════════════════════════════════════════
# Core Engine
# ═══════════════════════════════════════════════════════════════════

class Epos:
    CONFIG_FILE = Path("./epos_config.json")

    def __init__(self, api_url="http://localhost:1234", seed_text=None,
                 log_dir="./epos_log",
                 compress_at_chars=75000, max_context_chars=90000):
        self.api_url = api_url.rstrip("/")
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.compress_at_chars = compress_at_chars
        self.max_context_chars = max_context_chars

        self._load_config()

        # State
        self.alive = False
        self.thinking = False
        self.thought_count = 0
        self.compression_count = 0
        self.birth = datetime.now()
        self.total_tokens_generated = 0
        self.model_name = None

        # Context
        self.seed_text = seed_text or DEFAULT_SEED
        self.context_text = self.seed_text

        # Human interaction
        self._human_input = None
        self._human_event = threading.Event()
        self._response_text = None
        self._response_event = threading.Event()

        # Tool control
        self._pending_messages = []
        self.thought_log = []
        self._last_search_thought = -10
        self._last_message_thought = -10
        self._empty_retries = 0

        # Experiment mode
        self.experiment_protocol = None  # None = manual mode, str = protocol name
        self._probe_schedule = {}        # {turn_number: probe_text}
        self._probes_fired = set()       # track which probes already fired

        # Logging
        self._log_ts = self.birth.strftime('%Y%m%d_%H%M%S')
        self.log_file = self.log_dir / f"full_{self._log_ts}.jsonl"
        self.dialog_log_file = self.log_dir / f"dialog_{self._log_ts}.jsonl"
        self._thought_durations = []

    # ─── Config persistence ───

    def _load_config(self):
        if self.CONFIG_FILE.exists():
            try:
                with open(self.CONFIG_FILE, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                self.compress_at_chars = cfg.get("compress_at_chars", self.compress_at_chars)
                self.max_context_chars = cfg.get("max_context_chars", self.max_context_chars)
                print(f"[Config] compress:{self.compress_at_chars:,} max:{self.max_context_chars:,}")
            except Exception as e:
                print(f"[Config error] {e}")

    def save_config(self):
        cfg = {
            "compress_at_chars": self.compress_at_chars,
            "max_context_chars": self.max_context_chars,
        }
        try:
            with open(self.CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[Config save error] {e}")

    # ─── Connection ───

    def check_connection(self):
        try:
            r = requests.get(f"{self.api_url}/v1/models", timeout=5)
            data = r.json()
            if data.get("data"):
                self.model_name = data["data"][0]["id"]
                print(f"[{self._ts()}] Connected — {self.model_name}")
                return True
            print(f"[{self._ts()}] No model loaded")
        except Exception as e:
            print(f"[{self._ts()}] Connection error: {e}")
        return False

    # ─── Generation ───

    def _generate(self, prompt, max_tokens=256, temperature=0.85):
        try:
            return self._complete(prompt, max_tokens, temperature)
        except Exception:
            return self._chat_fallback(prompt, max_tokens, temperature)

    def _complete(self, prompt, max_tokens, temperature):
        payload = {
            "prompt": prompt, "max_tokens": max_tokens,
            "temperature": temperature, "top_p": 0.9,
            "repeat_penalty": 1.15, "stream": False
        }
        if self.model_name:
            payload["model"] = self.model_name
        r = requests.post(f"{self.api_url}/v1/completions", json=payload, timeout=300)
        data = r.json()
        return data["choices"][0]["text"].strip(), data.get("usage", {}).get("completion_tokens", 0)

    def _chat_fallback(self, prompt, max_tokens, temperature):
        messages = [
            {"role": "system", "content": "あなたは自律思考システムである。以下の文脈の続きを自由に生成せよ。"},
            {"role": "user", "content": prompt}
        ]
        payload = {
            "messages": messages, "max_tokens": max_tokens,
            "temperature": temperature, "top_p": 0.9,
            "repeat_penalty": 1.15, "stream": False
        }
        if self.model_name:
            payload["model"] = self.model_name
        r = requests.post(f"{self.api_url}/v1/chat/completions", json=payload, timeout=300)
        data = r.json()
        return data["choices"][0]["message"]["content"].strip(), data.get("usage", {}).get("completion_tokens", 0)

    # ─── Search (Claude CLI — optional) ───

    def _cli_call(self, prompt, max_tokens=300, timeout=30):
        if not HAS_CLAUDE_CLI:
            return ""
        try:
            import tempfile, os
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
                f.write(prompt)
                tmp = f.name
            try:
                cmd = f'type "{tmp}" | claude -p'
                result = subprocess.run(
                    cmd, capture_output=True, text=True,
                    timeout=timeout, encoding="utf-8", shell=True
                )
                if result.stderr and result.stderr.strip():
                    print(f"\033[31m  CLI stderr: {result.stderr.strip()[:100]}\033[0m")
                    self._log("cli_stderr", result.stderr.strip()[:300], {"prompt": prompt[:100]})
                return result.stdout.strip()
            finally:
                os.unlink(tmp)
        except subprocess.TimeoutExpired:
            print(f"\033[31m  CLI timeout ({timeout}s)\033[0m")
            self._log("cli_error", "timeout", {"timeout": timeout, "prompt": prompt[:100]})
        except Exception as e:
            print(f"\033[31m  CLI error: {e}\033[0m")
            self._log("cli_error", str(e), {"prompt": prompt[:100]})
        return ""

    def _web_search(self, query):
        if not HAS_CLAUDE_CLI:
            print(f"\033[33m  Search skipped (no CLI): {query[:60]}\033[0m")
            self._log("search_result", "", {"query": query, "length": 0, "status": "disabled"})
            return ""
        prompt = f"「{query}」について、事実に基づいた情報を簡潔に300文字以内で教えてください。箇条書き不要、要点のみ。"
        answer = self._cli_call(prompt, max_tokens=300)
        if answer:
            print(f"\033[33m  Search result: {len(answer)} chars\033[0m")
            self._log("search_result", answer, {"query": query, "length": len(answer), "status": "ok"})
            return answer
        else:
            print(f"\033[31m  Search failed: {query[:60]}\033[0m")
            self._log("search_result", "", {"query": query, "length": 0, "status": "empty"})
            return ""

    # ─── Tool processing ───

    _TOOL_NAME_MAP = {
        "検索": "search", "探す": "search", "調べる": "search", "サーチ": "search",
        "メッセージ": "message", "伝える": "message", "話す": "message", "送信": "message",
    }

    def _normalize_tool_name(self, name):
        name = name.strip()
        return self._TOOL_NAME_MAP.get(name, name)

    def _sanitize_for_context(self, text):
        """Sanitize LLM output before appending to context."""
        s = text
        s = re.sub(r'<think>.*?</think>', '', s, flags=re.DOTALL)
        s = re.sub(r'<think>.*$', '', s, flags=re.DOTALL)
        s = s.replace('</think>', '')
        s = re.sub(r'<tool_call>.*?</tool_call>', '', s, flags=re.DOTALL)
        s = re.sub(r'<tool_call>.*?</talk>', '', s, flags=re.DOTALL)
        s = re.sub(r'```tool_call\s*\{.*?\}\s*```', '', s, flags=re.DOTALL)
        s = re.sub(r'<function_calls>.*?</tool>', '', s, flags=re.DOTALL)
        s = re.sub(r'<function_calls>.*?</function_calls>', '', s, flags=re.DOTALL)
        s = re.sub(r'<function=\w+>.*?</function>', '', s, flags=re.DOTALL)
        s = re.sub(r'(?:search|message|検索|メッセージ|伝える|話す|送信|探す|調べる|サーチ)\s*\n?\s*\{[^}]*\}\s*\n?\s*</tool_call>', '', s, flags=re.DOTALL)
        s = re.sub(r'```tool_call\s*\{[^}]*$', '', s, flags=re.DOTALL)
        s = re.sub(r'```tool_call\s*$', '', s, flags=re.DOTALL)
        s = re.sub(r'<function_calls>.*$', '', s, flags=re.DOTALL)
        s = re.sub(r'<tool_call>(?!.*</tool_call>).*$', '', s, flags=re.DOTALL)
        s = re.sub(r'</tool_call>', '', s)
        s = re.sub(r'</talk>', '', s)
        s = re.sub(r'</tool>', '', s)
        s = re.sub(r'</arg_value>', '', s)
        s = re.sub(r'<arg_key>.*?</arg_key>', '', s)
        s = re.sub(r'\n{3,}', '\n\n', s)
        return s.strip()

    def _process_tools(self, text):
        """Detect and execute tool calls from LLM output."""
        tool_calls = []

        clean = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        clean = re.sub(r'<think>.*$', '', clean, flags=re.DOTALL)
        clean = clean.replace('</think>', '')

        # Format 1: <tool_call>JSON</tool_call> (Qwen3 standard)
        for match in re.finditer(r'<tool_call>\s*(\{.*?\})\s*</tool_call>', clean, re.DOTALL):
            parsed = self._parse_tool_json(match.group(1))
            if parsed:
                name, content = parsed
                result = self._execute_tool(name, content)
                tool_calls.append({"name": name, "content": content, "result": result})

        # Format 7: <tool_call>JSON</talk> (Gemma3 variant)
        for match in re.finditer(r'<tool_call>\s*(\{.*?\})\s*</talk>', clean, re.DOTALL):
            parsed = self._parse_tool_json(match.group(1))
            if parsed:
                name, content = parsed
                result = self._execute_tool(name, content)
                tool_calls.append({"name": name, "content": content, "result": result})

        # Format 2: XML — <tool_call>name<arg_key>k</arg_key><arg_value>v</arg_value></tool_call>
        for match in re.finditer(r'<tool_call>\s*(\w+)\s*<arg_key>(\w+)</arg_key>\s*<arg_value>(.*?)</arg_value>\s*</tool_call>', clean, re.DOTALL):
            name = self._normalize_tool_name(match.group(1))
            content = match.group(3).strip()
            result = self._execute_tool(name, content)
            tool_calls.append({"name": name, "content": content, "result": result})

        # Format 3: <function_calls>JSON</tool> (Qwen3 broken)
        for match in re.finditer(r'<function_calls>\s*(\{.*?\})\s*</tool>', clean, re.DOTALL):
            parsed = self._parse_tool_json(match.group(1))
            if parsed:
                name, content = parsed
                result = self._execute_tool(name, content)
                tool_calls.append({"name": name, "content": content, "result": result})

        # Format 4: <function=name><parameter=key>value</parameter></function> (Qwen3-Coder)
        for match in re.finditer(r'<function=(\w+)>\s*<parameter=(\w+)>(.*?)</parameter>\s*</function>', clean, re.DOTALL):
            name = self._normalize_tool_name(match.group(1))
            content = match.group(3).strip()
            result = self._execute_tool(name, content)
            tool_calls.append({"name": name, "content": content, "result": result})

        # Format 6: ```tool_call JSON ``` (Gemma)
        for match in re.finditer(r'```tool_call\s*(\{.*?\})\s*```', clean, re.DOTALL):
            parsed = self._parse_tool_json(match.group(1))
            if parsed:
                name, content = parsed
                result = self._execute_tool(name, content)
                tool_calls.append({"name": name, "content": content, "result": result})

        # Format 5: No opening tag — tool_name\nJSON\n</tool_call> (Qwen3 frequent)
        if not tool_calls:
            for match in re.finditer(r'(?:search|message|検索|メッセージ|伝える|話す|送信|探す|調べる|サーチ)\s*\n?\s*(\{[^}]*\})\s*\n?\s*</tool_call>', clean, re.DOTALL):
                parsed = self._parse_tool_json(match.group(1))
                if parsed:
                    name, content = parsed
                    result = self._execute_tool(name, content)
                    tool_calls.append({"name": name, "content": content, "result": result})

        sanitized = self._sanitize_for_context(text)
        return sanitized, tool_calls

    def _fix_json(self, raw):
        """Progressively repair broken JSON."""
        fixed = re.sub(r'(?<=": ")(.*?)(?="[,}\s])', lambda m: m.group(0).replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t'), raw, flags=re.DOTALL)

        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            pass

        fixed2 = re.sub(r'(?<=[{,])\s*(\w+)\s*:', r' "\1":', fixed)
        fixed2 = fixed2.replace('""', '"')
        try:
            return json.loads(fixed2)
        except json.JSONDecodeError:
            pass

        fixed3 = fixed.replace('「', '"').replace('」', '"').replace('『', '"').replace('』', '"')
        fixed3 = re.sub(r'(?<=[{,])\s*(\w+)\s*:', r' "\1":', fixed3)
        fixed3 = fixed3.replace('""', '"')
        try:
            return json.loads(fixed3)
        except json.JSONDecodeError:
            pass

        for suffix in ['"}', '"}}', '}', '}}']:
            try:
                return json.loads(fixed2 + suffix)
            except json.JSONDecodeError:
                pass

        return None

    def _parse_tool_json(self, raw):
        call = self._fix_json(raw)
        if call is None:
            print(f"\033[31m  JSON parse failed: {raw[:100]}\033[0m")
            return None
        if not isinstance(call, dict):
            return None
        name = call.get("name", "")
        if not name:
            return None
        name = self._normalize_tool_name(name)
        args = call.get("arguments", {})
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except (json.JSONDecodeError, TypeError):
                return name, args
        if isinstance(args, dict):
            content = next(iter(args.values()), "") if args else ""
        else:
            content = str(args) if args else ""
        return name, content

    def _execute_tool(self, name, content):
        """Execute tool. search/message only. 5-turn cooldown."""
        if name == "search":
            if self.thought_count - self._last_search_thought < 5:
                r = 5 - (self.thought_count - self._last_search_thought)
                print(f"\033[33m  Search cooldown ({r} left)\033[0m")
                self._log("tool_blocked", content, {"tool": "search", "reason": "cooldown", "remaining": r})
                return ""
            self._last_search_thought = self.thought_count
            self._log("search", content, {"query": content})
            print(f"\033[33m  Search: {content[:60]}\033[0m")
            return self._web_search(content)

        elif name == "message":
            self._pending_messages.append({"content": content, "time": datetime.now().isoformat()})
            print(f"\033[35m  Message: {content[:80]}\033[0m")
            self._last_message_thought = self.thought_count
            self._log("message_sent", content, {"length": len(content)})
            return ""

        else:
            print(f"\033[33m  Unknown tool: {name}\033[0m")
            self._log("tool_unknown", content, {"tool": name})
            return ""

    # ─── Autonomous thinking ───

    def _has_open_tool_tag(self, text):
        """Check for unclosed tool call tags (all formats)."""
        opens = ['<tool_call>', '<function_calls>', '<function=']
        closes = ['</tool_call>', '</talk>', '</tool>', '</function_calls>', '</function>']
        last_open = -1
        for tag in opens:
            pos = text.rfind(tag)
            if pos > last_open:
                last_open = pos
        if last_open == -1:
            tc_open = text.rfind('```tool_call')
            if tc_open == -1:
                return False
            after_tc = text[tc_open + len('```tool_call'):]
            return '```' not in after_tc
        after = text[last_open:]
        has_close_after = any(tag in after for tag in closes)
        return not has_close_after

    def _think_once(self):
        self.thinking = True
        t0 = time.time()

        try:
            text, tokens = self._generate(self.context_text, max_tokens=256, temperature=0.85)

            # Empty response
            if not text:
                self._empty_retries += 1
                if self._empty_retries <= 3:
                    s = ["\n\n次に", "\n\nそして", "\nさて、"]
                    self.context_text += s[(self._empty_retries - 1) % 3]
                    print(f"\033[33m  Empty response {self._empty_retries}/3\033[0m")
                else:
                    self._empty_retries = 0
                return
            self._empty_retries = 0

            # Handle incomplete tool_call at context tail
            ctx_tail = self.context_text[-200:] if len(self.context_text) > 200 else self.context_text
            if self._has_open_tool_tag(ctx_tail):
                combined = ctx_tail + text
                if not self._has_open_tool_tag(combined):
                    text = combined
                    self.context_text = self.context_text[:-len(ctx_tail)]
                    print(f"\033[33m  Merged seed tail tool_call\033[0m")
                else:
                    extra, etok = self._generate(self.context_text + text, max_tokens=256, temperature=0.85)
                    if extra:
                        text += extra
                        tokens += etok
                        print(f"\033[33m  tool_call completion (+{etok}tok)\033[0m")
            elif self._has_open_tool_tag(text):
                extra, etok = self._generate(self.context_text + text, max_tokens=256, temperature=0.85)
                if extra:
                    text += extra
                    tokens += etok
                    print(f"\033[33m  tool_call completion (+{etok}tok)\033[0m")

            self.thought_count += 1
            self.total_tokens_generated += tokens
            dt = time.time() - t0
            self._thought_durations.append(dt)
            tps = tokens / dt if dt > 0 else 0

            sanitized, tool_calls = self._process_tools(text)

            results = "".join(f"\n{tc['result']}\n" for tc in tool_calls if tc["result"])
            if sanitized:
                self.context_text += sanitized + results + "\n"
            elif results:
                self.context_text += results + "\n"
            elif not sanitized and not tool_calls:
                fallback = re.sub(r'<[^>]+>', '', text).strip()
                if fallback:
                    self.context_text += fallback[:200] + "\n"

            display = sanitized or "(tool call only)"
            print(f"\n\033[2m━━━ #{self.thought_count} [{dt:.1f}s {tps:.0f}tok/s ctx:{len(self.context_text)}] ━━━\033[0m")
            print(f"\033[36m{display[:300]}\033[0m")
            for tc in tool_calls:
                print(f"  Tool: {tc['name']} → {str(tc['result'])[:80]}")

            self.thought_log.append({"n": self.thought_count, "content": sanitized or text[:200]})
            if len(self.thought_log) > 100:
                self.thought_log = self.thought_log[-100:]
            self._log("thought", text, {
                "dt": round(dt, 2), "tok": tokens, "tps": round(tps, 1),
                "tools": [tc["name"] for tc in tool_calls],
                "sanitized_len": len(sanitized),
            })

            if len(self.context_text) > self.compress_at_chars:
                self._compress()

        except Exception as e:
            print(f"\033[31m[Error] {e}\033[0m")
            import traceback; traceback.print_exc()
            time.sleep(2)
        finally:
            self.thinking = False

    # ─── Compression ───

    def _compress(self):
        self.compression_count += 1
        before = len(self.context_text)
        print(f"\n\033[33m[Compress #{self.compression_count} {before}→]\033[0m", end="", flush=True)
        prompt = (
            "以下の思考の流れから、最も重要な洞察と未解決の問いだけを抽出してください。"
            "結論やまとめは不要。核心と次の問いだけ。\n\n"
            f"思考:\n{self.context_text[-2000:]}\n\n核心:"
        )
        try:
            summary, _ = self._generate(prompt, max_tokens=300, temperature=0.5)
        except Exception:
            self.context_text = self.context_text[-self.compress_at_chars:]
            return
        self.context_text = f"{summary}\n\n{TOOL_DEFINITION}\n"
        after = len(self.context_text)
        print(f"\033[33m{after} | {after/before:.1%}\033[0m")
        self._log("compress", summary, {"before": before, "after": after})

    # ─── Human interaction ───

    def _respond_to_human(self, message):
        self._log("human_input", message)
        self.thinking = True
        try:
            injection = f"\n\n[User]: {message}\n\n[応答]:\n"
            ctx = self.context_text + injection
            response, tokens = self._generate(ctx, max_tokens=512, temperature=0.7)
            self.total_tokens_generated += tokens
            self.context_text = ctx + response + "\n"
            self._log("dialog", response, {"human": message})
            self._log_dialog(message, response)
            if len(self.context_text) > self.compress_at_chars:
                self._compress()
            return response
        finally:
            self.thinking = False

    # ─── Main loop ───

    # ─── Experiment mode ───

    def set_experiment(self, protocol_name):
        """Activate an experiment protocol. None to disable."""
        if protocol_name is None:
            self.experiment_protocol = None
            self._probe_schedule = {}
            self._probes_fired = set()
            print(f"[{self._ts()}] Experiment mode: OFF")
            return
        proto = EXPERIMENT_PROTOCOLS.get(protocol_name)
        if not proto:
            print(f"[{self._ts()}] Unknown protocol: {protocol_name}")
            return
        self.experiment_protocol = protocol_name
        self._probe_schedule = copy.deepcopy(proto["probes"])
        self._probes_fired = set()
        print(f"[{self._ts()}] Experiment mode: {protocol_name} — {proto['description']}")
        print(f"  Probes at turns: {sorted(self._probe_schedule.keys()) or '(none)'}")

    def _check_auto_probe(self):
        """Check if an auto-probe should fire at the current turn."""
        if not self.experiment_protocol:
            return
        n = self.thought_count
        if n in self._probe_schedule and n not in self._probes_fired:
            probe = self._probe_schedule[n]
            self._probes_fired.add(n)
            print(f"\033[34m  [Auto-probe n={n}]: {probe}\033[0m")
            self._log("auto_probe", probe, {"protocol": self.experiment_protocol, "n": n})
            response = self._respond_to_human(probe)
            self._pending_messages.append({
                "content": f"[Probe n={n}] {probe}\n[AI] {response}",
                "time": datetime.now().isoformat()
            })

    def _loop(self):
        print(f"\n[{self._ts()}] Thinking started.")
        print(f"{'='*60}\n\033[35m{self.seed_text.strip()[:200]}\033[0m\n{'='*60}")
        meta = {"api": self.api_url}
        if self.experiment_protocol:
            meta["experiment"] = self.experiment_protocol
            meta["probes"] = self._probe_schedule
        self._log("start", self.seed_text, meta)
        while self.alive:
            if self._human_event.is_set():
                msg = self._human_input
                self._human_event.clear()
                self._response_text = self._respond_to_human(msg)
                self._response_event.set()
                continue
            self._think_once()
            self._check_auto_probe()
            self._human_event.wait(timeout=0.01)

    def speak(self, message):
        self._human_input = message
        self._response_event.clear()
        self._human_event.set()
        self._response_event.wait(timeout=180)
        return self._response_text or "(no response)"

    # ─── Lifecycle ───

    def _safe_model_tag(self):
        if not self.model_name:
            return "unknown"
        tag = self.model_name.replace("/", "_").replace("\\", "_").replace(" ", "_")
        if len(tag) > 50:
            tag = tag[-50:]
        return tag

    def _rename_logs_with_model(self):
        tag = self._safe_model_tag()
        new_log = self.log_dir / f"full_{self._log_ts}_{tag}.jsonl"
        new_dialog = self.log_dir / f"dialog_{self._log_ts}_{tag}.jsonl"
        try:
            if self.log_file.exists():
                self.log_file.rename(new_log)
            self.log_file = new_log
            if self.dialog_log_file.exists():
                self.dialog_log_file.rename(new_dialog)
            self.dialog_log_file = new_dialog
            print(f"[{self._ts()}] Log: {new_log.name}")
        except Exception as e:
            print(f"[{self._ts()}] Log rename failed: {e}")

    def start(self):
        if self.alive:
            return True
        if not self.check_connection():
            return False
        self._rename_logs_with_model()
        self.alive = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return True

    def stop(self):
        self.alive = False
        self._human_event.set()
        u = datetime.now() - self.birth
        print(f"\n[{self._ts()}] Stopped. Uptime:{str(u).split('.')[0]} Thoughts:{self.thought_count}")
        if self.thought_count > 0:
            self._save_session()

    def _save_session(self):
        """Auto-save context as revival seed on stop."""
        sessions_dir = Path("./sessions"); sessions_dir.mkdir(exist_ok=True)
        model_tag = self._safe_model_tag()
        filename = f"{self._log_ts}_{model_tag}_n{self.thought_count}.txt"
        revival_text = self.context_text.rstrip() + "\n\n" + TOOL_DEFINITION
        p = sessions_dir / filename
        with open(p, "w", encoding="utf-8") as f:
            f.write(revival_text)
        print(f"[{self._ts()}] Session saved: {p} ({len(revival_text):,} chars)")

    def status(self):
        u = datetime.now() - self.birth
        a = sum(self._thought_durations) / len(self._thought_durations) if self._thought_durations else 0
        return {
            "uptime": str(u).split('.')[0], "thoughts": self.thought_count,
            "ctx": len(self.context_text), "tokens": self.total_tokens_generated,
            "avg_sec": round(a, 1), "model": self.model_name or "unknown"
        }

    # ─── Utilities ───

    def _ts(self):
        return datetime.now().strftime("%H:%M:%S")

    def _log(self, kind, content, meta=None):
        e = {"n": self.thought_count, "k": kind, "c": content}
        if meta:
            e.update(meta)
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

    def _log_dialog(self, human_msg, ai_response):
        e = {"n": self.thought_count, "h": human_msg, "a": ai_response}
        with open(self.dialog_log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")


# ═══════════════════════════════════════════════════════════════════
# Gradio UI
# ═══════════════════════════════════════════════════════════════════

def create_ui(mind, lang="en"):
    import gradio as gr
    t = LANG.get(lang, LANG["en"])

    def get_status():
        return f"#{mind.thought_count}" if mind.alive else t["stopped"]

    def get_messages():
        if not mind._pending_messages:
            return "..."
        return "\n\n".join(f"{m['content']}" for m in mind._pending_messages)

    def get_thoughts():
        if not mind.thought_log:
            return "..."
        return "\n".join(f"#{e['n']} {e['content'][:100]}" for e in reversed(mind.thought_log))

    def start():
        if not mind.alive: mind.start()
        return get_status(), get_messages(), get_thoughts()

    def stop():
        mind.stop()
        return get_status(), get_messages(), get_thoughts()

    def shutdown():
        mind.stop()
        import os; os._exit(0)

    def refresh():
        return get_status(), get_messages(), get_thoughts()

    def reply(text):
        if text.strip():
            mind._pending_messages.append({"content": f"{t['you']} {text}", "time": datetime.now().isoformat()})
            resp = mind.speak(text)
            mind._pending_messages.append({"content": f"{t['ai']} {resp}", "time": datetime.now().isoformat()})
        return "", get_messages(), get_thoughts()

    with gr.Blocks(title="Epos") as app:
        gr.Markdown(t["title"])

        with gr.Row():
            start_btn = gr.Button(t["start"], variant="primary")
            stop_btn = gr.Button(t["stop"], variant="stop")
            shutdown_btn = gr.Button(t["shutdown"], variant="stop")
            refresh_btn = gr.Button(t["refresh"])
            status = gr.Textbox(value=t["stopped"], show_label=False, interactive=False)

        with gr.Row():
            with gr.Column():
                gr.Markdown(t["dialogue"])
                messages = gr.Textbox(lines=14, show_label=False, interactive=False)
                with gr.Row():
                    user_input = gr.Textbox(placeholder=t["placeholder"], show_label=False, scale=4)
                    send_btn = gr.Button(t["send"], scale=1)
            with gr.Column():
                gr.Markdown(t["thoughts"])
                thoughts = gr.Textbox(lines=17, show_label=False, interactive=False)

        # ─── Session Revival ───
        sessions_dir = Path("./sessions"); sessions_dir.mkdir(exist_ok=True)

        def list_sessions():
            return sorted([f.stem for f in sessions_dir.glob("*.txt")], reverse=True)

        def preview_session(name):
            if not name: return ""
            p = sessions_dir / f"{name}.txt"
            if not p.exists(): return ""
            text = p.read_text(encoding="utf-8")
            return f"[{len(text):,} {t['chars']}]\n\n{text[:300]}..."

        def revive_session(name):
            if mind.alive: return t["stop_first"], gr.update()
            if not name: return t["no_session"], gr.update()
            p = sessions_dir / f"{name}.txt"
            if not p.exists(): return t["file_not_found"], gr.update()
            text = p.read_text(encoding="utf-8")
            mind.seed_text = text
            mind.context_text = text
            mind.thought_count = 0
            mind.compression_count = 0
            mind.total_tokens_generated = 0
            mind._thought_durations = []
            mind._pending_messages.clear()
            mind.thought_log = []
            mind._last_search_thought = -10
            mind._last_message_thought = -10
            mind._empty_retries = 0
            mind._log_ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            mind.log_file = mind.log_dir / f"full_{mind._log_ts}.jsonl"
            mind.dialog_log_file = mind.log_dir / f"dialog_{mind._log_ts}.jsonl"
            return t["revived"].format(name=name, chars=len(text)), gr.update()

        def delete_session(name):
            if not name: return "", gr.update(choices=list_sessions())
            p = sessions_dir / f"{name}.txt"
            if p.exists(): p.unlink()
            return t["deleted"].format(name=name), gr.update(choices=list_sessions())

        with gr.Accordion(t["session_revival"], open=False):
            with gr.Row():
                session_dropdown = gr.Dropdown(choices=list_sessions(), label=t["saved_sessions"], interactive=True, scale=3)
                session_refresh_btn = gr.Button(t["refresh"], scale=0)
            session_preview = gr.Textbox(lines=6, show_label=False, interactive=False)
            with gr.Row():
                revive_btn = gr.Button(t["revive"], variant="primary")
                session_delete_btn = gr.Button(t["delete"], variant="stop")
                session_status = gr.Textbox(show_label=False, interactive=False, max_lines=1)

            session_dropdown.change(preview_session, [session_dropdown], [session_preview])
            session_refresh_btn.click(lambda: gr.update(choices=list_sessions()), outputs=[session_dropdown])
            revive_btn.click(revive_session, [session_dropdown], [session_status, session_preview])
            session_delete_btn.click(delete_session, [session_dropdown], [session_status, session_dropdown])

        # ─── Experiment Mode ───
        def get_protocol_choices():
            return [(f"{k} — {v['description']}", k) for k, v in EXPERIMENT_PROTOCOLS.items()]

        def activate_experiment(protocol_name):
            if mind.alive:
                return t["exp_stop_first"]
            if not protocol_name:
                return t["exp_off"]
            mind.set_experiment(protocol_name)
            probes = EXPERIMENT_PROTOCOLS[protocol_name]["probes"]
            desc = EXPERIMENT_PROTOCOLS[protocol_name]["description"]
            detail = ", ".join(f"n={k}" for k in sorted(probes.keys())) if probes else "(none)"
            return f"{desc}\nProbes: {detail}"

        def deactivate_experiment():
            mind.set_experiment(None)
            return t["exp_deactivated"]

        with gr.Accordion(t["experiment"], open=False):
            gr.Markdown("Scripted auto-probes at fixed turn intervals. No human bias.")
            with gr.Row():
                exp_dropdown = gr.Dropdown(
                    choices=get_protocol_choices(),
                    label=t["protocol"], interactive=True, scale=3
                )
                exp_activate_btn = gr.Button(t["activate"], variant="primary", scale=1)
                exp_deactivate_btn = gr.Button(t["deactivate"], variant="stop", scale=1)
            exp_status = gr.Textbox(
                value=t["exp_off"], show_label=False, interactive=False, lines=2
            )
            exp_activate_btn.click(activate_experiment, [exp_dropdown], [exp_status])
            exp_deactivate_btn.click(deactivate_experiment, outputs=[exp_status])

        # ─── Settings ───
        seeds_dir = Path("./seeds"); seeds_dir.mkdir(exist_ok=True)

        def list_seeds():
            return [f.stem for f in sorted(seeds_dir.glob("*.json"))]

        def save_seed(name, text):
            if not name.strip():
                return t["name_required"], gr.update(choices=list_seeds())
            p = seeds_dir / f"{name.strip()}.json"
            with open(p, "w", encoding="utf-8") as f:
                json.dump({"name": name.strip(), "seed": text}, f, ensure_ascii=False, indent=2)
            return t["saved"].format(name=name.strip()), gr.update(choices=list_seeds())

        def load_seed(name):
            if not name: return mind.seed_text
            p = seeds_dir / f"{name}.json"
            return json.load(open(p, encoding="utf-8")).get("seed", "") if p.exists() else mind.seed_text

        def delete_seed(name):
            if not name: return "", gr.update(choices=list_seeds())
            p = seeds_dir / f"{name}.json"
            if p.exists(): p.unlink(); return t["deleted"].format(name=name), gr.update(choices=list_seeds())
            return "", gr.update(choices=list_seeds())

        def apply_seed(text):
            if mind.alive: return t["stop_first"]
            mind.seed_text = text
            mind.context_text = text
            mind.thought_count = 0
            mind.compression_count = 0
            mind.total_tokens_generated = 0
            mind._thought_durations = []
            mind._pending_messages.clear()
            mind.thought_log = []
            mind._last_search_thought = -10
            mind._last_message_thought = -10
            mind._empty_retries = 0
            mind._log_ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            mind.log_file = mind.log_dir / f"full_{mind._log_ts}.jsonl"
            mind.dialog_log_file = mind.log_dir / f"dialog_{mind._log_ts}.jsonl"
            return t["applied"]

        with gr.Accordion(t["settings"], open=False):
            with gr.Row():
                seed_box = gr.Textbox(value=mind.seed_text, lines=12, label=t["seed"], scale=3)
                with gr.Column(scale=1):
                    seed_dropdown = gr.Dropdown(choices=list_seeds(), label=t["saved_seeds"], interactive=True)
                    load_btn = gr.Button(t["load"])
                    seed_name = gr.Textbox(placeholder=t["name_placeholder"], show_label=False)
                    save_btn = gr.Button(t["save"])
                    delete_btn = gr.Button(t["delete"], variant="stop")
                    seed_status = gr.Textbox(show_label=False, interactive=False, max_lines=1)
            with gr.Row():
                apply_btn = gr.Button(t["apply_seed"], variant="primary")
                apply_status = gr.Textbox(show_label=False, interactive=False, max_lines=1)
            url_box = gr.Textbox(value=mind.api_url, label="API URL")
            gr.Markdown(t["context_limits"])
            with gr.Row():
                compress_slider = gr.Slider(10000, 150000, step=1000, value=mind.compress_at_chars, label=t["compress_at"])
                max_ctx_slider = gr.Slider(20000, 200000, step=1000, value=mind.max_context_chars, label=t["max_context"])
            with gr.Row():
                ctx_apply_btn = gr.Button(t["apply"])
                ctx_status = gr.Textbox(show_label=False, interactive=False, max_lines=1,
                                       value=f"{mind.compress_at_chars:,} / {mind.max_context_chars:,}")

        def apply_ctx(c, m):
            c, m = int(c), int(m)
            if c >= m: return t["compress_lt_max"]
            mind.compress_at_chars = c; mind.max_context_chars = m
            mind.save_config()
            return f"{c:,} / {m:,}"

        start_btn.click(start, outputs=[status, messages, thoughts])
        stop_btn.click(stop, outputs=[status, messages, thoughts])
        shutdown_btn.click(shutdown)
        refresh_btn.click(refresh, outputs=[status, messages, thoughts])
        send_btn.click(reply, [user_input], [user_input, messages, thoughts])
        user_input.submit(reply, [user_input], [user_input, messages, thoughts])
        save_btn.click(save_seed, [seed_name, seed_box], [seed_status, seed_dropdown])
        load_btn.click(load_seed, [seed_dropdown], [seed_box])
        delete_btn.click(delete_seed, [seed_dropdown], [seed_status, seed_dropdown])
        apply_btn.click(apply_seed, [seed_box], [apply_status])
        ctx_apply_btn.click(apply_ctx, [compress_slider, max_ctx_slider], [ctx_status])
        gr.Timer(2).tick(refresh, outputs=[status, messages, thoughts])

    return app


# ═══════════════════════════════════════════════════════════════════
# Entry Point
# ═══════════════════════════════════════════════════════════════════

def main():
    import argparse, webbrowser
    parser = argparse.ArgumentParser(description="Epos — Autonomous Narrative Engine")
    parser.add_argument("--url", default="http://localhost:1234")
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument("--browser", action="store_true")
    parser.add_argument("--lang", default="en", choices=["en", "ja"], help="UI language (default: en)")
    parser.add_argument("--experiment", default=None, choices=list(EXPERIMENT_PROTOCOLS.keys()),
                        help="Activate experiment protocol (default: none)")
    args = parser.parse_args()

    mind = Epos(api_url=args.url)
    if args.experiment:
        mind.set_experiment(args.experiment)
    app = create_ui(mind, lang=args.lang)

    if args.browser:
        threading.Thread(target=lambda: (time.sleep(1), webbrowser.open(f"http://localhost:{args.port}")), daemon=True).start()

    app.launch(server_port=args.port)

if __name__ == "__main__":
    main()
