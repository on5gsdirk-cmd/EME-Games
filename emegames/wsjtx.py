"""WSJT-X UDP protocol: listen for decodes and send free-text messages.

Unchanged from the original EME Chess (W4ATC)."""
import socket
import struct
import threading
import time

UDP_IP = "127.0.0.1"
UDP_PORT = 2237

MAGIC = 0xADBCCBDA
SCHEMA = 2
MSG_STATUS = 1
MSG_DECODE = 2
MSG_HALT_TX = 8
MSG_FREE_TEXT = 9


def _utf8(text):
    raw = text.encode("utf-8")
    return struct.pack(">I", len(raw)) + raw


class Reader:
    """Tiny helper to pull values out of a WSJT-X packet."""

    def __init__(self, data):
        self.data = data
        self.pos = 0

    def take(self, fmt):
        values = struct.unpack_from(fmt, self.data, self.pos)
        self.pos += struct.calcsize(fmt)
        return values[0] if len(values) == 1 else values

    def utf8(self):
        n = self.take(">I")
        if n == 0xFFFFFFFF:
            return ""
        text = self.data[self.pos:self.pos + n].decode("utf-8", "replace")
        self.pos += n
        return text


class WsjtxLink:
    """Listens for WSJT-X decodes and sends it free-text messages."""

    def __init__(self, inbox):
        self.inbox = inbox
        self.addr = None            # where WSJT-X is (learned from its packets)
        self.client_id = "WSJT-X"
        self.n_packets = 0
        self.n_decodes = 0
        self.last_decode = None
        self._seen_errors = set()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((UDP_IP, UDP_PORT))
        threading.Thread(target=self._listen, daemon=True).start()

    def _listen(self):
        announced = False
        while True:
            try:
                data, addr = self.sock.recvfrom(65535)
            except OSError:
                break
            mtype = None
            try:
                r = Reader(data)
                magic, _schema, mtype = r.take(">III")
                if magic != MAGIC:
                    continue
                self.n_packets += 1
                self.client_id = r.utf8() or self.client_id
                self.addr = addr
                if not announced:
                    announced = True
                    self.inbox.put(("connected", self.client_id))
                if mtype == MSG_DECODE:
                    r.take(">?")            # is new
                    r.take(">I")            # time of day
                    snr = r.take(">i")
                    r.take(">d")            # delta time
                    r.take(">I")            # delta frequency
                    r.utf8()                # mode character
                    message = r.utf8()
                    self.n_decodes += 1
                    self.last_decode = time.time()
                    self.inbox.put(("decode", snr, message))
                elif mtype == MSG_STATUS:
                    r.take(">Q")            # dial frequency
                    r.utf8()                # mode
                    dx_call = r.utf8()
                    r.utf8()                # report
                    r.utf8()                # tx mode
                    tx_enabled = r.take(">?")
                    transmitting = r.take(">?")
                    r.take(">?")            # decoding
                    r.take(">I")            # rx df
                    r.take(">I")            # tx df
                    de_call = r.utf8()
                    tx_message = None       # only newer WSJT-X versions send it
                    try:
                        r.utf8()            # de grid
                        r.utf8()            # dx grid
                        r.take(">?")        # tx watchdog
                        r.utf8()            # sub-mode
                        r.take(">?")        # fast mode
                        r.take(">B")        # special operation mode
                        r.take(">I")        # frequency tolerance
                        r.take(">I")        # T/R period
                        r.utf8()            # configuration name
                        tx_message = r.utf8()
                    except Exception:
                        pass
                    self.inbox.put(("status", tx_enabled, transmitting,
                                    de_call, dx_call, tx_message))
            except Exception as err:
                key = (mtype, type(err).__name__)
                if key not in self._seen_errors:     # report each kind once
                    self._seen_errors.add(key)
                    self.inbox.put(("error", f"Could not parse a WSJT-X packet "
                                             f"(type {mtype}): {err!r}"))
                continue

    @property
    def connected(self):
        return self.addr is not None

    def send_free_text(self, text):
        if not self.addr:
            return False
        packet = (struct.pack(">III", MAGIC, SCHEMA, MSG_FREE_TEXT)
                  + _utf8(self.client_id) + _utf8(text)
                  + struct.pack(">?", True))
        self.sock.sendto(packet, self.addr)
        return True

    def halt_tx(self):
        if not self.addr:
            return False
        packet = (struct.pack(">III", MAGIC, SCHEMA, MSG_HALT_TX)
                  + _utf8(self.client_id) + struct.pack(">?", False))
        self.sock.sendto(packet, self.addr)
        return True


