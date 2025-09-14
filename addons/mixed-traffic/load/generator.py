import asyncio, os, random, time, httpx, argparse
from collections import Counter

B_URL = os.getenv("B_URL", "http://localhost:8080/process")

async def one(client, device_id, ms=None, mode=None):
    params = {"device_id": device_id}
    if ms is not None: params["ms"] = ms
    if mode is not None: params["mode"] = mode
    try:
        r = await client.get(B_URL, params=params, timeout=5.0)
        return r.status_code
    except Exception:
        return -1

async def main(rate, duration, normals, slows, hangs):
    t_end = time.time()+duration
    results = Counter()
    async with httpx.AsyncClient() as client:
        while time.time() < t_end:
            r = random.random()
            if hangs and r < 0.05:
                device = random.choice(hangs); mode = "hang"; ms = None
            elif slows and r < 0.20:
                device = random.choice(slows); mode = "slow"; ms = None
            else:
                device = random.choice(normals); mode = "normal"; ms = None

            asyncio.create_task(one(client, device, ms, mode))
            results["scheduled"] += 1
            await asyncio.sleep(1.0/rate)
        await asyncio.sleep(5)
    print("Sent:", results["scheduled"])

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--rate", type=float, default=10.0)
    p.add_argument("--duration", type=int, default=120)
    p.add_argument("--normal", type=int, default=80)
    p.add_argument("--slow", type=int, default=3)
    p.add_argument("--hang", type=int, default=1)
    args = p.parse_args()

    normals = [f"dev-{i}" for i in range(1, args.normal+1)]
    slows   = [f"dev-slow-{i}" for i in range(1, args.slow+1)]
    hangs   = [f"dev-hang-{i}" for i in range(1, args.hang+1)]
    asyncio.run(main(args.rate, args.duration, normals, slows, hangs))