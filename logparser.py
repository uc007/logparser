import yaml
import logging
import logging.config
import json
import sys
import getopt

# my modules
sys.path.append('./lib')
import lopa

__author__ = 'Ralf'

# !/usr/bin/env python3


def show_usage():
    """
    This function prints how to use the logparser in the command line
    :rtype : str
    :return: shows (prints) the usage and options of the logparser command
    """
    s_usage = \
"""Usage: logparser.py [options ...]
Options:
-c, --config-file FILE  Set up the config file to use, default ./config/logparser.yml
-o, --conn-file FILE  Set up the connection file to use, default ./config/connections.yml
-h, --help      This help text
    --no-send   Don't send data"""
    print('{}'.format(s_usage))


def main():

    # default values
    c_file = lopa.CONFIG_FILE
    o_file = lopa.CONN_FILE
    no_send = False

    # get command line options
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hc:o:", ["config-file=", "conn-file=", "no-send"])
    except getopt.GetoptError:
        show_usage()
        sys.exit(2)
    for opt, arg in opts:
        if opt in ('-h', "--help"):
            show_usage()
            sys.exit()
        elif opt in ("-c", "--config-file"):
            c_file = arg
        elif opt in ("-o", "--conn-file"):
            o_file = arg
        elif opt == "--no-send":
            no_send = True

    # read configuration file
    with open(c_file, 'r') as stream:
        cfg = yaml.load(stream)
        
    # read connection file
    with open(o_file, 'r') as stream:
        conns = yaml.load(stream)

    # print(yaml.dump(cfg))

    # initialize the logging for the log parser
    logging.config.dictConfig(cfg['logging'])
    logger = logging.getLogger('parser')

    logger.info('')
    logger.info('')
    logger.info(lopa.LOG_MAX_TEXT_LEN * '=')
    logger.info('START LOG PARSER')
    logger.info(lopa.LOG_MAX_TEXT_LEN * '=')

    # get the number of log parser runs
    total_runs = 0
    for log in cfg['logs']:
        for par in cfg['parser']:
            if par['active'] == 'yes':
                if log['id'] in par['logId']:
                    total_runs += 1

    run = 0
    l_all = []
    # read configuration file
    with open(cfg['out']['file']['pathName'] + '/' + cfg['out']['file']['fileName'], 'w') as fha:
        # loop through all specified log files
        for log in cfg['logs']:
            # loop through all specified parsers
            for par in cfg['parser']:
                if par['active'] == 'yes':
                    if log['id'] in par['logId']:
                        run += 1
                        logger.info('')
                        logger.info('{} {:>2} {} {:2}'.format('RUN', str(run), '/', str(total_runs)))
                        obj_parser = lopa.ClsParser(log, par, logger)
                        obj_parser.log_info()
                        l_par = obj_parser.result_list
                        # if --no-send is active than don't send data (used for testing purposes)
                        if not no_send:
                            # loop through all connections specified in the connections file
                            for con in conns['connections']:
                                # check which output is configured and provide data accordingly
                                if 'http' in par['out']:
                                    if con['id'] in par['out']['http']['connections']:
                                        obj_parser.curl_result(l_par, con)
                                if 'mail' in par['out']:
                                    if con['id'] in par['out']['mail']['connections']:
                                        obj_parser.mail_result(l_par, con)
                        # check if the output to a file is configured
                        if 'file' in par['out']:
                            # write the parser specific result sets to a file
                            with open(obj_parser.result_file_path, 'w') as fh:
                                logger.info(lopa.LOG_MAX_TEXT_LEN * '-')
                                logger.info('{} {}'.format('Write events to parser file', fh.name))
                                print(json.dumps(l_par, sort_keys=True, indent=4), file=fh)  # file with parser events
                                logger.info(lopa.LOG_MAX_TEXT_LEN * '-')
                        # build a total list of all json result records
                        for res in l_par:
                            l_all.append(res)
        # write the total parser result sets to a summary file
        logger.info('{} {}'.format('Write events to summary file', fha.name))
        print(json.dumps(l_all, sort_keys=True, indent=4), file=fha)  # file containing all events

if __name__ == "__main__":
    main()
