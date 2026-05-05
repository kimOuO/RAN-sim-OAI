#!/usr/bin/env python3
"""
RAN-sim Frontend-Backend 連接完整測試
測試所有 case：
1. SceneGateway/init - 場景初始化
2. SimLoop/setup - 軌跡設置
3. SimLoop/start - 啟動模擬
4. SimLoop/status - 查詢狀態
5. SimLoop/stop - 停止模擬
6. Playback 連接 (可選)
"""

import requests
import json
import time
from typing import Dict, Any

BASE_URL = "http://localhost:8000"
OMNIVERSE_URL = "http://localhost:8001"

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

def print_warning(msg: str):
    print(f"{Colors.YELLOW}⚠️ {msg}{Colors.END}")

def test_health_check() -> bool:
    """Test 1: 健康狀態檢查"""
    print_header("Test 1: Health Check")

    try:
        response = requests.post(
            f"{BASE_URL}/api/v0.1/RanpSim/RanSignal/HealthChecker/read",
            json={},
            timeout=5
        )

        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)}")
            print_success("Health check passed")
            return True
        else:
            print_error(f"Unexpected status code: {response.status_code}")
            print(f"Response: {response.text}")
            return False

    except Exception as e:
        print_error(f"Connection failed: {e}")
        return False

def test_scene_gateway_init() -> str | None:
    """Test 2: 場景初始化 (SceneGateway/init)"""
    print_header("Test 2: Scene Gateway Init")

    scene_config = {
        "scene_id": "test_scene_01",
        "geometry_source": {
            "type": "buildings_json",
            "buildings": [
                {
                    "name": "Building_1",
                    "position": [0, 0, 0],
                    "size": [100, 100, 50],
                    "color": [0.8, 0.8, 0.8]
                }
            ],
            "ground": {
                "x_min": -500,
                "x_max": 500,
                "y_min": -500,
                "y_max": 500,
                "material": "concrete"
            }
        },
        "gnbs": [
            {
                "name": "gNB_1",
                "pci": 1,
                "cell_id": 0x1000001,
                "position": [100, 100, 50],
                "frequency_ghz": 28.0,
                "power_dbm": 30,
                "bandwidth_mhz": 100
            }
        ],
        "ues": [
            {
                "name": "UE_1",
                "role": 1,
                "qos_5qi": 1
            }
        ]
    }

    try:
        response = requests.post(
            f"{BASE_URL}/api/v0.1/RanpSim/Scene/SceneGateway/init",
            json=scene_config,
            timeout=30
        )

        print(f"Status Code: {response.status_code}")

        if response.status_code in [200, 201]:
            data = response.json()
            session_uuid = data.get('data', {}).get('session_uuid')
            print(f"Response: {json.dumps(data, indent=2)}")
            print_success(f"Scene initialized with session_uuid: {session_uuid}")
            return session_uuid
        else:
            print_error(f"Scene init failed with status {response.status_code}")
            print(f"Response: {response.text}")
            return None

    except Exception as e:
        print_error(f"Scene init error: {e}")
        return None

def test_sim_loop_setup(session_uuid: str) -> bool:
    """Test 3: 軌跡設置 (SimLoop/setup)"""
    print_header("Test 3: SimLoop Setup")

    ue_trajectories = [
        {
            "name": "UE_1",
            "waypoints": [
                [0, 0, 2],
                [100, 0, 2],
                [100, 100, 2],
                [0, 100, 2]
            ],
            "speed_mps": 5.0,
            "loop": True
        }
    ]

    try:
        response = requests.post(
            f"{BASE_URL}/api/v0.1/RanpSim/RanSignal/SimLoop/setup",
            json={"ues": ue_trajectories},
            timeout=10
        )

        print(f"Status Code: {response.status_code}")

        if response.status_code in [200, 201]:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)}")
            print_success("SimLoop setup successful")
            return True
        else:
            print_error(f"SimLoop setup failed with status {response.status_code}")
            print(f"Response: {response.text}")
            return False

    except Exception as e:
        print_error(f"SimLoop setup error: {e}")
        return False

def test_sim_loop_start() -> bool:
    """Test 4: 啟動模擬 (SimLoop/start)"""
    print_header("Test 4: SimLoop Start")

    try:
        response = requests.post(
            f"{BASE_URL}/api/v0.1/RanpSim/RanSignal/SimLoop/start",
            json={},
            timeout=10
        )

        print(f"Status Code: {response.status_code}")

        if response.status_code in [200, 201]:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)}")
            print_success("SimLoop started")
            return True
        else:
            print_error(f"SimLoop start failed with status {response.status_code}")
            print(f"Response: {response.text}")
            return False

    except Exception as e:
        print_error(f"SimLoop start error: {e}")
        return False

