# -*- coding: utf-8 -*-
"""
核心路由集成测试
覆盖 5 个核心模块：login / dashboard / devices / spatial_twin / chat
使用 FastAPI TestClient，无需启动真实服务器
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    """创建测试客户端，整个模块复用"""
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def auth_token(client):
    """登录获取 JWT token，供需要鉴权的接口使用"""
    r = client.post("/api/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "success"
    return data["token"]


# ===== 1. 登录模块测试 =====
class TestLogin:
    """POST /api/login"""

    def test_login_success(self, client):
        """正常登录：正确账号密码"""
        r = client.post("/api/login", json={"username": "admin", "password": "admin123"})
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "success"
        assert "token" in data
        assert data["username"] == "admin"

    def test_login_wrong_password(self, client):
        """边界：错误密码 → 401"""
        r = client.post("/api/login", json={"username": "admin", "password": "wrong"})
        assert r.status_code == 401

    def test_login_unknown_user(self, client):
        """边界：不存在的用户 → 401"""
        r = client.post("/api/login", json={"username": "nobody", "password": "x"})
        assert r.status_code == 401

    def test_login_missing_field(self, client):
        """边界：缺少字段"""
        r = client.post("/api/login", json={"username": "admin"})
        assert r.status_code == 422  # Pydantic 校验失败


# ===== 2. Dashboard 模块测试 =====
class TestDashboard:
    """GET /api/dashboard, /api/cop_trend, /api/energy_distribution"""

    def test_dashboard(self, client):
        """正常获取仪表盘数据"""
        r = client.get("/api/dashboard")
        assert r.status_code == 200
        data = r.json()
        # 兜底数据也应有基本结构
        assert isinstance(data, dict)

    def test_cop_trend(self, client):
        """COP 趋势"""
        r = client.get("/api/cop_trend")
        assert r.status_code == 200

    def test_energy_distribution(self, client):
        """能耗分布"""
        r = client.get("/api/energy_distribution")
        assert r.status_code == 200


# ===== 3. 设备模块测试 =====
class TestDevices:
    """GET /api/devices, /api/equipment/predictive_maintenance"""

    def test_devices_list(self, client):
        """设备列表"""
        r = client.get("/api/devices")
        assert r.status_code == 200

    def test_devices_with_status_filter(self, client):
        """带查询参数"""
        r = client.get("/api/devices?status=ALARM")
        assert r.status_code == 200

    def test_predictive_maintenance(self, client):
        """预测性维护"""
        r = client.get("/api/equipment/predictive_maintenance")
        assert r.status_code == 200


# ===== 4. 空间孪生模块测试 =====
class TestSpatialTwin:
    """GET /api/spatial-twin/*, /api/buildings/{id}/3d-data"""

    def test_campus_data(self, client):
        """校园数据"""
        r = client.get("/api/spatial-twin/campus-data")
        assert r.status_code == 200

    def test_full_campus_sim(self, client):
        """全校园模拟"""
        r = client.get("/api/spatial-twin/full-campus-sim")
        assert r.status_code == 200

    def test_building_3d_data(self, client):
        """单建筑 3D 数据"""
        r = client.get("/api/buildings/1/3d-data")
        assert r.status_code == 200

    def test_building_3d_data_invalid_id(self, client):
        """边界：无效建筑 ID"""
        r = client.get("/api/buildings/99999/3d-data")
        # 应返回 200 + 空数据或 404，不应 500
        assert r.status_code in (200, 404)


# ===== 5. 鉴权保护接口测试 =====
class TestAuthProtection:
    """验证 require_auth / require_admin 依赖"""

    def test_admin_dashboard_without_token(self, client):
        """无 token 访问管理接口 → 401"""
        r = client.get("/api/admin/dashboard")
        assert r.status_code == 401

    def test_admin_dashboard_with_token(self, client, auth_token):
        """带 token 访问管理接口 → 200"""
        r = client.get(
            "/api/admin/dashboard",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert r.status_code == 200

    def test_admin_dashboard_invalid_token(self, client):
        """无效 token → 401"""
        r = client.get(
            "/api/admin/dashboard",
            headers={"Authorization": "Bearer invalid_token_xxx"}
        )
        assert r.status_code == 401
