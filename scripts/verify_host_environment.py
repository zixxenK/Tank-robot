#!/usr/bin/env python3
"""
Host Environment Diagnostic Verification Script

This script verifies the host machine environment for the autonomous
robotics agent stack, checking Python, libraries, directories, and ROS 2.
"""

import os
import sys
from pathlib import Path
from typing import List, Tuple


def print_section(title: str) -> None:
    """Print a section header."""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def check_python() -> Tuple[bool, str]:
    """Check Python version and configuration."""
    print_section("Python Environment")
    
    version = sys.version_info
    version_str = f"{version.major}.{version.minor}.{version.micro}"
    
    print(f"Python Version: {version_str}")
    print(f"Python Executable: {sys.executable}")
    print(f"Platform: {sys.platform}")
    
    if version.major == 3 and version.minor >= 10:
        print("✅ Python 3.10+ detected")
        return True, f"Python {version_str}"
    else:
        print("❌ Python 3.10+ required")
        return False, f"Python {version_str} (need 3.10+)"


def check_libraries() -> List[Tuple[str, bool, str]]:
    """Check ML/CV library installation."""
    print_section("ML/CV Library Verification")
    
    libraries = [
        ("torch", "PyTorch"),
        ("torchvision", "TorchVision"),
        ("onnxruntime", "ONNX Runtime"),
        ("cv2", "OpenCV"),
        ("openai", "OpenAI"),
        ("numpy", "NumPy"),
    ]
    
    results = []
    for module, name in libraries:
        try:
            mod = __import__(module)
            version = getattr(mod, "__version__", "unknown")
            print(f"✅ {name:20s} - {version}")
            results.append((name, True, version))
        except ImportError as e:
            print(f"❌ {name:20s} - Not installed ({e})")
            results.append((name, False, str(e)))
    
    return results


def check_directories() -> List[Tuple[str, bool, str]]:
    """Check sandbox and memory directories."""
    print_section("Directory Structure")
    
    base_path = Path(__file__).parent.parent
    directories = [
        ("sandbox", base_path / "sandbox"),
        ("agent_memory", base_path / "agent_memory"),
        ("host_ws", base_path / "host_ws"),
        ("host_ws/src", base_path / "host_ws" / "src"),
        ("agent_core", base_path / "host_ws" / "src" / "agent_core"),
    ]
    
    results = []
    for name, path in directories:
        if path.exists():
            if path.is_dir():
                # Check write permission
                test_file = path / ".write_test"
                try:
                    test_file.touch()
                    test_file.unlink()
                    print(f"✅ {name:20s} - {path} (writable)")
                    results.append((name, True, str(path)))
                except PermissionError:
                    print(f"⚠️  {name:20s} - {path} (read-only)")
                    results.append((name, False, f"{path} (read-only)"))
            else:
                print(f"❌ {name:20s} - {path} (not a directory)")
                results.append((name, False, f"{path} (not a directory)"))
        else:
            print(f"❌ {name:20s} - {path} (does not exist)")
            results.append((name, False, f"{path} (does not exist)"))
    
    return results


def check_ros2() -> Tuple[bool, str]:
    """Check ROS 2 installation and configuration."""
    print_section("ROS 2 Environment")
    
    # Check for ROS 2 environment variables
    ros_distro = os.environ.get("ROS_DISTRO", "not set")
    ros_domain_id = os.environ.get("ROS_DOMAIN_ID", "not set")
    rmw_impl = os.environ.get("RMW_IMPLEMENTATION", "not set")
    
    print(f"ROS_DISTRO: {ros_distro}")
    print(f"ROS_DOMAIN_ID: {ros_domain_id}")
    print(f"RMW_IMPLEMENTATION: {rmw_impl}")
    
    # Check for ROS 2 commands
    ros2_found = False
    for cmd in ["ros2", "colcon"]:
        if sys.platform == "win32":
            # On Windows, check if command is in PATH
            from shutil import which
            if which(cmd):
                print(f"✅ {cmd} command found")
                ros2_found = True
            else:
                print(f"❌ {cmd} command not found")
        else:
            # On Unix, use which
            from shutil import which
            if which(cmd):
                print(f"✅ {cmd} command found")
                ros2_found = True
            else:
                print(f"❌ {cmd} command not found")
    
    if ros2_found:
        return True, f"ROS 2 {ros_distro}"
    else:
        if sys.platform == "win32":
            msg = "ROS 2 not installed on Windows (install on Rock64 or WSL)"
        else:
            msg = "ROS 2 commands not found"
        return False, msg


def check_env_file() -> Tuple[bool, str]:
    """Check .env configuration file."""
    print_section("Environment Configuration")
    
    base_path = Path(__file__).parent.parent
    env_example = base_path / ".env.example"
    env_file = base_path / ".env"
    
    print(f".env.example: {env_example}")
    if env_example.exists():
        print("✅ .env.example exists")
    else:
        print("❌ .env.example missing")
    
    print(f".env: {env_file}")
    if env_file.exists():
        print("✅ .env configured")
        return True, str(env_file)
    else:
        print("⚠️  .env not configured (copy from .env.example)")
        return False, ".env not configured"


def print_summary(results: dict) -> None:
    """Print summary of all checks."""
    print_section("Summary")
    
    all_passed = True
    for category, passed, message in results.values():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status:8s} - {category:30s}: {message}")
        if not passed:
            all_passed = False
    
    print(f"\n{'=' * 60}")
    if all_passed:
        print("✅ All checks passed!")
    else:
        print("⚠️  Some checks failed - see details above")
    print(f"{'=' * 60}\n")


def main() -> int:
    """Run all diagnostic checks."""
    print("\n" + "=" * 60)
    print("  HOST ENVIRONMENT DIAGNOSTIC VERIFICATION")
    print("=" * 60)
    
    results = {}
    
    # Run checks
    python_ok, python_msg = check_python()
    results["Python"] = ("Python", python_ok, python_msg)
    
    lib_results = check_libraries()
    libs_ok = all(r[1] for r in lib_results)
    failed_libs = [r[0] for r in lib_results if not r[1]]
    results["Libraries"] = ("Libraries", libs_ok, f"Failed: {failed_libs}" if failed_libs else "All installed")
    
    dir_results = check_directories()
    dirs_ok = all(r[1] for r in dir_results)
    failed_dirs = [r[0] for r in dir_results if not r[1]]
    results["Directories"] = ("Directories", dirs_ok, f"Failed: {failed_dirs}" if failed_dirs else "All accessible")
    
    ros2_ok, ros2_msg = check_ros2()
    results["ROS 2"] = ("ROS 2", ros2_ok, ros2_msg)
    
    env_ok, env_msg = check_env_file()
    results["Environment"] = ("Environment", env_ok, env_msg)
    
    # Print summary
    print_summary(results)
    
    return 0 if all(r[1] for r in results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
