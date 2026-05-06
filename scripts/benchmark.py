#!/usr/bin/env python
"""
scripts/benchmark.py — WebSocket Load Testing Script for TaskBoard

Usage:
    python scripts/benchmark.py [options]

Examples:
    python scripts/benchmark.py --clients 10 --board-id 1
    python scripts/benchmark.py --clients 50 --board-id 1 --duration 10 --url http://localhost:8000

Requirements:
    pip install websockets aiohttp
"""
import argparse
import asyncio
import json
import statistics
import sys
import time
from datetime import datetime

try:
    import aiohttp
except ImportError:
    print("ERROR: aiohttp not installed. Run: pip install aiohttp")
    sys.exit(1)

try:
    import websockets
    from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK
except ImportError:
    print("ERROR: websockets not installed. Run: pip install websockets")
    sys.exit(1)


# ──────────────────────────────────────────────────────────────────────────────
# Auth helper
# ──────────────────────────────────────────────────────────────────────────────

async def get_session_cookie(base_url: str, username: str, password: str) -> str | None:
    """Log in via Django's session auth and return the session cookie string."""
    login_url = f"{base_url}/login/"
    connector = aiohttp.TCPConnector(ssl=False)

    async with aiohttp.ClientSession(connector=connector) as session:
        # Get CSRF token
        async with session.get(login_url) as resp:
            csrf_token = None
            for cookie in resp.cookies.values():
                if cookie.key == 'csrftoken':
                    csrf_token = cookie.value
                    break
            if not csrf_token:
                # Try extracting from Set-Cookie header
                set_cookie = resp.headers.get('Set-Cookie', '')
                for part in set_cookie.split(';'):
                    if 'csrftoken=' in part:
                        csrf_token = part.strip().split('=', 1)[1]

        if not csrf_token:
            print("  WARNING: Could not get CSRF token; attempting login without it")

        # Post login form
        form_data = {
            'username': username,
            'password': password,
            'csrfmiddlewaretoken': csrf_token or '',
            'next': '/',
        }
        headers = {'Referer': login_url}
        async with session.post(login_url, data=form_data, headers=headers, allow_redirects=True) as resp:
            cookies = session.cookie_jar.filter_cookies(login_url)
            sessionid = cookies.get('sessionid')
            csrftoken = cookies.get('csrftoken')
            if sessionid:
                cookie_str = f"sessionid={sessionid.value}"
                if csrftoken:
                    cookie_str += f"; csrftoken={csrftoken.value}"
                return cookie_str
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Client Worker
# ──────────────────────────────────────────────────────────────────────────────

async def run_client(
    client_id: int,
    ws_url: str,
    cookie: str,
    board_id: int,
    duration: int,
    results: dict,
    task_ids: list[int],
):
    """
    Single WebSocket client:
    - Connects to the board
    - Sends move_task messages with embedded timestamps
    - Measures round-trip broadcast latency
    """
    results[client_id] = {
        'connected': False,
        'messages_sent': 0,
        'messages_received': 0,
        'latencies_ms': [],
        'error': None,
    }

    statuses = ['todo', 'in_progress', 'done']
    task_id = task_ids[client_id % len(task_ids)]

    try:
        extra_headers = {'Cookie': cookie}
        async with websockets.connect(ws_url, extra_headers=extra_headers, open_timeout=10) as ws:
            results[client_id]['connected'] = True
            end_time = time.monotonic() + duration

            async def sender():
                status_idx = 0
                while time.monotonic() < end_time:
                    ts = time.time()
                    msg = json.dumps({
                        'action': 'move_task',
                        'task_id': task_id,
                        'new_status': statuses[status_idx % 3],
                        '_timestamp': ts,
                        '_client_id': client_id,
                    })
                    await ws.send(msg)
                    results[client_id]['messages_sent'] += 1
                    status_idx += 1
                    await asyncio.sleep(1.0)

            async def receiver():
                while time.monotonic() < end_time + 2:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
                        data = json.loads(raw)
                        results[client_id]['messages_received'] += 1

                        # Measure latency if this is a task.moved broadcast with our timestamp
                        if data.get('type') == 'task.moved' and '_timestamp' in data:
                            latency_ms = (time.time() - data['_timestamp']) * 1000
                            results[client_id]['latencies_ms'].append(latency_ms)

                    except asyncio.TimeoutError:
                        if time.monotonic() >= end_time + 2:
                            break
                    except (ConnectionClosedOK, ConnectionClosedError):
                        break

            await asyncio.gather(sender(), receiver())

    except Exception as exc:
        results[client_id]['error'] = str(exc)


