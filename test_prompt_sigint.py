import asyncio
import signal
import sys
from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout

async def main():
    loop = asyncio.get_running_loop()
    
    def _handle_sigint():
        print("ASYNCIO SIGINT HANDLER CALLED")
        
    loop.add_signal_handler(signal.SIGINT, _handle_sigint)
    
    session = PromptSession()
    print("Please type something (Ctrl+D to continue to sleep block)")
    try:
        with patch_stdout():
            await session.prompt_async(">>> ")
    except EOFError:
        print("EOF, now sleeping 5 seconds. Press Ctrl+C NOW.")
        
    for i in range(5):
        await asyncio.sleep(1)
        print(f"Tick {i}")

if __name__ == "__main__":
    asyncio.run(main())
