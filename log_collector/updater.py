"""
Update module for Log Collector.
Handles checking for updates, pulling from git, and upgrading the package.
"""
import os
import sys
import subprocess
import time
from pathlib import Path

from prompt_toolkit import prompt
from prompt_toolkit.shortcuts import clear
from prompt_toolkit.formatted_text import HTML
from colorama import Fore, Style as ColorStyle

from log_collector.config import (
    logger,
    BASE_DIR,
)
import os
import sys
import subprocess
import time
from pathlib import Path

from prompt_toolkit import prompt
from prompt_toolkit.shortcuts import clear
from prompt_toolkit.formatted_text import HTML
from colorama import Fore, Style as ColorStyle

from log_collector.config import (
    logger,
    BASE_DIR,
)

def check_for_updates(cli):
    """Check for updates and perform upgrade if available.
    
    Args:
        cli: CLI instance for header and prompt style
    
    Returns:
        bool: True if system should restart, False otherwise
    """
    clear()
    cli._print_header()
    print(f"{Fore.CYAN}=== Check for Updates ==={ColorStyle.RESET_ALL}")
    
    # Verify git is installed
    if not _is_git_installed():
        print(f"{Fore.RED}Git is not installed or not available in PATH.{ColorStyle.RESET_ALL}")
        print("Please install Git to use this feature.")
        input("Press Enter to continue...")
        return False
    
    # Check if we're in a git repository
    if not _is_git_repo():
        print(f"{Fore.RED}Current installation is not a Git repository.{ColorStyle.RESET_ALL}")
        print("This feature only works when Log Collector is installed from Git.")
        input("Press Enter to continue...")
        return False
    
    # Check current branch
    current_branch = _get_current_branch()
    if not current_branch:
        print(f"{Fore.RED}Could not determine current Git branch.{ColorStyle.RESET_ALL}")
        input("Press Enter to continue...")
        return False
    
    print(f"\nCurrent Git branch: {current_branch}")
    
    # Check for uncommitted changes
    if _has_local_changes():
        print(f"\n{Fore.YELLOW}Warning: You have uncommitted local changes.{ColorStyle.RESET_ALL}")
        print("Updating may overwrite your changes.")
        
        confirm = prompt(
            HTML("<ansicyan>Continue anyway? (y/n): </ansicyan>"),
            style=cli.prompt_style
        )
        
        if confirm.lower() != 'y':
            print(f"{Fore.YELLOW}Update canceled.{ColorStyle.RESET_ALL}")
            input("Press Enter to continue...")
            return False
    
    # Fetch updates
    print(f"\n{Fore.CYAN}Checking for updates...{ColorStyle.RESET_ALL}")
    fetch_result = _git_fetch()
    
    if not fetch_result:
        print(f"{Fore.RED}Failed to fetch updates from remote repository.{ColorStyle.RESET_ALL}")
        input("Press Enter to continue...")
        return False
    
    # Check if updates are available
    updates_available = _updates_available(current_branch)
    
    if not updates_available:
        print(f"\n{Fore.GREEN}Your installation is up to date!{ColorStyle.RESET_ALL}")
        input("Press Enter to continue...")
        return False
    
    # Show available updates
    print(f"\n{Fore.GREEN}Updates available!{ColorStyle.RESET_ALL}")
    
    # Show commit log
    print(f"\n{Fore.CYAN}Latest changes:{ColorStyle.RESET_ALL}")
    _show_commit_log(current_branch)
    
    # Prompt for update
    confirm = prompt(
        HTML("<ansicyan>Do you want to update now? (y/n): </ansicyan>"),
        style=cli.prompt_style
    )
    
    if confirm.lower() != 'y':
        print(f"{Fore.YELLOW}Update canceled.{ColorStyle.RESET_ALL}")
        input("Press Enter to continue...")
        return False
    
    # Perform update
    print(f"\n{Fore.CYAN}Updating...{ColorStyle.RESET_ALL}")
    update_success = _git_pull(current_branch)
    
    if not update_success:
        print(f"{Fore.RED}Update failed. You may need to resolve conflicts manually.{ColorStyle.RESET_ALL}")
        input("Press Enter to continue...")
        return False
    
    # Install updated package
    print(f"\n{Fore.CYAN}Installing updated package...{ColorStyle.RESET_ALL}")
    install_success = _pip_install_upgrade()
    
    if not install_success:
        print(f"{Fore.RED}Package upgrade failed.{ColorStyle.RESET_ALL}")
        input("Press Enter to continue...")
        return False
    
    print(f"\n{Fore.GREEN}Update successful!{ColorStyle.RESET_ALL}")
    print("The application will restart to apply changes.")
    time.sleep(2)  # Short pause to let the user read the message
    
    return True  # Signal that the app should restart

