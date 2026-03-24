"""
MPM CLI — Multi Project Manager for AI coding agents.
"""

import json
import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path

import click
import questionary
from questionary import Style

MPM_STYLE = Style([
    ("highlighted", "fg:orange bold"),
    ("pointer", "fg:orange bold"),
    ("selected", "fg:orange"),
    ("instruction", "fg:#888888 italic"),
])

# Config lives in ~/.mpm/
MPM_HOME = Path.home() / ".mpm"
CONFIG_PATH = MPM_HOME / "config.json"


def _load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def _save_config(config: dict) -> None:
    MPM_HOME.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _templates_dir() -> Path:
    """Find the templates directory (installed via shared-data or dev)."""
    # Development: templates/ next to pyproject.toml
    dev_path = Path(__file__).parent.parent.parent / "templates"
    if dev_path.exists():
        return dev_path
    # Installed via pip/uv: look relative to the venv or tool directory
    # hatch shared-data puts files in {prefix}/share/mpm/templates
    for base in [Path(sys.prefix), Path(sys.exec_prefix)]:
        installed_path = base / "share" / "mpm" / "templates"
        if installed_path.exists():
            return installed_path
    # uv tool install: {tool_dir}/share/mpm/templates
    cli_path = Path(__file__).resolve()
    # Walk up from site-packages to find share/
    for parent in cli_path.parents:
        candidate = parent / "share" / "mpm" / "templates"
        if candidate.exists():
            return candidate
    raise FileNotFoundError("MPM templates not found. Try reinstalling: uv tool install --force ...")


def _is_mpm_hook_entry(entry: dict) -> bool:
    """Check if a hook entry contains MPM hooks (references .mpm/)."""
    return any(".mpm/" in h.get("command", "") for h in entry.get("hooks", []))


