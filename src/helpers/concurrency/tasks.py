import asyncio
from typing import Callable, Any


TargetFunction = Callable[..., Any]


class InterruptibleAsyncTask:
    def __init__(self, target_fn: TargetFunction, *args, **kwargs):
        self.target_fn = target_fn
        self.args = args
        self.kwargs = kwargs

        self.task: asyncio.Task = None
        self.started_event = asyncio.Event()

    def schedule(self):
        # reset the event in case run() is called multiple times
        self.started_event.clear()

        # wrap the target coroutine to set the event once it starts
        async def target_coroutine(*args, **kwargs):
            self.started_event.set()  # signal that the coroutine has started

            return await self.target_fn(*args, **kwargs)

        # schedule task on the event loop
        self.task = asyncio.create_task(target_coroutine(*self.args, **self.kwargs))

    async def interrupt(self):
        if self.task and not self.task.done():
            # cancel the task
            self.task.cancel()

            try:
                """
                attempt to await the task which may raise asyncio.CancelledError
                if it's an async task.
                """
                await self.task
            except asyncio.CancelledError:
                # TODO: the task was cancelled, handle cleanup if necessary
                pass
            except Exception:
                # TODO: handle any other exceptions that may have occurred during task execution
                pass
