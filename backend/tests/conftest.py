import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pymysql
import pytest
import requests


BACKEND_ROOT = Path(__file__).resolve().parents[1]
TEST_DB_NAME = os.getenv("SLC_TEST_DB_NAME", "employment_slc_auto_test")
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "infini_rag_flow")
API_STARTUP_TIMEOUT_SECONDS = int(os.getenv("API_STARTUP_TIMEOUT_SECONDS", "90"))

if "test" not in TEST_DB_NAME.lower():
    raise RuntimeError("Refusing to run destructive test setup without a test database name.")

os.environ.setdefault("DB_HOST", DB_HOST)
os.environ.setdefault("DB_PORT", str(DB_PORT))
os.environ.setdefault("DB_USER", DB_USER)
os.environ.setdefault("DB_PASSWORD", DB_PASSWORD)
os.environ.setdefault("DB_NAME", TEST_DB_NAME)
os.environ.setdefault("AUTO_SEED", "true")
os.environ.setdefault("DIFY_API_KEY", "")
os.environ.setdefault("LANGCHAIN_API_KEY", "")
os.environ.setdefault("RAGFLOW_API_KEY", "")
os.environ.setdefault("RATE_LIMIT_MAX_REQUESTS", "10000")
os.environ.setdefault("MAX_REQUEST_BYTES", "8192")
os.environ.setdefault("MAX_UPLOAD_BYTES", "65536")


def _drop_test_database() -> None:
    connection = pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        charset="utf8mb4",
        connect_timeout=10,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"DROP DATABASE IF EXISTS `{TEST_DB_NAME.replace('`', '``')}`")
        connection.commit()
    finally:
        connection.close()


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="session")
def api_base_url():
    _drop_test_database()
    port = _free_port()
    env = os.environ.copy()
    env.update(
        {
            "DB_NAME": TEST_DB_NAME,
            "AUTO_SEED": "true",
            "DIFY_API_KEY": "",
            "LANGCHAIN_API_KEY": "",
            "RAGFLOW_API_KEY": "",
            "RATE_LIMIT_MAX_REQUESTS": "10000",
            "MAX_REQUEST_BYTES": "8192",
            "MAX_UPLOAD_BYTES": "65536",
            "PYTHONUNBUFFERED": "1",
        }
    )
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=BACKEND_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    base_url = f"http://127.0.0.1:{port}"
    try:
        deadline = time.time() + API_STARTUP_TIMEOUT_SECONDS
        last_error = ""
        while time.time() < deadline:
            if process.poll() is not None:
                output = process.stdout.read() if process.stdout else ""
                raise RuntimeError(f"API server exited early with code {process.returncode}\n{output}")
            try:
                response = requests.get(f"{base_url}/health", timeout=1)
                if response.status_code == 200:
                    break
                last_error = f"HTTP {response.status_code}: {response.text[:500]}"
            except requests.RequestException as exc:
                last_error = str(exc)
            time.sleep(0.5)
        else:
            process.terminate()
            output = process.stdout.read() if process.stdout else ""
            raise RuntimeError(f"API server did not become ready: {last_error}\n{output}")

        yield base_url
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
        _drop_test_database()


@pytest.fixture()
def client(api_base_url):
    session = requests.Session()
    session.headers.update({"X-Tenant-Code": "demo-sx"})
    try:
        yield session
    finally:
        session.close()


def assert_ok(response: requests.Response) -> dict:
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload.get("success") is True, payload
    return payload


@pytest.fixture(scope="session")
def super_headers(api_base_url):
    response = requests.post(
        f"{api_base_url}/api/admin/login",
        json={"username": "admin", "password": "Admin@123456"},
        timeout=10,
    )
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}", "X-Tenant-Code": "demo-sx"}


@pytest.fixture(scope="session")
def tenant_headers(api_base_url):
    response = requests.post(
        f"{api_base_url}/api/admin/login",
        json={"username": "tenant_admin", "password": "Tenant@123456", "tenant_code": "demo-sx"},
        timeout=10,
    )
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}", "X-Tenant-Code": "demo-sx"}


def unique(prefix: str) -> str:
    return f"{prefix}-{int(time.time() * 1000)}"
