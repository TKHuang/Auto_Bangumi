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

    def test_verify_case_sensitive(self):
        """Password verification should be case-sensitive."""
        password = "MyPassword"
        hashed = hash_password(password)
        assert verify_password("MyPassword", hashed) is True
        assert verify_password("mypassword", hashed) is False
        assert verify_password("MYPASSWORD", hashed) is False


@pytest.mark.unit
class TestPasswordIntegration:
    """Integration tests for password hashing and verification."""

    @pytest.mark.parametrize(
        "password, wrong_password",
        [
            pytest.param("", "nonempty", id="empty"),
            pytest.param(
                "p@$$w0rd!#%&*()[]{}|;:',.<>?/~`",
                "p@$$w0rd!#%&*()[]{}|;:',.<>?/~",
                id="special_characters",
            ),
            pytest.param("密码🔐パスワード", "密码🔐", id="unicode"),
            pytest.param("a" * 1000, "b" * 1000, id="long"),
        ],
    )
    def test_hash_and_verify_roundtrip(self, password, wrong_password):
        """Hash -> verify roundtrip should hold for empty/special/unicode/long passwords."""
        hashed = hash_password(password)
        assert isinstance(hashed, str)
        assert len(hashed) > 0
        assert hashed != password
        assert verify_password(password, hashed) is True
        assert verify_password(wrong_password, hashed) is False

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