# ──────────────────────────────────────────────────────────────────────────────
# Note: The consumer broadcasts task.moved without the _timestamp field.
# We patch the consumer output for benchmark by embedding the timestamp
# in the move_task message and re-echoing it. For accurate benchmark
# testing, you can temporarily modify the consumer to pass through
# unknown fields, or use the ping/pong mechanism below.
# ──────────────────────────────────────────────────────────────────────────────

async def run_ping_client(
    client_id: int,
    ws_url: str,
    cookie: str,
    duration: int,
    results: dict,
):
    """Alternative: measure latency via ping/pong round-trip."""
    key = f'ping_{client_id}'
    results[key] = {
        'connected': False,
        'pings_sent': 0,
        'pongs_received': 0,
        'latencies_ms': [],
        'error': None,
    }

    try:
        extra_headers = {'Cookie': cookie}
        async with websockets.connect(ws_url, extra_headers=extra_headers, open_timeout=10) as ws:
            results[key]['connected'] = True
            end_time = time.monotonic() + duration

            while time.monotonic() < end_time:
                ts = time.time()
                await ws.send(json.dumps({'action': 'ping', 'timestamp': ts}))
                results[key]['pings_sent'] += 1
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
                    data = json.loads(raw)
                    if data.get('type') == 'pong' and 'timestamp' in data:
                        latency_ms = (time.time() - data['timestamp']) * 1000
                        results[key]['latencies_ms'].append(latency_ms)
                        results[key]['pongs_received'] += 1
                except asyncio.TimeoutError:
                    pass
                await asyncio.sleep(1.0)

    except Exception as exc:
        results[key]['error'] = str(exc)


# ──────────────────────────────────────────────────────────────────────────────
# Reporting
# ──────────────────────────────────────────────────────────────────────────────

def print_report(args, results: dict, elapsed: float):
    print("\n" + "═" * 60)
    print("  📊 BENCHMARK RESULTS")
    print("═" * 60)
    print(f"  Board ID     : {args.board_id}")
    print(f"  Clients      : {args.clients}")
    print(f"  Duration     : {args.duration}s")
    print(f"  Total time   : {elapsed:.2f}s")
    print("─" * 60)

    connected = sum(1 for r in results.values() if r.get('connected'))
    errors = [r['error'] for r in results.values() if r.get('error')]
    all_latencies = []
    for r in results.values():
        all_latencies.extend(r.get('latencies_ms', []))

    total_sent = sum(r.get('messages_sent', r.get('pings_sent', 0)) for r in results.values())
    total_recv = sum(r.get('messages_received', r.get('pongs_received', 0)) for r in results.values())

    print(f"  Connected    : {connected}/{args.clients} ({100*connected/max(args.clients,1):.0f}%)")
    print(f"  Messages sent: {total_sent}")
    print(f"  Messages recv: {total_recv}")

    if all_latencies:
        print("─" * 60)
        print(f"  Latency (round-trip broadcast)")
        print(f"    Mean  : {statistics.mean(all_latencies):.2f} ms")
        print(f"    Median: {statistics.median(all_latencies):.2f} ms")
        print(f"    P95   : {sorted(all_latencies)[int(len(all_latencies)*0.95)]:.2f} ms")
        print(f"    P99   : {sorted(all_latencies)[int(len(all_latencies)*0.99)]:.2f} ms")
        print(f"    Min   : {min(all_latencies):.2f} ms")
        print(f"    Max   : {max(all_latencies):.2f} ms")
        print(f"    Samples: {len(all_latencies)}")
    else:
        print("  No latency samples collected (ping/pong used; check 'pong' responses)")

    if errors:
        print("─" * 60)
        print(f"  Errors ({len(errors)}):")
        for e in set(errors[:5]):
            print(f"    ✗ {e}")

    print("═" * 60)

    # Per-client summary (first 10)
    print("\n  Per-client summary (first 10):")
    print(f"  {'ID':>4}  {'Connected':>10}  {'Sent':>6}  {'Recv':>6}  {'Avg Lat':>10}  Error")
    print("  " + "-" * 56)
    for cid, r in list(results.items())[:10]:
        lats = r.get('latencies_ms', [])
        avg_lat = f"{statistics.mean(lats):.1f}ms" if lats else "N/A"
        sent = r.get('messages_sent', r.get('pings_sent', 0))
        recv = r.get('messages_received', r.get('pongs_received', 0))
        err = (r.get('error') or '')[:25]
        print(f"  {str(cid):>4}  {'✓' if r['connected'] else '✗':>10}  {sent:>6}  {recv:>6}  {avg_lat:>10}  {err}")
    print()


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

