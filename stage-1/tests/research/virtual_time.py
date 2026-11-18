"""Run a coroutine on an event loop whose clock is virtual: sleeps finish at once."""
import asyncio
import selectors


class _InstantSelector:
    def __init__(self, inner, loop):
        self._inner, self._loop = inner, loop

    def select(self, timeout=None):
        ready = self._inner.select(0)
        if not ready and timeout:
            self._loop.virtual_now += timeout
        return ready

    def __getattr__(self, name):
        return getattr(self._inner, name)


class VirtualLoop(asyncio.SelectorEventLoop):
    def __init__(self):
        super().__init__(selectors.DefaultSelector())
        self.virtual_now = 0.0
        self._selector = _InstantSelector(self._selector, self)

    def time(self):
        return self.virtual_now


def run_virtual(make_coro):
    """Run ``make_coro()`` to completion; returns (result, virtual seconds elapsed)."""
    box = {}

    async def main():
        loop = asyncio.get_running_loop()
        start = loop.time()
        box["result"] = await make_coro()
        box["elapsed"] = loop.time() - start

    asyncio.run(main(), loop_factory=VirtualLoop)
    return box["result"], box["elapsed"]
