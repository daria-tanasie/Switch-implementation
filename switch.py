#!/usr/bin/python3
import sys
import struct
import wrapper
import threading
import time
from wrapper import recv_from_any_link, send_to_link, get_switch_mac, get_interface_name
class BPDU:
    def __init__(self, root_bid, root_pc, bid, port_id):
        self.root_bid = root_bid
        self.root_pc = root_pc
        self.bid = bid
        self.port_id = port_id

def parse_ethernet_header(data):
    # Unpack the header fields from the byte array
    #dest_mac, src_mac, ethertype = struct.unpack('!6s6sH', data[:14])
    dest_mac = data[0:6]
    src_mac = data[6:12]
    
    # Extract ethertype. Under 802.1Q, this may be the bytes from the VLAN TAG
    ether_type = (data[12] << 8) + data[13]

    vlan_id = -1
    # Check for VLAN tag (0x8100 in network byte order is b'\x81\x00')
    if ether_type == 0x8200:
        vlan_tci = int.from_bytes(data[14:16], byteorder='big')
        vlan_id = vlan_tci & 0x0FFF  # extract the 12-bit VLAN ID
        ether_type = (data[16] << 8) + data[17]

    return dest_mac, src_mac, ether_type, vlan_id

def create_vlan_tag(vlan_id):
    # 0x8100 for the Ethertype for 802.1Q
    # vlan_id & 0x0FFF ensures that only the last 12 bits are used
    return struct.pack('!H', 0x8200) + struct.pack('!H', vlan_id & 0x0FFF)

def send_bdpu_every_sec(bpdu, interfaces):
    while True:
        # TODO Send BDPU every second if necessary
        if bpdu.root_bid == bpdu.bid:
            bpdu_packet = create_bpdu_packet(bpdu)
            for i in interfaces:
                if interfaces[i] == "T":
                    send_to_link(i, 29, bpdu_packet)
        time.sleep(1)

def is_unicast(mac):
    second_digit = int(mac[1], 16)
    if second_digit & 1 == 1:
        return False
    else:
        return True

def is_multicast(mac):
    if is_unicast(mac) is False:
        return True
    else:
        return False

def parse_bpdu_packet(data):    # parse the received packet
    root_bid = int.from_bytes(data[21:22], byteorder='big')
    root_pc = int.from_bytes(data[22:26], byteorder='big')
    bid = int.from_bytes(data[26:27], byteorder='big')
    port_id = int.from_bytes(data[27:29], byteorder='big')
    parsed_bpdu = BPDU(root_bid, root_pc, bid, port_id)

    return parsed_bpdu

def create_bpdu_packet(bpdu):   # create a BPDU packet to send
    dest = (0x0180c2000000).to_bytes(6, byteorder='big')
    src = get_switch_mac()

    llc_length = (38).to_bytes(2, byteorder='big')
    llc_header = (0x424203).to_bytes(3, byteorder='big')

    bpdu_header = (0).to_bytes(4, byteorder='big')
    root_bid = bpdu.root_bid.to_bytes(1, byteorder='big')
    root_pc = bpdu.root_pc.to_bytes(4, byteorder='big')
    bid = bpdu.bid.to_bytes(1, byteorder='big')
    port_id = bpdu.port_id.to_bytes(2, byteorder='big')

    created_packet = dest + src + llc_length + llc_header + bpdu_header + root_bid + root_pc + bid + port_id

    return created_packet

