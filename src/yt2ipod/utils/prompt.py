def ask_ip(prompt_message: str = "Enter the IP address of the iPod: ") -> str:
    """Prompt the user for an IP address and return it.

    Basic validation ensures the input looks like an IPv4 address.
    """
    while True:
        ip = input(prompt_message).strip()
        parts = ip.split('.')
        if len(parts) == 4 and all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
            return ip
        print("Invalid IP address format. Please enter a valid IPv4 address (e.g., 192.168.1.10).")
