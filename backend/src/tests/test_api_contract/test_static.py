import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from module.api.response import u_response
from module.domain.value_objects import ResponseModel


class TestResponseHelper:
    def test_u_response_success(self):
        model = ResponseModel(status=True, status_code=200, msg_en="Success", msg_zh="成功")
        response = u_response(model)
        assert response.status_code == 200
        data = json.loads(response.body)
        assert data["msg_en"] == "Success"
        assert data["msg_zh"] == "成功"

    def test_u_response_error(self):
        model = ResponseModel(status=False, status_code=400, msg_en="Bad Request", msg_zh="请求错误")
        response = u_response(model)
        assert response.status_code == 400
        data = json.loads(response.body)
        assert data["msg_en"] == "Bad Request"
        assert data["msg_zh"] == "请求错误"

    def test_u_response_server_error(self):
        model = ResponseModel(status=False, status_code=500, msg_en="Internal Server Error", msg_zh="服务器内部错误")
        response = u_response(model)
        assert response.status_code == 500
        data = json.loads(response.body)
        assert data["msg_en"] == "Internal Server Error"
        assert data["msg_zh"] == "服务器内部错误"

    def test_u_response_with_special_chars(self):
        model = ResponseModel(status=True, status_code=200, msg_en="Hello 'World'", msg_zh="你好 \"世界\"")
        response = u_response(model)
        assert response.status_code == 200
        data = json.loads(response.body)
        assert data["msg_en"] == "Hello 'World'"
        assert data["msg_zh"] == "你好 \"世界\""


class TestStaticFileServing:
    @pytest.fixture
    def temp_posters_dir(self, tmp_path):
        posters_dir = tmp_path / "data" / "posters"
        posters_dir.mkdir(parents=True)
        
        test_image = posters_dir / "test.jpg"
        test_image.write_bytes(b"fake image data")
        
        yield tmp_path

    @pytest.fixture
    def app_with_posters(self, temp_posters_dir, monkeypatch):
        original_cwd = os.getcwd()
        monkeypatch.chdir(temp_posters_dir)
        
        import importlib
        import main as main_module
        importlib.reload(main_module)
        
        app = main_module.create_app()
        client = TestClient(app)
        
        yield client
        
        os.chdir(original_cwd)

    def test_posters_mount_exists(self, app_with_posters):
        response = app_with_posters.get("/posters/test.jpg")
        assert response.status_code == 200
        assert response.content == b"fake image data"

    def test_posters_nonexistent_file(self, app_with_posters):
        response = app_with_posters.get("/posters/nonexistent.jpg")
        assert response.status_code == 404

    def test_posters_path_traversal_blocked(self, app_with_posters):
        response = app_with_posters.get("/posters/../etc/passwd")
        assert response.status_code in [404, 400]

    def test_dev_mode_redirect(self, tmp_path, monkeypatch):
        from unittest.mock import patch
        
        original_cwd = os.getcwd()
        monkeypatch.chdir(tmp_path)
        
        with patch("module.conf.VERSION", "DEV_VERSION"):
            import importlib
            import main as main_module
            importlib.reload(main_module)
            
            app = main_module.create_app()
            client = TestClient(app)
            response = client.get("/", follow_redirects=False)
            assert response.status_code in [302, 307]
            assert response.headers["location"] == "/docs"
        
        os.chdir(original_cwd)

    def test_dev_mode_redirect_follows(self, tmp_path, monkeypatch):
        from unittest.mock import patch
        
        original_cwd = os.getcwd()
        monkeypatch.chdir(tmp_path)
        
        with patch("module.conf.VERSION", "DEV_VERSION"):
            import importlib
            import main as main_module
            importlib.reload(main_module)
            
            app = main_module.create_app()
            client = TestClient(app)
            response = client.get("/", follow_redirects=True)
            assert response.status_code == 200
            assert "swagger" in response.text.lower() or "openapi" in response.text.lower()
        
        os.chdir(original_cwd)
