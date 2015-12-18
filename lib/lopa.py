import time
import datetime
import re
import json
import dicttools
import platform
import socket
import copy
import sys
import pprint
from operator import itemgetter
from subprocess import Popen, PIPE

__author__ = 'Ralf'

# !/usr/bin/env python3

# constants
LOG_INTEND = 4
LOG_MAX_TEXT_LEN = 80
KEY_KEYS = 'keys'
CONFIG_FILE = './config/logparser.yml'
CONN_FILE = './config/connections.yml'
VAR_DELIMITER = '%'
#  placeholders
PH_DATE = '%dt%'
PH_DATE_NOW = '%dtNow%'
PH_BUSINESS_AREA = '%businessArea%'
PH_CONFIGFILE = '%configFile%'
PH_CUSTOMER_ID = '%customerId%'
PH_EVENT_STATUS = '%eventStatus%'
PH_EVENT_DATE = '%eventDate%'
PH_EVENT_MESSAGE = '%eventMessage%'
PH_ENVIRONMENT = '%environment%'
PH_PARSER_ID = '%parserId%'
PH_PARSER_REGEX = '%parserRegex%'
PH_SOURCEFILE = '%sourceFile%'
PH_SOURCE_LINE_NUM = '%sourceLineNum%'
PH_SOURCE_HOST = '%sourceHost%'
PH_SOURCE_HOST_SHORT = '%sourceHostShort%'
PH_SOURCE_SYSTEM = '%sourceSystem%'
PH_PYTHON_COMPILER = '%pythonCompiler%'
PH_PYTHON_VERSION = '%pythonVersion%'
PH_PYTHON_IMPLEMENTATION = '%pythonImplementation%'
PH_PYTHON_SCRIPT = '%pythonScript%'


class ClsChunk:
    """ This class is a container for chunk information
    in form of properties.

    It is initialized by a chunk of a file and creates
    properties of it.
    """

    def __init__(self, chunk):
        self.__chunk = chunk
        if self.__chunk:
            assert isinstance(self.__chunk, list)

    @property
    def list(self):
        if self.__chunk:
            return self.__chunk
        else:
            return None

    @property
    def length(self):
        if self.__chunk:
            return [('size', len(self.__chunk))]
        else:
            return None

    @property
    def line_start(self):
        if self.__chunk:
            return [('start', self.__chunk[0]['number'])]
        else:
            return None

    @property
    def line_end(self):
        if self.__chunk:
            return [('end', self.__chunk[-1]['number'])]
        else:
            return None

    @property
    def log_info(self):
        if self.__chunk:
            return [self.line_start[0], self.line_end[0], self.length[0]]
        else:
            return None


class ClsResList:
    """ This class is a container for result information
    in form of properties.

    It is initialized by a result list and creates
    properties of it.
    """

    def __init__(self, res_list):
        self.__r_list = res_list
        if self.__r_list:
            assert isinstance(self.__r_list, list)

    @property
    def list(self):
        return self.__r_list

    @property
    def length(self):
        return len(self.__r_list)

    @property
    def status_tuples(self):
        s_count = {}
        for r in self.__r_list:
            if r['status'] not in s_count:
                s_count[r['status']] = 1
            else:
                s_count[r['status']] += 1
        # sort keys for output
        s_list = []
        for k, v in s_count.items():
            s_list.append((k, v))
        s_list.sort()
        return s_list

    def filter(self, *, status_list=None) -> list:
        """
        This function filters the list of normalized combi items (events)
        for a given list of status

        :param status_list: Status list which events are filtered for
        :return: Filtered list of normalized combi items (events)
        """
        if status_list:
            return [r for r in self.__r_list if r['status'] in status_list]
        else:
            return self.__r_list


class ClsEnvTuples:
    """ This class is a container for environment information
    in form of tuples.
    """

    def __init__(self):
        self.__list = []
        if socket.gethostname().find('.') >= 0:
            self.__list.append((PH_SOURCE_HOST, socket.gethostname()))
            self.__list.append((PH_SOURCE_HOST_SHORT, socket.gethostname().split('.')[0]))
        else:
            self.__list.append((PH_SOURCE_HOST, socket.gethostbyaddr(socket.gethostname())[0]))
            self.__list.append((PH_SOURCE_HOST_SHORT, socket.gethostname()))
        self.__list.append((PH_SOURCE_SYSTEM, platform.system()))
        self.__list.append((PH_PYTHON_COMPILER, platform.python_compiler()))
        self.__list.append((PH_PYTHON_VERSION, platform.python_version()))
        self.__list.append((PH_PYTHON_IMPLEMENTATION, platform.python_implementation()))
        self.__list.append((PH_PYTHON_SCRIPT, sys.argv[0]))

    @property
    def list(self):
        return self.__list


