import socket
import argparse

# Dict of clients
clients = {}

def handle_client(conn, addr):
    # While data can be received from the socket
    while True:
        try:
            # Get the message if it exists, and break otherwise
            data = conn.recv(1024).decode('utf-8').strip()
            if not data:
                break
            print(f"Received: {data} from {addr}")
            # Handle the message type
            if data.startswith("REGISTER"):
                handle_register(conn, data, addr)
            elif data.startswith("BRIDGE"):
                handle_bridge(conn, data)
        except Exception as e:
            print(f"Error: {e}")
            break
    conn.close()

# Handle client's /register message
def handle_register(conn, data, addr):
    _, client_id, ip, port = data.split()
    # Store the client's id with its ip and port information
    clients[client_id] = (ip, port)
    response = f"REGACK clientID:{client_id} IP:{ip} Port:{port} Status:registered\n"
    # Send an ACK back for the register message
    conn.send(response.encode())

# Handle client's /bridge message
def handle_bridge(conn, data):
    _, requester_id = data.split()
    response = "BRIDGEACK"
    for client_id, (ip, port) in clients.items():
        if client_id != requester_id:
            response += f" clientID:{client_id} IP:{ip} Port:{port}"
    conn.send((response + "\n").encode())

if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(prog="CSE 150 Final Project: Chat Server", description="Final project made by Alex Woelkers and Jaden Maxwell Provost Comfort")
    parser.add_argument("--port", type=int, required=True, help="Port to bind the server")
    # Parse the arguments provided
    args = parser.parse_args()
    # Create the server socket object (IPv4 and TCP based)
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM) 
    # Bind server to 10.0.0.1 and port provided
    server.bind(("10.0.0.1", args.port))
    # Set a listening backlog of 5 connections (5 new clients can wait, others will be rejected)
    server.listen(5)
    print(f"Server listening on 10.0.0.1:{args.port}")

    # Set up the main event loop
    while True:
        # Accept a connection, save it in conn and addr (connection info)
        conn, addr = server.accept()
        print(f"Connection from {addr}")
        handle_client(conn, addr) # Should thread this later
