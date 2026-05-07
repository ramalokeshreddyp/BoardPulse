#!/usr/bin/env python
"""Load test script for TaskBoard WebSocket collaboration."""
import argparse
import asyncio
import json
import statistics
import sys
import time
from collections import deque

import aiohttp
import websockets
from websockets.exceptions import ConnectionClosed


async def open_websocket(ws_url: str, cookie_header: str):
    """Open a websocket connection across websockets library versions."""
    try:
        return await websockets.connect(
            ws_url,
            extra_headers={'Cookie': cookie_header},
            open_timeout=10,
        )
    except TypeError:
        return await websockets.connect(
            ws_url,
            additional_headers={'Cookie': cookie_header},
            open_timeout=10,
        )


def build_ws_url(base_url: str, board_id: int) -> str:
    base = base_url.rstrip('/')
    scheme = 'wss' if base.startswith('https://') else 'ws'
    host = base.split('://', 1)[1]
    return f"{scheme}://{host}/ws/board/{board_id}/"


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    idx = min(len(values) - 1, int(len(values) * p))
    return sorted(values)[idx]


async def authenticate(base_url: str, username_or_email: str, password: str) -> tuple[str, aiohttp.CookieJar]:
    login_url = f"{base_url.rstrip('/')}/login/"
    jar = aiohttp.CookieJar()
    async with aiohttp.ClientSession(cookie_jar=jar) as session:
        async with session.get(login_url) as resp:
            if resp.status >= 400:
                raise RuntimeError(f"Failed to load login page ({resp.status})")

        csrf_cookie = jar.filter_cookies(aiohttp.client_reqrep.URL(login_url)).get('csrftoken')
        csrf = csrf_cookie.value if csrf_cookie else ''

        form_data = {
            'username': username_or_email,
            'password': password,
            'csrfmiddlewaretoken': csrf,
            'next': '/',
        }
        headers = {'Referer': login_url}
        async with session.post(login_url, data=form_data, headers=headers, allow_redirects=True) as resp:
            if resp.status >= 400:
                raise RuntimeError(f"Login request failed ({resp.status})")

        cookies = jar.filter_cookies(aiohttp.client_reqrep.URL(login_url))
        sessionid = cookies.get('sessionid')
        csrftoken = cookies.get('csrftoken')
        if not sessionid:
            raise RuntimeError('Authentication failed: no sessionid cookie returned')

        cookie_header = f"sessionid={sessionid.value}"
        if csrftoken:
            cookie_header += f"; csrftoken={csrftoken.value}"
        return cookie_header, jar


async def fetch_or_create_tasks(
    base_url: str,
    board_id: int,
    clients: int,
    cookie_jar: aiohttp.CookieJar,
) -> list[int]:
    tasks_url = f"{base_url.rstrip('/')}/api/boards/{board_id}/tasks/"
    async with aiohttp.ClientSession(cookie_jar=cookie_jar) as session:
        async with session.get(tasks_url) as resp:
            if resp.status != 200:
                raise RuntimeError(f"Failed to list tasks for board {board_id} ({resp.status})")
            data = await resp.json()

        task_ids = [t['id'] for t in data if 'id' in t]
        if not task_ids:
            raise RuntimeError(f"No tasks found for board {board_id}; seed data or create at least one task first")

    return [task_ids[i % len(task_ids)] for i in range(clients)]


async def run_client(
    client_id: int,
    ws_url: str,
    cookie_header: str,
    task_id: int,
    duration: int,
    interval: float,
    results: dict,
):
    statuses = ['todo', 'in_progress', 'done']
    pending = deque()
    results[client_id] = {
        'connected': False,
        'messages_sent': 0,
        'messages_received': 0,
        'latencies_ms': [],
        'error': None,
    }

    try:
        ws = await open_websocket(ws_url, cookie_header)
        results[client_id]['connected'] = True
        end = time.monotonic() + duration

        async def sender():
            idx = client_id % len(statuses)
            while time.monotonic() < end:
                status = statuses[idx % len(statuses)]
                pending.append(time.time())
                await ws.send(json.dumps({
                    'action': 'move_task',
                    'task_id': task_id,
                    'new_status': status,
                }))
                results[client_id]['messages_sent'] += 1
                idx += 1
                await asyncio.sleep(interval)

        async def receiver():
            while time.monotonic() < end + 2:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=2.5)
                except asyncio.TimeoutError:
                    if time.monotonic() >= end + 2:
                        break
                    continue

                msg = json.loads(raw)
                results[client_id]['messages_received'] += 1
                if msg.get('type') == 'task.moved' and msg.get('task_id') == task_id and pending:
                    sent_at = pending.popleft()
                    results[client_id]['latencies_ms'].append((time.time() - sent_at) * 1000)

        await asyncio.gather(sender(), receiver())
        await ws.close()
    except ConnectionClosed as exc:
        results[client_id]['error'] = f"Connection closed: code={exc.code}"
    except Exception as exc:  # pragma: no cover
        results[client_id]['error'] = str(exc)