async def main(args):
    base_url = args.url.rstrip('/')
    ws_scheme = 'wss' if base_url.startswith('https') else 'ws'
    ws_base = ws_scheme + '://' + base_url.split('://', 1)[1]
    ws_url = f"{ws_base}/ws/board/{args.board_id}/"

    print("═" * 60)
    print("  ⚡ TaskBoard WebSocket Benchmark")
    print("═" * 60)
    print(f"  Target URL : {ws_url}")
    print(f"  Clients    : {args.clients}")
    print(f"  Duration   : {args.duration}s")
    print(f"  Mode       : {'ping/pong latency' if args.ping else 'task move broadcast'}")
    print("─" * 60)

    # Authenticate
    print(f"\n[1/3] Authenticating as {args.username}...")
    cookie = await get_session_cookie(base_url, args.username, args.password)
    if not cookie:
        print("  ERROR: Authentication failed. Check credentials and server URL.")
        sys.exit(1)
    print(f"  ✓ Session obtained")

    # Task IDs to use (default: 1, 2, 3)
    task_ids = list(range(1, max(4, args.clients + 1)))

    results = {}
    print(f"\n[2/3] Connecting {args.clients} client(s)...")

    start = time.monotonic()

    if args.ping:
        tasks = [
            run_ping_client(i, ws_url, cookie, args.duration, results)
            for i in range(args.clients)
        ]
    else:
        tasks = [
            run_client(i, ws_url, cookie, args.board_id, args.duration, results, task_ids)
            for i in range(args.clients)
        ]

    await asyncio.gather(*tasks)
    elapsed = time.monotonic() - start

    print(f"  ✓ All clients finished")

    print(f"\n[3/3] Generating report...")
    print_report(args, results, elapsed)


def parse_args():
    parser = argparse.ArgumentParser(
        description='WebSocket load test for TaskBoard',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument('--url', default='http://localhost:8000', help='Base HTTP URL of the server')
    parser.add_argument('--board-id', type=int, default=1, help='Board ID to connect to')
    parser.add_argument('--clients', type=int, default=10, help='Number of concurrent WebSocket clients')
    parser.add_argument('--duration', type=int, default=10, help='Duration of test per client (seconds)')
    parser.add_argument('--username', default='user1', help='Username for authentication')
    parser.add_argument('--password', default='password123', help='Password for authentication')
    parser.add_argument('--ping', action='store_true', help='Use ping/pong for latency measurement instead of task moves')
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()
    try:
        asyncio.run(main(args))
    except KeyboardInterrupt:
        print("\nBenchmark interrupted.")
