#!/usr/bin/env python3
"""
/usr/local/bin/f2b-slow-attack-detector.py

Анализирует журнал SSH на паттерны медленных/распределённых атак:
- Один и тот же логин пробуется с разных IP
- Один IP пробует разные логины с большими интервалами
"""

import subprocess
import re
import json
from collections import defaultdict
from datetime import datetime, timedelta
import sys

DAYS_BACK = 7
USERNAME_THRESHOLD = 3   # Один логин с N разных IP = подозрительно
IP_USERNAME_THRESHOLD = 5  # Один IP пробует N разных логинов = подозрительно

def get_ssh_failures(days):
    """Получает неудачные SSH-попытки из journalctl."""
    cmd = [
        'journalctl', '-u', 'ssh',
        '--since', f'{days} days ago',
        '--no-pager', '-o', 'short-iso'
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    # Паттерны
    patterns = [
        r'(\S+).*sshd\[\d+\]: Failed password for (?:invalid user )?(\S+) from (\d+\.\d+\.\d+\.\d+)',
        r'(\S+).*sshd\[\d+\]: Invalid user (\S+) from (\d+\.\d+\.\d+\.\d+)',
    ]
    
    entries = []
    for line in result.stdout.split('\n'):
        for pattern in patterns:
            match = re.search(pattern, line)
            if match:
                timestamp, username, ip = match.groups()
                entries.append({
                    'timestamp': timestamp,
                    'username': username,
                    'ip': ip
                })
                break
    
    return entries

def analyze(entries):
    """Анализирует паттерны атак."""
    # Группировка по логину
    by_username = defaultdict(set)
    # Группировка по IP
    by_ip = defaultdict(set)
    # Группировка по подсети /24
    by_subnet = defaultdict(set)
    
    for entry in entries:
        ip = entry['ip']
        username = entry['username']
        subnet = '.'.join(ip.split('.')[:3]) + '.0/24'
        
        by_username[username].add(ip)
        by_ip[ip].add(username)
        by_subnet[subnet].add(ip)
    
    results = {
        'distributed_by_username': {},
        'credential_stuffing_by_ip': {},
        'suspicious_subnets': {},
        'recommended_bans': set()
    }
    
    # Один логин с множества IP — распределённая атака
    for username, ips in sorted(by_username.items(), key=lambda x: len(x[1]), reverse=True):
        if len(ips) >= USERNAME_THRESHOLD:
            results['distributed_by_username'][username] = list(ips)
            results['recommended_bans'].update(ips)
    
    # Один IP пробует множество логинов — credential stuffing
    for ip, usernames in sorted(by_ip.items(), key=lambda x: len(x[1]), reverse=True):
        if len(usernames) >= IP_USERNAME_THRESHOLD:
            results['credential_stuffing_by_ip'][ip] = list(usernames)
            results['recommended_bans'].add(ip)
    
    # Подозрительные подсети
    for subnet, ips in sorted(by_subnet.items(), key=lambda x: len(x[1]), reverse=True):
        if len(ips) >= 3:
            results['suspicious_subnets'][subnet] = list(ips)
    
    results['recommended_bans'] = list(results['recommended_bans'])
    return results

def ban_ips(ips):
    """Банит список IP через fail2ban."""
    for ip in ips:
        subprocess.run(
            ['fail2ban-client', 'set', 'sshd-slow', 'banip', ip],
            capture_output=True
        )
        print(f"  Banned: {ip}")

def main():
    print(f"=== Slow/Distributed Attack Analysis ({DAYS_BACK} days) ===\n")
    
    entries = get_ssh_failures(DAYS_BACK)
    print(f"Total failed attempts: {len(entries)}\n")
    
    if not entries:
        print("No failed attempts found.")
        return
    
    results = analyze(entries)
    
    # Отчёт
    if results['distributed_by_username']:
        print("🔴 DISTRIBUTED ATTACKS (same username from multiple IPs):")
        for username, ips in results['distributed_by_username'].items():
            print(f"  Username '{username}': {len(ips)} different IPs")
            for ip in ips[:10]:
                print(f"    - {ip}")
            if len(ips) > 10:
                print(f"    ... and {len(ips)-10} more")
        print()
    
    if results['credential_stuffing_by_ip']:
        print("🔴 CREDENTIAL STUFFING (one IP tries many usernames):")
        for ip, usernames in results['credential_stuffing_by_ip'].items():
            print(f"  IP {ip}: tried {len(usernames)} usernames")
            print(f"    Users: {', '.join(usernames[:10])}")
        print()
    
    if results['suspicious_subnets']:
        print("🟡 SUSPICIOUS SUBNETS:")
        for subnet, ips in results['suspicious_subnets'].items():
            print(f"  {subnet}: {len(ips)} attacking IPs")
        print()
    
    if results['recommended_bans']:
        print(f"📋 Recommended bans: {len(results['recommended_bans'])} IPs")
        
        if '--auto-ban' in sys.argv:
            print("\nAuto-banning...")
            ban_ips(results['recommended_bans'])
        else:
            print("Run with --auto-ban to automatically ban these IPs")

if __name__ == '__main__':
    main()
