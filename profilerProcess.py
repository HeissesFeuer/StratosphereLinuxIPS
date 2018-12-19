import multiprocessing
import json
from datetime import datetime
from datetime import timedelta
import sys
from collections import OrderedDict
import configparser
from slips.core.database import __database__
import time
import ipaddress

# Profiler Process
class ProfilerProcess(multiprocessing.Process):
    """ A class to create the profiles for IPs and the rest of data """
    def __init__(self, inputqueue, outputqueue, config, width):
        multiprocessing.Process.__init__(self)
        self.inputqueue = inputqueue
        self.outputqueue = outputqueue
        self.config = config
        self.width = width
        self.columns_defined = False
        self.timeformat = ''
        # Read the configuration
        self.read_configuration()

    def read_configuration(self):
        """ Read the configuration file for what we need """
        # Get the home net if we have one from the config
        try:
            self.home_net = ipaddress.ip_network(self.config.get('parameters', 'home_network'))
        except (configparser.NoOptionError, configparser.NoSectionError, NameError):
            # There is a conf, but there is no option, or no section or no configuration file specified
            self.home_net = False
        # Get the time window width, if it was not specified as a parameter 
        if self.width == None:
            try:
                self.width = int(config.get('parameters', 'time_window_width'))
            except configparser.NoOptionError:
                self.width = 60
            except (configparser.NoOptionError, configparser.NoSectionError, NameError):
                # There is a conf, but there is no option, or no section or no configuration file specified
                pass
        # Limit any width to be > 0
        elif self.width < 0:
            self.width = 60

        # Get the format of the time in the flows
        try:
            self.timeformat = config.get('timestamp', 'format')
        except (configparser.NoOptionError, configparser.NoSectionError, NameError):
            # There is a conf, but there is no option, or no section or no configuration file specified
            self.timeformat = '%Y/%m/%d %H:%M:%S.%f'

    def process_columns(self, line):
        """
        Analyze the line and detect the format
        Valid formats are:
            - CSV, typically generated by the ra tool of Argus
                - In the case of CSV, recognize commas or TABS as field separators
            - JSON, typically generated by Suricata
        The function returns True when the colums are alredy defined, which means you can continue analyzing the data. A return of False means the columns were not defined, but we defined now.
        A return of -2 means an error
        """
        self.column_values = {}
        self.column_values['starttime'] = False
        self.column_values['endtime'] = False
        self.column_values['dur'] = False
        self.column_values['proto'] = False
        self.column_values['appproto'] = False
        self.column_values['saddr'] = False
        self.column_values['sport'] = False
        self.column_values['dir'] = False
        self.column_values['daddr'] = False
        self.column_values['dport'] = False
        self.column_values['state'] = False
        self.column_values['pkts'] = False
        self.column_values['spkts'] = False
        self.column_values['dpkts'] = False
        self.column_values['bytes'] = False
        self.column_values['sbytes'] = False
        self.column_values['dbytes'] = False

        # If the columns are already defined, just get the correct values fast using indexes. If not, find the columns
        if self.columns_defined:
            # Read the lines fast
            nline = line.strip().split(self.separator)
            try:
                self.column_values['starttime'] = datetime.strptime(nline[self.column_idx['starttime']], self.timeformat)
            except IndexError:
                pass
            try:
                self.column_values['endtime'] = nline[self.column_idx['endtime']]
            except IndexError:
                pass
            try:
                self.column_values['dur'] = nline[self.column_idx['dur']]
            except IndexError:
                pass
            try:
                self.column_values['proto'] = nline[self.column_idx['proto']]
            except IndexError:
                pass
            try:
                self.column_values['appproto'] = nline[self.column_idx['appproto']]
            except IndexError:
                pass
            try:
                self.column_values['saddr'] = nline[self.column_idx['saddr']]
            except IndexError:
                pass
            try:
                self.column_values['sport'] = nline[self.column_idx['sport']]
            except IndexError:
                pass
            try:
                self.column_values['dir'] = nline[self.column_idx['dir']]
            except IndexError:
                pass
            try:
                self.column_values['daddr'] = nline[self.column_idx['daddr']]
            except IndexError:
                pass
            try:
                self.column_values['dport'] = nline[self.column_idx['dport']]
            except IndexError:
                pass
            try:
                self.column_values['state'] = nline[self.column_idx['state']]
            except IndexError:
                pass
            try:
                self.column_values['pkts'] = nline[self.column_idx['pkts']]
            except IndexError:
                pass
            try:
                self.column_values['spkts'] = nline[self.column_idx['spkts']]
            except IndexError:
                pass
            try:
                self.column_values['dpkts'] = nline[self.column_idx['dpkts']]
            except IndexError:
                pass
            try:
                self.column_values['bytes'] = nline[self.column_idx['bytes']]
            except IndexError:
                pass
            try:
                self.column_values['sbytes'] = nline[self.column_idx['sbytes']]
            except IndexError:
                pass
            try:
                self.column_values['dbytes'] = nline[self.column_idx['dbytes']]
            except IndexError:
                pass
        else:
            # Find the type of lines, and the columns indexes
            # These are the indexes for later
            self.column_idx = {}
            self.column_idx['starttime'] = False
            self.column_idx['endtime'] = False
            self.column_idx['dur'] = False
            self.column_idx['proto'] = False
            self.column_idx['appproto'] = False
            self.column_idx['saddr'] = False
            self.column_idx['sport'] = False
            self.column_idx['dir'] = False
            self.column_idx['daddr'] = False
            self.column_idx['dport'] = False
            self.column_idx['state'] = False
            self.column_idx['pkts'] = False
            self.column_idx['spkts'] = False
            self.column_idx['dpkts'] = False
            self.column_idx['bytes'] = False
            self.column_idx['sbytes'] = False
            self.column_idx['dbytes'] = False

            try:
                # Heuristic detection: can we read it as json?
                try:
                    data = json.loads(line)
                    data_type = 'json'
                except ValueError:
                    data_type = 'csv'

                if data_type == 'json':
                    # Only get the suricata flows, not all!
                    if data['event_type'] != 'flow':
                        return -2
                    # JSON
                    self.column_values['starttime'] = datetime.strptime(data['flow']['start'].split('+')[0], '%Y-%m-%dT%H:%M:%S.%f') # We do not process timezones now
                    self.column_values['endtime'] = datetime.strptime(data['flow']['end'].split('+')[0], '%Y-%m-%dT%H:%M:%S.%f')  # We do not process timezones now
                    difference = self.column_values['endtime'] - self.column_values['starttime']
                    self.column_values['dur'] = difference.total_seconds()
                    self.column_values['proto'] = data['proto']
                    try:
                        self.column_values['appproto'] = data['app_proto']
                    except KeyError:
                        pass
                    self.column_values['saddr'] = data['src_ip']
                    try:
                        self.column_values['sport'] = data['src_port']
                    except KeyError:
                        # Some protocols like icmp dont have ports
                        self.column_values['sport'] = '0'
                    # leave dir as default
                    self.column_values['daddr'] = data['dest_ip']
                    try:
                        self.column_values['dport'] = data['dest_port']
                    except KeyError:
                        # Some protocols like icmp dont have ports
                        column_values['dport'] = '0'
                    self.column_values['state'] = data['flow']['state']
                    self.column_values['pkts'] = int(data['flow']['pkts_toserver']) + int(data['flow']['pkts_toclient'])
                    self.column_values['spkts'] = int(data['flow']['pkts_toserver'])
                    self.column_values['dpkts'] = int(data['flow']['pkts_toclient'])
                    self.column_values['bytes'] = int(data['flow']['bytes_toserver']) + int(data['flow']['bytes_toclient'])
                    self.column_values['sbytes'] = int(data['flow']['bytes_toserver'])
                    self.column_values['dbytes'] = int(data['flow']['bytes_toclient'])
                elif data_type == 'csv':
                    # Are we using commas or tabs?. Just count them and choose as separator the char with more counts
                    nr_commas = len(line.split(','))
                    nr_tabs = len(line.split('	'))
                    if nr_commas > nr_tabs:
                        # Commas is the separator
                        self.separator = ','
                    elif nr_tabs > nr_commas:
                        # Tabs is the separator
                        self.separator = '	'
                    else:
                        self.outputqueue.put("10|profiler|Error. The file is not comma or tab separated.")
                        return -2
                    nline = line.strip().split(self.separator)
                    for field in nline:
                        if 'time' in field.lower():
                            self.column_idx['starttime'] = nline.index(field)
                        elif 'dur' in field.lower():
                            self.column_idx['dur'] = nline.index(field)
                        elif 'proto' in field.lower():
                            self.column_idx['proto'] = nline.index(field)
                        elif 'srca' in field.lower():
                            self.column_idx['saddr'] = nline.index(field)
                        elif 'sport' in field.lower():
                            self.column_idx['sport'] = nline.index(field)
                        elif 'dir' in field.lower():
                            self.column_idx['dir'] = nline.index(field)
                        elif 'dsta' in field.lower():
                            self.column_idx['daddr'] = nline.index(field)
                        elif 'dport' in field.lower():
                            self.column_idx['dport'] = nline.index(field)
                        elif 'state' in field.lower():
                            self.column_idx['state'] = nline.index(field)
                        elif 'totpkts' in field.lower():
                            self.column_idx['pkts'] = nline.index(field)
                        elif 'totbytes' in field.lower():
                            self.column_idx['bytes'] = nline.index(field)
                self.columns_defined = True
            except Exception as inst:
                self.outputqueue.put("10|profiler|\tProblem in process_columns() in profilerProcess.")
                self.outputqueue.put("10|profiler|"+str(type(inst)))
                self.outputqueue.put("10|profiler|"+str(inst.args))
                self.outputqueue.put("10|profiler|"+str(inst))
                sys.exit(1)
            # This is the return when the columns were not defined. False
            return False
        # This is the return when the columns were defined. True
        return True

    def add_flow_to_profile(self, columns):
        """ 
        This is the main function that takes a flow and does all the magic to convert it into a working data in our system. 
        It includes checking if the profile exists and how to put the flow correctly.
        """
        self.outputqueue.put('5|profiler|Received flow')
        # Get data
        saddr = columns['saddr']
        daddr = columns['daddr']
        profileid = 'profile|' + str(saddr)
        starttime = time.mktime(columns['starttime'].timetuple())
        # In the future evaluate
        try:
            saddr_as_obj = ipaddress.IPv4Address(saddr) 
            # Is ipv4
        except ipaddress.AddressValueError:
            # Is it ipv6?
            try:
                saddr_as_obj = ipaddress.IPv6Address(saddr) 
            except ipaddress.AddressValueError:
                # Its a mac
                return False

        if self.home_net and saddr_as_obj in self.home_net:
            # The steps for adding a flow in a profile should be
            # 1. Add the profile to the DB. If it already exists, nothing happens. So now profileid is the id of the profile to work with. 
            # The width is unique for all the timewindow in this profile
            __database__.addProfile(profileid, starttime, self.width)

            # 3. For this profile, find the id in the databse of the tw where the flow belongs.
            twid = self.get_timewindow(starttime, profileid)

            # 4. Put information from the flow in this tw for this profile
            # - DstIPs
            __database__.add_dstips(profileid, twid, daddr)
        elif self.home_net and saddr_as_obj not in self.home_net:
            # Here we should pick up the profile of the dstip, and add this as being 'received' by our saddr
            pass
        elif not self.home_net:
            # The steps for adding a flow in a profile should be
            # 1. Add the profile to the DB. If it already exists, nothing happens. So now profileid is the id of the profile to work with. 
            # The width is unique for all the timewindow in this profile
            __database__.addProfile(profileid, starttime, self.width)

            # 3. For this profile, find the id in the databse of the tw where the flow belongs.
            twid = self.get_timewindow(starttime, profileid)

            # 4. Put information from the flow in this tw for this profile
            # - DstIPs
            __database__.add_dstips(profileid, twid, daddr)

    def get_timewindow(self, flowtime, profileid):
        """" 
        This function should get the id of the TW in the database where the flow belong.
        If the TW is not there, we create as many tw as necessary in the future or past until we get the correct TW for this flow.
        - We use this function to avoid retrieving all the data from the DB for the complete profile. We use a separate table for the TW per profile.
        -- Returns the time window id
        """
        try:
            # First check of we are not in the last TW
            lasttw = __database__.getLastTWforProfile(profileid)
            if lasttw:
                # There was a last TW, so check if the current flow belongs here.
                twid = lasttw
                pass
            elif not lasttw:
                # There was no last TW. Create the first one
                startoftw = flowtime
                # Add this TW, of this profile, to the DB
                __database__.addNewTW(profileid, startoftw, self.width)
            # For now always use the lasttw, we need to put the logic here later

            """
            # We have the last TW
            self.outputqueue.put("12|profiler|" + 'Found a TW. {} -> {}'.format(lasttw.get_starttime(),lasttw.get_endtime()))
            if lasttw.get_endtime() >= flowtime and lasttw.get_starttime() < flowtime:
                self.outputqueue.put("11|profiler|The flow is on the last time windows")
                return lasttw
            elif flowtime > lasttw.get_endtime():
                # Then check if we are not a NEW tw
                self.outputqueue.put("11|profiler|We need to create a new TW")
                tw = TimeWindows(self.outputqueue, starttime, self.width)
                self.time_windows[tw.get_endtime()] = tw
                self.outputqueue.put("12|profiler|" + 'Create a TW. Starttime: {}, Endtime: {}'.format(lasttw.get_starttime(),lasttw.get_endtime()))
                self.outputqueue.put("1|profiler|" + 'TW. {} -> {}'.format(lasttw.get_starttime(),lasttw.get_endtime()))
                return tw
            """
            return twid
        except IndexError:
            print('Error in get_timewindow()')


    def run(self):
        # Main loop function
        try:
            while True:
                # If the input communication queue is empty, just wait
                if self.inputqueue.empty():
                    pass
                else:
                    # The input communication queue is not empty, we are receiving
                    line = self.inputqueue.get()
                    if 'stop' == line:
                        self.outputqueue.put("10|profiler|Stopping Profiler Process.")
                        return True
                    else:
                        # Received new input data
                        # Extract the columns smartly
                        if self.process_columns(line):
                            # Add the flow to the profile
                            self.add_flow_to_profile(self.column_values)
        except KeyboardInterrupt:
            return True
        except Exception as inst:
            self.outputqueue.put("10|profiler|\tProblem with Profiler Process.")
            self.outputqueue.put("10|profiler|"+str(type(inst)))
            self.outputqueue.put("10|profiler|"+str(inst.args))
            self.outputqueue.put("10|profiler|"+str(inst))
            sys.exit(1)


