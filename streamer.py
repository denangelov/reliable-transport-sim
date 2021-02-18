# do not import anything else from loss_socket besides LossyUDP
from lossy_socket import LossyUDP
# do not import anything else from socket except INADDR_ANY
from socket import INADDR_ANY
import struct
import concurrent.futures
import time

class Streamer:
    def __init__(self, dst_ip, dst_port,
                 src_ip=INADDR_ANY, src_port=0):
        """Default values listen on all network interfaces, chooses a random source port,
           and does not introduce any simulated packet loss."""
        self.socket = LossyUDP()
        self.socket.bind((src_ip, src_port))
        self.dst_ip = dst_ip
        self.dst_port = dst_port

        self.recv_buff = {}
        self.incoming_sequence_num = 0
        self.outbound_sequence_num = 0

        self.closed = False
        self.ack = False
        
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        executor.submit(self.listener)

    def listener(self):
        while not self.closed:
            try:
                data, addr = self.socket.recvfrom()

                recv_packet_num = struct.unpack('i', data[0:4])[0]
                is_ack = struct.unpack('i', data[4:8])[0]
                
                # Case1: The received packet is an ACK
                if is_ack:
                    self.ack = True

                # Case2: The received packet is normal data that we must add to the recv buffer
                else:
                    data_bytes = data[8:]

                    # Add the data to the receive buffer
                    self.recv_buff[recv_packet_num] = data_bytes

                    # Send an ACK back
                    self.send(b'', 1)

            except Exception as e:
                print("listener died!")
                print(e)

    def send(self, data_bytes: bytes, is_ack =0) -> None:
        if is_ack:
            self.socket.sendto(struct.pack('ii', self.outbound_sequence_num, is_ack), (self.dst_ip, self.dst_port))
            return

        header = struct.pack('ii', self.outbound_sequence_num, is_ack)

        # Break up the data into chunks of 1464 bytes and send it
        while len(data_bytes) > 1464:
            packet = header + data_bytes[0:1464]

            self.socket.sendto(packet, (self.dst_ip, self.dst_port))
            data_bytes = data_bytes[1464:]
            self.outbound_sequence_num = self.outbound_sequence_num + 1

            self.ack = False

            # Waiting to receive an ACK for the sent data before the send is "completed"
            while not self.ack:
                time.sleep(0.01)

        # Sending the last packet of data of len <= 1464 bytes
        packet = header + data_bytes
        self.socket.sendto(packet, (self.dst_ip, self.dst_port))
        self.ack = False

        # Waiting to receive an ACK for the sent data before the send is "completed"
        while not self.ack:
            time.sleep(0.01)
                
    def recv(self) -> bytes:
        while True:      
            if self.outbound_sequence_num in list(self.recv_buff):
                data_bytes = self.recv_buff[self.outbound_sequence_num]
                self.recv_buff.pop(self.outbound_sequence_num)
                return data_bytes

    def close(self) -> None:
        # your code goes here, especially after you add ACKs and retransmissions.
        self.closed = True
        self.socket.stoprecv()