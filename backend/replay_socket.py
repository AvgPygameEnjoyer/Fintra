import logging
from flask_socketio import Namespace, emit, disconnect
from flask import request
from backend.replay import get_one_min_candles

logger = logging.getLogger(__name__)


class ReplayNamespace(Namespace):
    """WebSocket namespace for live candle replay.

    Flow:
        1. Client connects → on_connect
        2. Client emits 'init' with {symbol, start, end} → server loads candles
        3. Server emits 'ready' with {total: N}
        4. Client emits 'start' → server sends ALL candles at once
        5. Client handles playback timing (play/pause/speed/step) locally
    """

    def __init__(self, namespace):
        super().__init__(namespace)
        self.sessions = {}

    def on_connect(self):
        logger.info(f"Replay socket connected: {request.sid}")
        self.sessions[request.sid] = {
            'candles': [],
        }

    def on_disconnect(self):
        logger.info(f"Replay socket disconnected: {request.sid}")
        self.sessions.pop(request.sid, None)

    def on_init(self, data):
        """Client sends init with symbol, start, end."""
        sid = request.sid
        symbol = data.get('symbol')
        start = data.get('start')
        end = data.get('end')

        if not (symbol and start and end):
            emit('error', {'msg': 'Missing parameters: symbol, start, end'}, room=sid)
            disconnect()
            return

        try:
            df = get_one_min_candles(symbol, start, end)
            candles = df.to_dict(orient='records')

            # Serialise timestamps to ISO strings for JSON
            for c in candles:
                for key in list(c.keys()):
                    if hasattr(c[key], 'isoformat'):
                        c[key] = c[key].isoformat()

            sess = self.sessions.get(sid, {})
            sess['candles'] = candles
            emit('ready', {'total': len(candles)}, room=sid)
            logger.info(f"Replay ready for {symbol}: {len(candles)} candles")

        except Exception as e:
            logger.error(f"Replay init error: {e}")
            emit('error', {'msg': str(e)}, room=sid)
            disconnect()

    def on_start(self):
        """Send ALL candles to the client at once.
        The client handles playback timing locally."""
        sid = request.sid
        sess = self.sessions.get(sid)
        if not sess:
            emit('error', {'msg': 'Session not initialized'}, room=sid)
            return

        candles = sess.get('candles', [])
        if not candles:
            emit('error', {'msg': 'No candles loaded'}, room=sid)
            return

        # Send all candles in a single batch for smooth client-side playback
        for candle in candles:
            emit('candle', candle, room=sid)

        emit('end', {}, room=sid)
        logger.info(f"Streamed {len(candles)} candles to {sid}")