def _is_git_installed():
    """Check if git is installed and available in PATH.
    
    Returns:
        bool: True if git is available, False otherwise
    """
    try:
        subprocess.run(
            ["git", "--version"], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            check=True
        )
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        return False

def _is_git_repo():
    """Check if the current directory is a git repository.
    
    Returns:
        bool: True if git repo, False otherwise
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=BASE_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        return result.stdout.strip() == "true"
    except subprocess.SubprocessError:
        return False

def _get_current_branch():
    """Get the name of the current git branch.
    
    Returns:
        str: Branch name or empty string if error
    """
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=BASE_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.SubprocessError:
        return ""

def _has_local_changes():
    """Check if there are uncommitted local changes.
    
    Returns:
        bool: True if there are local changes, False otherwise
    """
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=BASE_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        return bool(result.stdout.strip())
    except subprocess.SubprocessError:
        return True  # Assume changes on error to be safe

def _git_fetch():
    """Fetch updates from remote repository.
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        subprocess.run(
            ["git", "fetch"],
            cwd=BASE_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True
        )
        return True
    except subprocess.SubprocessError:
        return False

def _updates_available(branch):
    """Check if updates are available for the current branch.
    
    Args:
        branch: Current branch name
    
    Returns:
        bool: True if updates available, False otherwise
    """
    try:
        # Check how many commits the local branch is behind the remote
        result = subprocess.run(
            ["git", "rev-list", f"HEAD..origin/{branch}", "--count"],
            cwd=BASE_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        commit_count = int(result.stdout.strip())
        return commit_count > 0
    except (subprocess.SubprocessError, ValueError):
        return False

def _show_commit_log(branch):
    """Display the commit log of changes that will be applied.
    
    Args:
        branch: Current branch name
    """
    try:
        result = subprocess.run(
            ["git", "log", f"HEAD..origin/{branch}", "--oneline", "--no-decorate", "--max-count=5"],
            cwd=BASE_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        
        commits = result.stdout.strip().split('\n')
        if commits and commits[0]:
            for commit in commits:
                print(f"  {commit}")
            
            # Check if there are more than 5 commits
            count_result = subprocess.run(
                ["git", "rev-list", f"HEAD..origin/{branch}", "--count"],
                cwd=BASE_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            total_commits = int(count_result.stdout.strip())
            
            if total_commits > 5:
                remaining = total_commits - 5
                print(f"  ... and {remaining} more commit{'s' if remaining > 1 else ''}")
        else:
            print("  No new commits found")
    except subprocess.SubprocessError:
        print("  Could not retrieve commit log")

def _git_pull(branch):
    """Pull updates from remote repository.
    
    Args:
        branch: Current branch name
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        subprocess.run(
            ["git", "pull", "origin", branch],
            cwd=BASE_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True
        )
        return True
    except subprocess.SubprocessError:
        return False

def _pip_install_upgrade():
    """Upgrade the package using pip.
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-e", ".", "--upgrade"],
            cwd=BASE_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True
        )
        return True
    except subprocess.SubprocessError:
        return False

def restart_application():
    """Restart the current application.
    
    This function does not return as it replaces the current process.
    """
    python = sys.executable
    
    # Add restart flag to indicate this is a restart after update
    if "--restart" not in sys.argv:
        sys.argv.insert(1, "--restart")
    
    os.execl(python, python, *sys.argv)
