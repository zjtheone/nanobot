import asyncio
import signal
import time
import sys

async def worker():
    print("Worker started")
    try:
        while True:
            # Simulate CPU/Network fast loop
            # Just sleep 0 to yield
            await asyncio.sleep(0)
            # and do some dummy work
            pass
    except asyncio.CancelledError:
        print("Worker cancelled!")

async def main():
    loop = asyncio.get_running_loop()
    task = asyncio.create_task(worker())
    
    def _handle_sigint():
        print("SIGINT CAUGHT")
        task.cancel()
        
    loop.add_signal_handler(signal.SIGINT, _handle_sigint)
    
    await task

if __name__ == "__main__":
    asyncio.run(main())
