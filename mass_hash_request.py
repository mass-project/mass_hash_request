#! /usr/bin/env python
import argparse
import logging
import sys
import requests
import os
import json
import re
import tarfile

PROGRAM_NAME = "MASS Hash Request"
PROGRAM_VERSION = "0.1"
PROGRAM_DESCRIPTION = "This tool queries a MASS server for multiple hash sums and represents the results as a directory tree."


def _setup_argparser():
    parser = argparse.ArgumentParser(description="{} - {}".format(PROGRAM_NAME, PROGRAM_DESCRIPTION))

    parser.add_argument('hashfile', help='file containing hash sums')
    parser.add_argument('--hash-type')
    parser.add_argument('-V', '--version', action='version', version="{} {}".format(PROGRAM_NAME, PROGRAM_VERSION))
    parser.add_argument("-l", "--log_file",
                        help="path to log file",
                        default="./log/program.log")
    parser.add_argument("-L", "--log_level",
                        help="define the log level [DEBUG,INFO,WARNING,ERROR]",
                        default="WARNING")
    parser.add_argument('-p', '--print-missing', action='store_true', default=False,
                        help='print hash values which were not found on MASS')
    return parser.parse_args()


def _setup_logging(args):
    log_level = getattr(logging, args.log_level.upper(), None)
    log_format = logging.Formatter(fmt="[%(asctime)s][%(module)s][%(levelname)s]: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    logger = logging.getLogger('')
    logger.setLevel(logging.DEBUG)
    file_log = logging.FileHandler(args.log_file)
    file_log.setLevel(log_level)
    file_log.setFormatter(log_format)
    console_log = logging.StreamHandler()
    console_log.setLevel(logging.INFO)
    console_log.setFormatter(log_format)
    logger.addHandler(file_log)
    logger.addHandler(console_log)


def load_configuration(config_path):
    if not os.path.exists(config_path):
        print("configuration file not found.\ncreating config: config.json ")
        config = create_config()
        save_configuration(config, config_path)
    else:
        with open(config_path, "r") as fp:
            config = json.load(fp)
    return config


def create_config():
    config['base_url'] = 'https://tools.net.cs.uni-bonn.de/mass-dev/api/'
    config['hash'] = 'md5'
    config['hashes'] = ['md5', 'sha1', 'sha256', 'sha512']
    config['directory'] = 'mhr_result'
    return config


def save_configuration(config, config_path):
    with open(config_path, "w") as fp:
        json.dump(config, fp, indent=4, sort_keys=True)


def update_config_from_options(config, options):
    if options.hash_type:
        if options.hash_type in config['hashes']:
            config['hash'] = options.hash_type
        else:
            raise ValueError('{} is not a known hash.'.format(options.hash_type))


def read_hash_sums(filename):
    hashes = []
    with open(filename) as hash_file:
        for h in hash_file:
            hashes.append(h.strip())
    return hashes


def query_mass_for_hashes(mass_url, hash_type, hashes):
    request_url = '{}?{}={}'
    results = {}
    for h in hashes:
        url = request_url.format(mass_url, hash_type + 'sum', h)
        query_response = requests.get(url)
        response = json.loads(query_response.text)
        if response['results']:
            results[h] = response['results'][0]
        else:
            results[h] = None
    return results


def touch_path(path):
    if not os.path.exists(path):
        os.mkdir(path)


def generate_no_file_found_file(path):
    open(path + '/SampleNotFound', 'w').close()


def generate_report_dir(path, result):
    reports_path = path + '/Reports'
    result = requests.get(result['url'] + 'reports/')
    reports = result.json()['results']
    if reports:
        touch_path(reports_path)
        for report in reports:
            analysis_system = re.search('/analysis_system/([^/]*)/', report['analysis_system']).group(1)
            report_path = '{}/{}.json'.format(reports_path, analysis_system)
            with open(report_path, 'w') as report_file:
                report_file.write(json.dumps(report, indent=4))


def download_file(url, dest_path):
    response = requests.get(url)
    with open(dest_path, 'wb') as f:
        f.write(response.content)


def generate_sample_dir(path, result):
    sample_path = path + '/Sample'
    touch_path(sample_path)
    file_url = result['file']
    file_path = '{}/{}'.format(sample_path, result['file_names'][0])
    download_file(file_url, file_path)


def generate_file_dirs(path, result):
    generate_report_dir(path, result)
    generate_sample_dir(path, result)


def generate_file_structure(base_dir, query_results, options):
    if not os.path.exists(base_dir):
        os.mkdir(base_dir)
    for h, result in query_results.items():
        path = base_dir + '/' + h
        touch_path(path)
        if result:
            generate_file_dirs(path, result)
        else:
            generate_no_file_found_file(path)
            if options.print_missing:
                print(h)


def make_archive(path):
    with tarfile.open('result_archive.tar.gz', 'w:gz') as tar:
        tar.add(path)


if __name__ == '__main__':
    args = _setup_argparser()
    _setup_logging(args)

    config_path = 'config.json'
    config = load_configuration(config_path)
    update_config_from_options(config, args)
    hashes = read_hash_sums(args.hashfile)
    results = query_mass_for_hashes(config['base_url'], config['hash'], hashes)
    generate_file_structure(config['directory'], results, args)
    make_archive(config['directory'])

    sys.exit()
