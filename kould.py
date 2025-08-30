#!/usr/bin/env python3
import os
import sys
import subprocess
import re
from pathlib import Path
from urllib.parse import quote_plus

# --- URL Templates ---
GITHUB_SEARCH_URL_TEMPLATE = "https://github.com/search?q=repo%3Atorvalds%2Flinux+{query}&type=code"
LKML_SEARCH_URL_TEMPLATE = "https://lore.kernel.org/lkml/?q={query}"
PATCHEW_SEARCH_URL_TEMPLATE = "https://patchew.org/search?q=project%3Alinux+{query}"

# --- Configuration ---
BUS_TYPES_TO_SCAN = ["pci", "usb", "platform", "i2c", "spi"]
DMESG_LOG_MAX_WIDTH = 55

def get_dmesg_output():
    """Executes dmesg once and returns its output as a list of lines."""
    try:
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
    return ""  # Return an empty string instead of "N/A"

def show_active_drivers():
    """Prints a list of drivers bound to active devices, showing each driver only once."""
    print(f"🐧️ Active Device Drivers (from /sys)\n")
    header = (f" {'Device':<22} | {'Driver':<18} | {'Patchwork Search':<65} | "
              f"{'GitHub Code Search':<65} | {'Mailing List Search'}")
    print(header)
    print("-" * len(header))

    processed_drivers = set()
    for bus in BUS_TYPES_TO_SCAN:
        bus_path = Path(f"/sys/bus/{bus}/devices")
        if not bus_path.is_dir(): continue

        for device_path in bus_path.iterdir():
            driver_link = device_path / "driver"
            if driver_link.is_symlink():
                driver_name = os.path.basename(os.readlink(driver_link))
                if driver_name in processed_drivers:
                    continue  # Show each driver only once

                device_name = device_path.name
                query = quote_plus(driver_name)
                github_url = GITHUB_SEARCH_URL_TEMPLATE.format(query=query)
                lkml_url = LKML_SEARCH_URL_TEMPLATE.format(query=query)
                patchew_url = PATCHEW_SEARCH_URL_TEMPLATE.format(query=query)

                print(f" {device_name:<22} | {driver_name:<18} | {patchew_url:<65} | "
                      f"{github_url:<65} | {lkml_url}")
                processed_drivers.add(driver_name)

def show_loaded_modules():
    """Executes lsmod and prints a list of all loaded kernel modules."""
    print(f"\n🐧️ All Loaded Kernel Modules (from lsmod)\n")
    header = (f" {'Module':<22} | {'Size':<10} | {'Used by':<20} | {'Patchwork Search':<65} | "
              f"{'GitHub Code Search':<65} | {'Mailing List Search'}")
    print(header)
    print("-" * len(header))

    try:
        lsmod_output = subprocess.check_output(['lsmod'], text=True).splitlines()
        for line in lsmod_output[1:]:  # Skip header
            parts = line.split()
            if not parts: continue
            module_name, size, used_by_list = parts[0], parts[1], parts[3:] if len(parts) > 3 else ["-"]
            used_by = ",".join(used_by_list)
            query = quote_plus(module_name)
            github_url = GITHUB_SEARCH_URL_TEMPLATE.format(query=query)
            lkml_url = LKML_SEARCH_URL_TEMPLATE.format(query=query)
            patchew_url = PATCHEW_SEARCH_URL_TEMPLATE.format(query=query)
            print(f" {module_name:<22} | {size:<10} | {used_by:<20} | {patchew_url:<65} | "
                  f"{github_url:<65} | {lkml_url}")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Could not execute the 'lsmod' command.")

def show_drivers_from_dmesg(dmesg_lines):
    """Parses dmesg logs to print a unique, filtered list of detected board drivers."""
    print(f"\n🐧️ Drivers from dmesg Log (Unique, Filtered)\n")

    blocklist = {
        'acpi', 'alternatives', 'apparmor', 'audit', 'blacklist', 'cacheinfo', 'cma', 'console',
        'device-mapper', 'devtmpfs', 'dma', 'dmi', 'drop_monitor', 'efi', 'efivars', 'evm',
        'ftrace', 'fuse', 'gic', 'gicv3', 'hrtimer', 'hugetlb', 'hw-breakpoint', 'ima', 'input',
        'integrity', 'iommu', 'its', 'kauditd_printk_skb', 'kernel', 'landlock', 'lsm', 'lr',
        'memory', 'mce', 'microcode', 'net', 'netlabel', 'nr_irqs', 'numa', 'pc', 'pcpu-alloc',
        'percpu', 'pid_max', 'pm', 'pnp', 'printk', 'psci', 'pstore', 'random', 'rcu', 'sched_clock',
        'scsi', 'sdei', 'secureboot', 'serial', 'slub', 'smccc', 'smp', 'sp', 'squashfs', 'sve',
        'systemd', 'tainted', 'tcp', 'thermal_sys', 'vfs', 'warning', 'workingset', 'yama'
    }
    log_pattern = re.compile(r'^\[\s*\d+\.\d+\]\s*([^:]+):.*')
    found_drivers = set()

    for line in dmesg_lines:
        match = log_pattern.match(line)
        if match:
            driver_name = match.group(1).strip().split('@')[0]
            if ' ' in driver_name or not driver_name or driver_name.isdigit(): continue
            if driver_name.lower() in blocklist: continue
            if re.match(r'^(CPU|loop|x)\d*$', driver_name) or re.match(r'^nvme\d+n\d+$', driver_name): continue
            found_drivers.add(driver_name)

    header = (f" {'Detected Driver':<22} | {'Patchwork Search':<65} | {'GitHub Code Search':<65} | "
              f"{'Mailing List Search':<45} | {'Relevant dmesg Log'}")
    print(header)
    print("-" * len(header))

    for driver in sorted(list(found_drivers)):
        query = quote_plus(driver)
        github_url = GITHUB_SEARCH_URL_TEMPLATE.format(query=query)
        lkml_url = LKML_SEARCH_URL_TEMPLATE.format(query=query)
        patchew_url = PATCHEW_SEARCH_URL_TEMPLATE.format(query=query)
        dmesg_log = find_relevant_dmesg_log(driver, dmesg_lines)
        print(f" {driver:<22} | {patchew_url:<65} | {github_url:<65} | "
              f"{lkml_url:<45} | {dmesg_log}")


if __name__ == "__main__":
    if os.geteuid() != 0:
        print("🛑 This script requires root privileges.")
        print("   Please run with sudo to read 'dmesg' logs for complete information.")
        print("   Example: sudo python3 ./kould.py")
        sys.exit(1)

    dmesg_output = get_dmesg_output()
    show_active_drivers()
    show_loaded_modules()
    show_drivers_from_dmesg(dmesg_output)