def _merge_settings(dest_path: Path, template_path: Path) -> None:
    """Merge MPM hooks from template into existing settings.json, preserving user hooks."""
    template = json.loads(template_path.read_text(encoding="utf-8"))
    template_hooks = template.get("hooks", {})

    if dest_path.exists():
        existing = json.loads(dest_path.read_text(encoding="utf-8"))
    else:
        existing = {}

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    existing_hooks = existing.get("hooks", {})

    # For each event: remove old MPM entries, then add new ones from template
    for event, mpm_entries in template_hooks.items():
        current = existing_hooks.get(event, [])
        # Remove existing MPM hook entries
        current = [e for e in current if not _is_mpm_hook_entry(e)]
        # Add MPM entries from template
        current.extend(mpm_entries)
        existing_hooks[event] = current

    existing["hooks"] = existing_hooks
    dest_path.write_text(
        json.dumps(existing, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


@click.group()
@click.pass_context
def main(ctx):
    """MPM — Multi Project Manager for AI coding agents."""
    if not CONFIG_PATH.exists() and ctx.invoked_subcommand not in ("onboard",):
        click.echo("MPM has not been initialized yet.")
        if click.confirm("Run initial setup now?"):
            ctx.invoke(onboard)
        else:
            click.echo("Run 'mpm onboard' when ready.")
            raise SystemExit(0)


def _check_deps() -> list[tuple[str, bool, str]]:
    """Check system dependencies. Returns [(name, found, install_hint)]."""
    from shutil import which
    is_mac = sys.platform == "darwin"
    deps = [
        ("tmux", "brew install tmux" if is_mac else "sudo apt install tmux"),
        ("ttyd", "brew install ttyd" if is_mac else "sudo snap install ttyd --classic"),
        ("jq", "brew install jq" if is_mac else "sudo apt install jq"),
        ("claude", "npm install -g @anthropic-ai/claude-code"),
    ]
    return [(name, which(name) is not None, hint) for name, hint in deps]


def _get_timezones() -> list[str]:
    """Get sorted list of all IANA timezones."""
    from zoneinfo import available_timezones
    return sorted(available_timezones())


def _detect_timezone() -> str:
    """Auto-detect local timezone."""
    try:
        tz_path = os.readlink("/etc/localtime")
        return tz_path.split("zoneinfo/")[-1]
    except Exception:
        import time
        return time.tzname[0]


@main.command()
@click.pass_context
def onboard(ctx):
    """Initial setup — configure timezone, port, and preferences."""
    config = _load_config()

    click.echo("Welcome to MPM! Let's set up your configuration.\n")

    # 1. Dependency check
    click.echo("Checking dependencies...")
    deps = _check_deps()
    missing = []
    for name, found, hint in deps:
        mark = click.style("✓", fg="green") if found else click.style("✗", fg="red")
        click.echo(f"  {mark} {name}")
        if not found:
            missing.append((name, hint))
    click.echo()

    # 2. Timezone (autocomplete with arrow keys)
    local_tz = config.get("timezone", _detect_timezone())
    all_tzs = _get_timezones()
    tz = questionary.autocomplete(
        "Timezone:",
        choices=all_tzs,
        default=local_tz,
        style=MPM_STYLE,
    ).ask()
    if tz is None:
        raise SystemExit(0)

    # 3. Port
    port = click.prompt("Dashboard port", default=config.get("port", 5100), type=int)

    # 4. Save config
    workspace = str(Path.home() / "MpmWorkspace")
    config.update({
        "timezone": tz,
        "port": port,
        "workspace": config.get("workspace", workspace),
        "tmux_prefix": config.get("tmux_prefix", "mpm"),
        "patterns": config.get("patterns", ["claude"]),
        "projects": config.get("projects", []),
        "saved_commands": config.get("saved_commands", ["claude"]),
    })
    _save_config(config)
    click.echo(f"\nConfig saved to {CONFIG_PATH}")

    # 5. First project registration
    if not config.get("projects"):
        click.echo()
        choice = questionary.select(
            "Register your first project:",
            choices=[
                "Create new project",
                "Register existing project",
                "Skip for now",
            ],
            instruction="",
            style=MPM_STYLE,
        ).ask()
        if choice is None:
            raise SystemExit(0)

        ws_path = Path(config["workspace"])

        if choice == "Create new project":
            ws_path.mkdir(parents=True, exist_ok=True)
            project_name = questionary.text("Project name:").ask()
            if not project_name:
                raise SystemExit(0)
            project_dir = ws_path / project_name
            project_dir.mkdir(parents=True, exist_ok=True)
            click.echo(f"Created {project_dir}")
            ctx.invoke(init, path=str(project_dir))

        elif choice == "Register existing project":
            project_path = questionary.path(
                "Project path:",
                only_directories=True,
            ).ask()
            if not project_path:
                raise SystemExit(0)
            project_dir = Path(project_path).resolve()
            if project_dir.is_dir():
                ctx.invoke(init, path=str(project_dir))
            else:
                click.echo(f"Error: {project_dir} is not a directory")

    # 6. Missing dependency reminder
    if missing:
        click.echo()
        click.echo(click.style("⚠ Missing dependencies:", fg="yellow", bold=True))
        for name, hint in missing:
            click.echo(click.style(f"  {name}: {hint}", fg="yellow"))
        click.echo()
    else:
        click.echo("\nRun 'mpm dashboard' to start.")


@main.command()
@click.option("--foreground", "-f", is_flag=True, help="Run in foreground (default is background)")
@click.option("--no-open", is_flag=True, help="Don't open browser")
def dashboard(foreground, no_open):
    """Start the MPM dashboard server."""
    config = _load_config()
    if not config:
        click.echo("Run 'mpm onboard' first to set up configuration.")
        return

    port = config.get("port", 5100)
    url = f"http://localhost:{port}"

    if foreground:
        click.echo(f"MPM Dashboard → {url}")
        click.echo("Press Ctrl+C to stop.\n")
        if not no_open:
            _open_browser(url)
        try:
            subprocess.run([sys.executable, "-m", "mpm.dashboard.server"], check=True)
        except KeyboardInterrupt:
            click.echo("\nDashboard stopped.")
        return

    # Background (default)
    pid_file = MPM_HOME / "dashboard.pid"
    if pid_file.exists():
        pid = int(pid_file.read_text().strip())
        try:
            os.kill(pid, 0)
            click.echo(f"Dashboard already running (PID {pid}) → {url}")
            if not no_open:
                _open_browser(url)
            return
        except OSError:
            pid_file.unlink()

    log_file = MPM_HOME / "dashboard.log"
    proc = subprocess.Popen(
        [sys.executable, "-m", "mpm.dashboard.server"],
        start_new_session=True,
        stdout=open(log_file, "a"),
        stderr=subprocess.STDOUT,
    )
    pid_file.write_text(str(proc.pid))
    click.echo(f"MPM Dashboard → {url} (PID {proc.pid})")
    click.echo(f"Logs: {log_file}")

    if not no_open:
        import time
        time.sleep(2)  # Wait for server to start
        _open_browser(url)


def _open_browser(url):
    import webbrowser
    try:
        webbrowser.open(url)
    except Exception:
        pass


@main.command()
@click.option("--path", "-p", default=None, help="Project directory (skip interactive prompt)")
def init(path):
    """Initialize MPM in a project directory."""
    if path is None:
        # Interactive mode: ask where to init
        cwd = Path.cwd().resolve()
        config = _load_config()
        workspace = config.get("workspace", str(Path.home() / "MpmWorkspace"))
        choice = questionary.select(
            "Initialize project in:",
            choices=[
                f"Current directory ({cwd})",
                f"New project ({workspace}/)",
                "Other directory",
            ],
            instruction="",
            style=MPM_STYLE,
        ).ask()
        if choice is None:
            return
        if choice.startswith("New project"):
            name = questionary.text("Project directory name:").ask()
            if not name:
                return
            new_dir = Path(workspace) / name
            new_dir.mkdir(parents=True, exist_ok=True)
            path = str(new_dir)
            click.echo(f"Created {new_dir}")
        elif choice.startswith("Other"):
            path = questionary.path(
                "Project path:",
                only_directories=True,
            ).ask()
            if not path:
                return
        else:
            path = str(cwd)

    project_dir = Path(path).resolve()
    if not project_dir.is_dir():
        click.echo(f"Error: {project_dir} is not a directory")
        return

    templates = _templates_dir()

    # Copy .mpm/ structure
    mpm_dir = project_dir / ".mpm"
    if mpm_dir.exists():
        click.echo(f"MPM already initialized in {project_dir}")
        click.echo("Re-syncing scripts and rules...")
    else:
        click.echo(f"Initializing MPM in {project_dir}")

    # Copy template files (except settings.json — merged separately)
    for src_file in templates.rglob("*"):
        if src_file.is_dir():
            continue
        rel = src_file.relative_to(templates)
        dest = project_dir / rel

        # Don't overwrite data files
        if "data/" in str(rel) and dest.exists():
            continue
        # Don't overwrite PROJECT.md
        if rel.name == "PROJECT.md" and dest.exists():
            continue
        # settings.json is merged, not copied
        if rel == Path(".claude") / "settings.json":
            continue

        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, dest)

    # Merge MPM hooks into settings.json (preserve user hooks)
    _merge_settings(
        project_dir / ".claude" / "settings.json",
        templates / ".claude" / "settings.json",
    )

    # Create required empty directories
    for d in [".mpm/data/current", ".mpm/data/past", ".mpm/data/review", ".mpm/docs"]:
        (project_dir / d).mkdir(parents=True, exist_ok=True)

    # Make scripts executable
    scripts_dir = project_dir / ".mpm" / "scripts"
    if scripts_dir.exists():
        for sh in scripts_dir.glob("*.sh"):
            sh.chmod(0o755)

    # Register in config
    config = _load_config()
    projects = config.get("projects", [])
    project_str = str(project_dir)
    if project_str not in projects:
        projects.append(project_str)
        config["projects"] = projects
        _save_config(config)

    click.echo(f"✓ MPM initialized in {project_dir}")
    click.echo(f"✓ Registered in {CONFIG_PATH}")
    click.echo("\nStart a Claude Code session to begin. The agent will guide you through PROJECT.md setup.")

    # Notify dashboard to close init terminal and refresh
    try:
        import requests as _req
        port = config.get("port")
        if not port:
            raise KeyError
        _req.delete(f"http://localhost:{port}/api/sessions/_mpm-init", timeout=2)
        _req.post(f"http://localhost:{port}/api/refresh", timeout=2)
    except Exception:
        pass


@main.command()
@click.option("--path", "-p", default=".", help="Project directory (default: current)")
def disable(path):
    """Remove MPM from a project (preserves task data)."""
    project_dir = Path(path).resolve()

    removed = []

    # Remove scripts (but keep data and docs)
    scripts_dir = project_dir / ".mpm" / "scripts"
    if scripts_dir.exists():
        shutil.rmtree(scripts_dir)
        removed.append(".mpm/scripts/")

    # Remove Claude Code integration
    for p in [
        project_dir / ".claude" / "rules" / "mpm-workflow.md",
    ]:
        if p.exists():
            p.unlink()
            removed.append(str(p.relative_to(project_dir)))

    for d in [
        # Current skills
        project_dir / ".claude" / "skills" / "mpm-next",
        project_dir / ".claude" / "skills" / "mpm-autonext",
        project_dir / ".claude" / "skills" / "mpm-init",
        project_dir / ".claude" / "skills" / "mpm-init-uiux",
        project_dir / ".claude" / "skills" / "mpm-task-write",
        project_dir / ".claude" / "skills" / "mpm-office-hour",
        project_dir / ".claude" / "skills" / "mpm-plan-ceo-review",
        project_dir / ".claude" / "skills" / "mpm-plan-eng-review",
        project_dir / ".claude" / "skills" / "mpm-plan-design-review",
        project_dir / ".claude" / "skills" / "mpm-review-functional",
        project_dir / ".claude" / "skills" / "mpm-review-code",
        project_dir / ".claude" / "skills" / "mpm-review-uiux",
        project_dir / ".claude" / "skills" / "mpm-recycle",
        project_dir / ".claude" / "skills" / "mpm-ui-ux-pro-max",
        project_dir / ".claude" / "agents",
    ]:
        if d.exists():
            shutil.rmtree(d)
            removed.append(str(d.relative_to(project_dir)))

    # Remove MPM hooks from settings.json (keep user hooks)
    settings_path = project_dir / ".claude" / "settings.json"
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
            hooks = settings.get("hooks", {})
            for event in list(hooks.keys()):
                hooks[event] = [
                    entry for entry in hooks[event]
                    if not any(".mpm/" in h.get("command", "") for h in entry.get("hooks", []))
                ]
                if not hooks[event]:
                    del hooks[event]
            if hooks:
                settings["hooks"] = hooks
            else:
                settings.pop("hooks", None)
            if settings:
                settings_path.write_text(
                    json.dumps(settings, indent=2) + "\n", encoding="utf-8"
                )
            else:
                settings_path.unlink()
            removed.append(".claude/settings.json (MPM hooks removed)")
        except Exception:
            pass

    # Unregister from config
    config = _load_config()
    projects = config.get("projects", [])
    project_str = str(project_dir)
    if project_str in projects:
        projects.remove(project_str)
        config["projects"] = projects
        _save_config(config)

    if removed:
        click.echo("Removed:")
        for r in removed:
            click.echo(f"  - {r}")
    click.echo(f"\nMPM disabled in {project_dir}")
    click.echo("Task data preserved in .mpm/data/ and .mpm/docs/")


@main.command()
def status():
    """Show registered projects and dashboard status."""
    config = _load_config()

    if not config:
        click.echo("MPM not configured. Run 'mpm onboard' first.")
        return

    click.echo(f"Config: {CONFIG_PATH}")
    click.echo(f"Port: {config.get('port', 5100)}")
    click.echo(f"Timezone: {config.get('timezone', 'UTC')}")
    click.echo()

    # Check dashboard
    pid_file = MPM_HOME / "dashboard.pid"
    if pid_file.exists():
        pid = int(pid_file.read_text().strip())
        try:
            os.kill(pid, 0)
            click.echo(f"Dashboard: running (PID {pid})")
        except OSError:
            click.echo("Dashboard: stopped")
            pid_file.unlink()
    else:
        click.echo("Dashboard: stopped")

    click.echo()
    projects = config.get("projects", [])
    click.echo(f"Projects ({len(projects)}):")
    for p in projects:
        exists = Path(p).exists()
        mark = "✓" if exists else "✗"
        click.echo(f"  {mark} {p}")


@main.command()
@click.argument("port_number", type=int, required=False)
def port(port_number):
    """Get or set the dashboard port."""
    config = _load_config()
    if port_number is None:
        click.echo(f"Current port: {config.get('port', 5100)}")
        return
    if port_number < 1 or port_number > 65535:
        click.echo("Error: port must be between 1 and 65535")
        return
    config["port"] = port_number
    _save_config(config)
    click.echo(f"Port set to {port_number}")
    pid_file = MPM_HOME / "dashboard.pid"
    if pid_file.exists():
        click.echo("Restart dashboard to apply: mpm stop && mpm dashboard")


@main.command()
def stop():
    """Stop the dashboard server."""
    pid_file = MPM_HOME / "dashboard.pid"
    if not pid_file.exists():
        click.echo("Dashboard is not running.")
        return
    pid = int(pid_file.read_text().strip())
    try:
        os.kill(pid, signal.SIGTERM)
        click.echo(f"Dashboard stopped (PID {pid})")
    except OSError:
        click.echo("Dashboard was not running.")
    pid_file.unlink(missing_ok=True)


@main.command()
@click.pass_context
def uninstall(ctx):
    """Remove MPM from all projects and clean up global config."""
    config = _load_config()
    projects = config.get("projects", [])

    if not projects and not MPM_HOME.exists():
        click.echo("Nothing to uninstall.")
        return

    if not click.confirm(f"This will disable MPM in {len(projects)} project(s) and remove {MPM_HOME}. Continue?"):
        return

    # 1. Stop dashboard
    ctx.invoke(stop)

    # 2. Disable all registered projects
    for p in projects:
        if Path(p).is_dir():
            click.echo(f"\nDisabling {p}...")
            ctx.invoke(disable, path=p)

    # 3. Remove global config
    if MPM_HOME.exists():
        shutil.rmtree(MPM_HOME)
        click.echo(f"\nRemoved {MPM_HOME}")

    click.echo("\nMPM uninstalled. Run this to complete:")
    click.echo("  uv tool uninstall mpm")


if __name__ == "__main__":
    main()
