def _install_package(package: str) -> str:
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", package],
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=120,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if result.returncode == 0:
            return f"Installed: {package}"
        return f"Install failed: {result.stderr[:300]}"
    except subprocess.TimeoutExpired:
        return "Install timed out."
    except Exception as e:
        return f"Install error: {e}"


def _add_to_requirements(package: str) -> str:
    req_path = BASE_DIR / "requirements.txt"
    try:
        existing = req_path.read_text(encoding="utf-8") if req_path.exists() else ""
        lines = [l.strip().lower() for l in existing.splitlines()]
        pkg_name = package.split(">=")[0].split("==")[0].strip()
        if pkg_name.lower() in lines or any(l.startswith(pkg_name.lower() + "=") or l.startswith(pkg_name.lower() + ">") for l in lines):
            return f"Already in requirements.txt: {pkg_name}"
        with open(str(req_path), "a", encoding="utf-8") as f:
            f.write(f"\n{package}")
        return f"Added to requirements.txt: {package}"
    except Exception as e:
        return f"Could not update requirements.txt: {e}"


def _review_code(file_path: str) -> str:
    code, err = _read_file(file_path)
    if err:
        return err
    model = _get_gemini()
    prompt = f"""Review this Python code for:
1. Bugs or logical errors
2. Security issues
3. Performance problems
4. Style/convention issues
5. Missing error handling

Be concise and specific. If you see issues, suggest fixes.

```python
{code[:6000]}

Review:"""
    try:
        resp = model.generate_content(prompt)
        return resp.text.strip()
    except Exception as e:
        return f"Review failed: {e}"


def _explain_self() -> str:
    parts = []
    parts.append("VAYU Architecture:\n")
    parts.append("  main.py — Gemini live audio session, tool declarations, tool executor")
    parts.append("  vayu_ui.py — PyQt6 window, HUD, camera overlay, mode/gesture/cursor UI")
    parts.append("  actions/ — Tool implementations (one file per domain)")
    parts.append("  brain/ — AI providers (Gemini, OpenRouter, Groq, Ollama)")
    parts.append("  core/ — Modes, prompts, cache, lazy loader")
    parts.append("  memory/ — TF-IDF vector memory, conversation DB")
    parts.append("  vision/ — MediaPipe hand gesture recognition")
    parts.append("  ui/ — Camera overlay widget")
    parts.append("  plugins/ — Auto-discovered plugin tools")
    parts.append("")
    parts.append("Tool registration pattern:")
    parts.append("  1. Create actions/<name>.py with function <name>(parameters, response, player, session_memory, speak)")
    parts.append("  2. Add import in main.py: from actions.<name> import <name>")
    parts.append("  3. Add declaration dict to TOOL_DECLARATIONS list")
    parts.append("  4. Add handler in _execute_tool: elif name == '<name>': result = await loop.run_in_executor(...)")
    parts.append("  5. Optionally add to mode whitelist in core/modes.py")
    return "\n".join(parts)


def code_agent(
    parameters: dict,
    response=None,
    player=None,
    session_memory=None,
    speak=None,
) -> str:
    p = parameters or {}
    action = p.get("action", "auto").strip().lower()
    name = p.get("name", "").strip()
    description = p.get("description", "").strip()
    file_path = p.get("file_path", "").strip()
    package = p.get("package", "").strip()
    code = p.get("code", "").strip()
    params_raw = p.get("parameters", "[]")
    language = p.get("language", "python").strip()
    output_path = p.get("output_path", "").strip()

    if action == "auto":
        if description and not file_path and not package:
            action = "write_code"
        elif name and description:
            action = "create_action"
        elif file_path:
            action = "read"
        elif package:
            action = "install_dep"
        else:
            action = "explore"

    if action == "explore":
        out = _list_project()
        out += "\n\n" + _list_tools()
        return out

    elif action == "read":
        content, err = _read_file(file_path)
        if err:
            return err
        lines = content.splitlines()
        return f"=== {file_path} ({len(lines)} lines) ===\n" + content[:8000]

    elif action == "create_action":
        if not name:
            return "Provide 'name' for the new action."
        try:
            params_list = json.loads(params_raw) if isinstance(params_raw, str) else params_raw
        except json.JSONDecodeError:
            params_list = []
        desc = description or f"Action: {name}"
        result = _create_action_file(name, desc, params_list)
        if player:
            player.write_log(f"[CodeAgent] {result}")
        return result

    elif action == "register_tool":
        if not name:
            return "Provide 'name' for the tool declaration."
        try:
            params_list = json.loads(params_raw) if isinstance(params_raw, str) else params_raw
        except json.JSONDecodeError:
            params_list = []
        desc = description or f"Tool: {name}"
        results = []
        imp = _add_import(name)
        results.append(imp)
        if "already" not in imp and "error" not in imp.lower():
            decl = _add_tool_declaration(name, desc, params_list)
            results.append(decl)
            handler = _add_tool_handler(name, f"{name}(parameters=args, player=self.ui)")
            results.append(handler)
        return "\n".join(results)

    elif action == "install_dep":
        if not package:
            return "Provide 'package' name to install."
        results = []
        r1 = _install_package(package)
        results.append(r1)
        r2 = _add_to_requirements(package)
        results.append(r2)
        return "\n".join(results)

    elif action == "review":
        if not file_path and not code:
            return "Provide 'file_path' or 'code' to review."
        return _review_code(file_path) if file_path else code[:4000]

    elif action == "explain_self":
        return _explain_self()

    elif action == "backup":
        target = Path(file_path) if file_path else MAIN_PY
        if not target.is_absolute():
            target = BASE_DIR / target
        bak = _backup(target)
        if bak:
            return f"Backup: {bak}"
        return f"File not found: {target}"

    elif action == "write_code":
        if not description:
            return "Provide 'description' of the code to generate."
        return _write_code(name or "generated", description, language, output_path, [])

    elif action == "list_tools":
        return _list_tools()

    else:
        return f"Unknown action: '{action}'. Try: explore, read, create_action, register_tool, install_dep, review, write_code, explain_self, backup, list_tools"
