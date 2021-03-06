#! /usr/bin/env python
import argparse
import logging
import sys
import os
import json
import re
import tarfile

from datetime import datetime

from mass_api_client import ConnectionManager
from mass_api_client.resources import Sample, FileSample, IPSample, URISample, DomainSample

PROGRAM_NAME = "MASS Hash Request"
PROGRAM_VERSION = "0.1"
PROGRAM_DESCRIPTION = "This tool queries a MASS server for multiple hash sums and represents the results as a directory tree."


def _setup_argparser():
    parser = argparse.ArgumentParser(description="{} - {}".format(PROGRAM_NAME, PROGRAM_DESCRIPTION))

    parser.add_argument('--delivered-after', type=_valid_date)
    parser.add_argument('--delivered-before', type=_valid_date)
    parser.add_argument('--first-seen-after', type=_valid_date)
    parser.add_argument('--first-seen-before', type=_valid_date)
    parser.add_argument('--tags', help='A list of comma-separated tags')
    parser.add_argument('--entropy-below', type=float)
    parser.add_argument('--entropy-above', type=float)
    parser.add_argument('--filesize-below', type=int)
    parser.add_argument('--filesize-above', type=int)
    parser.add_argument('--hashfile', help='file containing hash sums')
    parser.add_argument('--mime-type')
    parser.add_argument('--file-name')
    parser.add_argument('--domain')
    parser.add_argument('--domain-contains')
    parser.add_argument('--domain-startswith')
    parser.add_argument('--domain-endswith')
    parser.add_argument('--uri')
    parser.add_argument('--uri-contains')
    parser.add_argument('--uri-startswith')
    parser.add_argument('--uri-endswith')
    parser.add_argument('--ip')
    parser.add_argument('--ip-startswith')

    parser.add_argument('-A', '--api_key', help='API Key for MASS')
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


def _valid_date(string):
    try:
        return datetime.strptime(string, "%Y-%m-%d")
    except ValueError:
        message = "Invalid date: {}".format(string)
        raise argparse.ArgumentTypeError(message)


def _setup_logging(args):
    log_level = getattr(logging, args.log_level.upper(), None)
    log_format = logging.Formatter(fmt="[%(asctime)s][%(module)s][%(levelname)s]: %(message)s",
                                   datefmt="%Y-%m-%d %H:%M:%S")
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


def get_query_parameters(args):
    query_parameters = {
        'delivery_date__lte': args.delivered_before,
        'delivery_date__gte': args.delivered_after,
        'first_seen__lte': args.first_seen_before,
        'first_seen__gte': args.first_seen_after,
        'tags__all': args.tags,
        'mime_type': args.mime_type,
        'file_names': args.file_name,
        'file_size__lte': args.filesize_below,
        'file_size__gte': args.filesize_above,
        'shannon_entropy__lte': args.entropy_below,
        'shannon_entropy__gte': args.entropy_above,
        'domain': args.domain,
        'domain__startswith': args.domain_startswith,
        'domain__endswith': args.domain_endswith,
        'uri': args.uri,
        'uri__contains': args.uri_contains,
        'uri__startswith': args.uri_startswith,
        'uri__endswith': args.uri_endswith,
        'ip_address': args.ip,
        'ip_address__startswith': args.ip_startswith
    }

    return {k: v for k, v in query_parameters.items() if v}


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
    config = dict()
    config['base_url'] = 'http://localhost:5000/api/'
    config['api_key'] = ''
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
    if options.api_key:
        config['api_key'] = options.api_key


def read_hash_sums(filename):
    hashes = []
    with open(filename) as hash_file:
        for h in hash_file:
            hashes.append(h.strip())
    return hashes


def query_mass_for_hashes(hash_type, hashes, query_parameters=None):
    if query_parameters is None:
        query_parameters = {}

    results = {}

    for h in hashes:
        query_parameters[hash_type + 'sum'] = h
        returned_samples = list(FileSample.query(**query_parameters))

        if len(returned_samples) == 1:
            s = returned_samples[0]
            results[s.id] = s
        else:
            results[h] = None

    return results


def query_mass_for_samples(query_parameters):
    for sample_class in [Sample, DomainSample, FileSample, IPSample, URISample]:
        try:
            returned_samples = sample_class.query(**query_parameters)
            return {s.id: s for s in returned_samples}
        except ValueError:
            continue

    print('Incompatible choice of parameters')
    sys.exit(1)


def touch_path(path):
    if not os.path.exists(path):
        os.makedirs(path)


def generate_no_file_found_file(path):
    open(path + '/SampleNotFound', 'w').close()


def generate_report_dir(path, result):
    reports_path = path + '/Reports'
    reports = result.get_reports()
    for report in reports:
        analysis_system = re.search('/analysis_system/([^/]*)/', report.analysis_system).group(1)
        analysis_system_path = '{}/{}'.format(reports_path, analysis_system)
        touch_path(analysis_system_path)

        for key in report.json_report_objects:
            report_object_path = '{}/{}.json'.format(analysis_system_path, key)
            with open(report_object_path, 'w') as report_file:
                report_file.write(json.dumps(report.get_json_report_object(key), indent=4))

        for key in report.raw_report_objects:
            report_object_path = '{}/{}'.format(analysis_system_path, key)
            with open(report_object_path, 'wb') as report_file:
                report.download_raw_report_object_to_file(key, report_file)


def generate_sample_dir(path, result):
    sample_path = path + '/Sample'
    touch_path(sample_path)
    file_path = '{}/{}'.format(sample_path, result.file_names[0])
    with open(file_path, 'wb') as f:
        result.download_to_file(f)


def generate_sample_file(path, result):
    sample_path = path + '/Sample.txt'
    content = ''

    if isinstance(result, DomainSample):
        sample_path = path + '/Domain.txt'
        content = result.domain
    if isinstance(result, IPSample):
        sample_path = path + '/IPAddress.txt'
        content = result.ip_address
    if isinstance(result, URISample):
        sample_path = path + '/URI.txt'
        content = result.uri

    with open(sample_path, 'w') as f:
        f.write(content)


def generate_file_dirs(path, result):
    generate_report_dir(path, result)

    if isinstance(result, FileSample):
        generate_sample_dir(path, result)
    else:
        generate_sample_file(path, result)


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
    query_parameters = get_query_parameters(args)

    ConnectionManager().register_connection('default', config['api_key'], config['base_url'])
    if args.hashfile:
        hashes = read_hash_sums(args.hashfile)
        results = query_mass_for_hashes(config['hash'], hashes)
    elif query_parameters:
        results = query_mass_for_samples(query_parameters)
    else:
        print('No query parameters given')
        sys.exit()

    generate_file_structure(config['directory'], results, args)
    make_archive(config['directory'])

    sys.exit()