class ClsParser:
    """ This class is a container for any parser instance.
     A parser is meant to do the parsing of
     a dedicated log object.
    """

    def __init__(self, dict_log, dict_parser, logger):
        # log
        self.__dict_log = dict_log
        self.__log_id = dict_log['id']
        self.__log_environment = dict_log['environment']
        self.__log_business_area = dict_log['businessArea']
        self.__log_name = dict_log['name']
        self.__log_type = dict_log['type']
        self.__log_pathname = dict_log['pathName']
        self.__log_filename = dict_log['fileName']
        self.__log_file_path = dict_log['pathName'] + '/' + dict_log['fileName']
        self.__log_file_lines_number = self.get_log_lines_number()
        self.__log_date_exists = dict_log['date']['exists']
        self.__log_date_format = dict_log['date']['format']
        self.__log_date_regex = dict_log['date']['regex']
        # parser
        self.__dict_parser = dict_parser
        self.__parser_id = dict_parser['id']
        self.__parser_text = dict_parser['text']
        # - chunk
        try:
            self.__parser_chunk_size = dict_parser['selection']['chunk']['size']
            if self.__parser_chunk_size > self.__log_file_lines_number:
                self.__parser_chunk_size = self.__log_file_lines_number
        except TypeError:
            self.__parser_chunk_size = 100000
        except AttributeError:
            self.__parser_chunk_size = 100000
        try:
            self.__parser_chunk_number = abs(dict_parser['selection']['chunk']['number'])
            if self.__parser_chunk_number * self.__parser_chunk_size > self.__log_file_lines_number:
                self.__parser_chunk_number = self.__log_file_lines_number // self.__parser_chunk_size
        except TypeError:
            self.__parser_chunk_number = 0  # 0 - all chunks
        except AttributeError:
            self.__parser_chunk_number = 0  # 0 - all chunks
        try:
            self.__parser_chunk_offset = dict_parser['selection']['chunk']['offset']
            isinstance(self.__parser_chunk_offset, int)
            if abs(self.__parser_chunk_offset * self.__parser_chunk_size) > self.__log_file_lines_number:
                if self.__parser_chunk_offset > 0:
                    self.__parser_chunk_offset = self.__log_file_lines_number // self.__parser_chunk_size
                else:
                    self.__parser_chunk_offset = -1 * (self.__log_file_lines_number // self.__parser_chunk_size)
            if self.__parser_chunk_offset < 0:
                if self.__parser_chunk_number > abs(self.__parser_chunk_offset):
                    self.__parser_chunk_number = abs(self.__parser_chunk_offset)
        except TypeError:
            self.__parser_chunk_offset = 0
        self.__parser_chunk_index = self.__parser_chunk_offset
        self.__parser_chunk_count = self.__parser_chunk_number
        self.__parser_mode_id = dict_parser['mode']['id']
        try:
            self.__parser_mode_keys_text = dict_parser['mode']['keys']['text']
            self.__parser_mode_keys_group = dict_parser['mode']['keys']['group']
        except KeyError:
            self.__parser_mode_keys_text = []
            self.__parser_mode_keys_group = 0
        self.__parser_regex_positive = dict_parser['regex']['positive'] == 'yes'
        self.__parser_regex = dict_parser['regex']['text']
        self.__parser_key_level = dicttools.count_key_level(dict_parser, KEY_KEYS)
        self.__parser_search_col = self.search_list()
        self.__parser_filter_time = dict_parser['selection']['time']['active'] == 'yes'
        self.__parser_filter_status = dict_parser['selection']['status']
        self.__parser_time_offset = self.get_time_offset()
        self.__parser_time_interval = self.get_time_interval()
        self.__parser_const_status_ok = self.__dict_parser['result']['constants']['status']['ok']
        self.__parser_const_status_error = self.__dict_parser['result']['constants']['status']['error']
        self.__parser_const_status_warning = self.__dict_parser['result']['constants']['status']['warning']
        self.__parser_dt_start = datetime.datetime.now() + datetime.timedelta(**self.__parser_time_offset)
        self.__parser_dt_end = self.__parser_dt_start + datetime.timedelta(**self.__parser_time_interval)
        if re.search(r'(-?\d*):(-?\d*):(\d*)', dict_parser['selection']['group']['slice']):
            self.__parser_group_slice = dict_parser['selection']['group']['slice']
        else:
            self.__parser_group_slice = '-1::'  # default - last element
        self.__parser_result_fields = dict_parser['result']['fields']
        self.env_tuples = ClsEnvTuples()
        self.__parser_result_file_path = dict_parser['out']['file']['pathName'] + '/' + \
            dict_parser['out']['file']['fileName']
        self.__parser_result_file_path = self.__parser_result_file_path.replace(PH_PARSER_ID, self.__parser_id)
        self.__parser_http_out_chunk_key = dict_parser['out']['http']['chunkKey']
        self.__parser_http_out_time_factor = dict_parser['out']['http']['timeFactor']

        # logger
        self.__logger = logger

    @property
    def result_file_path(self):
        return self.__parser_result_file_path

    @property
    def http_out_chunk_key(self):
        try:
            assert isinstance(self.__parser_http_out_chunk_key, str)
            return self.__parser_http_out_chunk_key
        except AssertionError:
            return None

    @property
    def http_out_time_factor(self):
        try:
            assert isinstance(self.__parser_http_out_time_factor, int)
            return self.__parser_http_out_time_factor
        except AssertionError:
            return None

    @property
    def log_date_exists(self):
        try:
            assert isinstance(self.__log_date_exists, str)
            return self.__log_date_exists
        except AssertionError:
            return None

    @property
    def log_file_path(self):
        try:
            assert isinstance(self.__log_file_path, str)
            return self.__log_file_path
        except ValueError:
            return None

    def get_log_lines_number(self):
        """
        Get the number of lines in log file.
        :return: The number of lines in log file.
        """
        line_counter = 0
        with open(self.log_file_path, 'r') as fh:
            for _ in fh:
                line_counter += 1
        return line_counter

    def get_chunk(self, n=0):
        """
        Get the next chunk from logfile or if given the n-th chunk.

        :param n: optional parameter for the n-th chunk to obtain
        :return: Dictionary containing the next or n-th chunk of logfile
                 - number: line number of logfile
                 - date: line date if existing
                 - text: line text

        """
        chunk = []
        line_counter = 0

        if n > 0:
            chunk_no = n - 1
        else:
            chunk_no = self.__parser_chunk_index
            self.__parser_chunk_index += 1
            # check number of requested chunks has already been reached
            if self.__parser_chunk_number == 0:
                return None
            else:
                self.__parser_chunk_number -= 1

        if chunk_no >= 0:
            chunk_line_start = (chunk_no * self.__parser_chunk_size) + 1
        else:
            chunk_line_start = self.__log_file_lines_number + (chunk_no * self.__parser_chunk_size) + 1
        chunk_line_end = chunk_line_start + self.__parser_chunk_size - 1

        with open(self.__log_file_path, 'r') as fh:
            for line in fh:
                line_counter += 1
                item = {}
                if line_counter in range(chunk_line_start, chunk_line_end + 1):
                    item['number'] = line_counter
                    item['date'] = self.get_datetime(line)
                    item['text'] = line
                    chunk.append(item)

        return chunk

    def filter_chunk(self, chunk, filter_type):
        """
        Filter a chunk of lines for defined criteria like date range of key words.

        :param chunk: chunk of lines from logfile
        :param filter_type: 'date' - filter for lines in datetime range
                            'keys' - filter for the keys
        :return: List containing the filtered lines
        """
        filtered_chunk = []
        take_item = False  # don't take items until the first item with a date is compliant
        if filter_type == 'date':
            if self.log_date_exists:
                for item in chunk:
                    if item['date']:
                        if self.in_time_range(item):
                            filtered_chunk.append(item)
                            take_item = True  # switch take_item ON to take subsequent items without date
                        elif take_item:
                            take_item = False  # switch take_item OFF to ignore subsequent items without date
                    elif take_item:
                        filtered_chunk.append(item)
        else:
            if filter_type == 'keys':
                for item in chunk:
                    if self.in_search_list(item['text']):
                        filtered_chunk.append(item)
        return filtered_chunk

    def has_dates(self):
        """
        Evaluates if log file lines contain datetime values
        :return: True if log file lines contain datetime values
                 return self.log_date_exists == 'yes'
        """
        return self.log_date_exists == 'yes'

    def get_datetime(self, line):
        """
        Extracts the datetime from a line string based
        on a regular expression search
        :param line: String containing a datetime
        :return: datetime or None
        """
        try:
            m = re.search(self.__log_date_regex, line)
            dt_string = m.group(0)
            dt = datetime.datetime.strptime(dt_string, self.__log_date_format)
            assert isinstance(dt, datetime.datetime)
            return dt
        except TypeError:
            return None
        except AttributeError:
            return None

    def get_time_offset(self):
        """
        Get the time offset for line selection.
        If nothing is specified, take a default of -99998 days

        :return: time offset as key value pair
        """
        time_offset = dict()

        try:
            datetime.timedelta(**self.__dict_parser['selection']['time']['offset'])
            time_offset = self.__dict_parser['selection']['time']['offset']
        except TypeError:
            time_offset['days'] = -99998
        return time_offset

    def get_time_interval(self):
        """
        Get the time interval for line selection.
        If nothing is specified, take take a default of 99999 days

        :return: time interval as key value pair
        """
        time_interval = dict()
        try:
            datetime.timedelta(**self.__dict_parser['selection']['time']['interval'])
            time_interval = self.__dict_parser['selection']['time']['interval']
        except TypeError:
            time_interval['days'] = 99999
        return time_interval

    def in_time_range(self, item):
        """
        Looks if item is within a time range defined by
        self.__parser_dt_start and self.__parser_dt_end

        :param item: Item is a dictionary representing one line of logfile
                     with some additional attributes.
        :return: true if extracted datetime is in time range,
                 otherwise false
        """
        if self.has_dates():
            try:
                return self.__parser_dt_start <= item['date'] <= self.__parser_dt_end
            except TypeError:
                return False
        else:
            return False

    def search_list(self):
        """
        Build a list of all search key combinations including the regex.
        The maximum level of nested keys is 4.

        :return: List with each item containing three lists
                 - in: list of search strings
                 - out: list of translated search strings
                 - regex: regular expression for search
        """
        combi_list = []

        def compose_result(in_lst, out_lst, rx, rx_dt):
            """
            This sub function composes the final search list.
            It's useful, as it can be called at different places
            depending on the level of nested keys in configuration.
            :param in_lst: list of search strings
            :param out_lst: list of translated search strings
            :param rx: regex pattern for line search
            :param rx_dt: regex pattern for date search
            :return: Dictionary item containing an
                     - in: list of search strings
                     - out: list of translated search strings
                     - regex: regular expression for search
            """
            result_item = {}

            rx = rx.replace(PH_DATE, rx_dt)
            for i in range(0, len(in_lst)):
                rx = rx.replace('%k' + str(i + 1) + '%', in_lst[i])

            result_item['in'] = in_lst
            result_item['out'] = out_lst
            result_item['regex'] = rx

            return result_item

        if KEY_KEYS in self.__dict_parser.keys():

            for k1 in self.__dict_parser[KEY_KEYS]:
                # re-initialize for every 1st level key
                in_list = []
                out_list = []
                in_list.append(k1['text'])
                out_list.append(k1['out'])
                if KEY_KEYS in k1.keys():
                    for k2 in k1[KEY_KEYS]:
                        # re-initialize with preserving above level information
                        in_list = in_list[:1]
                        out_list = out_list[:1]
                        in_list.append(k2['text'])
                        out_list.append(k2['out'])
                        if KEY_KEYS in k2.keys():
                            for k3 in k2[KEY_KEYS]:
                                # re-initialize with preserving above level information
                                in_list = in_list[:2]
                                out_list = out_list[:2]
                                in_list.append(k3['text'])
                                out_list.append(k3['out'])
                                if KEY_KEYS in k3.keys():
                                    for k4 in k3[KEY_KEYS]:
                                        # re-initialize with preserving above level information
                                        in_list = in_list[:3]
                                        out_list = out_list[:3]
                                        in_list.append(k4['text'])
                                        out_list.append(k4['out'])
                                        combi_list.append(compose_result(in_list, out_list, self.__parser_regex,
                                                                         self.__log_date_regex))
                                else:
                                    combi_list.append(
                                        compose_result(in_list, out_list, self.__parser_regex, self.__log_date_regex))
                        else:
                            combi_list.append(
                                compose_result(in_list, out_list, self.__parser_regex, self.__log_date_regex))
                else:
                    combi_list.append(compose_result(in_list, out_list, self.__parser_regex, self.__log_date_regex))

        return combi_list

    def in_search_list(self, line):
        """
        Check if line meets parser regex list.
        :param line: line of logfile
        :return: Return True if line meets parser regex list.
        """
        in_list = False
        for item in self.__parser_search_col:
            if re.search(item['regex'], line):
                in_list = True
                break
        return in_list

    def combi_list(self, chunk):
        """
        This function extends search list items with the found items.
        :param chunk: List of filtered items, each of which containing
                      - number: line number
                      - date: date of line
                      - text: text of line
        :return: List containing the search items together with the found items.
        """
        combi_list = []
        for search_item in self.__parser_search_col:
            found_list = []
            for found_item in chunk:
                if re.search(search_item['regex'], found_item['text']):
                    found_list.append(found_item)
            # post process found_list
            #  slice the list in order to get only defined items
            #  -1:None:None for only the last item
            found_list = self.sliced_list(found_list, self.__parser_group_slice)

            # add found_list to search_item
            search_item['found'] = found_list
            combi_list.append(search_item)

        return combi_list

    def combi_list_normalized(self, clist):
        """
        This function normalizes the combi list by transforming items with
        multiple found items into items with one result for one or more found items.
        Thus the normalized combi list will contain more items then the input combi list.

        The objective is to have items also in the case of searches not being successful,
        where the found list is empty. In any case there will be a status and a message.

        :param clist: List containing the search items together with the found items.
                      - regex: regular expression for search
                      - in: keys for search
                      - out: keys for output
                      - found: list of dicts
                          - number: line number
                          - date: date of line
                          - text: text of line
        :return: List containing the normalized combi list.
                      - regex: regular expression for search
                      - in: list of keys for search
                      - out: list of keys for output
                      - number: line number
                      - date: date of line
                      - status: event status (ok, error)
                      - text: found text
                      - message: event message
        """
        combi_list_normalized = []
        for citem in clist:
            if self.__parser_regex_positive:
                # regex search looks for positive events
                if citem['found']:
                    # positive events found
                    if self.__parser_mode_id == 1:
                        # single mode
                        for fitem in citem['found']:
                            cin = {}  # combi item normalized
                            for k in citem.keys():
                                if k == 'found':
                                    cin['number'] = fitem['number']
                                    cin['date'] = fitem['date']
                                    cin['status'] = self.__parser_const_status_ok
                                    cin['text'] = fitem['text']
                                    cin['message'] = fitem['text']
                                else:
                                    cin[k] = citem[k]
                            combi_list_normalized.append(cin)
                    else:
                        if self.__parser_mode_id == 2:
                            # multi mode - all found items shall result in in one item
                            cin = self.multi_item_normalized(citem, self.__parser_mode_keys_text,
                                                             self.__parser_mode_keys_group)
                            combi_list_normalized.append(cin)
                else:
                    # positive events not found
                    cin = {}  # combi item normalized
                    for k in citem.keys():
                        if k == 'found':
                            cin['number'] = None
                            cin['date'] = datetime.datetime.now()
                            cin['status'] = self.__parser_const_status_error
                            cin['text'] = None
                            cin['message'] = 'Not found: ' + citem['regex']
                        else:
                            cin[k] = citem[k]
                    combi_list_normalized.append(cin)
            else:
                # regex search looks for negative events
                if citem['found']:
                    # negative events found
                    if self.__parser_mode_id == 1:
                        # single mode
                        for fitem in citem['found']:
                            cin = {}  # combi item normalized
                            for k in citem.keys():
                                if k == 'found':
                                    cin['number'] = fitem['number']
                                    cin['date'] = fitem['date']
                                    cin['status'] = self.__parser_const_status_error
                                    cin['text'] = fitem['text']
                                    cin['message'] = fitem['text']
                                else:
                                    cin[k] = citem[k]
                            combi_list_normalized.append(cin)
                else:
                    # negative events not found
                    cin = {}  # combi item normalized
                    for k in citem.keys():
                        if k == 'found':
                            cin['number'] = None
                            cin['date'] = datetime.datetime.now()
                            cin['status'] = self.__parser_const_status_ok
                            cin['text'] = None
                            cin['message'] = 'Not found: ' + citem['regex']
                        else:
                            cin[k] = citem[k]
                    combi_list_normalized.append(cin)

        return combi_list_normalized

    def multi_item_normalized(self, citem, evtlist, rgroup):
        """
        This function normalizes one combi list item by evaluating multiple found items.
        The objective is to consolidate found items each representing a defined step of a
        multi step event (e.g. START, END) into one resulting normalized combi list item.

        In case that there is one step missing or the number of the steps does not match
        the status will become error.

        :param citem: One item of the combi list containing found items each representing
                      one step of a multi step event.
        :param evtlist: List of multiple keywords each representing one step of a
                        multiple step event.
        :param rgroup: The regex group where the key of the evtlist is contained.
        :return: One normalized combi list item
        """

        def step_counts_equal(scounter) -> bool:
            """
            Check if all step counts are equal
            :rtype : bool
            :param scounter: step counter
            :return: True if all step counts are equal
            """
            i = None
            for _, v in scounter:
                if not i:
                    i = v
                else:
                    if not i == v:
                        return False
            return True

        def steps_in_order(citm, elist, rgrp) -> bool:
            """
            Check if event steps are in order.
            :param citm: One item of the combi list containing found items each representing
                         one step of a multi step event.
            :param elist: List of multiple keywords each representing one step of a
                          multiple step event.
            :param rgrp: The regex group where the key of the evtlist is contained.
            :return: True if all events steps are in order
            """
            # check if there is an item 'date' in the found item list
            # if not, return steps_in_order=True
            if not citm['found'][0]['date']:
                return True

            # get a found item list sorted by data ascending
            c_item_found_sorted = sorted(citm['found'], key=itemgetter('date'))

            # slice last n items of found items
            # n is number of event steps
            slice_str = '-' + str(elist.__len__) + '::'
            c_item_found_sliced = self.sliced_list(c_item_found_sorted, slice_str)

            str_last_item_date = None
            assert isinstance(c_item_found_sliced, list)
            i = 0
            for f in c_item_found_sliced:
                if str_last_item_date:
                    if not f['date'] == str_last_item_date:
                        rs = re.search(citem['regex'], f['text'])
                        if not re.search(elist[i], rs.group(rgrp)):
                            return False
                else:
                    str_last_item_date = f['date']
                i += 1
            return True

        # count steps for every step type of the multi step event (e.g. START, END)
        step_counter = []  # list of event count tuples (event_key, count)
        for eitem in evtlist:
            count = 0
            for fitem in citem['found']:
                m = re.search(citem['regex'], fitem['text'])
                if re.search(eitem, m.group(rgroup)):
                    count += 1
            step_counter.append((eitem, count))

        # build normalized combi item
        cin = {}  # combi item normalized

        error_step_order = ''
        if step_counts_equal(step_counter):
            if steps_in_order(citem, evtlist, rgroup):
                status = self.__parser_const_status_ok
            else:
                status = self.__parser_const_status_error
                error_step_order = ' error: steps not in order!'
        else:
            status = self.__parser_const_status_error

        for k in citem.keys():
            if k == 'found':
                m = re.search(citem['regex'], citem[k][-1]['text'])
                cin['number'] = citem[k][-1]['number']
                if citem[k][-1]['date']:
                    cin['date'] = citem[k][-1]['date']
                else:
                    cin['date'] = datetime.datetime.now()
                cin['status'] = status
                cin['text'] = m.group(0)
                cin['message'] = m.group(0) + ' (step counter: ' + format(step_counter) + ', ' + error_step_order + ')'
            else:
                cin[k] = citem[k]

        return cin

    @staticmethod
    def sliced_list(org_list, slice_str):
        """ Reduce the number of list items by slice.

        :param org_list: List to be sliced
        :param slice_str: String telling how to slice
        :return: Sliced list
        """
        o_list = org_list
        m = re.search(r'(-?\d*):(-?\d*):(\d*)', slice_str)
        x, y, z = m.groups(None)

        try:
            x = int(x)
        except ValueError:
            x = None
        try:
            y = int(y)
        except ValueError:
            y = None
        try:
            z = int(z)
        except ValueError:
            z = None

        sliced_list = o_list[x:y:z]
        return sliced_list

    def result_tuples(self, citem):
        """ This function builds result tuples.
         The result tuples contain placeholders as keys
         and the respective values. They will be used for building the
         result dictionary by replacing placeholders by values.

         The background is, that the result dictionary may contain nested
         elements like another dictionary. The result tuple is a flat result set
         for collecting the results and serves as a kind of intermediate result.

         Example:
        ('%k1%', 'AZSE') - key is the placeholder '%k1%', value is 'AZSE'

        :param citem: Normalized combi item containing search and found items
        :return: tuples list containing the results
        """
        # time
        #  date
        date_now = datetime.datetime.now()
        if citem['date'] is None:
            event_date = datetime.datetime.now()
        else:
            event_date = citem['date']
        #  time factor
        try:
            time_factor = int(self.http_out_time_factor)
        except AttributeError:
            time_factor = 1

        # tuple list
        tuple_list_all = []
        tuple_list = [(PH_ENVIRONMENT, self.__log_environment), (PH_BUSINESS_AREA, self.__log_business_area),
                      (PH_PARSER_ID, self.__parser_id), (PH_PARSER_REGEX, citem['regex']),
                      (PH_SOURCEFILE, self.__log_file_path), (PH_SOURCE_LINE_NUM, str(citem['number'])),
                      (PH_CONFIGFILE, CONFIG_FILE), (PH_EVENT_STATUS, citem['status']),
                      (PH_DATE_NOW, int(time.mktime(date_now.timetuple()) * time_factor)),
                      (PH_EVENT_DATE, int(time.mktime(event_date.timetuple()) * time_factor)),
                      (PH_EVENT_MESSAGE, str(citem['message']))]
        # environment details
        for k, v in self.env_tuples.list:
            tuple_list.append((k, v))
        # out keys %k..%
        for i, o in enumerate(citem['out'], start=1):
            tuple_list.append(('%k' + str(i) + '%', o))
            # tuple_list.append(('%k' + str(i) + '.lower%', str(o).lower()))
        # regex groups %g..%
        if citem['text']:
            m = re.search(citem['regex'], citem['text'])
            for i, r in enumerate(m.groups(), start=1):
                if i > 0:
                    tuple_list.append(('%g' + str(i) + '%', r))
        else:
            for i in range(1, 10):
                tuple_list.append(('%g' + str(i) + '%', 'None'))

        for k, v in tuple_list:
            tuple_list_all.append((k, v))  # original tuple
            # lower and upper case tuples
            if isinstance(v, str):
                tuple_list_all.append((VAR_DELIMITER + k.strip(VAR_DELIMITER) + '.lower' + VAR_DELIMITER, v.lower()))
                tuple_list_all.append((VAR_DELIMITER + k.strip(VAR_DELIMITER) + '.upper' + VAR_DELIMITER, v.upper()))
            else:  # keep it unchanged
                tuple_list_all.append((VAR_DELIMITER + k.strip(VAR_DELIMITER) + '.lower' + VAR_DELIMITER, v))
                tuple_list_all.append((VAR_DELIMITER + k.strip(VAR_DELIMITER) + '.upper' + VAR_DELIMITER, v))

        return tuple_list_all

    @staticmethod
    def fill_placeholders(obj_dict, tuple_list):
        """
        Copy the dictionary obj_dict and replace placeholders with
        values from tuple_list
        :param obj_dict: Dictionary which serves as a pattern for the dictionary to return.
        :param tuple_list: Tuple list containing tuples of keys with names that equal the placeholder
                          names in obj_dict and values that shall replace the placeholders.
        :return: Dictionary with values instead of placeholders
        """
        resdict = copy.deepcopy(obj_dict)
        for key_map in dicttools.key_sequences(resdict):
            for k, v in tuple_list:
                dict_value_old = str(dicttools.get_from_dict(resdict, key_map))
                if re.search(k, dict_value_old):
                    try:
                        dict_value_new = dict_value_old.replace(k, v)
                    except TypeError:
                        dict_value_new = v  # number
                    dicttools.set_from_dict(resdict, key_map, dict_value_new)
        return resdict

    @property
    def result_list(self):
        """
        This function gets the parser result as a list of dictionaries.

        :return: Parser result list of dictionaries
        """
        chunks_accumulated = []
        result_list = []
        search_list = self.search_list()
        intend = LOG_INTEND * ' '
        print('parser: {}'.format(self.__parser_id))
        print('search list: size: {}\n'.format(len(search_list)))
        self.__logger.info('Search for ' + str(len(search_list)) + ' regular expression patterns in the log file.')
        self.__logger.debug(LOG_MAX_TEXT_LEN * '-')
        self.__logger.debug('Search patterns:')
        for s_item in search_list:
            self.__logger.debug(intend + s_item['regex'])
        self.__logger.debug(LOG_MAX_TEXT_LEN * '-')
        self.__logger.debug('Processing chunks of the log file.')
        i = 0
        while True:
            # Get file content chunk wise to save memory
            # A chunk contains a number of lines defined in config file via chunksize.
            chunk = ClsChunk(self.get_chunk())
            if not chunk.list:
                break
            i += 1
            self.__logger.debug('{} {:>2}:'.format('Chunk', i))
            self.__logger.debug('{:>12} {}'.format('original:', chunk.log_info))
            print('chunk start: {}, end: {}, size: {}'.format(chunk.line_start, chunk.line_end, chunk.length))
            # filter date
            if self.__parser_filter_time:
                self.__logger.debug('Filtering dates ..')
                chunk_filtered_date = ClsChunk(self.filter_chunk(chunk.list, 'date'))
                if not chunk_filtered_date.list:
                    self.__logger.debug('{:>12} {}'.format('filtered:', str(None)))
                    continue
                self.__logger.debug('{:>12} {}'.format('filtered:', chunk_filtered_date.log_info))
            else:
                chunk_filtered_date = ClsChunk(chunk.list)
            # filter keys
            self.__logger.debug('Filtering keys ..')
            chunk_filtered_keys = ClsChunk(self.filter_chunk(chunk_filtered_date.list, 'keys'))
            if not chunk_filtered_keys.list:
                self.__logger.debug('{:>12} {}'.format('filtered:', str(None)))
                continue
            print('chunk_filtered: size: {}'.format(chunk_filtered_keys.length))
            self.__logger.debug('{:>12} {}'.format('filtered:', chunk_filtered_keys.log_info))
            # add found lines to the accumulated chunk list
            for item in chunk_filtered_keys.list:
                chunks_accumulated.append(item)

        # log search result
        self.__logger.debug(LOG_MAX_TEXT_LEN * '-')
        self.__logger.info('Found ' + str(len(chunks_accumulated)) + ' lines in the log file.')
        self.__logger.debug(LOG_MAX_TEXT_LEN * '-')
        self.__logger.debug('Found lines:')
        for c_acc in chunks_accumulated:
            self.__logger.debug('{:8}: {}'.format(c_acc['number'], c_acc['text'].rstrip()))

        # combi list - combines search and found items
        self.__logger.debug(LOG_MAX_TEXT_LEN * '-')
        self.__logger.debug('Combining search and found items in combi list.')
        combi_list = self.combi_list(chunks_accumulated)
        print('combi list: size: {}\n'.format(len(combi_list)))
        self.__logger.debug('combi list: size: {}'.format(len(combi_list)))
        for c_item in combi_list:
            self.__logger.debug(c_item)

        # combi list getting normalized
        self.__logger.debug(LOG_MAX_TEXT_LEN * '-')
        self.__logger.debug('Normalizing combi list by consolidating the found items.')
        combi_list_normalized = ClsResList(self.combi_list_normalized(combi_list))
        print('combi list normalized: size: {}\n'.format(len(combi_list_normalized.list)))
        self.__logger.debug('combi list normalized: size: {}'.format(combi_list_normalized.length))
        for c_item in combi_list_normalized.list:
            self.__logger.debug(c_item)

        # combi list normalized is filtered for status
        self.__logger.debug(LOG_MAX_TEXT_LEN * '-')
        self.__logger.debug('Normalized combi list is filtered for status.')
        combi_list_normalized_filtered = ClsResList(combi_list_normalized.filter(
            status_list=self.__parser_filter_status))
        self.__logger.debug('combi list normalized filtered: size: {}'.format(combi_list_normalized_filtered.length))
        for c_item in combi_list_normalized_filtered.list:
            self.__logger.debug(c_item)

        # log the event status
        self.__logger.info(LOG_MAX_TEXT_LEN * '-')
        self.__logger.info('Events:')
        self.__logger.info(intend + '{:12}{}'.format('status:', combi_list_normalized_filtered.status_tuples))
        self.__logger.info(LOG_MAX_TEXT_LEN * '-')
        self.__logger.info('Compose a list of events each in form of a dictionary.')

        self.__logger.debug(LOG_MAX_TEXT_LEN * '-')
        self.__logger.debug('Calculate result tuples (T) and create result dictionaries (D).')
        i = 0
        for combi_item in combi_list_normalized_filtered.list:
            i += 1
            # calculate result tuples for replacing placeholders in the final result dictionary
            result_tuples = self.result_tuples(combi_item)
            self.__logger.debug('{}{}: {}'.format('T', i, result_tuples))
            # replace placeholders in the result dictionary by tuple values
            result_dict = self.fill_placeholders(self.__parser_result_fields, result_tuples)
            self.__logger.debug('{}{}: {}'.format('D', i, result_dict))
            # accumulate list of result dictionaries
            result_list.append(result_dict)

        return result_list

    def http_key_tuples(self, data):
        """
        This function provides a list of unique tuples for the http chunk sending.
        Each tuple represents a key for collecting events to be sent in one chunk.
        :return: List of unique tuples for the http chunk sending

        Example:
        [('customerId','azse_datasynch'), ('customerId','hei_datasynch'), ('customerId','azse_datasynch')]
        """
        t_list = []
        for d in data:
            for (k, v) in d.items():
                if k == self.http_out_chunk_key:
                    t_list.append((k, v))
        # create a set of tuples in order to obtain unique items
        t_set = set(t_list)
        # return the set as a list of tuples
        return list(t_set)

    def curl_token(self, con):
        """
        This function gets an authentication token from the ssd,
        after posting username and password.
        :param con: connection from connections file.
        :return: authentication token
        """
        protocol = con['protocol']
        port = con['port']
        host = con['hostName']
        path = con['tokenPath']
        user = con['userName']
        pw = con['passWord']

        content_type = "content-type: application/x-www-form-urlencoded"
        url = protocol + "://" + host + ":" + port + path
        data = "client_id=pushClient&grant_type=password&scope=sportal&username=" + user + "&password=" + pw

        self.__logger.debug(LOG_MAX_TEXT_LEN * '-')
        self.__logger.debug('Get auth token from url: ' + url)
        result = ''
        with Popen(["curl", "-XPOST", "-H", content_type, url, "-d", data],
                   stdout=PIPE, bufsize=1, universal_newlines=True) as p:
            for line in p.stdout:
                result = result + line
        return result

    def curl_result(self, data, con):
        """
        This functions posts the data into the target url via curl.
        The data is sent in chunks that are built on the basis of the same customerId.
        Because the target url does contain the customerId in it's path.
        Every single json event is sent separately
        :param data: Data to be sent to the target url.
        :param con: connection from connections file.
        :return: True id success, False if failed.
        """
        intend = LOG_INTEND * ' '

        try:
            protocol = con['protocol']
            port = con['port']
            host = con['hostName']
            path = con['eventPath']
        except AttributeError:
            return None

        json_token = json.loads(self.curl_token(con))  # contains multiple token parameters
        access_token = json_token['access_token']  # extract the access token string exclusively
        authorization = "authorization: Bearer " + access_token
        content_type = "content-type: application/json"

        self.__logger.info(LOG_MAX_TEXT_LEN * '-')
        self.__logger.info('Send ' + str(len(data)) + ' events to SSD.')
        result = ''
        for (k, v) in self.http_key_tuples(data):
            # calculate chunk of result list due to chunkKey
            c_list = [d for d in data if d[k] == v]
            url = protocol + "://" + host + ":" + port + path.replace(PH_CUSTOMER_ID, v)
            self.__logger.debug(LOG_MAX_TEXT_LEN * '-')
            self.__logger.debug(intend + 'Send ' + str(len(c_list)) + ' events for ' + v + '.')
            self.__logger.debug(intend + 'URL: ' + url)
            # send every single json event separately
            for c_event in c_list:
                with Popen(["curl", "-XPOST", "-H", authorization, "-H", content_type, url, "-d", json.dumps(c_event)],
                           stdout=PIPE, bufsize=1, universal_newlines=True) as p:
                    for line in p.stdout:
                        result += line
            result += '\n'
        return result

    def log_info(self):
        """
        This function logs basic information about the log parser.
        :return: log entries about log file and parser
        """
        intend = LOG_INTEND * ' '
        self.__logger.info(LOG_MAX_TEXT_LEN * '-')
        self.__logger.info('Log:')
        self.__logger.info(intend + '{:12}{}'.format('id:', self.__log_id))
        self.__logger.info(intend + '{:12}{}'.format('name:', self.__log_name))
        self.__logger.info(intend + '{:12}{}'.format('fileName:', self.__log_filename))
        self.__logger.info('Parser:')
        self.__logger.info(intend + '{:12}{}'.format('id:', self.__parser_id))
        self.__logger.info(intend + '{:12}{}'.format('info:', self.__parser_text))
        if self.__parser_regex_positive:
            status = '"ok"'
        else:
            status = '"error"'
        self.__logger.info(intend + '{:12}{}'.format('search:', 'Found lines are interpreted as ' + status + '.'))
        self.__logger.info(LOG_MAX_TEXT_LEN * '-')
        # debug info
        self.__logger.debug('Log dictionary:')
        for line in pprint.pformat(self.__dict_log).split('\n'):
            self.__logger.debug(intend + '{}'.format(line))
        self.__logger.debug('')
        self.__logger.debug('Parser dictionary:')
        for line in pprint.pformat(self.__dict_parser).split('\n'):
            self.__logger.debug(intend + '{}'.format(line))
        self.__logger.debug(LOG_MAX_TEXT_LEN * '-')
        self.__logger.debug('')

        pass

    def dump(self):
        print('\tlog_name: {}'.format(self.__log_name))
        print('\tlog_type: {}'.format(self.__log_type))
        print('\tlog_pathname: {}'.format(self.__log_pathname))
        print('\tlog_filename: {}'.format(self.__log_filename))
        print('\tlog_date_exists: {}'.format(self.log_date_exists))
        print('\tlog_date_format: {}'.format(self.__log_date_format))
        print('\tlog_date_regex: {}'.format(self.__log_date_regex))
        print('\tparser_id: {}'.format(self.__parser_id))
        print('\tparser_regex: {}'.format(self.__parser_regex))
        print('\tparser_key_level: {}'.format(self.__parser_key_level))
        print('\tparser_search_col: {}'.format(self.__parser_search_col))
        print('\tparser_chunk_size: {}'.format(self.__parser_chunk_size))
        print('\tparser_chunk_offset: {}'.format(self.__parser_chunk_offset))
        print('\tparser_chunk_number: {}'.format(self.__parser_chunk_number))
        print('\tparser_chunk_counter: {}'.format(self.__parser_chunk_index))
        print('\tparser_time_offset: {}'.format(self.__parser_time_offset))
        print('\tparser_time_interval: {}'.format(self.__parser_time_interval))
        print('\tparser_dt_start: {}'.format(self.__parser_dt_start))
        print('\tparser_dt_end: {}'.format(self.__parser_dt_end))
        print('\tparser_group_slice: {}\n'.format(self.__parser_group_slice))