def print_report(args, results: dict, elapsed: float) -> None:
    connected = sum(1 for r in results.values() if r['connected'])
    sent = sum(r['messages_sent'] for r in results.values())
    recv = sum(r['messages_received'] for r in results.values())
    all_latencies = []
    for r in results.values():
        all_latencies.extend(r['latencies_ms'])

    print('\n' + '=' * 64)
    print('TaskBoard WebSocket Benchmark Results')
    print('=' * 64)
    print(f"Board ID              : {args.board_id}")
    print(f"Concurrent clients    : {args.clients}")
    print(f"Duration              : {args.duration}s")
    print(f"Send interval         : {args.interval:.2f}s")
    print(f"Elapsed               : {elapsed:.2f}s")
    print(f"Connection success    : {connected}/{args.clients} ({(connected / max(args.clients, 1)) * 100:.1f}%)")
    print(f"Messages sent         : {sent}")
    print(f"Messages received     : {recv}")

    if all_latencies:
        print('Broadcast latency (move_task -> task.moved):')
        print(f"  Average             : {statistics.mean(all_latencies):.2f} ms")
        print(f"  Median              : {statistics.median(all_latencies):.2f} ms")
        print(f"  P95                 : {percentile(all_latencies, 0.95):.2f} ms")
        print(f"  P99                 : {percentile(all_latencies, 0.99):.2f} ms")
        print(f"  Max                 : {max(all_latencies):.2f} ms")
        print(f"  Samples             : {len(all_latencies)}")
    else:
        print('Broadcast latency     : no samples collected')

    errors = [r['error'] for r in results.values() if r['error']]
    if errors:
        print('Errors:')
        for err in sorted(set(errors))[:10]:
            print(f"  - {err}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Load test TaskBoard websocket collaboration')
    parser.add_argument('--url', default='http://localhost:8000', help='Base HTTP URL')
    parser.add_argument('--board-id', type=int, default=1, help='Board id to test')
    parser.add_argument('--clients', type=int, default=10, help='Concurrent websocket clients')
    parser.add_argument('--duration', type=int, default=10, help='Test duration in seconds')
    parser.add_argument('--interval', type=float, default=1.0, help='Message interval per client in seconds')
    parser.add_argument('--username', default='user1@example.com', help='Login username or email')
    parser.add_argument('--password', default='password123', help='Login password')
    return parser.parse_args()


async def main(args: argparse.Namespace) -> None:
    ws_url = build_ws_url(args.url, args.board_id)
    print(f"Target websocket URL: {ws_url}")
    print(f"Authenticating as: {args.username}")

    cookie_header, jar = await authenticate(args.url, args.username, args.password)
    task_ids = await fetch_or_create_tasks(args.url, args.board_id, args.clients, jar)
    print(f"Using {len(task_ids)} task(s) for client message streams")

    results: dict = {}
    start = time.monotonic()
    await asyncio.gather(*[
        run_client(
            client_id=i,
            ws_url=ws_url,
            cookie_header=cookie_header,
            task_id=task_ids[i],
            duration=args.duration,
            interval=args.interval,
            results=results,
        )
        for i in range(args.clients)
    ])
    elapsed = time.monotonic() - start
    print_report(args, results, elapsed)


if __name__ == '__main__':
    cli_args = parse_args()
    try:
        asyncio.run(main(cli_args))
    except KeyboardInterrupt:
        print('\nBenchmark interrupted by user')
    except Exception as exc:
        print(f"Benchmark failed: {exc}")
        sys.exit(1)
