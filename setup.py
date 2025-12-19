#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Strava Local - Interactive Setup Script

Run this after cloning to set up your local environment.
Usage: python setup.py
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

# Minimum Python version
MIN_PYTHON = (3, 10)

# ANSI color codes for terminals without rich
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    END = '\033[0m'


def print_banner():
    """Print the welcome banner."""
    banner = f"""
{Colors.BOLD}{Colors.GREEN}
   _____ _                        _                    _
  / ____| |                      | |                  | |
 | (___ | |_ _ __ __ ___   ____ _| |     ___   ___ __ _| |
  \\___ \\| __| '__/ _` \\ \\ / / _` | |    / _ \\ / __/ _` | |
  ____) | |_| | | (_| |\\ V / (_| | |___| (_) | (_| (_| | |
 |_____/ \\__|_|  \\__,_| \\_/ \\__,_|______\\___/ \\___\\__,_|_|
{Colors.END}
{Colors.CYAN}  ─────────────────────────────────────────────────────────
{Colors.BOLD}              Your Strava data, stored locally
{Colors.CYAN}  ─────────────────────────────────────────────────────────{Colors.END}
"""
    print(banner)


def print_step(step_num, total, message):
    """Print a step indicator."""
    print(f"\n{Colors.CYAN}[{step_num}/{total}]{Colors.END} {Colors.BOLD}{message}{Colors.END}")


def print_success(message):
    """Print a success message."""
    print(f"    {Colors.GREEN}✓{Colors.END} {message}")


def print_warning(message):
    """Print a warning message."""
    print(f"    {Colors.YELLOW}⚠{Colors.END} {message}")


def print_error(message):
    """Print an error message."""
    print(f"    {Colors.RED}✗{Colors.END} {message}")


def print_info(message):
    """Print an info message."""
    print(f"    {Colors.DIM}{message}{Colors.END}")


def ask_yes_no(question, default=True):
    """Ask a yes/no question."""
    default_str = "Y/n" if default else "y/N"
    while True:
        response = input(f"    {question} [{default_str}]: ").strip().lower()
        if response == "":
            return default
        if response in ("y", "yes"):
            return True
        if response in ("n", "no"):
            return False
        print_warning("Please enter 'y' or 'n'")


def ask_input(question, default=None, validator=None):
    """Ask for input with optional default and validation."""
    default_str = f" [{default}]" if default else ""
    while True:
        response = input(f"    {question}{default_str}: ").strip()
        if response == "" and default is not None:
            return default
        if response == "":
            continue
        if validator:
            try:
                return validator(response)
            except (ValueError, TypeError) as e:
                print_warning(f"Invalid input: {e}")
                continue
        return response


