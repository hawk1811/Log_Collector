"""
Authentication module for Log Collector.
Handles user authentication, password management and login attempts tracking.
"""
import os
import json
import time
import re
import hashlib
import secrets
import threading
from pathlib import Path

from log_collector.config import (
    logger,
    DATA_DIR,
)

# Constants
AUTH_FILE = DATA_DIR / "auth.json"
DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "password"
MAX_FAILED_ATTEMPTS = 6
LOCKOUT_TIMES = {
    3: 5 * 60,  # 5 minutes after 3 failed attempts
    5: 10 * 60,  # 10 minutes after 5 failed attempts
    6: 10 * 60,  # 10 minutes for 6th attempt and beyond
}
PASSWORD_PATTERN = re.compile(r'^(?=.*[A-Z])(?=.*[0-9])(?=.*[!@#$%^&*()_+{}\[\]:;<>,.?~\\/-]).{12,}$')


class AuthManager:
    """Manages user authentication and password security."""
    
    def __init__(self):
        """Initialize the authentication manager."""
        self.users = {}
        self.failed_attempts = {}
        self.lockouts = {}
        self.lock = threading.Lock()
        self._load_auth_data()
    
    def _load_auth_data(self):
        """Load authentication data from file."""
        if not AUTH_FILE.exists():
            # Initialize with default admin user
            self._initialize_default_user()
            return
        
        try:
            with open(AUTH_FILE, "r") as f:
                auth_data = json.load(f)
                
            self.users = auth_data.get("users", {})
            self.failed_attempts = auth_data.get("failed_attempts", {})
            self.lockouts = auth_data.get("lockouts", {})
            
            # Convert lockout timestamps back to float
            for username, lockout_info in self.lockouts.items():
                if "until" in lockout_info:
                    lockout_info["until"] = float(lockout_info["until"])
            
            logger.info("Authentication data loaded successfully")
        except Exception as e:
            logger.error(f"Error loading authentication data: {e}")
            # Initialize with default admin user if loading fails
            self._initialize_default_user()
    
    def _save_auth_data(self):
        """Save authentication data to file with debugging."""
        try:
            auth_data = {
                "users": self.users,
                "failed_attempts": self.failed_attempts,
                "lockouts": self.lockouts
            }
    
    
            with open(AUTH_FILE, "w") as f:
                json.dump(auth_data, f, indent=2)
    
            logger.info("Authentication data saved successfully.")
            return True
        except IOError as e:
            logger.error(f"IOError saving authentication data: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error saving authentication data: {e}")
            return False


    
    def _initialize_default_user(self):
        """Initialize with default admin user."""
        salt = self._generate_salt()
        hashed_password = self._hash_password(DEFAULT_PASSWORD, salt)
        
        self.users = {
            DEFAULT_USERNAME: {
                "password_hash": hashed_password,
                "salt": salt,
                "force_change": True,
                "last_changed": time.time()
            }
        }
        
        self.failed_attempts = {}
        self.lockouts = {}
        
        self._save_auth_data()
        logger.info("Initialized default admin user")
    
    def _generate_salt(self):
        """Generate a random salt for password hashing."""
        return secrets.token_hex(16)
    
    def _hash_password(self, password, salt):
        """Hash a password with the given salt.
        
        Args:
            password: Password to hash
            salt: Salt to use
            
        Returns:
            str: Hashed password
        """
        # Use SHA-256 with multiple iterations for security
        iterations = 100000
        password_hash = hashlib.pbkdf2_hmac(
            'sha256', 
            password.encode('utf-8'), 
            salt.encode('utf-8'), 
            iterations
        ).hex()
        
        return password_hash
    
    def authenticate(self, username, password):
        """Authenticate a user.
        
        Args:
            username: Username
            password: Password
            
        Returns:
            tuple: (success, message, needs_password_change)
        """
        with self.lock:
            # Check if user exists
            if username not in self.users:
                return False, "Invalid username or password", False
            
            # Check if user is locked out
            if self._is_locked_out(username):
                lockout_time = self.lockouts[username]["until"]
                remaining_time = int(lockout_time - time.time())
                if remaining_time > 0:
                    minutes = remaining_time // 60
                    seconds = remaining_time % 60
                    return False, f"Account locked. Try again in {minutes}m {seconds}s", False
            
            # Verify password
            user_data = self.users[username]
            salt = user_data["salt"]
            stored_hash = user_data["password_hash"]
            input_hash = self._hash_password(password, salt)
            
            if input_hash == stored_hash:
                # Successful login - reset failed attempts
                if username in self.failed_attempts:
                    del self.failed_attempts[username]
                
                # Check if password change is required
                force_change = user_data.get("force_change", False)
                
                self._save_auth_data()
                return True, "Authentication successful", force_change
            else:
                # Failed login - increment failed attempts
                self._record_failed_attempt(username)
                
                # Check if we should display a warning
                attempts = self.failed_attempts.get(username, {}).get("count", 0)
                warning_attempts = [2, 4]  # Warning before 3rd and 5th attempts
                
                if attempts in warning_attempts:
                    next_lockout = 3 if attempts == 2 else 5
                    warning = f"Warning: {attempts} failed attempts. Account will be locked after {next_lockout}."
                    return False, warning, False
                
                return False, "Invalid username or password", False
    
    def _record_failed_attempt(self, username):
        """Record a failed login attempt.
        
        Args:
            username: Username that failed login
        """
        current_time = time.time()
        
        if username not in self.failed_attempts:
            self.failed_attempts[username] = {
                "count": 1,
                "first_attempt": current_time,
                "last_attempt": current_time
            }
        else:
            self.failed_attempts[username]["count"] += 1
            self.failed_attempts[username]["last_attempt"] = current_time
            
            # Check if we need to lock the account
            count = self.failed_attempts[username]["count"]
            
            for threshold, lockout_time in sorted(LOCKOUT_TIMES.items()):
                if count >= threshold:
                    self.lockouts[username] = {
                        "until": current_time + lockout_time,
                        "reason": f"{count} failed login attempts"
                    }
        
        self._save_auth_data()
    
    def _is_locked_out(self, username):
        """Check if a user is locked out.
        
        Args:
            username: Username to check
            
        Returns:
            bool: True if user is locked out, False otherwise
        """
        if username not in self.lockouts:
            return False
        
        lockout_until = self.lockouts[username]["until"]
        current_time = time.time()
        
        if current_time >= lockout_until:
            # Lockout period has expired
            del self.lockouts[username]
            self._save_auth_data()
            return False
        
        return True
    
    def validate_password(self, password):
        """Validate a password against security requirements.
        
        Args:
            password: Password to validate
            
        Returns:
            tuple: (is_valid, message)
        """
        if not password:
            return False, "Password cannot be empty"
        
        if len(password) < 12:
            return False, "Password must be at least 12 characters long"
        
        if not re.search("[A-Z]", password):
            return False, "Password must contain at least one uppercase letter"
        
        if not re.search("[0-9]", password):
            return False, "Password must contain at least one digit"
        
        if not re.search("[!@#$%^&*()_+{}\[\]:;<>,.?~\\/-]", password):
            return False, "Password must contain at least one special character"
        
        return True, "Password meets requirements"
    
    def change_password(self, username, old_password, new_password):
        """Change a user's password."""
        with self.lock:
            logger.info(f"Attempting password change for user: {username}")  # Debugging log
        
            # First authenticate with old password
            auth_result, auth_message, _ = self.authenticate(username, old_password)
            if not auth_result:
                logger.warning(f"Password change failed: {auth_message}")
                return False, auth_message
        
            # Validate new password
            valid, message = self.validate_password(new_password)
            if not valid:
                logger.warning(f"New password validation failed: {message}")
                return False, message
        
            # Change password
            salt = self._generate_salt()
            hashed_password = self._hash_password(new_password, salt)
        
            # Verify old password before saving new one
            auth_result, _, _ = self.authenticate(username, old_password)
            if not auth_result:
                logger.warning("Password change aborted: Incorrect old password")
                return False, "Incorrect current password"
            
            # Store new password hash
            self.users[username]["password_hash"] = hashed_password
            self.users[username]["salt"] = salt
            self.users[username]["force_change"] = False
            self.users[username]["last_changed"] = time.time()
                
            logger.info(f"New password set for user: {username}")
            
            # Save changes to auth.json
            if not self._save_auth_data():
                logger.error("Failed to save new password to auth.json")
                return False, "Error saving new password"
            
            logger.info("Password change successful and saved.")
            return True, "Password changed successfully"


    
    def reset_password(self, username, new_password=None):
        """Reset a user's password to a default value or specified password.
        
        Args:
            username: Username to reset
            new_password: New password (optional)
            
        Returns:
            tuple: (success, message)
        """
        with self.lock:
            if username not in self.users:
                return False, "User does not exist"
            
            # If no password provided, use the default
            if not new_password:
                new_password = DEFAULT_PASSWORD
                
            # Hash and save new password
            salt = self._generate_salt()
            hashed_password = self._hash_password(new_password, salt)
            
            self.users[username]["password_hash"] = hashed_password
            self.users[username]["salt"] = salt
            self.users[username]["force_change"] = True
            self.users[username]["last_changed"] = time.time()
            
            # Reset failed attempts and lockouts
            if username in self.failed_attempts:
                del self.failed_attempts[username]
            
            if username in self.lockouts:
                del self.lockouts[username]
            
            if self._save_auth_data():
                return True, f"Password for {username} has been reset"
            else:
                return False, "Error saving new password"
