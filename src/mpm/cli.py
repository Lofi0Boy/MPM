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


@click.group()
def main():
    """MPM — Multi Project Manager for AI coding agents."""
    pass


@main.command()
def onboard():
    """Initial setup — configure timezone, port, and preferences."""
    config = _load_config()

    click.echo("Welcome to MPM! Let's set up your configuration.\n")

    # Timezone
    import time
    local_tz = time.tzname[0]
    try:
        # Try to get IANA timezone
        tz_path = os.readlink("/etc/localtime")
        local_tz = tz_path.split("zoneinfo/")[-1]
    except Exception:
        pass

    tz = click.prompt("Timezone", default=config.get("timezone", local_tz))

    # Port
    port = click.prompt("Dashboard port", default=config.get("port", 5100), type=int)

    config.update({
        "timezone": tz,
        "port": port,
        "tmux_prefix": config.get("tmux_prefix", "mpm"),
        "patterns": config.get("patterns", ["claude"]),
        "projects": config.get("projects", []),
        "saved_commands": config.get("saved_commands", ["claude"]),
    })
    _save_config(config)

    click.echo(f"\nConfig saved to {CONFIG_PATH}")
    click.echo("Run 'mpm dashboard' to start the dashboard.")


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
@click.option("--path", "-p", default=".", help="Project directory (default: current)")
def init(path):
    """Initialize MPM in a project directory."""
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

    # Copy template files
    for src_file in templates.rglob("*"):
        if src_file.is_dir():
            continue
        rel = src_file.relative_to(templates)
        dest = project_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)

        # Don't overwrite data files
        if "data/" in str(rel) and dest.exists():
            continue
        # Don't overwrite PROJECT.md
        if rel.name == "PROJECT.md" and dest.exists():
            continue

        shutil.copy2(src_file, dest)

    # Create required empty directories
    for d in [".mpm/data/current", ".mpm/data/past", ".mpm/docs"]:
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
        project_dir / ".claude" / "skills" / "mpm-next",
        project_dir / ".claude" / "skills" / "mpm-autonext",
        project_dir / ".claude" / "skills" / "mpm-init-project",
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


if __name__ == "__main__":
    main()
