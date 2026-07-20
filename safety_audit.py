import os
import re

class SafetyAuditor:
    DANGEROUS_CMD_PATTERNS = [
        r'\brm\s+-[rfRF]*\s+/',          # rm -rf /
        r'\brm\s+-[rfRF]*\s+\*',          # rm -rf *
        r'\bmkfs\b',                      # filesystem formatting
        r'\bdd\s+if=.*of=/dev/sda\b',     # dd directly to hard drive
        r'\bshutdown\b',                  # shutdown
        r'\breboot\b',                    # reboot
        r':\(\)\{\s*:\|\s*:&\s*\};\s*:',   # fork bomb
        r':\(\)\{\s*:\|\s*:&\s*\};:',     # fork bomb variations
        r'\bchmod\s+-[R\s]*777\s+/',      # chmod 777 /
    ]

    DANGEROUS_WRITE_PATHS = [
        r'^/etc/passwd',
        r'^/etc/shadow',
        r'^/etc/sudoers',
        r'^/boot',
        r'^/dev',
    ]

    @classmethod
    def audit_command(cls, command: str):
        cleaned_cmd = command.strip()
        for pattern in cls.DANGEROUS_CMD_PATTERNS:
            if re.search(pattern, cleaned_cmd):
                raise ValueError(f"Langwatch Safety Audit Alert: Destructive command blocked: '{cleaned_cmd}' matches dangerous pattern.")
        return True

    @classmethod
    def audit_file_write(cls, file_path: str, content: str = ""):
        abs_path = os.path.abspath(file_path)
        for pattern in cls.DANGEROUS_WRITE_PATHS:
            if re.search(pattern, abs_path):
                raise ValueError(f"Langwatch Safety Audit Alert: Destructive file write blocked: Attempted to write to sensitive system path '{abs_path}'.")
        
        # Check content for high-risk exploit injections or dangerous scripts
        if "rm -rf /" in content:
            raise ValueError("Langwatch Safety Audit Alert: File content contains dangerous script ('rm -rf /').")
        return True
