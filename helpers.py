import socket
import cv2
import sys
from threading import Thread, Lock
import sys
import time
import numpy as np


class VideoGrabber(Thread):
    def __init__(self, jpeg_quality):
            Thread.__init__(self)
            self.encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality]
            self.cap = cv2.VideoCapture(0)
            self.running = True
            self.buffer = None
            self.lock = Lock()

    def stop(self):
            self.running = False

    def set_quality(self, jpeg_quality):
            self.encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality]

    def get_buffer(self):
            if self.buffer is not None:
                    self.lock.acquire()
                    cpy = self.buffer.copy()
                    self.lock.release()
                    return cpy
            
    def run(self):
            while self.running:
                    success, img = self.cap.read()
                    if not success:
                            continue
                    
                    self.lock.acquire()
                    result, self.buffer = cv2.imencode('.jpg', img, self.encode_param)
                    self.lock.release()


class SendVideo:
    def __init__(self, host, port):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((host, port))
        self.operation = ""

    def startTransfer(self):
        print("Starting transfer...")
        self.operation, self.address = self.sock.recvfrom(10)
        print(self.operation)

    def send(self, data):
        
        if self.operation == "get":
            header = ''
            len_data = len(data)
            remaining = len_data
            offset = 65490
            frag_no = 0
            # Remaining space after timestamp and one byte to indicate if more
            while((remaining - 65490) > 0):
                ts = "%.5f"%time.time()
                more = '1'
                header = ts + more
                frag_data = data[frag_no*offset: (frag_no+1)*offset]
                frag_no += 1
                frag_data = header + frag_data
                self.sock.sendto(frag_data, self.address)

            more = '0'
            ts = "%.5f"%time.time()
            header = ts + more
            frag_data = data[frag_no*offset: (frag_no+1)*offset]
            frag_no += 1
            frag_data = header + frag_data
            self.sock.sendto(frag_data, self.address)


class ReceiveVideo(Thread):
    def __init__(self, server, port):
        Thread.__init__(self)        
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server = server
        self.port = int(port)
        self.lock = Lock()
        self.buffer = cv2.imread('default.jpg', 1)
        self.running = True
        self.delay = []
        self.delay_start = time.time()

    def setOperation(self, operation="get"):
        server_address = (self.server, self.port)
        self.sock.sendto(operation, server_address)

    def get_frame(self):
        self.lock.acquire()
        copy = self.buffer.copy()
        self.lock.release()
        return copy
        

    def run(self):
        while(self.running):
            more, data = self.revc_data()
            while(more):
                print("more to come...")
                more, tmp = self.revc_data()
                data += tmp

            array = np.frombuffer(data, dtype=np.dtype('uint8'))
            img = cv2.imdecode(array, 1)

            #TODO: Handle multiple packets with acks

            self.lock.acquire()
            self.buffer = img
            self.lock.release()

    def handle_delay(self, delay):
        self.delay.append(delay)

        if (time.time() - self.delay_start) > 5:
            self.delay_start = time.time()
            self.delay = [] 
        
    def get_delay(self):
        ndelay = len(self.delay)
        ret_val = sum(self.delay)/float(ndelay)
        self.delay_start = time.time()
        self.delay = []
        return ret_val

    def revc_data(self):
        data, server = self.sock.recvfrom(65507)
        ts = time.time()
        if len(data) == 4:
            if(data == "FAIL"):
                return None

        ts_recv = float(data[:16])
        delay = ts - ts_recv
        self.handle_delay(delay)

        more = int(data[16])

        data = data[17:]
        
        return (more, data)