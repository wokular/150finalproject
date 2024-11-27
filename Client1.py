import re
import socket
import sys
import argparse

# Constants
CLIENT_MAX_CONNECTIONS = 5
CLIENT_BUF_SIZE = 4096


class MessageType:
    REGISTER = "REGISTER"
    BRIDGE = "BRIDGE"
    CHAT = "CHAT"
    QUIT = "QUIT"
    REGACK = "REGACK"
    BRIDGEACK = "BRIDGEACK"

class ChatMessage:
    def __init__(self, message_type, headers):
        # Sanity checks
        assert isinstance(message_type, str)
        assert isinstance(headers, dict)

        self.message_type = message_type
        self.headers = headers

    def send(self, ip, port):
        sockt = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sockt.connect((ip, port))

        sockt.send(str(self).encode())
        raw_pkt = sockt.recv(CLIENT_BUF_SIZE)
        ack_pkt = ChatMessage.from_bytes(raw_pkt)

        sockt.close()
        return ack_pkt


    def __str__(self):
        headers = '\r\n'.join([k + ': ' + str(v) for k, v in self.headers.items()])
        return self.message_type + '\r\n' + headers + '\r\n\r\n'

    @classmethod
    def from_bytes(cls, raw_pkt):
        request = raw_pkt.decode()
        lines = request.split('\r\n')
        message_type = None

        for mt in dir(MessageType):
            if mt.startswith('__'):
                continue

            if mt == lines[0]:
                message_type = mt
                break

        if message_type is None:
            return None

        headers = {}
        for line in lines[1:-1]:
            if len(line) < 4:
                continue

            sections = line.split(': ')
            if len(sections) != 2:
                print(f"Parsing error for header line: {line}")
                continue

            headers[sections[0]] = sections[1]

        return cls(message_type, headers)

class ClientState:
    INIT = "INIT"
    REGISTERED = "REGISTERED"
    WAITING = "WAITING"
    CHATTING = "CHATTING"

    # I don't think quit will ever be used, but including it for consistency.
    QUIT = "QUIT"

class Client:
    def __init__(self, name, client_ip, client_port, server_ip, server_port):
        self.name = name
        self.client_ip = client_ip
        self.client_port = client_port
        self.server_ip = server_ip
        self.server_port = server_port

        # Socket programming stuff. Bind to client ip and port.
        sockt = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sockt.bind((self.client_ip, self.client_port))
        print(f"{self.name} running on {self.client_ip}:{self.client_port}")
        self.client_socket = sockt

        self.state = ClientState.INIT


    def handle_command(self, line):
        if line.startswith("/id"):
            print(f">{self.name}")
        elif line.startswith("/register"):
            self.handle_register()
        elif line.startswith("/bridge"):
            self.handle_bridge()
        elif line.startswith("/chat"):
            self.handle_chat()
        elif line.startswith("/quit"):
            self.handle_quit()

    def handle_register(self):
        pkt = ChatMessage(MessageType.REGISTER, {
            "clientID": self.name,
            "IP": self.client_ip,
            "Port": self.client_port
        })

        ack_pkt = pkt.send(self.server_ip, self.server_port)
        print(ack_pkt)
        assert ack_pkt is not None and ack_pkt.message_type == MessageType.REGACK
        self.state = ClientState.REGISTERED

    def handle_bridge(self):
        pkt = ChatMessage(MessageType.BRIDGE, {
            "clientID": self.name
        })

        ack_pkt = pkt.send(self.server_ip, self.server_port)
        print(ack_pkt)
        assert ack_pkt is not None and ack_pkt.message_type == MessageType.BRIDGEACK
        
        
        # Part 2
        print(ack_pkt.headers)

        # If this is the first client to bridge, no other clients will exist
        if ack_pkt.headers["clientID"] == None or ack_pkt.headers["clientID"] == "None":
            assert self.client_socket is not None
            assert self.state is ClientState.REGISTERED

            self.state = ClientState.WAITING
            self.client_socket.listen(CLIENT_MAX_CONNECTIONS)

            # Event loop for client that is waiting for a message to chat
            while True:
                sockt, addr = self.client_socket.accept()
                raw_pkt = sockt.recv(CLIENT_BUF_SIZE)

        # This is not the first client to connect, let's go connect to the other existing client
        else:
           sockt = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
           sockt.connect((ack_pkt.headers["IP"], int(ack_pkt.headers["Port"])))

    def handle_chat(self):
        
        # TODO in part 2
        
        
        
        raise NotImplementedError

    def handle_quit(self):
        if self.state == ClientState.CHATTING:
            raise NotImplementedError
        else:
            self.client_socket.close()
            exit(0)



def parse_args():
    # Create parser
    parser = argparse.ArgumentParser(
        prog='cse150-chat',
        description='Client for the custom CSE150 chat protocol'
    )

    # Specify arguments and types.
    parser.add_argument('--id', required=True, type=str, help="Client ID (user's name, composed of only letters and numbers)")
    parser.add_argument('--port', required=True, type=int, help="Client port number (client will wait for incoming chat requests)")
    parser.add_argument('--server', required=True, type=str, help="Server's IP and port number (Colon separated. eg. 127.0.0.1:5555)")

    # Run argument parser
    args = parser.parse_args()

    # Further validation on arguments using re library
    if not re.fullmatch(r'([0-9]{1,3}\.){3}[0-9]{1,3}\:[0-9]{1,5}', args.server):
        print("Invalid server IP specified. Please use the format: <IP>:<PORT>")
        exit(1)

    return args

def main():
    args = parse_args()
    client = Client(
        args.id,
        "127.0.0.1",
        int(args.port),
        args.server.split(":")[0],
        int(args.server.split(":")[1])
    )

    while True:
        try:
            for line in sys.stdin:
                client.handle_command(line.strip())
        except KeyboardInterrupt:
            client.stop()

if __name__ == '__main__':
    main()