import socket
import sys
import select
import threading
import argparse

SERVER_MAX_CONNECTIONS = 5
SERVER_BUF_SIZE = 4096

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
        
class Client:
    def __init__(self, client_id, client_ip, client_port):
        self.client_id = client_id
        self.client_ip = client_ip
        self.client_port = client_port
    
class Server:
    def __init__(self, server_port, server_ip):
        self.server_port = server_port
        self.server_ip = server_ip
        self.running = False
        self.registered_clients = {}
        
        sockt = socket.socket(socket.AF_INET, socket.SOCK_STREAM) 
        sockt.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sockt.bind((server_ip, server_port))
        # Set a max allowed connections
        sockt.listen(SERVER_MAX_CONNECTIONS)
        self.socket = sockt
        print(f"Server listening on {self.server_ip}:{self.server_port}")
        
        # Start the server's event loop (monitor for stdin/socket connections)
        self.start_event_loop()
        
    def start_event_loop(self):
        
        self.running = True
        
        try:
            while self.running:
                readable, _, _ = select.select([self.socket, sys.stdin], [], [], 0.1)
                for r in readable:
                    if r == self.socket:
                        # Handle new client connection
                        conn, addr = self.socket.accept()
                        print(f"Connection from {addr}")
                        threading.Thread(target=self.handle_connection, args=(conn, addr), daemon=True).start()
                    elif r == sys.stdin:
                        # Handle command-line input
                        command = sys.stdin.readline().strip()
                        if command == "/info":
                            self.handle_info()
                        else:
                            print("Unknown command. Available server commands: /info")
        except KeyboardInterrupt:
            print("Keyboard interrupt detected on main event loop, stopping server...")
            self.stop()
        except Exception as e:
            print(f"Error in event loop: {e}")
        finally:
            print("Event loop exiting.")
            
    def handle_connection(self, conn, addr):
        
        with conn:
            while True:
                # Receive some bytes from a client on the socket
                raw_pkt = conn.recv(SERVER_BUF_SIZE)
                if not raw_pkt: break
                # Convert the raw bytes to a ChatMessage object
                message = ChatMessage.from_bytes(raw_pkt)
                if not message:
                    break
                print(f"Received from {addr}:\n{message}")
                
                # Check the type of message received
                # Will not get a CHAT type, those must only be sent client to client
                if (message.message_type == MessageType.REGISTER):
                    self.handle_register(conn, message)
                    return
                elif (message.message_type == MessageType.BRIDGE):
                    self.handle_bridge(conn, message)
                    return
                else:
                    print(f"Error: message type should not be sent to server")
                    return
    
    def stop(self):
        print("Should stop server")
        if self.running:
            # Break accept() function and close socket
            try:
                self.socket.close()
            except Exception as e:
                print(f"Error closing socket: {e}")
            self.running = False
            self.socket.close()
            
    def handle_register(self, conn, msg):
        # Create a new client object
        new_client = Client(msg.headers["clientID"], msg.headers["IP"], msg.headers["Port"])
        # Add that client to server's list of registered clients
        self.registered_clients[msg.headers["clientID"]] = new_client
        
        # Send an ACK
        pkt = ChatMessage(MessageType.REGACK, {
            "clientID": msg.headers["clientID"],
            "IP": msg.headers["IP"],
            "Port": msg.headers["Port"],
            "Status": "registered",
        })
        
        print(f"REGISTER: {new_client.client_id} from {new_client.client_ip}:{new_client.client_port} received")
        
        # Send the ack
        conn.send(str(pkt).encode())
        # Client will close the connection
        return
    
    def handle_bridge(self, conn, msg):
        this_client_id = msg.headers["clientID"]
        bridging_client = None
        peer_client = None
        # Add all non-requesting registered clients to an array to be sent back
        for index, client in enumerate(self.registered_clients):
            client = self.registered_clients[client]
            if client.client_id == this_client_id:
                bridging_client = client
            else:
                peer_client = client
                
                
        headers = {
            "clientID": None,
            "IP": None,
            "Port": None,
        }
        if peer_client is not None:
            print(f"BRIDGE: {bridging_client.client_id} {bridging_client.client_ip}:{bridging_client.client_port} {peer_client.client_id} {peer_client.client_ip}:{peer_client.client_port}")
            headers = {
                "clientID": peer_client.client_id,
                "IP": peer_client.client_ip,
                "Port": peer_client.client_port,
            }
        else:
            print(f"BRIDGE: {bridging_client.client_id} {bridging_client.client_ip}:{bridging_client.client_port}")
            
        
        # Send an ACK with the appropriate headers
        
        pkt = ChatMessage(MessageType.BRIDGEACK, headers)
        
        # Send the ack with corresponding info
        conn.send(str(pkt).encode())
        # Client will close the connection
        return
            
    def handle_info(self):
        
        # Print every client that is registered
        for index, client in enumerate(self.registered_clients):
            client = self.registered_clients[client]
            print(f"{client.id} {client.client_ip}:{client.client_port}")
    
        return
            
    def handle_commands(self):
        while self.running:
            if not self.running: break
            try:
                # Check for user input on stdin, wait for user input
                ready, _, _ = select.select([sys.stdin], [], [], 0.1)
                if ready:
                    command = sys.stdin.readline().strip()
                    if command == "/info":
                        self.handle_info()
                    else:
                        print("Unknown command. Available commands: /info")
            except KeyboardInterrupt:
                print("Keyboard interrupt detected on CLI input, stopping server...")
                self.stop()
                break
            except Exception as e:
                print(f"Error on server input: {e}")
                break


def parse_args():
    # Create parser
    parser = argparse.ArgumentParser(
        prog='cse150-chat',
        description='Server for the custom CSE150 chat protocol'
    )

    # Specify arguments and types.
    parser.add_argument('--port', required=True, type=int, help="Server port number (server will handle connections on this port)")

    # Run argument parser
    args = parser.parse_args()

    # Further validation on arguments using re library
    if (args.port > 65535) or (args.port < 1):
        print("Invalid server port specified. Please provide a valid port between 1 and 65535")
        exit(1)

    return args

def main():
    args = parse_args()
    server = Server(
        args.port,
        "127.0.0.1"
    )

    try:
        # Handle CLI input from user on server
        server.handle_commands()
    except KeyboardInterrupt:
        print("\nKeyboard interrupt detected on CLI input, stop the server...")
        server.stop()

if __name__ == '__main__':
    main()