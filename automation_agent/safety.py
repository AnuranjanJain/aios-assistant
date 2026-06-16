import hashlib
import hmac
from pathlib import Path


BLOCKED_PARTS = {
    ".git",
    ".ssh",
    "credentials",
    "windows",
    "system32",
}


class SafetyError(ValueError):
    pass


class SafetyValidator:
    def __init__(self, config):
        self.config = config

    def validate_path(self, value, *, must_exist=False):
        path = Path(value).expanduser()
        resolved = path.resolve(strict=must_exist)
        matching_root = next(
            (root for root in self.config.allowed_roots if resolved == root or root in resolved.parents),
            None,
        )
        if matching_root is None:
            raise SafetyError(f"Path is outside the approved automation roots: {resolved}")
        relative_parts = {
            part.lower()
            for part in resolved.relative_to(matching_root).parts
        }
        if relative_parts & BLOCKED_PARTS:
            raise SafetyError(f"Protected path is not available to automation: {resolved}")
        return resolved

    def validate_batch(self, paths):
        if len(paths) > self.config.max_batch_files:
            raise SafetyError(
                f"Plan contains {len(paths)} files; the safety limit is {self.config.max_batch_files}."
            )

    @staticmethod
    def token_hash(token):
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @classmethod
    def token_matches(cls, supplied, expected_hash):
        if not supplied or not expected_hash:
            return False
        return hmac.compare_digest(cls.token_hash(supplied), expected_hash)
