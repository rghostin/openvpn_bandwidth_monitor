#!/usr/bin/python3
"""
Script to log bandwidth usage for users on an Openvpn servers infrastructure.

Note:
Server's configuration file must have the following options:
status <STATUSFILE> <PERIOD>
status-version 2
"""

from time import sleep
from requests import post
import threading

# settings
API_KEY = 'Ex4mpl3_K3y'
API_ENDPOINT = 'https://example.com/API/bw_update.php'
TCP_STATUSFILE = '/etc/openvpn/openvpn-status-tcp.log'
UDP_STATUSFILE = '/etc/openvpn/openvpn-status-udp.log'
PERIOD = 10         # period of updates


class User:
    def __init__(self, username=None, b_recv=None, b_sent=None):
        self.username = username
        self.bytes_received = b_recv
        self.bytes_sent = b_sent


class BWGuard:
    def __init__(self, statusfile, t=PERIOD):
        self.statusfile = statusfile
        self.t = t
        self.old_users = {}
        self.curr_users = {}
    
    """
    # lazy file reading using a generator
    
    def client_entry_generator(self, fileobj):
        # generator that yields client entries of statuslog file
        while True:
			line = fileobj.readline()
			if not line:
				return
			if line.startswith('CLIENT_LIST'):
				yield line.strip()
        

	def fetch_curr_users(self):
			# Update the list of current connected users
			self.curr_users.clear()
			with open(self.statusfile, 'r') as f:
				for entry in client_entry_generator(f):
					entry_list = entry.split(',')
					username = entry_list[9]
					user = User(username=username, b_recv=int(entry_list[5]), b_sent=int(entry_list[6]))
					self.curr_users[username] = user
    """
    
    def _get_client_entries(self):
        """ Fetch entries of client list in log file """
        with open(self.statusfile, 'r') as f:
            lines = f.readlines()
        return [l.strip() for l in lines if l.startswith('CLIENT_LIST')]

    def fetch_curr_users(self):
        """ Update the list of current connected users """
        self.curr_users.clear()
        c_entries = self._get_client_entries()
        for entry in c_entries:
            entry_list = entry.split(',')
            username = entry_list[9]
            user = User(username=username, b_recv=int(entry_list[5]), b_sent=int(entry_list[6]))
            self.curr_users[username] = user

    def get_disconnected_usernames(self):
        """ Compute disconnected users"""
        return set(self.old_users.keys()) - set(self.curr_users.keys())

    @staticmethod
    def update_bw_for(user):
        """ Update bandwidth usage for user by calling the API """
        print("Updating %s with bandwidth %s + %s" % (user.username, user.bytes_received, user.bytes_sent))
        post_data = {'key': API_KEY, 'username': user.username, 'bw_out': user.bytes_sent, 'bw_in': user.bytes_received}
        r = post(API_ENDPOINT, data=post_data)
        if r.status_code != 200:
            print('[!] Cannot update bandwidth for user %s', user.username)

    def run(self):
        while True:
            self.fetch_curr_users()
            for dc_username in self.get_disconnected_usernames():
                print('DBG: disconnected - ', dc_username)
                user = self.old_users[dc_username]
                self.update_bw_for(user)

            # move curr_users to old_users
            self.old_users, self.curr_users = self.curr_users, self.old_users
            self.curr_users.clear()
            sleep(self.t)


if __name__ == "__main__":
    # Run in parallel for both TCP and UDP servers
    try:
        tcp_bwguard = BWGuard(TCP_STATUSFILE, t=10)
        udp_bwguard = BWGuard(UDP_STATUSFILE, t=10)
        udp_thread = threading.Thread(target=udp_bwguard.run)
        udp_thread.start()
        tcp_bwguard.run()
        udp_thread.join()
    except KeyboardInterrupt:
        print("[!] Bandwidth monitoring stopped")
