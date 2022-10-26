import enum
import logging
from fc.llp import LLPEndpoint
import llp
import queue
import struct
import threading

class SWPType(enum.IntEnum):
    DATA = ord('D')
    ACK = ord('A')

class SWPPacket:
    _PACK_FORMAT = '!BI'
    _HEADER_SIZE = struct.calcsize(_PACK_FORMAT)
    MAX_DATA_SIZE = 1400 # Leaves plenty of space for IP + UDP + SWP header 

    def __init__(self, type, seq_num, data=b''):
        self._type = type
        self._seq_num = seq_num
        self._data = data

    @property
    def type(self):
        return self._type

    @property
    def seq_num(self):
        return self._seq_num
    
    @property
    def data(self):
        return self._data

    def to_bytes(self):
        header = struct.pack(SWPPacket._PACK_FORMAT, self._type.value, 
                self._seq_num)
        return header + self._data
       
    @classmethod
    def from_bytes(cls, raw):
        header = struct.unpack(SWPPacket._PACK_FORMAT,
                raw[:SWPPacket._HEADER_SIZE])
        type = SWPType(header[0])
        seq_num = header[1]
        data = raw[SWPPacket._HEADER_SIZE:]
        return SWPPacket(type, seq_num, data)

    def __str__(self):
        return "%s %d %s" % (self._type.name, self._seq_num, repr(self._data))

class SWPSender:
    _SEND_WINDOW_SIZE = 5
    _TIMEOUT = 1

    def __init__(self, remote_address, loss_probability=0):
        self._llp_endpoint = llp.LLPEndpoint(remote_address=remote_address,
                loss_probability=loss_probability)

        # Start receive thread
        self._recv_thread = threading.Thread(target=self._recv)
        self._recv_thread.start()

        # TODO: Add additional state variables
        self.send_semaphore = threading.Semaphore(value=SWPSender._SEND_WINDOW_SIZE)
        self.seq_no = 0
        self.buffer = {}
        self.next_ack = 0


    def send(self, data):
        for i in range(0, len(data), SWPPacket.MAX_DATA_SIZE):
            self._send(data[i:i+SWPPacket.MAX_DATA_SIZE])

    def _send(self, data):
        # wait for a free space in the send window
        self.send_semaphore.acquire()
        
        # add to buffer
        self.buffer[self.seq_no] = data

        # create a packet and assign a sequence number
        packet = SWPPacket(type=SWPType.DATA, data=data, seq_num=self.seq_no)

        # transmit SWP packet
        LLPEndpoint.send(raw_bytes=packet.to_bytes())

        # retransmit after 1 second
        retransmit = threading.Timer(interval=SWPSender._TIMEOUT, function=self._retransmit, args=[self.seq_no])
        retransmit.start()

        # update sequence number
        self.seq_no += 1

        return
        
    def _retransmit(self, seq_num):
        # we haven't already received ACK for this packet
        if seq_num in self.buffer:
            packet = SWPPacket(type=SWPType.DATA, seq_num=seq_num, data=self.buffer[seq_num])
            LLPEndpoint.send(self, raw_bytes=packet.to_bytes())
            retransmit = threading.Timer(interval=SWPSender._TIMEOUT, function=self._retransmit, args=[self.seq_no])
            retransmit.start(); 
        return 

    def _recv(self):
        while True:
            # Receive SWP packet
            raw = self._llp_endpoint.recv()
            if raw is None:
                continue
            packet = SWPPacket.from_bytes(raw)
            logging.debug("Received: %s" % packet)

            # only handle ACK messages
            if packet.type != SWPType.ACK: continue

            for seqno in range(self.next_ack, packet.seq_num + 1)
            # cancel retransmit timer by removing from buffer
            del self.buffer[packet.seq_num]

        return

class SWPReceiver:
    _RECV_WINDOW_SIZE = 5

    def __init__(self, local_address, loss_probability=0):
        self._llp_endpoint = llp.LLPEndpoint(local_address=local_address, 
                loss_probability=loss_probability)

        # Received data waiting for application to consume
        self._ready_data = queue.Queue()

        # Start receive thread
        self._recv_thread = threading.Thread(target=self._recv)
        self._recv_thread.start()
        
        # TODO: Add additional state variables


    def recv(self):
        return self._ready_data.get()

    def _recv(self):
        while True:
            # Receive data packet
            raw = self._llp_endpoint.recv()
            packet = SWPPacket.from_bytes(raw)
            logging.debug("Received: %s" % packet)
            
            # TODO

        return
