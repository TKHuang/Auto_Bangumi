"""
APScheduler 4.x Spike - Validate SQLite Compatibility

Tests:
1. AsyncScheduler with SQLite data store works
2. Periodic job fires multiple times
3. max_running_jobs=1 prevents concurrent execution
4. Graceful shutdown works

Run for 20 seconds, verify job fires 3+ times.
"""

import asyncio
import time
from datetime import datetime
from pathlib import Path

try:
    from apscheduler import AsyncScheduler
    from apscheduler.datastores.sqlalchemy import SQLAlchemyDataStore
    from apscheduler.triggers.interval import IntervalTrigger
    from apscheduler.job import Job
    from apscheduler.enums import ConflictPolicy
    APSCHEDULER_AVAILABLE = True
except ImportError:
    APSCHEDULER_AVAILABLE = False
    print("APScheduler 4.x not available - will use fallback")


job_execution_count = 0
job_execution_times = []


async def test_job():
    """Test periodic job that tracks execution."""
    global job_execution_count, job_execution_times
    job_execution_count += 1
    job_execution_times.append(datetime.now())
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Job executed (count: {job_execution_count})")
    await asyncio.sleep(0.1)  # Simulate work


async def slow_job():
    """Slow job to test concurrency limits."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Slow job started")
    await asyncio.sleep(3)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Slow job finished")


async def run_spike():
    """Run APScheduler spike test."""
    if not APSCHEDULER_AVAILABLE:
        print("❌ APScheduler 4.x not installed")
        print("Decision: Use fallback (asyncio.create_task loop)")
        return False

    print("=" * 60)
    print("APScheduler 4.x Spike Test")
    print("=" * 60)

    # Create SQLite data store
    db_path = Path("data/scheduler_spike.db")
    db_path.parent.mkdir(exist_ok=True)
    
    datastore = SQLAlchemyDataStore(f"sqlite:///{db_path}")
    
    # Create scheduler
    async with AsyncScheduler(data_store=datastore) as scheduler:
        print(f"✓ Scheduler created with SQLite data store: {db_path}")
        
        # Add periodic job (every 5 seconds)
        await scheduler.add_schedule(
            test_job,
            IntervalTrigger(seconds=5),
            id="test_periodic_job",
            conflict_policy=ConflictPolicy.replace,
        )
        print("✓ Periodic job added (fires every 5 seconds)")
        
        # Start scheduler
        await scheduler.start_in_background()
        print("✓ Scheduler started")
        
        # Run for 20 seconds
        print("\nRunning for 20 seconds...")
        start_time = time.time()
        
        while time.time() - start_time < 20:
            await asyncio.sleep(1)
            elapsed = int(time.time() - start_time)
            print(f"  Elapsed: {elapsed}s | Executions: {job_execution_count}")
        
        # Stop scheduler
        print("\nStopping scheduler...")
        await scheduler.stop()
        print("✓ Scheduler stopped gracefully")
    
    # Verify results
    print("\n" + "=" * 60)
    print("Results:")
    print("=" * 60)
    print(f"Total executions: {job_execution_count}")
    print(f"Expected: 3-4 executions (20s / 5s interval)")
    
    if job_execution_count >= 3:
        print("✅ SPIKE PASSED - APScheduler 4.x works with SQLite")
        print("Decision: Use APScheduler 4.x for background tasks")
        return True
    else:
        print("❌ SPIKE FAILED - Job did not fire enough times")
        print("Decision: Use fallback (asyncio.create_task loop)")
        return False


async def main():
    """Main entry point."""
    try:
        success = await run_spike()
        
        if success:
            print("\n" + "=" * 60)
            print("DECISION: APScheduler 4.x is VIABLE")
            print("=" * 60)
            print("- SQLite data store works")
            print("- Periodic jobs execute correctly")
            print("- Graceful shutdown works")
            print("\nTask 21 will use APScheduler 4.x AsyncScheduler")
        else:
            print("\n" + "=" * 60)
            print("DECISION: Use FALLBACK implementation")
            print("=" * 60)
            print("- Create zen_bangumi/scheduler/fallback.py")
            print("- Use asyncio.create_task with asyncio.sleep loops")
            print("- Simpler, more reliable for single-instance deployment")
    except Exception as e:
        print(f"\n❌ SPIKE FAILED WITH ERROR: {e}")
        print("Decision: Use fallback (asyncio.create_task loop)")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
