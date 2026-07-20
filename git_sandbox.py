import subprocess
import os

class GitSandbox:
    def __init__(self, repo_path: str, temp_branch: str = "agent/temp-task"):
        self.repo_path = os.path.abspath(repo_path)
        self.temp_branch = temp_branch
        self.original_branch = None

    def _run_git(self, args):
        res = subprocess.run(["git"] + args, cwd=self.repo_path, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"Git command failed: git {' '.join(args)}\nStderr: {res.stderr}")
        return res.stdout.strip()

    def get_current_branch(self):
        return self._run_git(["rev-parse", "--abbrev-ref", "HEAD"])

    def enter(self):
        # Determine original branch
        self.original_branch = self.get_current_branch()
        
        # Check if the temp branch already exists, delete it if it does
        branches = self._run_git(["branch"])
        if self.temp_branch in branches:
            # Switch back to original branch if we are on it
            if self.get_current_branch() == self.temp_branch:
                self._run_git(["checkout", self.original_branch])
            self._run_git(["branch", "-D", self.temp_branch])
            
        # Create and checkout the new temp branch
        self._run_git(["checkout", "-b", self.temp_branch])
        print(f"Sandbox Entered: Branched from '{self.original_branch}' to '{self.temp_branch}'")
        return self

    def commit_and_merge(self, message: str = "Verify success: Auto commit"):
        if not self.original_branch:
            raise ValueError("Sandbox has not been entered.")
            
        # Check if there are any modified files
        status = self._run_git(["status", "--porcelain"])
        if not status:
            print("Sandbox Commit: No changes to commit.")
            # Switch back to original and clean up
            self._run_git(["checkout", self.original_branch])
            self._run_git(["branch", "-D", self.temp_branch])
            return
            
        # Commit on temp branch
        self._run_git(["add", "."])
        self._run_git(["commit", "-m", message])
        
        # Switch back to original branch
        self._run_git(["checkout", self.original_branch])
        
        # Merge temp branch
        self._run_git(["merge", self.temp_branch])
        
        # Delete temp branch
        self._run_git(["branch", "-D", self.temp_branch])
        print(f"Sandbox Committed and Merged successfully into '{self.original_branch}'")

    def rollback(self):
        if not self.original_branch:
            raise ValueError("Sandbox has not been entered.")
            
        # Discard all changes on temp branch
        self._run_git(["reset", "--hard", "HEAD"])
        self._run_git(["clean", "-fd"])
        
        # Switch back to original branch
        self._run_git(["checkout", self.original_branch])
        
        # Delete temp branch
        self._run_git(["branch", "-D", self.temp_branch])
        print(f"Sandbox Rolled Back: Discarded changes, returned to '{self.original_branch}'")
