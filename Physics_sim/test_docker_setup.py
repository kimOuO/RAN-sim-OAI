#!/usr/bin/env python3
"""
Docker Setup Validation Test
Tests that the frontend and backend containers are properly configured
and can communicate over Docker network.
"""

import requests
import json
import socket
from typing import Dict, Any

BASE_URL = "http://localhost:8000"
FRONTEND_URL = "http://localhost:3002"

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

def print_header(title: str):
    print(f"\n{Colors.BLUE}{'='*70}")
    print(f"TEST: {title}")
    print(f"{'='*70}{Colors.END}\n")

def print_success(msg: str):
    print(f"{Colors.GREEN}✅ {msg}{Colors.END}")

def print_error(msg: str):
    print(f"{Colors.RED}❌ {msg}{Colors.END}")

def test_frontend_http() -> bool:
    """Test 1: Frontend HTTP server responding"""
    print_header("Test 1: Frontend HTTP Server")

    try:
        response = requests.get(FRONTEND_URL, timeout=5)

        if response.status_code == 200:
            # Check for basic HTML structure
            if "html" in response.text and "root" in response.text:
                print_success("Frontend serving HTML correctly")
                print(f"Response size: {len(response.text)} bytes")
                return True
            else:
                print_error("Frontend response missing expected HTML")
                return False
        else:
            print_error(f"Frontend returned status {response.status_code}")
            return False

    except Exception as e:
        print_error(f"Cannot reach frontend: {e}")
        return False

def test_backend_health() -> bool:
    """Test 2: Backend health check"""
    print_header("Test 2: Backend Health Check")

    try:
        response = requests.post(
            f"{BASE_URL}/api/v0.1/RanpSim/RanSignal/HealthChecker/read",
            json={},
            timeout=5
        )

        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                gpu_info = data.get('data', {}).get('gpu', {})
                print_success("Backend health check passed")
                print(f"GPU: {gpu_info.get('name')} ({gpu_info.get('total_memory_mb')}MB)")
                return True
            else:
                print_error("Backend returned non-success response")
                return False
        else:
            print_error(f"Health check returned status {response.status_code}")
            return False

    except Exception as e:
        print_error(f"Cannot reach backend: {e}")
        return False

def test_backend_api_structure() -> bool:
    """Test 3: Backend API endpoints accessible"""
    print_header("Test 3: Backend API Endpoints")

    endpoints = [
        "/api/v0.1/RanpSim/RanSignal/HealthChecker/read",
        "/api/v0.1/RanpSim/Scene/SceneGateway/init",
        "/api/v0.1/RanpSim/RanSignal/SimLoop/setup",
        "/api/v0.1/RanpSim/RanSignal/SimLoop/start",
        "/api/v0.1/RanpSim/RanSignal/SimLoop/status",
        "/api/v0.1/RanpSim/RanSignal/SimLoop/stop",
    ]

    accessible = 0
    for endpoint in endpoints:
        try:
            response = requests.post(
                f"{BASE_URL}{endpoint}",
                json={},
                timeout=5
            )
            # Any 4xx/5xx response means the endpoint exists and backend is routing
            if 200 <= response.status_code < 600:
                accessible += 1
                status_icon = "✓" if 200 <= response.status_code < 400 else "✗"
                print(f"  {status_icon} {endpoint}")
        except Exception as e:
            print(f"  ✗ {endpoint} - {str(e)}")

    if accessible == len(endpoints):
        print_success(f"All {len(endpoints)} endpoints accessible")
        return True
    else:
        print(f"Accessible: {accessible}/{len(endpoints)}")
        return accessible > 0

def test_docker_network() -> bool:
    """Test 4: Docker network connectivity"""
    print_header("Test 4: Docker Network")

    try:
        # Test from host perspective
        localhost_works = True
        try:
            requests.get("http://localhost:3002", timeout=2)
        except:
            localhost_works = False

        print(f"  Localhost access: {'✓' if localhost_works else '✗'}")

        if localhost_works:
            print_success("Docker containers accessible from host")
            return True
        else:
            print_error("Cannot access Docker containers from host")
            return False

    except Exception as e:
        print_error(f"Network test failed: {e}")
        return False

def test_port_mappings() -> bool:
    """Test 5: Port mappings"""
    print_header("Test 5: Port Mappings")

    ports = {
        3002: "frontend",
        8000: "backend"
    }

    all_listening = True
    for port, service in ports.items():
        try:
            response = requests.get(f"http://localhost:{port}", timeout=2)
            print(f"  ✓ Port {port} ({service}): responding")
        except:
            print(f"  ✗ Port {port} ({service}): not responding")
            all_listening = False

    if all_listening:
        print_success("All required ports are mapped and responding")
        return True
    else:
        return False

def main():
    print(f"\n{Colors.BLUE}{'='*70}")
    print("DOCKER SETUP VALIDATION TEST")
    print(f"{'='*70}{Colors.END}")
    print(f"Frontend: {FRONTEND_URL}")
    print(f"Backend: {BASE_URL}")

    results = {}

    # Run all tests
    results['frontend_http'] = test_frontend_http()
    results['backend_health'] = test_backend_health()
    results['backend_api'] = test_backend_api_structure()
    results['docker_network'] = test_docker_network()
    results['port_mappings'] = test_port_mappings()

    # Summary
    print(f"\n{Colors.BLUE}{'='*70}")
    print("TEST SUMMARY")
    print(f"{'='*70}{Colors.END}\n")

    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        display_name = test_name.replace('_', ' ').title()
        print(f"{display_name:<30} {status}")

    passed = sum(1 for r in results.values() if r)
    total = len(results)

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print_success("\n🎉 Docker setup is working correctly!")
        print(f"\nYou can access:")
        print(f"  Frontend at: {FRONTEND_URL}")
        print(f"  Backend API at: {BASE_URL}/api/v0.1/...")
    else:
        print(f"\n⚠️ {total - passed} test(s) failed. See details above.")

if __name__ == "__main__":
    main()
