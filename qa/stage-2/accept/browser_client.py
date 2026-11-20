"""Small Chrome DevTools client for independent headless browser checks."""
import base64
from concurrent.futures import Future, ThreadPoolExecutor
import json
import socket
import threading
import time

import websocket


class BrowserPage:
    def __init__(self, address, port, target, width=375, origin='http://dossier.internal:8080'):
        self.origin = origin
        self.closed = False
        raw = socket.create_connection((address, port), timeout=10)
        self.ws = websocket.create_connection(f'ws://{address}:{port}/devtools/page/{target}',
                                               socket=raw, timeout=30, suppress_origin=True,
                                               enable_multithread=True)
        self.ws.settimeout(None)
        self.lock = threading.Lock()
        self.pending = {}
        self.sequence = 0
        self.handlers = {}
        self.pool = ThreadPoolExecutor(max_workers=8)
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()
        self.call('Page.enable')
        self.call('Runtime.enable')
        self.call('Emulation.setDeviceMetricsOverride', {
            'width': width, 'height': 800, 'deviceScaleFactor': 1, 'mobile': width <= 375})

    def _read(self):
        try:
            while True:
                message = json.loads(self.ws.recv())
                if 'id' in message:
                    with self.lock:
                        result = self.pending.pop(message['id'], None)
                    if result:
                        result.set_result(message)
                elif message.get('method') in self.handlers:
                    self.pool.submit(self.handlers[message['method']], message.get('params', {}))
        except (OSError, ValueError, websocket.WebSocketException):
            with self.lock:
                pending, self.pending = self.pending, {}
            for result in pending.values():
                result.set_exception(RuntimeError('browser connection closed'))

    def call(self, method, params=None, timeout=20):
        result = Future()
        with self.lock:
            self.sequence += 1
            ident = self.sequence
            self.pending[ident] = result
            self.ws.send(json.dumps({'id': ident, 'method': method, 'params': params or {}}))
        message = result.result(timeout=timeout)
        if 'error' in message:
            raise RuntimeError(f'{method}: {message["error"]}')
        return message.get('result', {})

    def evaluate(self, expression):
        result = self.call('Runtime.evaluate', {'expression': expression, 'returnByValue': True,
                                                 'awaitPromise': True})
        if result.get('exceptionDetails'):
            raise AssertionError(result['exceptionDetails'].get('text', 'browser JavaScript failed'))
        return result['result'].get('value')

    def wait(self, expression, timeout=15):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            try:
                if self.evaluate(expression):
                    return
            except (AssertionError, RuntimeError):
                pass
            time.sleep(.05)
        raise AssertionError('browser condition did not become true: ' + expression)

    def navigate(self, path):
        url = self.origin + path
        result = self.call('Page.navigate', {'url': url})
        assert not result.get('errorText'), result.get('errorText')
        self.wait('location.origin === ' + json.dumps(self.origin) +
                  ' && location.pathname.toLowerCase() === ' + json.dumps(path.split('?',1)[0].lower()) +
                  " && document.readyState === 'complete'")

    def fill(self, testid, value):
        selector = json.dumps('[data-testid="' + testid + '"]')
        self.wait('!!document.querySelector(' + selector + ')')
        self.evaluate('''(() => { const e = document.querySelector(%s);
          const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
          set.call(e, %s); e.dispatchEvent(new Event('input', {bubbles:true}));
          e.dispatchEvent(new Event('change', {bubbles:true})); })()''' % (selector, json.dumps(value)))

    def click(self, testid):
        selector = json.dumps('[data-testid="' + testid + '"]')
        self.wait('!!document.querySelector(' + selector + ')')
        self.evaluate('document.querySelector(' + selector + ').click()')

    def screenshot(self, path):
        result = self.call('Page.captureScreenshot', {'format': 'png', 'captureBeyondViewport': True})
        path.write_bytes(base64.b64decode(result['data']))

    def on(self, event, callback):
        self.handlers[event] = callback

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.ws.close()
        self.pool.shutdown(wait=False, cancel_futures=True)
