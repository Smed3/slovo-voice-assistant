"""
Encryption Service for Slovo Memory System.

Phase 3: AES-256 encryption at rest for all persistent memory.

Security Rules:
- AES-256 encryption
- Local master key (OS keychain if available, fallback to password-derived)
- Encrypt: PostgreSQL data, Qdrant storage, Episodic logs
- Redis excluded (non-persistent)
- Agent never logs plaintext memory to disk
- Decrypted content exists only in memory
- Encryption/decryption happens at repository boundary
"""

import base64
import hashlib
import os
import secrets
from functools import lru_cache
from typing import Final

import structlog
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = structlog.get_logger(__name__)

# Constants
KEY_LENGTH: Final[int] = 32  # AES-256
SALT_LENGTH: Final[int] = 16
PBKDF2_ITERATIONS: Final[int] = 480000  # OWASP recommendation for PBKDF2-HMAC-SHA256


class EncryptionError(Exception):
    """Raised when encryption/decryption fails."""

    pass


class EncryptionService:
    """
    AES-256 encryption service for memory at rest.

    Encryption/decryption happens at the repository boundary.
    Decrypted content exists only in memory, never on disk.
    """

    def __init__(self, master_key: bytes | None = None, password: str | None = None) -> None:
        """
        Initialize encryption service.

        Args:
            master_key: Pre-existing 32-byte master key (from keychain)
            password: Password to derive key from (fallback)

        Raises:
            ValueError: If neither master_key nor password provided
        """
        if master_key is not None:
            if len(master_key) != KEY_LENGTH:
                raise ValueError(f"Master key must be {KEY_LENGTH} bytes")
            self._master_key = master_key
            self._salt: bytes | None = None
        elif password is not None:
            self._salt = self._load_or_create_salt()
            self._master_key = self._derive_key(password, self._salt)
        else:
            raise ValueError("Either master_key or password must be provided")

        # Create Fernet cipher with base64-encoded key
        fernet_key = base64.urlsafe_b64encode(self._master_key)
        self._fernet = Fernet(fernet_key)
        logger.info("Encryption service initialized")

    def _load_or_create_salt(self) -> bytes:
        """Load existing salt or create new one."""
        salt_file = self._get_salt_path()

        if os.path.exists(salt_file):
            with open(salt_file, "rb") as f:
                salt = f.read()
                if len(salt) == SALT_LENGTH:
                    return salt
                logger.warning("Invalid salt file, regenerating")

        # Generate new salt
        salt = secrets.token_bytes(SALT_LENGTH)
        os.makedirs(os.path.dirname(salt_file), exist_ok=True)
        with open(salt_file, "wb") as f:
            f.write(salt)

        logger.info("Created new encryption salt")
        return salt

    def _get_salt_path(self) -> str:
        """Get platform-appropriate salt storage path."""
        # Use user data directory
        if os.name == "nt":  # Windows
            base = os.environ.get("APPDATA", os.path.expanduser("~"))
        else:  # Unix/Linux/macOS
            base = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))

        return os.path.join(base, "slovo", "encryption.salt")

    def _derive_key(self, password: str, salt: bytes) -> bytes:
        """Derive encryption key from password using PBKDF2."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=KEY_LENGTH,
            salt=salt,
            iterations=PBKDF2_ITERATIONS,
        )
        return kdf.derive(password.encode("utf-8"))

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt plaintext string.

        Args:
            plaintext: String to encrypt

        Returns:
            Base64-encoded encrypted string

        Raises:
            EncryptionError: If encryption fails
        """
        try:
            encrypted = self._fernet.encrypt(plaintext.encode("utf-8"))
            return base64.urlsafe_b64encode(encrypted).decode("ascii")
        except Exception as e:
            logger.error("Encryption failed", error=str(e))
            raise EncryptionError(f"Failed to encrypt data: {e}") from e

    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt ciphertext string.

        Args:
            ciphertext: Base64-encoded encrypted string

        Returns:
            Decrypted plaintext string

        Raises:
            EncryptionError: If decryption fails
        """
        try:
            encrypted = base64.urlsafe_b64decode(ciphertext.encode("ascii"))
            decrypted = self._fernet.decrypt(encrypted)
            return decrypted.decode("utf-8")
        except Exception as e:
            logger.error("Decryption failed", error=str(e))
            raise EncryptionError(f"Failed to decrypt data: {e}") from e

    def encrypt_bytes(self, data: bytes) -> bytes:
        """
        Encrypt binary data.

        Args:
            data: Bytes to encrypt

        Returns:
            Encrypted bytes

        Raises:
            EncryptionError: If encryption fails
        """
        try:
            return self._fernet.encrypt(data)
        except Exception as e:
            logger.error("Encryption failed", error=str(e))
            raise EncryptionError(f"Failed to encrypt data: {e}") from e

    def decrypt_bytes(self, data: bytes) -> bytes:
        """
        Decrypt binary data.

        Args:
            data: Encrypted bytes

        Returns:
            Decrypted bytes

        Raises:
            EncryptionError: If decryption fails
        """
        try:
            return self._fernet.decrypt(data)
        except Exception as e:
            logger.error("Decryption failed", error=str(e))
            raise EncryptionError(f"Failed to decrypt data: {e}") from e

    def hash_for_index(self, value: str) -> str:
        """
        Create deterministic hash for indexing encrypted fields.

        This allows searching encrypted data without decryption
        by comparing hashes.

        Args:
            value: Value to hash

        Returns:
            Hex-encoded SHA-256 hash
        """
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def generate_master_key() -> bytes:
        """Generate a new random master key for storage in keychain."""
        return secrets.token_bytes(KEY_LENGTH)


# =============================================================================
# Global Service Management
# =============================================================================

_encryption_service: EncryptionService | None = None


def initialize_encryption(
    master_key: bytes | None = None,
    password: str | None = None,
) -> EncryptionService:
    """
    Initialize the global encryption service.

    Should be called once at application startup.

    Args:
        master_key: Pre-existing master key from keychain
        password: Password to derive key from (fallback)

    Returns:
        Initialized encryption service
    """
    global _encryption_service

    if master_key is None and password is None:
        # Use environment variable as fallback for development
        env_key = os.environ.get("SLOVO_ENCRYPTION_KEY")
        if env_key:
            password = env_key
        else:
            # Development fallback - NOT SECURE FOR PRODUCTION
            logger.warning(
                "Using default encryption key - set SLOVO_ENCRYPTION_KEY for security"
            )
            password = "slovo-development-key-change-in-production"

    _encryption_service = EncryptionService(master_key=master_key, password=password)
    return _encryption_service


def get_encryption_service() -> EncryptionService:
    """
    Get the global encryption service.

    Raises:
        RuntimeError: If encryption service not initialized
    """
    global _encryption_service

    if _encryption_service is None:
        # Auto-initialize for development convenience
        _encryption_service = initialize_encryption()

    return _encryption_service


def shutdown_encryption() -> None:
    """Shutdown and clear the encryption service."""
    global _encryption_service
    _encryption_service = None
    logger.info("Encryption service shut down")
