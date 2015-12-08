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
-h, --help      This help text
    --no-send   Don't send data"""
    print('{}'.format(s_usage))

def main():

    # default values
    c_file = lopa.CONFIG_FILE
    no_send = False

    # get command line options
    try:
        opts, args = getopt.getopt(sys.argv[1:],"hc:",["cfile=","no-send"])
    except getopt.GetoptError:
        show_usage()
        sys.exit(2)
    for opt, arg in opts:
        if opt in ('-h', "--help"):
            show_usage()
            sys.exit()
        elif opt in ("-c", "--config-file"):
            c_file = arg
        elif opt == "--no-send":
            no_send = True

    # read configuration file
    with open(c_file, 'r') as stream:
        cfg = yaml.load(stream)

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
    with open(cfg['out']['file']['pathName'] + '/' + cfg['out']['file']['fileName'], 'w') as fha:
        for log in cfg['logs']:
            for par in cfg['parser']:
                if par['active'] == 'yes':
                    if log['id'] in par['logId']:
                        run += 1
                        logger.info('')
                        logger.info('{} {:>2} {} {:2}'.format('RUN', str(run), '/', str(total_runs)))
                        obj_parser = lopa.ClsParser(log, par, logger)
                        obj_parser.log_info()
                        l_par = obj_parser.result_list
                        if not no_send:
                            obj_parser.curl_result(l_par)
                            # print('token: {}'.format(obj_parser.curl_result(l_par)))
                        for res in l_par:
                            l_all.append(res)
                        with open(obj_parser.result_file_path, 'w') as fh:
                            logger.info(lopa.LOG_MAX_TEXT_LEN * '-')
                            logger.info('{} {}'.format('Write events to parser file', fh.name))
                            print(json.dumps(l_par, sort_keys=True, indent=4), file=fh)  # file containing parser events
                            logger.info(lopa.LOG_MAX_TEXT_LEN * '-')
        logger.info('{} {}'.format('Write events to summary file', fha.name))
        print(json.dumps(l_all, sort_keys=True, indent=4), file=fha)  # file containing all events

if __name__ == "__main__":
    main()