def test_sim_loop_status() -> bool:
    """Test 5: 查詢狀態 (SimLoop/status)"""
    print_header("Test 5: SimLoop Status")

    try:
        response = requests.post(
            f"{BASE_URL}/api/v0.1/RanpSim/RanSignal/SimLoop/status",
            json={},
            timeout=5
        )

        print(f"Status Code: {response.status_code}")

        if response.status_code in [200, 201]:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)}")
            print_success("Status retrieved")
            return True
        else:
            print_error(f"Status retrieval failed with status {response.status_code}")
            print(f"Response: {response.text}")
            return False

    except Exception as e:
        print_error(f"Status retrieval error: {e}")
        return False

def test_sim_loop_stop() -> bool:
    """Test 6: 停止模擬 (SimLoop/stop)"""
    print_header("Test 6: SimLoop Stop")

    try:
        response = requests.post(
            f"{BASE_URL}/api/v0.1/RanpSim/RanSignal/SimLoop/stop",
            json={},
            timeout=10
        )

        print(f"Status Code: {response.status_code}")

        if response.status_code in [200, 201]:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)}")
            print_success("SimLoop stopped")
            return True
        else:
            print_error(f"SimLoop stop failed with status {response.status_code}")
            print(f"Response: {response.text}")
            return False

    except Exception as e:
        print_error(f"SimLoop stop error: {e}")
        return False

def test_omniverse_connection() -> bool:
    """Test 7: Omniverse 後端連接"""
    print_header("Test 7: Omniverse Backend Connection")

    try:
        response = requests.get(
            f"{OMNIVERSE_URL}/api/v0.1/RAN/status",
            timeout=5
        )

        print(f"Status Code: {response.status_code}")

        if response.status_code in [200, 404]:  # 404 is ok if endpoint doesn't exist
            print_success("Omniverse backend is reachable")
            if response.status_code == 200:
                print(f"Response: {response.text[:200]}")
            return True
        else:
            print_warning(f"Omniverse returned status {response.status_code}")
            return False

    except Exception as e:
        print_error(f"Cannot reach Omniverse backend: {e}")
        return False

def main():
    print(f"\n{Colors.BLUE}{'='*70}")
    print("RAN-SIM FRONTEND-BACKEND CONNECTION TEST")
    print(f"{'='*70}{Colors.END}")
    print(f"RAN-sim Backend: {BASE_URL}")
    print(f"Omniverse Backend: {OMNIVERSE_URL}")

    results = {}

    # Test 1: Health Check
    results['health_check'] = test_health_check()

    if not results['health_check']:
        print_error("\n⚠️ Health check failed. RAN-sim backend may not be running properly.")
        print("Please check Docker logs:")
        print("  docker compose logs ranp-sim")
        return results

    # Test 2: Scene Init
    session_uuid = test_scene_gateway_init()
    results['scene_init'] = session_uuid is not None

    if not session_uuid:
        print_error("\n⚠️ Scene initialization failed. Cannot proceed with other tests.")
        return results

    # Test 3: SimLoop Setup
    results['sim_setup'] = test_sim_loop_setup(session_uuid)

    # Test 4: SimLoop Start
    results['sim_start'] = test_sim_loop_start()

    if results['sim_start']:
        # Let simulation run for 2 seconds
        print_warning("Simulation running for 2 seconds...")
        time.sleep(2)

    # Test 5: SimLoop Status
    results['sim_status'] = test_sim_loop_status()

    # Test 6: SimLoop Stop
    results['sim_stop'] = test_sim_loop_stop()

    # Test 7: Omniverse Connection
    results['omniverse'] = test_omniverse_connection()

    # Summary
    print(f"\n{Colors.BLUE}{'='*70}")
    print("TEST SUMMARY")
    print(f"{'='*70}{Colors.END}\n")

    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:<25} {status}")

    passed = sum(1 for r in results.values() if r)
    total = len(results)

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print_success("\n🎉 All tests passed!")
    else:
        print_error(f"\n⚠️ {total - passed} test(s) failed. See details above.")

if __name__ == "__main__":
    main()