class IPProfile(object):
    """ A Class for managing the complete profile of an IP. Including the TimeWindows""" 
    def __init__(self, outputqueue, ip, width, timeformat):
        self.ip = ip
        self.width = width
        self.outputqueue = outputqueue
        self.timeformat = timeformat
        # Some features belong to the IP as a whole. Some features belong to an individual time window. 
        # Also the time windows can be of any length, including 'infinite' which means one time window in the complete capture.
        self.dst_ips = OrderedDict()
        self.dst_nets = OrderedDict()
        self.time_windows = OrderedDict()
        # Debug data
        self.outputqueue.put("1|profiler|" + 'A new Profile was created for the IP {}, with time window width {}'.format(self.ip, self.width))

    def add_flow(self, columns):
        """  
        This should be the first, and probably only, function to be called in this object
        Receive the columns of a flow and manage all the data and insertions 
        """
        # Extract the features that belong to the IP profile
        # Extract the features that belong to the current TW
        tw = self.get_timewindow(columns['starttime'])
        #tw.add_flow(columns)
        # Add the destination IP to this IP profile
        self.dst_ips[columns['daddr']] = ''

    def get_timewindow(self, flowtime):
        """" 
        This function should get or create the time windows need, accordingly to the current time of the flow
        Returns the time window object
        """
        #self.outputqueue.put("12|profiler|\n##########################")
        self.outputqueue.put("4|profiler|" + 'Current time of the flow: {}'.format(flowtime))
        # First check of we are not in the last TW
        try:
            lasttw = self.time_windows[list(self.time_windows.keys())[-1]]
            # We have the last TW
            self.outputqueue.put("12|profiler|" + 'Found a TW. {} -> {}'.format(lasttw.get_starttime(),lasttw.get_endtime()))
            if lasttw.get_endtime() >= flowtime and lasttw.get_starttime() < flowtime:
                self.outputqueue.put("11|profiler|The flow is on the last time windows")
                return lasttw
            elif flowtime > lasttw.get_endtime():
                # Then check if we are not a NEW tw
                self.outputqueue.put("11|profiler|We need to create a new TW")
                tw = TimeWindows(self.outputqueue, starttime, self.width)
                self.time_windows[tw.get_endtime()] = tw
                self.outputqueue.put("12|profiler|" + 'Create a TW. Starttime: {}, Endtime: {}'.format(lasttw.get_starttime(),lasttw.get_endtime()))
                self.outputqueue.put("1|profiler|" + 'TW. {} -> {}'.format(lasttw.get_starttime(),lasttw.get_endtime()))
                return tw
        except IndexError:
            # There are no TW yet. Create the first 
            self.outputqueue.put("12|profiler|\n-> There was no first TW. Creating one")
            ntw = TimeWindows(self.outputqueue, flowtime, self.width)
            self.outputqueue.put("12|profiler|\n-> Created")
            self.time_windows[ntw.get_endtime()] = ntw
            self.outputqueue.put("12|profiler|" + 'Create the first TW. Starttime: {}, Endtime: {}'.format(ntw.get_starttime(),ntw.get_endtime()))
            self.outputqueue.put("1|profiler|" + 'TW. {} -> {}'.format(ntw.get_starttime(),ntw.get_endtime()))
            return ntw

