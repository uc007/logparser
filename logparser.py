import yaml
import logging
import logging.config
import json
import sys

# my modules
sys.path.append('./lib')
import lopa

__author__ = 'Ralf'

# !/usr/bin/env python3


def main():

    with open(lopa.CONFIG_FILE, 'r') as stream:
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
                        obj_parser.curl_token()
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
