# do not import anything else from loss_socket besides LossyUDP
from lossy_socket import LossyUDP
# do not import anything else from socket except INADDR_ANY
from socket import INADDR_ANY
import struct


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
        self.curr_sequence_num = 0
        self.packet_num = 0

    def send(self, data_bytes: bytes) -> None:
        """Note that data_bytes can be larger than one packet."""
        byte_size = len(data_bytes)
        # print('data', data_bytes)
        # print('len', byte_size)
        if byte_size < 1468:
            # print('packet', struct.pack('i{}s'.format(byte_size), self.packet_num, data_bytes))
            self.socket.sendto(struct.pack('i{}s'.format(byte_size), self.packet_num, data_bytes), (self.dst_ip, self.dst_port))
            self.packet_num = self.packet_num + 1
        else:
            while len(data_bytes) > 1468:
                packet = struct.pack('i 1468s', self.packet_num, data_bytes[:1468])
                self.socket.sendto(packet, (self.dst_ip, self.dst_port))
                data_bytes = data_bytes[1468:]
                self.packet_num = self.packet_num + 1
            
            self.socket.sendto(struct.pack('i{}s'.format(len(data_bytes)), self.packet_num, data_bytes), (self.dst_ip, self.dst_port))
        
    def recv(self) -> bytes:
        """Blocks (waits) if no data is ready to be read from the connection."""
        while True:
            data, addr = self.socket.recvfrom()
            # print('packet_received', data)
            p_num, data_bytes = struct.unpack('i', data[:4]), data[4:]
            packet = struct.unpack('{}s'.format(len(data_bytes)), data_bytes)
            
            # print('data_bytes', packet)
            # print('p_num', p_num)

            # print('received packet', p_num)
            # print('current sequence num is', self.curr_sequence_num)

            if self.curr_sequence_num == p_num[0]:
                print('here1')
                self.curr_sequence_num = self.curr_sequence_num + 1
                return packet[0]
            
            self.recv_buff[p_num[0]] = packet[0]
            
            if self.curr_sequence_num in list(self.recv_buff):
                print('here2')
                key = self.curr_sequence_num
                self.curr_sequence_num = self.curr_sequence_num + 1
                return self.recv_buff[key]

    def close(self) -> None:
        """Cleans up. It should block (wait) until the Streamer is done with all
           the necessary ACKs and retransmissions"""
        # your code goes here, especially after you add ACKs and retransmissions.
        pass