import socket
import sys

def parse_tsl_v5_tcp(data):
    """
    Parses a TSL 5.0 TCP packet, accounting for the required FE 02 wrapper.
    """
    if len(data) < 2:
        print(f"Packet too short to evaluate wrapper ({len(data)} bytes).")
        return

    # Check for the DLE (0xFE) and STX (0x02) TCP wrapper bytes
    has_wrapper = (data[0] == 0xFE and data[1] == 0x02)
    
    if has_wrapper:
        print("\n--- [ Valid TSL v5.0 TCP Wrapper Detected (FE 02) ] ---")
        payload = data[2:]
    else:
        print("\n--- [ Warning: Missing TSL v5.0 TCP Wrapper (FE 02) ] ---")
        payload = data

    if len(payload) < 12:
        print(f"Payload too short to parse as TSL 5.0 ({len(payload)} bytes).")
        return

    # Extract TSL 5.0 headers (Little Endian parsing)
    msg_length = int.from_bytes(payload[0:2], byteorder='little')
    version = payload[2]
    flags = payload[3]
    screen_index = int.from_bytes(payload[4:6], byteorder='little')
    display_index = int.from_bytes(payload[6:8], byteorder='little')
    control_data = int.from_bytes(payload[8:10], byteorder='little')
    text_length = int.from_bytes(payload[10:12], byteorder='little')

    print(f"Message Length (PBC) : {msg_length} bytes")
    print(f"Protocol Version     : {version}")
    print(f"Flags                : {flags}")
    print(f"Screen Index         : {screen_index}")
    print(f"Display Index (Addr) : {display_index}")
    
    # Decode tally bits out of the Control Data byte (Byte 8)
    # Bit 0-1 = Tally 1 (Right/Red), Bit 2-3 = Tally 2 (Text/Green), Bit 4-5 = Tally 3 (Left/Blue)
    tally_byte = payload[8]
    tally1 = tally_byte & 0x03
    tally2 = (tally_byte >> 2) & 0x03
    tally3 = (tally_byte >> 4) & 0x03

    def get_status_str(val):
        if val == 1: return "RED (Program)"
        if val == 2: return "GREEN (Preview)"
        if val == 3: return "AMBER/YELLOW"
        return "OFF"

    print(f"Control Data (Hex)   : {payload[8:10].hex().upper()}")
    print(f"  └─ Right Tally     : {get_status_str(tally1)}")
    print(f"  └─ Text Tally      : {get_status_str(tally2)}")
    print(f"  └─ Left Tally      : {get_status_str(tally3)}")
    print(f"Text Length          : {text_length} bytes")

    if text_length > 0 and len(payload) >= 12 + text_length:
        text_bytes = payload[12:12+text_length]
        try:
            text_str = text_bytes.decode('ascii', errors='ignore')
            print(f"Text Data            : \"{text_str}\"")
        except Exception:
            print(f"Text Data (Hex)      : {text_bytes.hex().upper()}")
    print("-" * 55)

def start_server():
    # Prompt user for inputs
    ip = input("Enter the IP address to bind to (e.g., 127.0.0.1 or 0.0.0.0): ").strip()
    port_str = input("Enter the Port number to listen on (e.g., 9000 or 65434): ").strip()
    
    try:
        port = int(port_str)
    except ValueError:
        print("Error: Port must be a valid number.")
        sys.exit(1)

    # Create a TCP socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    # Allow immediate reuse of the port after stopping the script
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server_socket.bind((ip, port))
        server_socket.listen(1)
        print(f"\n[SUCCESS] Server started! Listening for TSL TCP data on {ip}:{port}...")
        print("Press Ctrl+C to exit at any time.\n")
    except Exception as e:
        print(f"[ERROR] Failed to bind to {ip}:{port}. Reason: {e}")
        sys.exit(1)

    try:
        while True:
            # Wait for the client device to connect
            client_socket, client_address = server_socket.accept()
            print(f"\n[CONNECT] Incoming connection accepted from {client_address[0]}:{client_address[1]}")

            while True:
                # Receive the continuous stream data
                data = client_socket.recv(1024)
                if not data:
                    print(f"[DISCONNECT] Client {client_address[0]} closed the connection.")
                    break
                
                # Print the raw hex representation
                hex_string = " ".join(f"{b:02X}" for b in data)
                print(f"\n[RAW DATA RECEIVED] ({len(data)} bytes):")
                print(hex_string)
                
                # Parse the packet contents
                parse_tsl_v5_tcp(data)

    except KeyboardInterrupt:
        print("\n[STOPPING] Server shutting down gracefully.")
    finally:
        server_socket.close()

if __name__ == "__main__":
    start_server()