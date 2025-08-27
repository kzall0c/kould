#!/usr/bin/env python3
import os
import sys
import subprocess
import re
from pathlib import Path
from urllib.parse import quote_plus  # For URL encoding

# --- URL Templates ---
GITHUB_SEARCH_URL_TEMPLATE = "https://github.com/search?q=repo%3Atorvalds%2Flinux+{query}&type=code"
LKML_SEARCH_URL_TEMPLATE = "https://lore.kernel.org/lkml/?q={query}"

# --- Configuration ---
BUS_TYPES_TO_SCAN = ["pci", "usb", "platform", "i2c", "spi"]
DMESG_LOG_MAX_WIDTH = 55

def get_dmesg_output():
    """Executes dmesg once and returns its output as a list of lines."""
    try:
        # Removed '--no-pager' for better compatibility
        return subprocess.check_output(['dmesg', '-k'], text=True, stderr=subprocess.DEVNULL).splitlines()
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Warning: Could not run 'dmesg'. Log output will be unavailable.")
        return []

def find_relevant_dmesg_log(driver_name, dmesg_lines):
    """Finds the first relevant log line for a given driver from dmesg output."""
    search_patterns = [f" {driver_name}: ", f"[{driver_name}]"]
    if '_' in driver_name:
        driver_name_hyphen = driver_name.replace('_', '-')
        search_patterns.extend([f" {driver_name_hyphen}: ", f"[{driver_name_hyphen}]"])

    for line in dmesg_lines:
        for pattern in search_patterns:
            if pattern in line:
                cleaned_line = re.sub(r'^\[\s*\d+\.\d+\]\s*', '', line).strip()
                if len(cleaned_line) > DMESG_LOG_MAX_WIDTH:
                    return cleaned_line[:DMESG_LOG_MAX_WIDTH - 3] + "..."
                return cleaned_line
    return "N/A"

def show_active_drivers(dmesg_lines):
    """Prints a list of drivers bound to active devices."""
    print(f"🐧️ Active Device Drivers (based on /sys)\n")
    header = (f" {'Device':<22} | {'Driver':<18} | {'Relevant dmesg Log':<{DMESG_LOG_MAX_WIDTH}} | "
              f"{'GitHub Code Search':<70} | {'Mailing List Search'}")
    print(header)
    print("-" * len(header))

    for bus in BUS_TYPES_TO_SCAN:
        bus_path = Path(f"/sys/bus/{bus}/devices")
        if not bus_path.is_dir(): continue

        for device_path in bus_path.iterdir():
            driver_link = device_path / "driver"
            if driver_link.is_symlink():
                driver_name = os.path.basename(os.readlink(driver_link))
                device_name = device_path.name
                query = quote_plus(driver_name)
                github_url = GITHUB_SEARCH_URL_TEMPLATE.format(query=query)
                lkml_url = LKML_SEARCH_URL_TEMPLATE.format(query=query)
                dmesg_log = find_relevant_dmesg_log(driver_name, dmesg_lines)

                print(f" {device_name:<22} | {driver_name:<18} | {dmesg_log:<{DMESG_LOG_MAX_WIDTH}} | "
                      f"{github_url:<70} | {lkml_url}")

def show_loaded_modules():
    """Executes lsmod and prints a list of all loaded kernel modules."""
    print(f"\n🐧️ All Loaded Kernel Modules (based on lsmod)\n")
    header = (f" {'Module':<22} | {'Size':<10} | {'Used by':<25} | "
              f"{'GitHub Code Search':<70} | {'Mailing List Search'}")
    print(header)
    print("-" * len(header))

    try:
        lsmod_output = subprocess.check_output(['lsmod'], text=True).splitlines()
        for line in lsmod_output[1:]: # Skip header line
            parts = line.split()
            if not parts: continue
            
            module_name = parts[0]
            size = parts[1]
            used_by_list = parts[3:] if len(parts) > 3 else ["-"]
            used_by = ",".join(used_by_list)

            query = quote_plus(module_name)
            github_url = GITHUB_SEARCH_URL_TEMPLATE.format(query=query)
            lkml_url = LKML_SEARCH_URL_TEMPLATE.format(query=query)

            print(f" {module_name:<22} | {size:<10} | {used_by:<25} | "
                  f"{github_url:<70} | {lkml_url}")

    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Could not execute the 'lsmod' command.")

if __name__ == "__main__":
    if os.geteuid() != 0:
        print("🛑 This script requires root privileges.")
        print("   Please run with sudo to read 'dmesg' logs for complete information.")
        print("   Example: sudo ./find_drivers.py")
        sys.exit(1)
    
    dmesg_output = get_dmesg_output()
    show_active_drivers(dmesg_output)
    show_loaded_modules()

