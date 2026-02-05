"""TDD tests for password hashing and verification."""

import pytest

from module.security import hash_password, verify_password


@pytest.mark.unit
class TestHashPassword:
    """Tests for hash_password function."""

    def test_hash_password_returns_string(self):
        """Hashed password should be a string."""
        hashed = hash_password("mypassword")
        assert isinstance(hashed, str)
        assert len(hashed) > 0

    def test_hash_password_not_plaintext(self):
        """Hashed password should not be plaintext."""
        password = "mypassword"
        hashed = hash_password(password)
        assert hashed != password

    def test_hash_password_different_each_time(self):
        """Same password should produce different hashes (due to salt)."""
        password = "mypassword"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        assert hash1 != hash2

    def test_hash_password_with_empty_string(self):
        """Should handle empty password."""
        hashed = hash_password("")
        assert isinstance(hashed, str)
        assert len(hashed) > 0

    def test_hash_password_with_special_characters(self):
        """Should handle special characters in password."""
        password = "p@$$w0rd!#%&*()[]{}|;:',.<>?/~`"
        hashed = hash_password(password)
        assert isinstance(hashed, str)
        assert hashed != password

    def test_hash_password_with_unicode(self):
        """Should handle unicode characters in password."""
        password = "密码🔐パスワード"
        hashed = hash_password(password)
        assert isinstance(hashed, str)
        assert hashed != password

    def test_hash_password_with_long_password(self):
        """Should handle very long passwords."""
        password = "a" * 1000
        hashed = hash_password(password)
        assert isinstance(hashed, str)
        assert hashed != password

    def test_hash_password_returns_bcrypt_format(self):
        """Hashed password should be in bcrypt format."""
        hashed = hash_password("mypassword")
        # bcrypt hashes start with $2a$, $2b$, $2x$, or $2y$
        assert hashed.startswith(("$2a$", "$2b$", "$2x$", "$2y$"))


@pytest.mark.unit
class TestVerifyPassword:
    """Tests for verify_password function."""

    def test_verify_correct_password(self):
        """Should verify correct password."""
        password = "mypassword"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_verify_incorrect_password(self):
        """Should reject incorrect password."""
        password = "mypassword"
        wrong_password = "wrongpassword"
        hashed = hash_password(password)
        assert verify_password(wrong_password, hashed) is False

    def test_verify_empty_password(self):
        """Should handle empty password verification."""
        hashed = hash_password("")
        assert verify_password("", hashed) is True
        assert verify_password("nonempty", hashed) is False

    def test_verify_case_sensitive(self):
        """Password verification should be case-sensitive."""
        password = "MyPassword"
        hashed = hash_password(password)
        assert verify_password("MyPassword", hashed) is True
        assert verify_password("mypassword", hashed) is False
        assert verify_password("MYPASSWORD", hashed) is False

    def test_verify_special_characters(self):
        """Should verify passwords with special characters."""
        password = "p@$$w0rd!#%&*()[]{}|;:',.<>?/~`"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True
        assert verify_password("p@$$w0rd!#%&*()[]{}|;:',.<>?/~", hashed) is False

    def test_verify_unicode_password(self):
        """Should verify unicode passwords."""
        password = "密码🔐パスワード"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True
        assert verify_password("密码🔐", hashed) is False

    def test_verify_long_password(self):
        """Should verify very long passwords."""
        password = "a" * 1000
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True
        assert verify_password("b" * 1000, hashed) is False

    def test_verify_with_different_hashes(self):
        """Same password with different hashes should both verify."""
        password = "mypassword"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True

    def test_verify_returns_boolean(self):
        """verify_password should return boolean."""
        password = "mypassword"
        hashed = hash_password(password)
        result_true = verify_password(password, hashed)
        result_false = verify_password("wrong", hashed)
        assert isinstance(result_true, bool)
        assert isinstance(result_false, bool)


@pytest.mark.unit
class TestPasswordIntegration:
    """Integration tests for password hashing and verification."""

    def test_roundtrip_hash_and_verify(self):
        """Should hash and verify password in roundtrip."""
        password = "mypassword"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_multiple_passwords_independent(self):
        """Multiple passwords should be independent."""
        password1 = "password1"
        password2 = "password2"
        hash1 = hash_password(password1)
        hash2 = hash_password(password2)
        assert verify_password(password1, hash1) is True
        assert verify_password(password2, hash2) is True
        assert verify_password(password1, hash2) is False
        assert verify_password(password2, hash1) is False

    def test_password_security_workflow(self):
        """Simulate typical password security workflow."""
        user_password = "SecureP@ssw0rd123"
        stored_hash = hash_password(user_password)
        login_attempt = "SecureP@ssw0rd123"
        assert verify_password(login_attempt, stored_hash) is True
        wrong_attempt = "WrongPassword"
        assert verify_password(wrong_attempt, stored_hash) is False

    def test_hash_not_reversible(self):
        """Hash should not be reversible to plaintext."""
        password = "mypassword"
        hashed = hash_password(password)
        # We can't reverse the hash, but we can verify it
        assert verify_password(password, hashed) is True
        # And we can't guess the original from the hash
        assert hashed != password
