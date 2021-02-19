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
        self.recv_seq_num = 0
        self.send_seq_num = 0

        self.closed = False
        self.ack = False
        self.recv_fin = False
        self.recv_finack = False
        
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        executor.submit(self.listener)

    def listener(self):
        while not self.closed:
            try:
                data, addr = self.socket.recvfrom()
                if len(data) == 0:
                    continue
                
                recv_packet_num = struct.unpack('i', data[0:4])[0]                
                is_ack = struct.unpack('i', data[4:8])[0]
                is_fin = struct.unpack('i', data[8:12])[0]
                data_bytes = data[12:]

                if len(data_bytes) > 0:
                    is_ack = 0
                    is_fin = 0

                if is_fin:
                    # Case1: A FINACK packet is received
                    if is_ack:
                        print('FINACK received.')
                        self.recv_finack = True

                    # Case2: A FIN packet is received - We FINACK the FIN
                    else:
                        print('FIN received.')
                        self.recv_fin = True

                        print('sending FINACK...')
                        self.send(b'', 1, 1)                        

                else:
                    # Case3: An ACK packet is received - We notify the main thread that an ACK was received
                    if is_ack == 1: 
                        print('ACK received for packet ', recv_packet_num)
                        self.ack = True

                    # Case4: The received packet is normal data that we must add to the recv buffer
                    else:
                        data_bytes = data[12:]

                        # Add the data to the receive buffer
                        self.recv_buff[recv_packet_num] = data_bytes

                        # Send ACK packet
                        print('ACK sent for packet ', self.recv_seq_num)
                        self.socket.sendto(struct.pack('iii', recv_packet_num, 1, 0), (self.dst_ip, self.dst_port))

            except Exception as e:
                print("listener died!")
                print(e)

    def send(self, data_bytes: bytes, is_ack=0, is_fin=0) -> None:
        if is_ack or is_fin:
            self.socket.sendto(struct.pack('iii', self.recv_seq_num, is_ack, is_fin), (self.dst_ip, self.dst_port))
            print('ack number: ', self.recv_seq_num)
            return

        # Break up the data into chunks of 1460 bytes and send it
        while len(data_bytes) > 1460:
            header = struct.pack('iii', self.send_seq_num, is_ack, is_fin)

            packet = header + data_bytes[0:1460]

            self.socket.sendto(packet, (self.dst_ip, self.dst_port))
            self.ack = False
            time.sleep(0.15)

            # Waiting to receive an ACK for the sent data before the send is "completed"
            while not self.ack:
                time.sleep(0.25)
                
                if not self.ack:
                    self.socket.sendto(packet, (self.dst_ip, self.dst_port))
                else:
                    break
                
            data_bytes = data_bytes[1460:]
            self.send_seq_num = self.send_seq_num + 1

        # Sending the last packet of data of len <= 1464 bytes
        header = struct.pack('iii', self.send_seq_num, is_ack, is_fin)
        packet = header + data_bytes
        self.socket.sendto(packet, (self.dst_ip, self.dst_port))
        self.send_seq_num = self.send_seq_num + 1
        self.ack = False

        time.sleep(0.25)

        # Waiting to receive an ACK for the sent data before the send is "completed"
        while not self.ack:
            time.sleep(0.25)

            if not self.ack:
                self.socket.sendto(packet, (self.dst_ip, self.dst_port))
            else:
                break
        
                
    def recv(self) -> bytes:
        while True:
            if self.recv_seq_num in self.recv_buff:
                data_bytes = self.recv_buff[self.recv_seq_num]
                self.recv_buff.pop(self.recv_seq_num)
                self.recv_seq_num = self.recv_seq_num + 1
                return data_bytes

    def close(self) -> None:
        print('sending FIN...')
        self.send(b'', 0, 1)

        while not self.recv_finack:
            time.sleep(0.1)

            if not self.recv_finack:
                self.send(b'', 0, 1)
            else:
                break

        while not self.recv_fin:
            print('waiting to receive a FIN...')
            time.sleep(0.1)        

        time.sleep(2)
        print('Closing...')
        self.closed = True
        self.socket.stoprecv()
        return