def check_python_version():
    """Check if Python version is sufficient."""
    if sys.version_info < MIN_PYTHON:
        print_error(f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ is required")
        print_info(f"You have Python {sys.version_info.major}.{sys.version_info.minor}")
        return False
    print_success(f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    return True


def check_venv():
    """Check if running in a virtual environment."""
    in_venv = sys.prefix != sys.base_prefix
    if in_venv:
        print_success(f"Virtual environment active: {sys.prefix}")
    return in_venv


def create_venv():
    """Create a virtual environment and return the path to its Python."""
    venv_path = Path(".venv")
    if venv_path.exists():
        print_warning(".venv already exists")
        # Return the venv python path
        if sys.platform == "win32":
            return venv_path / "Scripts" / "python.exe"
        return venv_path / "bin" / "python"

    try:
        subprocess.run([sys.executable, "-m", "venv", ".venv"], check=True)
        print_success("Created virtual environment at .venv")
        # Return the venv python path
        if sys.platform == "win32":
            return venv_path / "Scripts" / "python.exe"
        return venv_path / "bin" / "python"
    except subprocess.CalledProcessError:
        print_error("Failed to create virtual environment")
        return None


def install_dependencies(python_path=None):
    """Install Python dependencies."""
    python = str(python_path) if python_path else sys.executable
    pip_cmd = [python, "-m", "pip", "install", "-r", "requirements.txt", "-q"]
    try:
        subprocess.run(pip_cmd, check=True)
        print_success("Installed all dependencies")
        return True
    except subprocess.CalledProcessError:
        print_error("Failed to install dependencies")
        return False


def create_directories():
    """Create necessary data directories."""
    directories = ["activities", "data"]
    for dir_name in directories:
        path = Path(dir_name)
        if not path.exists():
            path.mkdir(parents=True)
            print_success(f"Created {dir_name}/ directory")
        else:
            print_info(f"{dir_name}/ already exists")


def init_database():
    """Initialize the SQLite database."""
    db_path = Path("data/strava_local.db")

    if db_path.exists():
        print_info("Database already exists at data/strava_local.db")
        return True

    try:
        # Import and create tables
        from db.models import init_db
        init_db()
        print_success("Initialized database at data/strava_local.db")
        return True
    except Exception as e:
        print_error(f"Failed to initialize database: {e}")
        return False


def configure_athlete_profile(db):
    """Configure athlete profile settings."""
    from db.models import AthleteProfile
    from metrics.profile import get_or_create_profile

    profile = get_or_create_profile(db)

    print_info("These help calculate accurate training metrics (TSS, zones, etc.)")
    print_info("Leave blank to skip or use estimates\n")

    # Max HR
    max_hr = ask_input(
        "Max Heart Rate (bpm)",
        default="skip",
        validator=lambda x: None if x == "skip" else int(x)
    )
    if max_hr != "skip" and max_hr:
        profile.max_hr = max_hr

    # Resting HR
    resting_hr = ask_input(
        "Resting Heart Rate (bpm)",
        default="skip",
        validator=lambda x: None if x == "skip" else int(x)
    )
    if resting_hr != "skip" and resting_hr:
        profile.resting_hr = resting_hr

    # LTHR
    lthr = ask_input(
        "Lactate Threshold HR (bpm)",
        default="skip",
        validator=lambda x: None if x == "skip" else int(x)
    )
    if lthr != "skip" and lthr:
        profile.lthr = lthr

    # Weight
    weight = ask_input(
        "Weight (kg)",
        default="skip",
        validator=lambda x: None if x == "skip" else float(x)
    )
    if weight != "skip" and weight:
        profile.weight_kg = weight

    db.commit()
    print_success("Saved athlete profile")


def print_next_steps():
    """Print next steps for the user."""
    # Check if venv exists to customize instructions
    venv_exists = Path(".venv").exists()
    activate_hint = ""
    if venv_exists:
        activate_hint = f"""
  {Colors.CYAN}0.{Colors.END} Activate the virtual environment (if not already):
     {Colors.BOLD}source .venv/bin/activate{Colors.END}  {Colors.DIM}# macOS/Linux{Colors.END}
     {Colors.BOLD}.venv\\Scripts\\activate{Colors.END}     {Colors.DIM}# Windows{Colors.END}
"""

    print(f"""
{Colors.BOLD}{Colors.GREEN}
  ✓ Setup Complete!
{Colors.END}
{Colors.BOLD}Next Steps:{Colors.END}
{activate_hint}
  {Colors.CYAN}1.{Colors.END} Export your data from Strava:
     {Colors.DIM}Go to strava.com → Settings → My Account → Download your data{Colors.END}

  {Colors.CYAN}2.{Colors.END} Extract and copy your data:
     {Colors.YELLOW}activities/{Colors.END}      {Colors.DIM}← folder containing your .fit.gz files{Colors.END}
     {Colors.YELLOW}activities.csv{Colors.END}   {Colors.DIM}← file with activity metadata{Colors.END}

  {Colors.CYAN}3.{Colors.END} Import your activities:
     {Colors.BOLD}python -m scripts.ingest{Colors.END}

  {Colors.CYAN}4.{Colors.END} Compute training metrics:
     {Colors.BOLD}python -m scripts.compute_metrics{Colors.END}

  {Colors.CYAN}5.{Colors.END} Start the web dashboard:
     {Colors.BOLD}python -m web.run{Colors.END}
     {Colors.DIM}Then open http://localhost:8000 in your browser{Colors.END}

{Colors.DIM}─────────────────────────────────────────────────────────────{Colors.END}
{Colors.DIM}Tip: You can update your athlete settings anytime at /settings{Colors.END}
""")


def main():
    """Main setup flow."""
    os.chdir(Path(__file__).parent)

    # Check if we're being run with --continue flag (after venv creation)
    continue_mode = "--continue" in sys.argv

    if not continue_mode:
        print_banner()

    total_steps = 5
    venv_python = None

    # Step 1: Check Python
    if not continue_mode:
        print_step(1, total_steps, "Checking Python version")
        if not check_python_version():
            sys.exit(1)

        # Step 2: Virtual environment
        print_step(2, total_steps, "Setting up virtual environment")
        in_venv = check_venv()

        if not in_venv:
            if ask_yes_no("Create a virtual environment?", default=True):
                venv_python = create_venv()
                if venv_python:
                    print_info("Installing dependencies in virtual environment...")
                    # Install deps in venv, then re-run ourselves with venv python
                    if not install_dependencies(venv_python):
                        print_error("Please fix dependency issues and try again")
                        sys.exit(1)
                    # Re-execute setup with venv python to continue
                    print_success("Continuing setup with virtual environment...")
                    result = subprocess.run([str(venv_python), __file__, "--continue"])
                    sys.exit(result.returncode)
            else:
                print_warning("Continuing without virtual environment")
                # Step 3: Install dependencies
                print_step(3, total_steps, "Installing dependencies")
                if not install_dependencies():
                    print_error("Please fix dependency issues and try again")
                    sys.exit(1)
    else:
        # Continue mode - we're running in the venv
        print_step(3, total_steps, "Dependencies installed")
        print_success("Using virtual environment")

    # Step 4: Create directories and database
    print_step(4, total_steps, "Setting up data directories")
    create_directories()

    if not init_database():
        print_error("Please fix database issues and try again")
        sys.exit(1)

    # Step 5: Configure athlete profile
    print_step(5, total_steps, "Athlete profile (optional)")

    if ask_yes_no("Configure your athlete profile now?", default=True):
        try:
            from db.models import get_session
            db = get_session()
            configure_athlete_profile(db)
            db.close()
        except Exception as e:
            print_warning(f"Could not configure profile: {e}")
            print_info("You can set this up later at /settings")
    else:
        print_info("You can configure this later at /settings")

    # Done!
    print_next_steps()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Setup cancelled.{Colors.END}")
        sys.exit(1)
