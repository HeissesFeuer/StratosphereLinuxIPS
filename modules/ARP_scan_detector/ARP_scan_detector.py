# Ths is a template module for you to copy and create your own slips module
# Instructions
# 1. Create a new folder on ./modules with the name of your template. Example:
#    mkdir modules/anomaly_detector
# 2. Copy this template file in that folder.
#    cp modules/template/template.py modules/anomaly_detector/anomaly_detector.py
# 3. Make it a module
#    touch modules/template/__init__.py
# 4. Change the name of the module, description and author in the variables
# 5. The file name of the python module (template.py) MUST be the same as the name of the folder (template)
# 6. The variable 'name' MUST have the public name of this module. This is used to ignore the module
# 7. The name of the class MUST be 'Module', do not change it.

# Must imports
from slips_files.common.abstracts import Module
import multiprocessing
from slips_files.core.database import __database__
import configparser

# Your imports
import json
import sys
import datetime
import ipaddress

class Module(Module, multiprocessing.Process):
    # Name: short name of the module. Do not use spaces
    name = 'ARPScanDetector'
    description = 'Detect ARP scans'
    authors = ['Alya Gomaa']

    def __init__(self, outputqueue, config):
        multiprocessing.Process.__init__(self)
        # All the printing output should be sent to the outputqueue.
        # The outputqueue is connected to another process called OutputProcess
        self.outputqueue = outputqueue
        # In case you need to read the slips.conf configuration file for
        # your own configurations
        self.config = config
        # Start the DB
        __database__.start(self.config)
        self.pubsub = __database__.r.pubsub()
        self.pubsub.subscribe('new_arp')
        self.pubsub.subscribe('tw_closed')
        self.timeout = None
        self.read_configuration()
        # this dict will categorize arp requests by profileid_twid
        self.cache_arp_requests = {}

    def print(self, text, verbose=1, debug=0):
        """
        Function to use to print text using the outputqueue of slips.
        Slips then decides how, when and where to print this text by taking all the processes into account
        :param verbose:
            0 - don't print
            1 - basic operation/proof of work
            2 - log I/O operations and filenames
            3 - log database/profile/timewindow changes
        :param debug:
            0 - don't print
            1 - print exceptions
            2 - unsupported and unhandled types (cases that may cause errors)
            3 - red warnings that needs examination - developer warnings
        :param text: text to print. Can include format like 'Test {}'.format('here')
        """

        levels = f'{verbose}{debug}'
        self.outputqueue.put(f"{levels}|{self.name}|{text}")

    def read_configuration(self):
        self.home_network = []
        try:
            self.home_network.append(self.config.get('parameters', 'home_network'))
        except (configparser.NoOptionError, configparser.NoSectionError, NameError):
            # There is a conf, but there is no option, or no section or no configuration file specified
            self.home_network = ['192.168.0.0/16', '172.16.0.0/12', '10.0.0.0/8']
        # convert the ranges into network obj
        self.home_network = list(map(ipaddress.ip_network,self.home_network))


    def check_arp_scan(self, profileid, twid, daddr, uid, ts, dst_mac, src_mac):
        """
        Check if the profile is doing an ARP scan
        If IP X sends ARP requests to 3 or more different IPs within 30 seconds, then this IP X is doing ARP scan
        The key profileid_twid is used to group requests from the same saddr
        ARP flows don't have uids, the uids received are randomly generated by slips
        """

        try:
            # Get together all the ARP requests for each IP in this TW
            cached_requests = self.cache_arp_requests[f'{profileid}_{twid}']
            # Append the ARP request, and when it happened
            cached_requests.update({daddr: {'uid' : uid,
                                    'ts' : ts}})
        except KeyError:
            # create the key if it doesn't exist
            self.cache_arp_requests[f'{profileid}_{twid}'] = {daddr: {'uid' : uid,
                                                                'ts' : ts}}
            return True

        # get the keys of cache_arp_requests in a list
        profileids_twids = list(cached_requests.keys())
        # The minimum amount of ARP packets to send to be considered as scan is 3
        if len(profileids_twids) >=3:
            # check if these requests happened within 30 secs
            # get the first and the last request of the 10
            first_daddr = profileids_twids[0]
            last_daddr = profileids_twids[-1]
            starttime = cached_requests[first_daddr]['ts']
            endtime = cached_requests[last_daddr]['ts']
            # get the time of each one in seconds
            # todo do we need mac addresses?
            starttime = datetime.datetime.fromtimestamp(starttime)
            endtime = datetime.datetime.fromtimestamp(endtime)
            # get the difference between them in seconds
            self.diff = float(str(endtime - starttime).split(':')[-1])
            if self.diff <= 30.00:
                # we are sure this is an arp scan
                confidence = 0.8
                threat_level = 60
                description = f'performing an ARP scan. Threat level {threat_level}. Confidence {confidence}.'
                type_evidence = 'ARPScan'
                type_detection = 'ip' #srcip
                detection_info = profileid.split("_")[1]
                __database__.setEvidence(type_detection, detection_info, type_evidence,
                                     threat_level, confidence, description, ts, profileid=profileid, twid=twid, uid=uid)
                # after we set evidence, clear the dict so we can detect if it does another scan
                self.cache_arp_requests.pop(f'{profileid}_{twid}')
                return True
        return False

    def check_dstip_outside_localnet(self, profileid, twid, daddr, uid, saddr, ts):
        """ Function to setEvidence when daddr is outside the local network """

        if '0.0.0.0' in saddr or '0.0.0.0' in daddr:
            # this is the case of ARP probe, not an arp outside of local network, don't alert
            return False

        daddr_as_obj = ipaddress.IPv4Address(daddr)
        if daddr_as_obj.is_multicast or daddr_as_obj.is_link_local:
            # The ARP to ‘outside’ the network should not dettect multicast or link-local addresses.
            return False

        for network in self.home_network:
            if daddr_as_obj in network:
                # IP is in this local network, don't alert
                return False
        # to prevent ARP alerts from one IP to itself
        local_net = saddr.split('.')[0]
        if not daddr.startswith(local_net):
            # comes here if the IP isn't in any of the local networks
            confidence = 0.8
            threat_level = 50
            description = f'sending ARP packet to a destination address outside of local network: {daddr}'
            type_evidence = 'ARPScan'
            type_detection = 'ip' #srcip
            detection_info = profileid.split("_")[1]
            __database__.setEvidence(type_detection, detection_info, type_evidence,
                                 threat_level, confidence, description, ts, profileid=profileid, twid=twid, uid=uid)

    def detect_unsolicited_arp(self, profileid, twid, uid, ts, dst_mac, src_mac, dst_hw, src_hw):
        """ Unsolicited ARP is used to update the neighbours' ARP caches but can also be used in ARP spoofing """
        if dst_mac=="ff:ff:ff:ff:ff:ff" and dst_hw=="ff:ff:ff:ff:ff:ff" and src_mac != '00:00:00:00:00:00' and src_hw != '00:00:00:00:00:00':
            # We're sure this is unsolicited arp
            confidence = 0.8
            threat_level = 50
            description = f'detected sending unsolicited ARP'
            type_evidence = 'UnsolicitedARP'
            type_detection = 'ip' #srcip
            detection_info = profileid.split("_")[1]
            __database__.setEvidence(type_detection, detection_info, type_evidence,
                                 threat_level, confidence, description, ts, profileid=profileid, twid=twid, uid=uid)
            return True


    def detect_MITM_ARP_attack(self, profileid, twid, uid, saddr, ts, src_mac):
        """Detects when a MAC with IP A, is trying to tell others that now that MAC is also for IP B (ARP cache attack)"""

        # to test this add these 2 flows to arp.log
        # {"ts":1636305825.755132,"operation":"request","src_mac":"2e:a4:18:f8:3d:02","dst_mac":"ff:ff:ff:ff:ff:ff","orig_h":"172.20.7.40","resp_h":"172.20.7.40","orig_hw":"2e:a4:18:f8:3d:02","resp_hw":"00:00:00:00:00:00"}
        # {"ts":1636305825.755132,"operation":"request","src_mac":"2e:a4:18:f8:3d:02","dst_mac":"ff:ff:ff:ff:ff:ff","orig_h":"172.20.7.41","resp_h":"172.20.7.41","orig_hw":"2e:a4:18:f8:3d:02","resp_hw":"00:00:00:00:00:00"}

        #todo will we get FPs when an ip changes?
        # todo what if the ip of the attacker came to us first and we stored it in the db? the original IP of this src mac is now the IP of the attacker?

        # get the original IP of the src mac from the database
        original_IP = __database__.get_IP_of_MAC(src_mac)
        # is this IP trying to tell everyone that it's own mac is now used with another IP?
        if saddr != original_IP:
            # From our db we know that:
            # original_IP has src_MAC
            # now saddr has src_MAC and saddr isn't the same as original_IP
            # so this is either a MITM ARP attack or the IP address of this src_mac simply changed
            # todo how to find out which one is it??
            confidence = 0.2 # low confidence for now
            threat_level = 90
            description = f'performing MITM attack.'
            # self.print(f'{saddr} is claiming to have {src_mac}')
            type_evidence = 'MITM-ARP-attack'
            type_detection = 'ip' #srcip
            detection_info = profileid.split("_")[1]
            __database__.setEvidence(type_detection, detection_info, type_evidence,
                                 threat_level, confidence, description, ts, profileid=profileid, twid=twid, uid=uid)
            return True


    def run(self):
        # Main loop function
        while True:
            try:
                message = self.pubsub.get_message(timeout=None)
                if message and message['data'] == 'stop_process':
                    # Confirm that the module is done processing
                    __database__.publish('finished_modules', self.name)
                    return True

                if message and message['channel'] == 'new_arp' and type(message['data'])==str:
                    flow = json.loads(message['data'])
                    ts = flow['ts']
                    profileid = flow['profileid']
                    twid = flow['twid']
                    daddr = flow['daddr']
                    saddr = flow['saddr']
                    dst_mac = flow['dst_mac']
                    src_mac = flow['src_mac']
                    dst_hw = flow['dst_hw']
                    src_hw = flow['src_hw']
                    operation = flow['operation']
                    # arp flows don't have uids, the uids received are randomly generated by slips
                    uid = flow['uid']

                    # The Gratuitous ARP is sent as a broadcast, as a way for a node to announce or update its IP to MAC mapping to the entire network.
                    #  Gratuitous ARP shouldn't be marked as an arp scan
                    is_gratuitous = saddr==daddr and (dst_mac=="ff:ff:ff:ff:ff:ff" or dst_mac=="00:00:00:00:00:00" or dst_mac==src_mac)
                    if is_gratuitous:
                        # keep track of the mac address of each IP
                        MAC_info = __database__.get_mac_addr_from_profile(profileid)
                        # store the mac of this profile if we don't already have it in the db
                        if not MAC_info:
                            MAC_info = {'MAC':src_mac }
                            __database__.add_mac_addr_to_profile(profileid, MAC_info)

                        # for MITM arp attack, the arp has to be gratuitous
                        self.detect_MITM_ARP_attack(profileid, twid, uid, saddr, ts, src_mac)

                    if not is_gratuitous:
                        # not gratuitous, may be an ARP scan
                        self.check_arp_scan(profileid, twid, daddr, uid, ts, dst_mac, src_mac)

                    if 'request' in operation:
                        self.check_dstip_outside_localnet(profileid, twid, daddr, uid, saddr, ts)
                        self.detect_unsolicited_arp(profileid, twid, uid, ts, dst_mac, src_mac, dst_hw, src_hw)

                # if the tw is closed, remove all its entries from the cache dict
                if message and message['channel'] == 'tw_closed' and type(message['data'])==str:
                    profileid_tw = message['data']
                    # when a tw is closed, this means that it's too old so we don't check for arp scan in this time range anymore
                    # this copy is made to avoid dictionary changed size during iteration err
                    cache_copy = self.cache_arp_requests.copy()
                    for key in cache_copy:
                        if profileid_tw in key:
                            self.cache_arp_requests.pop(key)
                            # don't break, keep looking for more keys that belong to the same tw
            except KeyboardInterrupt:
                # On KeyboardInterrupt, slips.py sends a stop_process msg to all modules, so continue to receive it
                continue
            except Exception as inst:
                exception_line = sys.exc_info()[2].tb_lineno
                self.print(f'Problem on the run() line {exception_line}', 0, 1)
                self.print(str(type(inst)), 0, 1)
                self.print(str(inst.args), 0, 1)
                self.print(str(inst), 0, 1)
                return True