def main():
    # init returns the max interface number. Our interfaces
    # are 0, 1, 2, ..., init_ret value + 1
    switch_id = sys.argv[1]

    num_interfaces = wrapper.init(sys.argv[2:])
    interfaces = range(0, num_interfaces)

    line_nr = 0
    priority = 0
    switch_interfaces = {}
    switch_interfaces_state = []

    with open("configs/switch" + switch_id + ".cfg", "r") as f:
        Lines = f.readlines()
        for line in Lines:
            if line_nr == 0:
                priority = int(line.split("\n")[0])
            else:
                aux = line.split(" ")
                aux[1] = aux[1].split("\n")[0]
                if aux[1] != "T":
                    switch_interfaces[line_nr - 1] = int(aux[1])
                    switch_interfaces_state.append("X") # not trunk
                else:
                    switch_interfaces[line_nr - 1] = aux[1]
                    switch_interfaces_state.append("D") # designated
            line_nr += 1

    mac_table = {}
    bpdu = BPDU(priority, 0, priority, 100)

    t = threading.Thread(target=send_bdpu_every_sec, args=(bpdu, switch_interfaces))
    t.start()

    while True:
        # Note that data is of type bytes([...]).
        # b1 = bytes([72, 101, 108, 108, 111])  # "Hello"
        # b2 = bytes([32, 87, 111, 114, 108, 100])  # " World"
        # b3 = b1[0:2] + b[3:4].
        interface, data, length = recv_from_any_link()

        dest_mac, src_mac, ethertype, vlan_id = parse_ethernet_header(data)

        # Print the MAC src and MAC dst in human readable format
        dest_mac = ':'.join(f'{b:02x}' for b in dest_mac)
        src_mac = ':'.join(f'{b:02x}' for b in src_mac)

        # Note. Adding a VLAN tag can be as easy as
        # tagged_frame = data[0:12] + create_vlan_tag(10) + data[12:]

        mac_table[src_mac] = interface

        if switch_interfaces[interface] != "T": # if it comes from access port
            tagged_frame = data[0:12] + create_vlan_tag(switch_interfaces[interface]) + data[12:]
            length += 4
            data = 0
            data = tagged_frame
            vlan_id = switch_interfaces[interface]

        if is_unicast(dest_mac):
            if dest_mac in mac_table:
                if switch_interfaces_state[mac_table[dest_mac]] != "B": # if port not blocked
                    if switch_interfaces[mac_table[dest_mac]] == "T":
                        send_to_link(mac_table[dest_mac], length, data)
                    elif switch_interfaces[mac_table[dest_mac]] == vlan_id:
                            untagged_frame = data[0:12] + data[16:]
                            send_to_link(mac_table[dest_mac], length - 4, untagged_frame)

            else:
                for i in interfaces:
                    if i != interface and switch_interfaces_state[i] != "B": # if port not blocked
                        if switch_interfaces[i] == "T":
                            send_to_link(i, length, data)
                        elif switch_interfaces[i] == vlan_id:
                                untagged_frame = data[0:12] + data[16:]
                                send_to_link(i, length - 4, untagged_frame)

        elif is_multicast(dest_mac):
            if dest_mac == "01:80:c2:00:00:00":   # packet is bpdu
                received_bpdu = parse_bpdu_packet(data)

                if received_bpdu.root_bid < bpdu.root_bid:  # new root found 
                    if bpdu.bid == bpdu.root_bid:   # check if I was root
                        for k in interfaces:
                            if switch_interfaces[k] == "T" and k != interface:
                                switch_interfaces_state[k] = "B" #blocked

                    bpdu.root_bid = received_bpdu.root_bid
                    bpdu.root_pc = received_bpdu.root_pc + 10
                    bpdu.port_id = interface

                    if switch_interfaces[interface] == "T" and switch_interfaces_state[interface] == "B": #blocked
                        switch_interfaces_state[interface] = "L" #listening

                    for k in interfaces:
                            if switch_interfaces[k] == "T" and k != interface:
                                send_to_link(k, 29, create_bpdu_packet(bpdu))
                    
                elif received_bpdu.root_bid == bpdu.root_bid: # same root
                    if interface == bpdu.port_id and received_bpdu.root_pc + 10 < bpdu.root_pc:
                        bpdu.root_pc = received_bpdu.root_pc + 10

                    elif interface != bpdu.port_id:
                        if received_bpdu.root_pc > bpdu.root_pc:
                            if switch_interfaces_state[interface] != "D": # designated
                                switch_interfaces_state[interface] = "D"
                
                elif received_bpdu.bid == bpdu.bid: # same priority
                    switch_interfaces_state[interface] = "B" #blocked
                
                if bpdu.bid == bpdu.root_bid:
                    for k in switch_interfaces:
                        if switch_interfaces[k] == "T":
                            switch_interfaces_state[k] = "D" #designated

            else:   # packet is not bpdu
                for i in interfaces:
                    if i != interface and switch_interfaces_state[i] != "B": # if port not blocked
                        if switch_interfaces[i] == "T":
                            send_to_link(i, length, data)
                        else:
                            if switch_interfaces[i] == vlan_id:
                                untagged_frame = data[0:12] + data[16:]
                                send_to_link(i, length - 4, untagged_frame)

if __name__ == "__main__":
    main()
