import time, argparse, json, uuid, socket

def gen_id(): return str(uuid.uuid4())

parser = argparse.ArgumentParser()
parser.add_argument("--topic", required=True)
parser.add_argument("--from-user", default="alice")
parser.add_argument("--to-user",   default="bob")
parser.add_argument("--skew-ms", type=int, default=0)      # simulate clock skew by adding milliseconds to timestamp
parser.add_argument("--broker-host", default="127.0.0.1")
parser.add_argument("--broker-port", type=int, default=7777)
args = parser.parse_args()

def now_ms():
    # Return current physical time in milliseconds, adjusted by skew-ms to simulate clock skew
    return int(time.time() * 1000) + args.skew_ms

def build_message(text: str):
    return {
        "id": gen_id(),
        "from": args.from_user,
        "to": args.to_user,
        "text": text,
        "ts": now_ms(),                 # physical time in ms, skewed if specified
        "topic": args.topic
    }

def send_pub(msg: dict):
    wire = f"PUB {json.dumps(msg)}\n".encode()
    with socket.create_connection((args.broker_host, args.broker_port)) as s:
        s.sendall(wire)
        _ = s.recv(4096)  # OK

if __name__ == "__main__":
    print("Type messages. Ctrl+C to exit.")
    try:
        while True:
            text = input("> ").strip()
            if text:
                send_pub(build_message(text))
    except KeyboardInterrupt:
        pass