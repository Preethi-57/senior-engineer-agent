import asyncio
from .services.job_queue import queue
from .services.run_manager import manager

async def main():
    while True:
        job=queue.pop(timeout=10)
        if not job: continue
        try:
            if job["kind"]=="analyze": await manager.analyze(job["run_id"])
            elif job["kind"]=="execute": await manager.execute_async(job["run_id"])
        except Exception as exc:
            try:
                run=manager.get(job["run_id"]); run.error=str(exc); manager._save(run)
            except Exception: pass

if __name__=="__main__": asyncio.run(main())
